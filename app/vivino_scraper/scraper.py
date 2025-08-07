import asyncio
import httpx
from selectolax.parser import HTMLParser

BASE_URL = "https://www.vivino.com/SE/en"
API_URL = "https://www.vivino.com/api/vintages/{}?language=en"


async def fetch_html(url, client):
    """Fetch HTML content of a given URL asynchronously."""
    response = await client.get(url)
    response.raise_for_status()
    return response.text


async def fetch_json(url, client):
    """Fetch JSON content from a given API URL asynchronously."""
    try:
        response = await client.get(url)
        response.raise_for_status()
        json_data = response.json()
        
        # Debug: Check if the response is empty or malformed
        if json_data is None:
            print(f"Warning: Got None JSON response from {url}")
            return None
        
        return json_data
    except Exception as e:
        print(f"Error fetching JSON from {url}: {e}")
        return None


def extract_wine_links(html):
    """Extract all wine links from the Vivino top list page."""
    tree = HTMLParser(html)
    return [BASE_URL + node.attrs["href"] for node in tree.css("a[data-testid='vintagePageLink']")]  # Updated selector


def extract_vintage_id(html):
    """Extract vintage ID from the wine page HTML."""
    tree = HTMLParser(html)
    meta_tag = tree.css_first("meta[name='twitter:app:url:iphone']")
    if meta_tag:
        content = meta_tag.attrs.get("content", "")
        if "vintage_id=" in content:
            return content.split("vintage_id=")[-1]
    return None


def extract_wine_image_from_api(data):
    """Extract wine image URL from Vivino API response."""
    image_url = None
    
    # Safety check for None data
    if data is None:
        return None
    
    # Get vintage data
    vintage = data.get("vintage", {})
    
    # Try to get bottle image from vintage.image.variations (preferred for wine cards)
    if "image" in vintage and isinstance(vintage["image"], dict):
        variations = vintage["image"].get("variations", {})
        
        # Prefer bottle images over label images for wine display
        # Try different bottle sizes in order of preference
        bottle_preferences = ["bottle_medium", "bottle_large", "bottle_small"]
        for bottle_size in bottle_preferences:
            if bottle_size in variations and variations[bottle_size]:
                image_url = variations[bottle_size]
                break
        
        # If no bottle image, try label images
        if not image_url:
            label_preferences = ["large", "label_large", "medium", "label_medium"]
            for label_size in label_preferences:
                if label_size in variations and variations[label_size]:
                    image_url = variations[label_size]
                    break
        
        # Fallback to the main location
        if not image_url and "location" in vintage["image"]:
            image_url = vintage["image"]["location"]
    
    # Convert relative URLs to absolute
    if image_url:
        if image_url.startswith("//"):
            image_url = "https:" + image_url
        elif image_url.startswith("/"):
            image_url = "https://www.vivino.com" + image_url
    
    return image_url


def extract_enhanced_wine_data(data):
    """Extract comprehensive wine data from Vivino API response."""
    import json
    
    # Safety check for None data
    if data is None:
        return None
    
    vintage = data.get("vintage", {})
    wine = vintage.get("wine", {})
    region = wine.get("region", {})
    country = region.get("country", {})
    winery = wine.get("winery", {})
    style = wine.get("style", {})
    wine_facts = vintage.get("wine_facts", {})
    
    # Extract grape varieties
    grapes = wine.get("grapes", [])
    grape_varieties = [grape.get("name") for grape in grapes if grape.get("name")]
    
    # Extract food pairings
    foods = wine.get("foods", [])
    food_pairings = [food.get("name") for food in foods if food.get("name")]
    
    # Get alcohol content from multiple possible sources
    alcohol_content = (
        wine_facts.get("alcohol") or
        vintage.get("alcohol_content") or 
        wine.get("alcohol")
    )
    
    # Handle year - convert to integer or None
    year = vintage.get("year")
    if year and str(year).strip() and str(year).strip().upper() not in ['N.V.', 'NV', '']:
        try:
            year = int(year)
        except (ValueError, TypeError):
            year = None
    else:
        year = None
    
    return {
        # Basic info
        "image_url": extract_wine_image_from_api(data),
        "name": vintage.get("name"),
        "ratings_average": vintage.get("statistics", {}).get("ratings_average"),
        "year": year,
        "description": wine.get("description", "").strip(),
        
        # Location data
        "country": country.get("name"),
        "country_code": country.get("code"),
        "region": region.get("name"),
        "winery": winery.get("name"),
        
        # Wine characteristics
        "wine_style": style.get("name"),
        "wine_type_id": wine.get("type_id"),
        "alcohol_content": float(alcohol_content) if alcohol_content else None,
        "body": style.get("body"),
        "acidity": style.get("acidity"),
        "sweetness": style.get("baseline_structure", {}).get("sweetness"),
        "closure_type": wine.get("closure"),
        "is_organic": vintage.get("organic_certification_id") is not None,
        "is_natural": wine.get("is_natural", False),
        
        # Complex data as JSON strings
        "grape_varieties": json.dumps(grape_varieties, ensure_ascii=False) if grape_varieties else None,
        "food_pairings": json.dumps(food_pairings, ensure_ascii=False) if food_pairings else None,
    }

async def fetch_vintage_details(vintage_id, client):
    """Fetch comprehensive vintage details from the Vivino API asynchronously."""
    try:
        api_url = API_URL.format(vintage_id)
        data = await fetch_json(api_url, client)
        
        # Check if data is valid
        if data is None:
            return None
        
        # Extract all enhanced wine data
        wine_data = extract_enhanced_wine_data(data)
        
        return wine_data
    except Exception as e:
        print(f"Error fetching vintage details for ID {vintage_id}: {e}")
        return None


async def fetch_wine_details(wine_url, client):
    """Fetch comprehensive wine details including vintage information, image, and enhanced data."""
    wine_html = await fetch_html(wine_url, client)
    vintage_id = extract_vintage_id(wine_html)
    
    if vintage_id:
        details = await fetch_vintage_details(vintage_id, client)
        if details is None:
            print(f"Warning: Got None details for vintage_id {vintage_id} from {wine_url}")
            return None
        
        # Add URL and vintage ID to the enhanced data
        try:
            details["wine_url"] = wine_url
            details["vintage_id"] = vintage_id
            return details
        except TypeError as e:
            print(f"Error adding wine_url/vintage_id to details: {e}, details type: {type(details)}")
            return None
    return None


async def get_toplist_items(toplist_url):
    """Main function to fetch wine links, extract vintage IDs, and get vintage details asynchronously."""
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
        toplist_html = await fetch_html(toplist_url, client)
        wine_links = extract_wine_links(toplist_html)
        
        # Start fetching wine details concurrently
        tasks = []
        for wine_url in wine_links:
            tasks.append(fetch_wine_details(wine_url, client))
        
        results = await asyncio.gather(*tasks)
        return [result for result in results if result]  # Filter out None results
