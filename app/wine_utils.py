"""
Wine utility functions for Best Wines Sweden
Extracted from api.py to avoid Telegraph dependencies
"""

import asyncio
import httpx
import re
import logging
import os
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from retrying import retry
from vivino_scraper import get_toplist_items

SUBSCRIPTION_KEY = os.getenv("SUBSCRIPTION_KEY", "8d39a7340ee7439f8b4c1e995c8f3e4a")
WINE_STYLES = {
    "Rött vin": [
        "Tinto", "Red", "Malbec", "Rosso", "Chianti", "Syrah", "Shiraz", "Merlot",
        "Cabernet", "Pinot", "Noir", "Grenache", "Tempranillo", "Zinfandel", "Sangiovese"
    ],
    "Vitt vin": ["Blanco", "White", "Riesling", "Chardonnay", "Sauvignon", "Blanc"],
    "Mousserande vin": ["Cava", "Champagne", "Sparkling", "Bubbel", "Brut", "Prosecco"],
    "Rosévin": ["Rosé", "Rose"],
}

@dataclass
class VivinoItem:
    name: str
    rating: float
    image_url: str = None
    vintage_id: str = None
    wine_url: str = None
    
    # Enhanced wine data
    country: str = None
    country_code: str = None
    region: str = None
    winery: str = None
    wine_style: str = None
    wine_type_id: int = None
    year: int = None
    alcohol_content: float = None
    body: int = None
    acidity: int = None
    sweetness: float = None
    grape_varieties: str = None  # JSON string
    food_pairings: str = None  # JSON string
    description: str = None
    closure_type: str = None
    is_organic: bool = False
    is_natural: bool = False

@dataclass
class SbSearchResult:
    name: str
    original_name: str
    href: str
    price: str
    rating: float
    style: str
    country: str

logger = logging.getLogger(__name__)

def wine_style_to_emoji(wine_style):
    if "Rött" in wine_style: return "🍇"
    if "Vitt" in wine_style: return "🥂"
    if "Mousserande" in wine_style: return "🍾"
    return wine_style

def country_name_to_emoji(country_name):
    country_emojis = {
        "Frankrike": "🇫🇷", "Italien": "🇮🇹", "Spanien": "🇪🇸", "Tyskland": "🇩🇪",
        "Argentina": "🇦🇷", "Chile": "🇨🇱", "Australien": "🇦🇺", "USA": "🇺🇸",
        "Sydafrika": "🇿🇦", "Nya Zeeland": "🇳🇿", "Portugal": "🇵🇹", "Grekland": "🇬🇷"
    }
    return country_emojis.get(country_name, country_name)

def how_similar(string_a, string_b):
    return SequenceMatcher(None, string_a, string_b).ratio()

def normalize_to_ascii(text):
    return "".join(char for char in unicodedata.normalize("NFD", text) if unicodedata.category(char) != "Mn")

def calculate_string_similarity(string_a, string_b):
    """
    Calculate string similarity using multiple algorithms as fallback when AI is not available.
    Returns a score between 0-100.
    """
    from unidecode import unidecode
    import re
    
    if not string_a or not string_b:
        return 0.0
    
    # Normalize strings
    def normalize(s):
        s = unidecode(str(s).lower())
        # Remove common wine words that add noise
        noise_words = ['wine', 'red', 'white', 'rosé', 'rose', 'dry', 'sweet', 'reserve', 'reserva', 'gran', 'none']
        for word in noise_words:
            s = re.sub(r'\b' + word + r'\b', '', s)
        # Clean up extra spaces and punctuation
        s = re.sub(r'[^\w\s]', ' ', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s
    
    norm_a = normalize(string_a)
    norm_b = normalize(string_b)
    
    # If one is empty after normalization, return low score
    if not norm_a or not norm_b:
        return 10.0
    
    # Exact match after normalization
    if norm_a == norm_b:
        return 100.0
    
    # Word-based matching
    words_a = set(norm_a.split())
    words_b = set(norm_b.split())
    
    if not words_a or not words_b:
        return 10.0
    
    # Calculate Jaccard similarity (intersection over union)
    intersection = len(words_a.intersection(words_b))
    union = len(words_a.union(words_b))
    jaccard_score = (intersection / union) * 100 if union > 0 else 0.0
    
    # Calculate word order similarity bonus
    common_words = words_a.intersection(words_b)
    order_bonus = 0.0
    if len(common_words) > 1:
        # Check if common words appear in similar order
        a_positions = {word: i for i, word in enumerate(norm_a.split()) if word in common_words}
        b_positions = {word: i for i, word in enumerate(norm_b.split()) if word in common_words}
        
        order_matches = 0
        for word in common_words:
            for other_word in common_words:
                if word != other_word:
                    a_before = a_positions[word] < a_positions[other_word]
                    b_before = b_positions[word] < b_positions[other_word]
                    if a_before == b_before:
                        order_matches += 1
        
        max_order_pairs = len(common_words) * (len(common_words) - 1)
        if max_order_pairs > 0:
            order_bonus = (order_matches / max_order_pairs) * 10  # Up to 10% bonus
    
    # Character-level similarity for partial matches
    def char_similarity(s1, s2):
        from difflib import SequenceMatcher
        return SequenceMatcher(None, s1, s2).ratio() * 100
    
    char_score = char_similarity(norm_a, norm_b)
    
    # Combine scores with weights
    final_score = max(
        jaccard_score + order_bonus,  # Word-based score with order bonus
        char_score * 0.7,  # Character-level score (weighted down)
        intersection / max(len(words_a), len(words_b)) * 85 if max(len(words_a), len(words_b)) > 0 else 0  # Coverage score
    )
    
    return min(final_score, 100.0)

def calculate_match_rating(string_a, string_b):
    """Legacy function for backward compatibility - now uses AI matching with fallback"""
    from ai_matcher import ai_calculate_match_rating
    import asyncio
    
    if not string_a or not string_b: 
        return 0.0
    
    try:
        # Use AI matching
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a new task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, ai_calculate_match_rating(string_a, string_b))
                confidence, match_type, reasoning = future.result()
        else:
            confidence, match_type, reasoning = asyncio.run(ai_calculate_match_rating(string_a, string_b))
        
        # Check if AI returned a valid score
        if confidence is not None and isinstance(confidence, (int, float)) and 0 <= confidence <= 100:
            logger.info(f"AI match: {string_a} <-> {string_b} = {confidence}% ({match_type})")
            logger.info(f"AI reasoning: {reasoning[:100]}...")
            return confidence
        else:
            logger.warning(f"AI returned invalid score ({confidence}), using string similarity fallback")
            fallback_score = calculate_string_similarity(string_a, string_b)
            logger.info(f"String similarity fallback: {string_a} <-> {string_b} = {fallback_score}%")
            return fallback_score
        
    except Exception as e:
        logger.error(f"AI matching failed, using string similarity fallback: {e}")
        fallback_score = calculate_string_similarity(string_a, string_b)
        logger.info(f"String similarity fallback: {string_a} <-> {string_b} = {fallback_score}%")
        return fallback_score

