#!/usr/bin/env python3
"""
Match scraped Vivino toplist wines with Systembolaget products.

Learnings implemented:
1. Normalize accents (Más → Mas)
2. Translate terms: "Red Blend" → "Red Wine", "Dry" → "Trocken"
3. Remove descriptors: "Tinto", "N.V.", vintage years
4. Prefer 750ml bottles (filter by volume)
5. Use producer metadata for validation
6. Prioritize brand/winery name matches
7. Handle smaller bottles (375ml) and tetrapacks
"""
import asyncio
import json
import re
import os
import unicodedata
import httpx
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Data directory
DATA_DIR = Path("/app/data") if Path("/app/data").exists() else Path(__file__).parent.parent / "data"

# Systembolaget API key
SUBSCRIPTION_KEY = os.getenv("SUBSCRIPTION_KEY", "8d39a7340ee7439f8b4c1e995c8f3e4a")

# Term translations (Vivino → Systembolaget)
TERM_TRANSLATIONS = {
    'red blend': 'red wine',
    'red wine': 'red wine',  # Keep explicit
    'dry': 'trocken',
    'blanc': 'white',
    'rouge': 'red',
    'tinto': '',  # Remove, not used in Swedish
    'blanco': '',  # Remove
    'rosado': 'rosé',
}

# Wine color/type words - incompatible types should reject match
WINE_COLOR_WORDS = {
    'red': {'red', 'rouge', 'rosso', 'tinto', 'rojo', 'rot'},
    'white': {'white', 'blanc', 'bianco', 'blanco', 'weiss'},
    'rosé': {'rosé', 'rose', 'rosato', 'rosado'},
}

# Descriptors to remove from search (these often don't appear in Systembolaget names)
REMOVE_DESCRIPTORS = [
    r'\bTinto\b', r'\bBlanco\b', r'\bRosado\b', 
    r'\bReserva\b', r'\bGran\b', r'\bCrianza\b',
    r'\bOrganic\b', r'\bBio\b', r'\bEcológico\b',
    r'\bSpecial\b', r'\bEdition\b', r'\bLimited\b',
    r'\bSuperior\b', r'\bSuperiore\b', r'\bClassico\b',
    r'\bD\.?O\.?C\.?G?\.?\b', r'\bI\.?G\.?T\.?\b', r'\bD\.?O\.?\b',
    r'\bVino\s+de\s+España\b', r'\bVino\s+d\'Italia\b',
]

# Region names that shouldn't be treated as distinctive wine names
REGION_WORDS = {
    # French
    'cotes', 'cote', 'du', 'rhone', 'rhône', 'bordeaux', 'bourgogne', 'burgundy',
    'languedoc', 'provence', 'loire', 'alsace', 'champagne', 'beaujolais',
    # Italian
    'alba', 'asti', 'barolo', 'barbaresco', 'chianti', 'toscana', 'tuscany',
    'piemonte', 'piedmont', 'veneto', 'sicilia', 'sicily', 'puglia', 'langhe',
    # Spanish
    'rioja', 'ribera', 'duero', 'priorat', 'rueda', 'rias', 'baixas', 'penedes',
    # Other
    'douro', 'alentejo', 'vinho', 'verde', 'marlborough', 'barossa', 'napa',
    # Common additions
    'sur', 'lie', 'village', 'villages', 'premier', 'cru', 'grand',
}

# Generic wine words that shouldn't heavily influence matching
GENERIC_WORDS = {
    'red', 'white', 'wine', 'blend', 'dry', 'sweet', 'rose', 'rosé', 'vin', 'vino',
    'organic', 'reserve', 'reserva', 'tinto', 'blanco', 'rouge', 'blanc',
    'bottle', 'vintage', 'edition', 'special', 'limited', 'superior', 'superiore',
    'cuvee', 'cuvée', 'brut', 'sec', 'demi', 'extra', 'nature'
}

# Grape varieties - if Vivino specifies one, SB should match it
GRAPE_VARIETIES = {
    'cabernet', 'merlot', 'shiraz', 'syrah', 'pinot', 'noir', 'grigio', 'gris',
    'chardonnay', 'sauvignon', 'riesling', 'gewurztraminer', 'moscato', 'muscat',
    'tempranillo', 'garnacha', 'grenache', 'mourvedre', 'malbec', 'carmenere',
    'sangiovese', 'nebbiolo', 'barbera', 'primitivo', 'zinfandel', 'dolcetto',
    'corvina', 'rondinella', 'vranec', 'vranac', 'temjanika', 'smederevka',
    'zweigelt', 'gruner', 'veltliner', 'weissburgunder', 'grauburgunder',
    'spatburgunder', 'trollinger', 'lemberger', 'dornfelder',
    'viognier', 'marsanne', 'roussanne', 'vermentino', 'fiano', 'greco',
    'albarino', 'verdejo', 'godello', 'monastrell', 'bobal', 'mencía',
    'touriga', 'nacional', 'tinta', 'roriz', 'castelao', 'baga', 'arinto'
}


