import asyncio
import httpx
import random
import logging
from selectolax.parser import HTMLParser
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

BASE_URL = "https://www.vivino.com/SE/en"
API_URL = "https://www.vivino.com/api/vintages/{}?language=en"

# Rate limiting configuration
MIN_REQUEST_DELAY = 0.5  # Minimum seconds between requests
MAX_REQUEST_DELAY = 1.5  # Maximum seconds between requests
MAX_RETRIES = 3  # Maximum retry attempts for failed requests
RETRY_BACKOFF_BASE = 2  # Exponential backoff base


async def rate_limit_delay():
    """Add a random delay between requests to avoid rate limiting."""
    delay = random.uniform(MIN_REQUEST_DELAY, MAX_REQUEST_DELAY)
    await asyncio.sleep(delay)


async def fetch_with_retry(fetch_func, url: str, client, max_retries: int = MAX_RETRIES) -> Optional[Any]:
    """
    Fetch with exponential backoff retry logic.
    
    Args:
        fetch_func: Async function to call (fetch_html or fetch_json_raw)
        url: URL to fetch
        client: httpx AsyncClient
        max_retries: Maximum number of retry attempts
    
    Returns:
        Response data or None if all retries failed
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            await rate_limit_delay()
            return await fetch_func(url, client)
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 429:  # Rate limited
                wait_time = RETRY_BACKOFF_BASE ** (attempt + 2)  # Longer wait for rate limits
                logger.warning(f"Rate limited on {url}, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                await asyncio.sleep(wait_time)
            elif e.response.status_code >= 500:  # Server error
                wait_time = RETRY_BACKOFF_BASE ** attempt
                logger.warning(f"Server error {e.response.status_code} on {url}, retry {attempt + 1}/{max_retries}")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"HTTP error {e.response.status_code} on {url}: {e}")
                break  # Don't retry client errors (4xx except 429)
        except httpx.RequestError as e:
            last_error = e
            wait_time = RETRY_BACKOFF_BASE ** attempt
            logger.warning(f"Request error on {url}, retry {attempt + 1}/{max_retries}: {e}")
            await asyncio.sleep(wait_time)
        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error on {url}: {e}")
            break
    
    if last_error:
        logger.error(f"All retries failed for {url}: {last_error}")
    return None


async def fetch_html_raw(url: str, client) -> str:
    """Raw HTML fetch without retry logic."""
    response = await client.get(url)
    response.raise_for_status()
    return response.text


async def fetch_json_raw(url: str, client) -> Optional[Dict]:
    """Raw JSON fetch without retry logic."""
    response = await client.get(url)
    response.raise_for_status()
    json_data = response.json()
    if json_data is None:
        logger.warning(f"Got None JSON response from {url}")
    return json_data


async def fetch_html(url: str, client) -> Optional[str]:
    """Fetch HTML content with retry logic."""
    return await fetch_with_retry(fetch_html_raw, url, client)


async def fetch_json(url: str, client) -> Optional[Dict]:
    """Fetch JSON content with retry logic."""
    return await fetch_with_retry(fetch_json_raw, url, client)


def extract_wine_links(html):
    """Extract all wine links from the Vivino top list page."""
    tree = HTMLParser(html)
    links = []
    for node in tree.css("a[data-testid='vintagePageLink']"):
        href = node.attrs.get("href", "")
        if href:
            # Handle both absolute and relative URLs
            if href.startswith("http"):
                links.append(href)
            elif href.startswith("/"):
                links.append("https://www.vivino.com" + href)
            else:
                links.append("https://www.vivino.com/" + href)
    return links


def extract_vintage_id(html):
    """Extract vintage ID from the wine page HTML."""
    tree = HTMLParser(html)
    meta_tag = tree.css_first("meta[name='twitter:app:url:iphone']")
    if meta_tag:
        content = meta_tag.attrs.get("content", "")
        if "vintage_id=" in content:
            return content.split("vintage_id=")[-1]
    return None


def extract_wine_image_from_api(data: Optional[Dict]) -> Optional[str]:
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


def validate_rating(rating: Any) -> Optional[float]:
    """Validate that rating is within expected range (1-5)."""
    if rating is None:
        return None
    try:
        rating_float = float(rating)
        if 1.0 <= rating_float <= 5.0:
            return round(rating_float, 2)
        logger.warning(f"Rating {rating} out of valid range (1-5)")
        return None
    except (ValueError, TypeError):
        return None


def calculate_data_quality_score(wine_data: Dict[str, Any]) -> float:
    """
    Calculate a data quality/completeness score for a wine record.
    
    Returns a score from 0-100 indicating how complete the data is.
    """
    weights = {
        'name': 10,
        'image_url': 15,
        'ratings_average': 15,
        'ratings_count': 10,
        'country': 8,
        'region': 5,
        'winery': 8,
        'wine_style': 10,
        'alcohol_content': 5,
        'food_pairings': 7,
        'grape_varieties': 7,
    }
    
    score = 0
    for field, weight in weights.items():
        value = wine_data.get(field)
        if value is not None and value != '' and value != [] and value != '[]':
            score += weight
    
    return score


def extract_enhanced_wine_data(data: Optional[Dict]) -> Optional[Dict[str, Any]]:
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
    statistics = vintage.get("statistics", {})
    
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
    
    # Extract and validate rating
    raw_rating = statistics.get("ratings_average")
    validated_rating = validate_rating(raw_rating)
    
    # Extract ratings count for credibility
    ratings_count = statistics.get("ratings_count")
    if ratings_count:
        try:
            ratings_count = int(ratings_count)
        except (ValueError, TypeError):
            ratings_count = None
    
    # Extract tannin (often in baseline_structure)
    baseline_structure = style.get("baseline_structure", {})
    tannin = baseline_structure.get("tannin")
    
    # Build the wine data dict
    wine_data = {
        # Basic info
        "image_url": extract_wine_image_from_api(data),
        "name": vintage.get("name"),
        "ratings_average": validated_rating,
        "ratings_count": ratings_count,
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
        "sweetness": baseline_structure.get("sweetness"),
        "tannin": tannin,
        "closure_type": wine.get("closure"),
        "is_organic": vintage.get("organic_certification_id") is not None,
        "is_natural": wine.get("is_natural", False),
        
        # Complex data as JSON strings
        "grape_varieties": json.dumps(grape_varieties, ensure_ascii=False) if grape_varieties else None,
        "food_pairings": json.dumps(food_pairings, ensure_ascii=False) if food_pairings else None,
    }
    
    # Calculate and add data quality score
    wine_data["data_quality_score"] = calculate_data_quality_score(wine_data)
    
    return wine_data

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


async def get_toplist_items(toplist_url: str, max_concurrent: int = 5) -> List[Dict[str, Any]]:
    """
    Main function to fetch wine links, extract vintage IDs, and get vintage details asynchronously.
    
    Args:
        toplist_url: URL of the Vivino toplist to scrape
        max_concurrent: Maximum number of concurrent requests (to avoid rate limiting)
    
    Returns:
        List of wine data dictionaries
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    
    async with httpx.AsyncClient(
        headers=headers,
        timeout=httpx.Timeout(30.0),
        follow_redirects=True
    ) as client:
        logger.info(f"Fetching toplist: {toplist_url}")
        toplist_html = await fetch_html(toplist_url, client)
        
        if not toplist_html:
            logger.error(f"Failed to fetch toplist HTML from {toplist_url}")
            return []
        
        wine_links = extract_wine_links(toplist_html)
        logger.info(f"Found {len(wine_links)} wine links")
        
        if not wine_links:
            logger.warning("No wine links found in toplist")
            return []
        
        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_semaphore(wine_url: str) -> Optional[Dict]:
            async with semaphore:
                return await fetch_wine_details(wine_url, client)
        
        # Fetch wine details with controlled concurrency
        tasks = [fetch_with_semaphore(wine_url) for wine_url in wine_links]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None results and exceptions
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception fetching wine {i}: {result}")
            elif result is not None:
                valid_results.append(result)
        
        logger.info(f"Successfully fetched {len(valid_results)}/{len(wine_links)} wines")
        return valid_results


def deduplicate_wines(wines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate wines based on vintage_id.
    Keeps the version with highest data quality score.
    """
    seen = {}
    for wine in wines:
        vintage_id = wine.get('vintage_id')
        if not vintage_id:
            continue
        
        if vintage_id not in seen:
            seen[vintage_id] = wine
        else:
            # Keep the one with higher data quality score
            existing_score = seen[vintage_id].get('data_quality_score', 0)
            new_score = wine.get('data_quality_score', 0)
            if new_score > existing_score:
                seen[vintage_id] = wine
    
    return list(seen.values())