def determine_wine_style(wine_name):
    for style, keywords in WINE_STYLES.items():
        if any(keyword in wine_name for keyword in keywords):
            return style
    return None

def clean_and_normalize(text):
    text = re.sub(r"\b(N\.V\.|U\.V\.|A\.V\.|O\.V\.)\b", "", text).strip()
    return normalize_to_ascii(re.sub(r"\b20\d{2}\b", "", text.lower().strip()))

async def validate_subscription_key(key):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api-extern.systembolaget.se/sb-api-ecommerce/v1/productsearch/search",
            headers={"ocp-apim-subscription-key": key}
        )
        return response.status_code == 200

@retry(stop_max_attempt_number=3, wait_fixed=2000)
async def iteratively_search_sb(vivino_wine):
    async with httpx.AsyncClient() as client:
        search_results = []
        wine_style = determine_wine_style(vivino_wine.name)
        cleaned_name = clean_and_normalize(vivino_wine.name)
        split_name = cleaned_name.split(" ")
        while split_name:
            joined_name = " ".join(split_name)
            logger.info(f"Looking for {joined_name}")
            try:
                response = await client.get(
                    "https://api-extern.systembolaget.se/sb-api-ecommerce/v1/productsearch/search",
                    headers={"ocp-apim-subscription-key": SUBSCRIPTION_KEY},
                    params={
                        "page": 1, "size": 30, "sortBy": "Score", "sortDirection": "Ascending",
                        "textQuery": joined_name, "volume.min": 750, "volume.max": 750, "categoryLevel1": "Vin"
                    }
                )
                response.raise_for_status()
                products = response.json().get("products", [])
                best_product = max(
                    (product for product in products if not wine_style or wine_style in product.get("categoryLevel2", "")),
                    key=lambda p: calculate_match_rating(cleaned_name, f"{p.get('productNameBold', '')} {p.get('productNameThin', '')}".strip()),
                    default=None
                )
                if best_product:
                    search_results.append(SbSearchResult(
                        name=f"{best_product.get('productNameBold', '')} {best_product.get('productNameThin', '')}".strip(),
                        original_name=vivino_wine.name,
                        href=f"/sortiment/vin/?q={best_product.get('productNumber')}",
                        price=f"{best_product.get('price', '')} SEK",
                        style=wine_style_to_emoji(best_product.get("categoryLevel2", "")),
                        rating=vivino_wine.rating,
                        country=country_name_to_emoji(best_product.get("country", ""))
                    ))
                    return search_results
                split_name.pop()
            except Exception as e:
                logger.error(f"Error during search: {e}")
                return None
        return search_results

async def parse_vivino_toplist(toplist_url):
    toplist_items = await get_toplist_items(toplist_url)
    
    # Filter out None items and create VivinoItem objects
    valid_items = []
    for item in toplist_items:
        if item is None:
            print("Warning: Skipping None item from toplist")
            continue
        
        # Check if item has required fields
        if not item.get("name") or not item.get("ratings_average"):
            print(f"Warning: Skipping item with missing required fields: {item}")
            continue
            
        try:
            valid_items.append(VivinoItem(
                name=item["name"], 
                rating=item["ratings_average"],
                image_url=item.get("image_url"),
                vintage_id=item.get("vintage_id"),
                wine_url=item.get("wine_url"),
                
                # Enhanced wine data
                country=item.get("country"),
                country_code=item.get("country_code"),
                region=item.get("region"),
                winery=item.get("winery"),
                wine_style=item.get("wine_style"),
                wine_type_id=item.get("wine_type_id"),
                year=item.get("year"),
                alcohol_content=item.get("alcohol_content"),
                body=item.get("body"),
                acidity=item.get("acidity"),
                sweetness=item.get("sweetness"),
                grape_varieties=item.get("grape_varieties"),
                food_pairings=item.get("food_pairings"),
                description=item.get("description"),
                closure_type=item.get("closure_type"),
                is_organic=item.get("is_organic", False),
                is_natural=item.get("is_natural", False)
            ))
        except Exception as e:
            print(f"Warning: Error creating VivinoItem from {item}: {e}")
            continue
    
    return valid_items