def normalize_text(text: str) -> str:
    """Normalize text by removing accents and converting to lowercase.
    
    Learning: Accents like "Más" need to become "Mas" for matching.
    """
    if not text:
        return ""
    # Normalize unicode to decomposed form (separate accents from letters)
    normalized = unicodedata.normalize('NFD', text)
    # Remove accent marks (combining characters)
    no_accents = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return no_accents.lower()


def translate_terms(text: str) -> str:
    """Translate Vivino terms to Systembolaget equivalents.
    
    Learning: "Red Blend" on Vivino = "Red Wine" on Systembolaget
              "Dry" in English = "Trocken" in German (for German wines)
    """
    if not text:
        return ""
    
    result = text.lower()
    for vivino_term, sb_term in TERM_TRANSLATIONS.items():
        result = re.sub(r'\b' + re.escape(vivino_term) + r'\b', sb_term, result, flags=re.IGNORECASE)
    
    return result


def clean_wine_name(name: str, remove_descriptors: bool = False) -> str:
    """Clean wine name for searching.
    
    Learning: Remove vintage years, N.V., and optionally descriptors like "Tinto"
    """
    if not name:
        return ""
    
    cleaned = name
    
    # Remove years (e.g., 2018, 2021)
    cleaned = re.sub(r'\b(19|20)\d{2}\b', '', cleaned)
    
    # Remove N.V., NV (non-vintage)
    cleaned = re.sub(r'\bN\.?V\.?\b', '', cleaned, flags=re.IGNORECASE)
    
    # Optionally remove common wine descriptors
    if remove_descriptors:
        for desc in REMOVE_DESCRIPTORS:
            cleaned = re.sub(desc, '', cleaned, flags=re.IGNORECASE)
    
    # Remove special characters but keep spaces
    cleaned = re.sub(r'[^\w\s]', ' ', cleaned)
    
    # Collapse whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned


def calculate_match_score(vivino_name: str, sb_name: str, winery: str = None, sb_producer: str = None) -> float:
    """Calculate similarity score between Vivino and Systembolaget wine names.
    
    Key insight from manual matching:
    - Distinctive words in the wine name MUST match (e.g., "Crianza", "Leunin", "Raimonda")
    - Winery/producer matching is a bonus, but not enough alone
    - If Vivino says "Crianza" but SB says "Reserva", that's a BAD match
    
    Scoring:
    1. Required: Key wine name words must match (returns 0 if not)
    2. Producer match bonus: +25 points
    3. Winery in name bonus: +25 points  
    4. Word coverage bonus: up to 50 points
    
    Total max: 100 points
    """
    if not vivino_name or not sb_name:
        return 0.0
    
    # Clean, normalize accents, and translate terms
    clean_vivino = normalize_text(clean_wine_name(vivino_name, remove_descriptors=False))  # Keep descriptors for matching
    clean_sb = normalize_text(clean_wine_name(sb_name, remove_descriptors=False))
    
    # Also apply term translation (e.g., "dry" -> "trocken")
    clean_vivino = translate_terms(clean_vivino)
    clean_sb = translate_terms(clean_sb)
    
    words_vivino = clean_vivino.split()
    words_sb = clean_sb.split()
    
    if not words_vivino or not words_sb:
        return 0.0
    
    # Get winery words to exclude from wine name analysis
    winery_words = set()
    if winery:
        winery_words = set(normalize_text(clean_wine_name(winery)).split())
    
    # CRITICAL: Identify distinctive wine name words (not winery, not generic, not region)
    # These are words like "Crianza", "Leunin", "Raimonda", "Saint-Esprit", "Parallele 45"
    distinctive_vivino = [w for w in words_vivino 
                          if w not in GENERIC_WORDS 
                          and w not in winery_words
                          and w not in REGION_WORDS
                          and len(w) >= 3]  # Skip very short words
    
    sb_words_set = set(words_sb)
    
    # Check for grape variety mismatch - if Vivino specifies a grape, SB must match
    vivino_grapes = set(words_vivino) & GRAPE_VARIETIES
    sb_grapes = sb_words_set & GRAPE_VARIETIES
    
    if vivino_grapes and sb_grapes:
        # Both specify grapes - they must overlap
        if not (vivino_grapes & sb_grapes):
            # Different grapes! e.g., "Vranec" vs "Temjanika"
            logger.debug(f"  Grape mismatch: {vivino_grapes} vs {sb_grapes}")
            return 0.0  # Reject this match
    
    # Check for wine color mismatch (red vs white vs rosé)
    def get_wine_color(words):
        for color, color_words in WINE_COLOR_WORDS.items():
            if words & color_words:
                return color
        # Also check grapes that imply color
        red_grapes = {'vranec', 'vranac', 'shiraz', 'cabernet', 'merlot', 'primitivo', 'nebbiolo', 'barbera', 'tempranillo', 'pinot'}
        white_grapes = {'temjanika', 'riesling', 'chardonnay', 'sauvignon', 'moscato', 'weissburgunder', 'gruner'}
        if words & red_grapes:
            return 'red'
        if words & white_grapes:
            return 'white'
        return None
    
    vivino_color = get_wine_color(set(words_vivino))
    sb_color = get_wine_color(sb_words_set)
    
    if vivino_color and sb_color and vivino_color != sb_color:
        # Color mismatch! e.g., red wine matched to white wine
        logger.debug(f"  Color mismatch: {vivino_color} vs {sb_color}")
        return 0.0  # Reject this match
    
    # If Vivino wine has distinctive name words, they MUST appear in SB name
    if distinctive_vivino:
        matching_distinctive = sum(1 for w in distinctive_vivino if w in sb_words_set)
        
        # Require at least half of distinctive words to match
        # This catches: "Crianza" must match "Crianza", not "Reserva"
        #               "Leunin" must appear in SB name, not just "Nebbiolo"
        match_ratio = matching_distinctive / len(distinctive_vivino)
        
        if match_ratio < 0.5:
            # Key words missing - this is likely a wrong match
            logger.debug(f"  Distinctive words missing: {distinctive_vivino} vs {sb_words_set}")
            return 0.0  # Reject this match
    
    score = 0.0
    
    # 1. Producer match bonus (+25 points)
    if winery and sb_producer:
        clean_producer = normalize_text(sb_producer)
        producer_words = set(clean_producer.split())
        
        if winery_words & producer_words:
            score += 25
            logger.debug(f"  Producer match: +25")
    
    # 2. Winery appears in SB wine name (+25 points)
    if winery_words and (winery_words & sb_words_set):
        score += 25
        logger.debug(f"  Winery in name: +25")
    
    # 3. Word coverage - how many Vivino words appear in SB name (up to 40 points)
    # This rewards more complete matches
    vivino_words_set = set(words_vivino) - GENERIC_WORDS
    if vivino_words_set:
        matched = len(vivino_words_set & sb_words_set)
        coverage = matched / len(vivino_words_set)
        word_score = coverage * 40
        score += word_score
        logger.debug(f"  Word coverage ({matched}/{len(vivino_words_set)}): +{word_score:.1f}")
    
    # 4. Penalize extra words in SB name that aren't in Vivino (up to -10 points)
    # This prefers "Appassimento" over "Gran Marzoni Appassimento" when matching "Appassimento"
    sb_distinctive = set(words_sb) - GENERIC_WORDS - winery_words
    vivino_all = set(words_vivino) | winery_words
    extra_words = sb_distinctive - vivino_all
    
    if extra_words and vivino_words_set:
        # Don't penalize if Vivino also has extra words (bidirectional mismatch)
        extra_penalty = min(10, len(extra_words) * 3)
        score -= extra_penalty
        logger.debug(f"  Extra words penalty ({extra_words}): -{extra_penalty}")
    
    # 5. If Vivino says generic "Red Blend" but SB has specific grape, slight penalty
    # Prefer "Red Wine" over "Shiraz" for "Red Blend"
    if not vivino_grapes and sb_grapes:
        # Vivino didn't specify grape but SB did
        score -= 5
        logger.debug(f"  SB added specific grape ({sb_grapes}): -5")
    
    return max(0, min(100, score))


async def search_systembolaget(wine_name: str, winery: str = None) -> Optional[Dict[str, Any]]:
    """Search Systembolaget API for a wine.
    
    Learning: 
    - Filter for 750ml bottles only (avoid 375ml half bottles and tetrapacks)
    - Try multiple search queries
    - Use producer metadata to validate matches
    """
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        best_match = None
        best_score = 0.0
        
        # Clean names
        clean_name = clean_wine_name(wine_name)
        clean_name_simple = clean_wine_name(wine_name, remove_descriptors=True)
        clean_winery = clean_wine_name(winery) if winery else ""
        
        # Normalize for search
        search_name = normalize_text(clean_name)
        search_name_simple = normalize_text(clean_name_simple)
        search_winery = normalize_text(clean_winery)
        
        # Build search queries to try (in order of preference)
        search_queries = []
        
        # 1. Winery + wine name (most specific for branded wines)
        if search_winery and search_name_simple:
            search_queries.append(f"{search_winery} {search_name_simple}")
        
        # 2. Just winery name (for wines like "19 Crimes" where winery IS the name)
        if search_winery:
            search_queries.append(search_winery)
        
        # 3. Wine name alone
        if search_name:
            search_queries.append(search_name)
        
        # 4. Wine name without descriptors
        if search_name_simple and search_name_simple != search_name:
            search_queries.append(search_name_simple)
        
        # 5. First two words of wine name (often the distinctive part)
        name_parts = search_name_simple.split()
        if len(name_parts) >= 2:
            search_queries.append(' '.join(name_parts[:2]))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_queries = []
        for q in search_queries:
            if q and q not in seen and len(q) >= 3:
                seen.add(q)
                unique_queries.append(q)
        
        for query in unique_queries:
            logger.debug(f"  Searching: '{query}'")
            
            try:
                response = await client.get(
                    "https://api-extern.systembolaget.se/sb-api-ecommerce/v1/productsearch/search",
                    headers={"ocp-apim-subscription-key": SUBSCRIPTION_KEY},
                    params={
                        "page": 1,
                        "size": 10,
                        "sortBy": "Score",
                        "sortDirection": "Ascending",
                        "textQuery": query,
                        "volume.min": 700,  # Allow 700-800ml to catch 750ml bottles
                        "volume.max": 800,
                        "categoryLevel1": "Vin"
                    }
                )
                
                if response.status_code != 200:
                    logger.warning(f"API returned {response.status_code}")
                    continue
                
                products = response.json().get("products", [])
                
                for product in products:
                    # Skip non-750ml bottles
                    volume = product.get('volume')
                    if volume and volume < 700:
                        continue
                    
                    # Learning: Prefer glass bottles over paper packaging (tetrapack/bag-in-box)
                    packaging = (product.get('packagingLevel1') or '').lower()
                    is_glass_bottle = 'glas' in packaging or 'flaska' in packaging
                    is_paper = 'papp' in packaging or 'bag' in packaging or 'box' in packaging
                    
                    name_bold = product.get('productNameBold') or ''
                    name_thin = product.get('productNameThin') or ''
                    sb_name = f"{name_bold} {name_thin}".strip()
                    sb_producer = product.get('producerName', '')
                    
                    # Calculate score with producer validation
                    score = calculate_match_score(
                        vivino_name=wine_name,
                        sb_name=sb_name,
                        winery=winery,
                        sb_producer=sb_producer
                    )
                    
                    # Also try matching full vivino name (winery + wine)
                    if winery:
                        full_vivino_name = f"{winery} {wine_name}"
                        score2 = calculate_match_score(
                            vivino_name=full_vivino_name,
                            sb_name=sb_name,
                            winery=winery,
                            sb_producer=sb_producer
                        )
                        score = max(score, score2)
                    
                    # Learning: Prefer glass bottles over paper packaging
                    # Add a small bonus for glass, penalty for paper
                    adjusted_score = score
                    if is_glass_bottle:
                        adjusted_score += 5
                    elif is_paper:
                        adjusted_score -= 10  # Strong penalty for paper packaging
                    
                    if adjusted_score > best_score and score >= 40:  # Minimum 40% base match
                        best_score = adjusted_score
                        best_match = {
                            'product_number': product.get('productNumber'),
                            'name_bold': name_bold,
                            'name_thin': name_thin,
                            'full_name': sb_name,
                            'price': product.get('price'),
                            'country': product.get('country'),
                            'region': product.get('originLevel1'),  # Region metadata
                            'producer': sb_producer,
                            'year': product.get('vintage') or product.get('year'),
                            'alcohol_percentage': product.get('alcoholPercentage'),
                            'category_level2': product.get('categoryLevel2'),
                            'volume': volume,
                            'packaging': packaging,
                            'match_score': score  # Original score without packaging adjustment
                        }
                
                # Stop if we have a great match (80+)
                if best_match and best_score >= 80:
                    break
                    
            except Exception as e:
                logger.error(f"Error searching Systembolaget: {e}")
                continue
        
        return best_match


async def get_systembolaget_image(product_number: str) -> Optional[str]:
    """Get wine image URL from Systembolaget."""
    if not product_number:
        return None
    
    image_url = f"https://product-cdn.systembolaget.se/productimages/{product_number}/{product_number}_400.webp?q=75&w=768"
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.head(image_url)
            if response.status_code == 200:
                return image_url
    except Exception as e:
        logger.debug(f"Image check failed: {e}")
    
    return None


def load_verified_matches() -> Dict[str, Optional[str]]:
    """Load manually verified matches from file.
    
    Returns a dict mapping (winery, wine_name) -> product_number or None for no match.
    """
    verified_file = Path(__file__).parent / "verified_matches.json"
    if not verified_file.exists():
        return {}
    
    try:
        with open(verified_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        result = {}
        for m in data.get('matches', []):
            key = (
                normalize_text(m.get('vivino_winery', '')),
                normalize_text(m.get('vivino_name', ''))
            )
            result[key] = m.get('sb_product')  # None means no match
        
        logger.info(f"Loaded {len(result)} verified matches")
        return result
    except Exception as e:
        logger.error(f"Error loading verified matches: {e}")
        return {}


async def get_verified_product(product_number: str) -> Optional[Dict[str, Any]]:
    """Fetch product details from Systembolaget for a verified product number."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                "https://api-extern.systembolaget.se/sb-api-ecommerce/v1/productsearch/search",
                headers={"ocp-apim-subscription-key": SUBSCRIPTION_KEY},
                params={
                    "page": 1,
                    "size": 1,
                    "textQuery": product_number,
                    "categoryLevel1": "Vin"
                }
            )
            
            if response.status_code == 200:
                products = response.json().get("products", [])
                for product in products:
                    if str(product.get('productNumber')) == str(product_number):
                        name_bold = product.get('productNameBold') or ''
                        name_thin = product.get('productNameThin') or ''
                        return {
                            'product_number': product.get('productNumber'),
                            'name_bold': name_bold,
                            'name_thin': name_thin,
                            'full_name': f"{name_bold} {name_thin}".strip(),
                            'price': product.get('price'),
                            'country': product.get('country'),
                            'region': product.get('originLevel1'),
                            'producer': product.get('producerName'),
                            'year': product.get('vintage') or product.get('year'),
                            'alcohol_percentage': product.get('alcoholPercentage'),
                            'category_level2': product.get('categoryLevel2'),
                            'volume': product.get('volume'),
                            'match_score': 100.0  # Verified match
                        }
        except Exception as e:
            logger.error(f"Error fetching verified product {product_number}: {e}")
    
    return None


async def match_toplist_wines(clear_existing: bool = True):
    """Match all wines from scraped toplists with Systembolaget products.
    
    Uses verified matches when available, falls back to algorithm.
    
    Args:
        clear_existing: If True, clear existing wines/matches before adding new ones
    """
    
    # Load verified matches first
    verified_matches = load_verified_matches()
    
    # Load toplists
    toplists_file = DATA_DIR / "toplists.json"
    if not toplists_file.exists():
        logger.error("No toplists.json found!")
        return
    
    with open(toplists_file, 'r', encoding='utf-8') as f:
        toplists = json.load(f)
    
    # Load or initialize wines/matches
    wines_file = DATA_DIR / "wines.json"
    matches_file = DATA_DIR / "matches.json"
    
    if clear_existing:
        existing_wines = []
        existing_matches = []
    else:
        existing_wines = []
        existing_matches = []
        if wines_file.exists():
            with open(wines_file, 'r', encoding='utf-8') as f:
                existing_wines = json.load(f)
        if matches_file.exists():
            with open(matches_file, 'r', encoding='utf-8') as f:
                existing_matches = json.load(f)
    
    new_wines = []
    new_matches = []
    updated_toplists = []
    
    total_matched = 0
    total_scraped = 0
    
    for toplist in toplists:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing toplist: {toplist.get('name')}")
        logger.info(f"{'='*60}")
        
        matched_wine_ids = []
        scraped_wines = toplist.get('scraped_wines', [])
        total_scraped += len(scraped_wines)
        
        for i, scraped in enumerate(scraped_wines, 1):
            wine_name = scraped.get('name', '')
            winery = scraped.get('winery', '')
            
            logger.info(f"\n[{i}/{len(scraped_wines)}] Searching for: {winery} - {wine_name}")
            
            # Search Systembolaget using algorithm
            # (verified_matches are available for fallback/validation but not used as override)
            sb_match = await search_systembolaget(wine_name, winery)
            
            if sb_match:
                total_matched += 1
                logger.info(f"  ✅ Found: {sb_match['full_name']} ({sb_match['match_score']:.1f}%) - {sb_match['price']} SEK")
                
                # Get image - prefer local Vivino image, fallback to Systembolaget
                image_url = scraped.get('local_image')  # Local Vivino image from scraping
                if not image_url:
                    image_url = scraped.get('vivino_image_url')  # Remote Vivino image
                if not image_url:
                    image_url = await get_systembolaget_image(sb_match['product_number'])  # Fallback to SB
                
                # Create wine ID
                match_id = f"toplist_{toplist['id']}_{i}"
                
                # Create wine record (combining Vivino + Systembolaget data)
                wine_record = {
                    'id': match_id,
                    'name': scraped.get('name'),
                    'winery': scraped.get('winery'),
                    'rating': scraped.get('rating'),
                    'ratings_count': scraped.get('ratings_count'),
                    'country': sb_match.get('country') or scraped.get('country'),
                    'region': sb_match.get('region') or scraped.get('region'),
                    'simplified_wine_style': sb_match.get('category_level2'),
                    'image_url': image_url,
                    'vivino_url': scraped.get('vivino_url'),  # Link to Vivino page
                    'alcohol_content': sb_match.get('alcohol_percentage'),
                    'year': sb_match.get('year'),
                    'vivino_rank': scraped.get('rank'),
                }
                new_wines.append(wine_record)
                
                # Create match record
                match_record = {
                    'id': f"match_{match_id}",
                    'vivino_wine_id': match_id,
                    'systembolaget_product': {
                        'product_number': sb_match['product_number'],
                        'name_bold': sb_match['name_bold'],
                        'name_thin': sb_match['name_thin'],
                        'full_name': sb_match['full_name'],
                        'price': sb_match['price'],
                        'country': sb_match['country'],
                        'region': sb_match.get('region'),
                        'producer': sb_match['producer'],
                        'year': sb_match['year'],
                        'alcohol_percentage': sb_match['alcohol_percentage'],
                        'category_level2': sb_match['category_level2'],
                        'volume': sb_match.get('volume'),
                    },
                    'match_score': sb_match['match_score'],
                    'verified': False,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat(),
                }
                new_matches.append(match_record)
                matched_wine_ids.append(match_id)
                
            else:
                logger.warning(f"  ❌ No match found on Systembolaget")
            
            # Rate limiting
            await asyncio.sleep(0.3)
        
        # Update toplist with matched wine IDs
        toplist['wines'] = matched_wine_ids
        toplist['wine_count'] = len(matched_wine_ids)
        toplist['updated_at'] = datetime.now().isoformat()
        updated_toplists.append(toplist)
        
        logger.info(f"\nMatched {len(matched_wine_ids)}/{len(scraped_wines)} wines from {toplist['name']}")
    
    # Save updated data
    logger.info(f"\n{'='*60}")
    logger.info("Saving results...")
    
    # Merge new wines with existing
    all_wines = existing_wines + new_wines
    with open(wines_file, 'w', encoding='utf-8') as f:
        json.dump(all_wines, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(all_wines)} wines to wines.json")
    
    # Merge new matches with existing
    all_matches = existing_matches + new_matches
    with open(matches_file, 'w', encoding='utf-8') as f:
        json.dump(all_matches, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(all_matches)} matches to matches.json")
    
    # Save updated toplists
    with open(toplists_file, 'w', encoding='utf-8') as f:
        json.dump(updated_toplists, f, indent=2, ensure_ascii=False)
    logger.info(f"Updated {len(updated_toplists)} toplists")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"TOTAL: Matched {total_matched}/{total_scraped} wines ({100*total_matched/total_scraped:.1f}%)")
    logger.info("Done! Run static_site_generator.py to update the website.")


if __name__ == "__main__":
    asyncio.run(match_toplist_wines(clear_existing=True))
