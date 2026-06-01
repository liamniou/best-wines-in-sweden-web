"""
Static Site Generator for Best Wines Sweden
Reads data from JSON files and generates static HTML pages
"""

import json
import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import logging
from translations import translate_country, translate_wine_style

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sanitize_id(match_id: str) -> str:
    """Sanitize match_id to be URL-safe (replace ? and & with _)"""
    if not match_id:
        return match_id
    return re.sub(r'[?&=]', '_', str(match_id))

def strip_year_from_name(name: str) -> str:
    """Remove trailing year (like ' 2022', ' 2021') from wine name"""
    if not name:
        return name
    # Remove year at end of string (4 digits preceded by space)
    return re.sub(r'\s+\d{4}\s*$', '', str(name)).strip()

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = Path("/app/data" if os.path.exists("/app/data") else BASE_DIR.parent / "data")
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = BASE_DIR / "static_site"

def load_json(file_path: Path):
    """Load JSON file with error handling"""
    if not file_path.exists():
        logger.warning(f"File not found: {file_path}")
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return []

def parse_food_pairings(pairings):
    """Parse food pairings from string or list"""
    if not pairings:
        return []
    if isinstance(pairings, str):
        try:
            return json.loads(pairings)
        except:
            return []
    return pairings

def merge_wine_data(wines: list, matches: list) -> list:
    """Merge wine data with match data to create complete wine records"""
    # Create lookup by vivino_wine_id
    wine_lookup = {w.get('id') or w.get('vivino_id'): w for w in wines}
    
    merged = []
    for match in matches:
        vivino_id = match.get('vivino_wine_id')
        wine = wine_lookup.get(vivino_id, {})
        sb_product = match.get('systembolaget_product', {})
        
        # Parse food pairings
        food_pairings = parse_food_pairings(wine.get('simplified_food_pairings'))
        
        merged_wine = {
            'match_id': sanitize_id(match.get('id', '').replace('match_', '')),
            'vivino_name': strip_year_from_name(wine.get('name', 'Unknown Wine')),
            'vivino_rating': wine.get('rating'),  # Only use valid rating (1-5 scale)
            'vivino_num_ratings': wine.get('ratings_count'),  # Number of Vivino reviews for credibility
            'vivino_country': translate_country(wine.get('country')),
            'vivino_region': wine.get('region'),
            'vivino_winery': wine.get('winery'),
            'vivino_wine_style': translate_wine_style(wine.get('simplified_wine_style')) if wine.get('simplified_wine_style') not in [None, 'Unknown', 'unknown'] else None,
            'vivino_alcohol_content': wine.get('alcohol_content'),
            'image_url': wine.get('image_url'),
            'vivino_url': wine.get('url'),
            'systembolaget_name': strip_year_from_name(sb_product.get('full_name', sb_product.get('name_bold', ''))),
            'product_number': sb_product.get('product_number'),
            'price': sb_product.get('price'),
            'country': translate_country(sb_product.get('country')),
            'producer': sb_product.get('producer'),
            'year': sb_product.get('year') or wine.get('year'),
            'alcohol_percentage': sb_product.get('alcohol_percentage'),
            'wine_style': translate_wine_style(sb_product.get('category_level2')),
            'match_score': match.get('match_score', 0),
            'verified': match.get('verified', False),
            'simplified_food_pairings': food_pairings,
            'body': wine.get('body'),
            'acidity': wine.get('acidity'),
            'sweetness': wine.get('sweetness'),
            'tannin': wine.get('tannin'),  # Tannin level for red wines
            'data_quality_score': wine.get('data_quality_score'),  # Data completeness score
            'updated_at': wine.get('updated_at') or match.get('updated_at', ''),
        }
        merged.append(merged_wine)
    
    # Sort by match score descending (default)
    merged.sort(key=lambda x: x.get('match_score', 0), reverse=True)
    return merged

def generate_static_site():
    """Generate all static HTML pages"""
    logger.info("Starting static site generation...")
    
    # Load data
    wines = load_json(DATA_DIR / "wines.json")
    matches = load_json(DATA_DIR / "matches.json")
    toplists = load_json(DATA_DIR / "toplists.json")
    stats = load_json(DATA_DIR / "stats.json")
    
    logger.info(f"Loaded {len(wines)} wines, {len(matches)} matches, {len(toplists)} toplists")
    
    # Merge wine data
    all_wines = merge_wine_data(wines, matches)
    logger.info(f"Merged into {len(all_wines)} complete wine records")
    
    # Calculate stats
    if all_wines:
        ratings = [w['vivino_rating'] for w in all_wines if w.get('vivino_rating')]
        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0
    else:
        avg_rating = 0
    
    stats = {
        'total_wines': len(all_wines),
        'total_toplists': len(toplists),
        'avg_rating': avg_rating
    }
    
    # Setup Jinja2 with custom url_for function
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    
    # Add url_for function for static file references
    def url_for(endpoint, **kwargs):
        if endpoint == 'static':
            path = kwargs.get('path', '')
            return f"/static{path}"
        return f"/{endpoint}"
    
    env.globals['url_for'] = url_for
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Copy static assets
    static_output = OUTPUT_DIR / "static"
    if static_output.exists():
        shutil.rmtree(static_output)
    shutil.copytree(STATIC_DIR, static_output)
    logger.info("Copied static assets")
    
    # Generate index.html
    # Sort by most recent for homepage
    recent_wines = sorted(all_wines, key=lambda x: x.get('updated_at', ''), reverse=True)
    
    template = env.get_template('index.html')
    html = template.render(
        wines=recent_wines,  # Pass all wines, template handles pagination
        total_wines=stats['total_wines'],
        total_toplists=stats['total_toplists'],
        avg_rating=stats['avg_rating']
    )
    (OUTPUT_DIR / "index.html").write_text(html, encoding='utf-8')
    logger.info("Generated index.html")
    
    # Generate filters.html
    template = env.get_template('filters.html')
    
    # Get filter options
    wine_styles = sorted(set(w.get('vivino_wine_style') or w.get('wine_style') for w in all_wines if w.get('vivino_wine_style') or w.get('wine_style')))
    countries = sorted(set(w.get('vivino_country') or w.get('country') for w in all_wines if w.get('vivino_country') or w.get('country')))
    
    # Build filter_options object for template
    filter_options = {
        'vivino_countries': countries,
        'wine_styles': wine_styles,
        'acidity_options': [
            {'value': '1', 'label': 'Low Acidity'},
            {'value': '2', 'label': 'Medium-Low'},
            {'value': '3', 'label': 'Medium'},
            {'value': '4', 'label': 'Medium-High'},
            {'value': '5', 'label': 'High Acidity'},
        ],
        'sweetness_options': [
            {'value': '1', 'label': 'Bone Dry'},
            {'value': '2', 'label': 'Dry'},
            {'value': '3', 'label': 'Off-Dry'},
            {'value': '4', 'label': 'Medium Sweet'},
            {'value': '5', 'label': 'Sweet'},
        ],
        'food_pairings': [
            {'value': 'beef', 'label': '🥩 Beef'},
            {'value': 'pork', 'label': '🥓 Pork'},
            {'value': 'lamb', 'label': '🐑 Lamb'},
            {'value': 'poultry', 'label': '🐔 Poultry'},
            {'value': 'fish', 'label': '🐟 Fish'},
            {'value': 'shellfish', 'label': '🦐 Shellfish'},
            {'value': 'cheese', 'label': '🧀 Cheese'},
            {'value': 'pasta', 'label': '🍝 Pasta'},
            {'value': 'vegetables', 'label': '🥬 Vegetables'},
            {'value': 'dessert', 'label': '🍰 Dessert'},
        ],
    }
    
    html = template.render(
        wines=all_wines,
        wine_styles=wine_styles,
        countries=countries,
        filter_options=filter_options,
        all_wines_json=json.dumps(all_wines)
    )
    (OUTPUT_DIR / "filters.html").write_text(html, encoding='utf-8')
    logger.info("Generated filters.html")
    
    # Calculate toplist statistics before rendering
    for toplist in toplists:
        scraped_wines = toplist.get('scraped_wines', [])
        
        # Set wine count from scraped wines
        toplist['wine_count'] = len(scraped_wines)
        
        # Calculate average rating from scraped wines
        ratings = [w.get('rating') for w in scraped_wines if w.get('rating')]
        if ratings:
            toplist['avg_rating'] = round(sum(ratings) / len(ratings), 1)
        else:
            toplist['avg_rating'] = None
    
    # Generate toplists.html
    template = env.get_template('toplists.html')
    html = template.render(toplists=toplists)
    (OUTPUT_DIR / "toplists.html").write_text(html, encoding='utf-8')
    logger.info("Generated toplists.html")
    
    # Generate individual toplist pages
    toplist_dir = OUTPUT_DIR / "toplist"
    toplist_dir.mkdir(exist_ok=True)
    
    try:
        template = env.get_template('toplist.html')
        
        # Create a lookup dictionary for matched wines by their vivino_id
        # The match_id format is like "toplist_best_wines_under_100_kr_right__1"
        matched_wines_lookup = {}
        for w in all_wines:
            match_id = w.get('match_id', '')
            if match_id:
                matched_wines_lookup[match_id] = w
        
        for toplist in toplists:
            toplist_wines = []
            toplist_id = toplist.get('id', '')
            
            # Always use scraped_wines and merge match data if available
            for scraped in toplist.get('scraped_wines', []):
                rank = scraped.get('rank', 0)
                winery = scraped.get('winery', '')
                name = scraped.get('name', '')
                
                # Build the expected match_id for this wine
                expected_match_id = f"toplist_{toplist_id}_{rank}"
                matched_wine = matched_wines_lookup.get(expected_match_id)
                
                if matched_wine:
                    # Use the matched wine data (has Systembolaget info)
                    toplist_wines.append(matched_wine)
                else:
                    # Create display name - avoid duplication if winery is in name
                    if winery.lower() in name.lower():
                        display_name = name
                    else:
                        display_name = f"{winery} {name}".strip()
                    
                    # Get image URL (prefer local, fallback to Vivino URL)
                    image_url = scraped.get('local_image')
                    if not image_url:
                        vivino_img = scraped.get('vivino_image_url', '')
                        # Fix protocol-relative URLs
                        if vivino_img.startswith('//'):
                            image_url = 'https:' + vivino_img
                        elif vivino_img:
                            image_url = vivino_img
                    
                    # Convert scraped wine to the format expected by the template
                    wine = {
                        'match_id': None,  # No match_id for unmatched wines
                        'vivino_name': name,
                        'vivino_winery': winery,
                        'vivino_rating': scraped.get('rating'),
                        'vivino_num_ratings': scraped.get('ratings_count'),
                        'vivino_country': scraped.get('country'),
                        'vivino_region': scraped.get('region'),
                        'price': scraped.get('price'),
                        'systembolaget_name': display_name,
                        'vivino_wine_style': scraped.get('wine_style') or (
                            'Red Wine' if 'red' in (name + scraped.get('region', '')).lower() else 
                            'White Wine' if 'white' in (name + scraped.get('region', '')).lower() or 'riesling' in name.lower() else
                            None),
                        'match_score': None,  # Not matched
                        'image_url': image_url,
                        'vivino_url': scraped.get('vivino_url'),
                        'simplified_food_pairings': [],
                    }
                    toplist_wines.append(wine)
            
            # Calculate stats
            wine_count = len(toplist_wines)
            avg_rating = None
            avg_price = None
            if toplist_wines:
                ratings = [w.get('vivino_rating') for w in toplist_wines if w.get('vivino_rating')]
                prices = [w.get('price') for w in toplist_wines if w.get('price')]
                if ratings:
                    avg_rating = round(sum(ratings) / len(ratings), 1)
                if prices:
                    avg_price = round(sum(prices) / len(prices))
            
            html = template.render(
                toplist=toplist,
                wines=toplist_wines,
                wine_count=wine_count,
                avg_rating=avg_rating,
                avg_price=avg_price
            )
            toplist_id = toplist.get('id', 'unknown')
            (toplist_dir / f"{toplist_id}.html").write_text(html, encoding='utf-8')
        logger.info(f"Generated {len(toplists)} toplist pages")
    except Exception as e:
        logger.warning(f"Could not generate toplist pages: {e}")
    
    # Generate individual wine detail pages
    wine_dir = OUTPUT_DIR / "wine"
    wine_dir.mkdir(exist_ok=True)
    
    try:
        template = env.get_template('wine_detail.html')
        for wine in all_wines:
            html = template.render(wine=wine)
            wine_id = wine.get('match_id', 'unknown')
            (wine_dir / f"{wine_id}.html").write_text(html, encoding='utf-8')
        logger.info(f"Generated {len(all_wines)} wine detail pages")
    except Exception as e:
        logger.warning(f"Could not generate wine detail pages: {e}")
    
    # Generate wines.json for client-side filtering
    (OUTPUT_DIR / "api" ).mkdir(exist_ok=True)
    (OUTPUT_DIR / "api" / "wines.json").write_text(json.dumps(all_wines), encoding='utf-8')
    
    # Generate filter options JSON
    filter_options = {
        'wine_styles': wine_styles,
        'countries': countries,
        'price_range': {
            'min': min((w.get('price') or 0) for w in all_wines) if all_wines else 0,
            'max': max((w.get('price') or 0) for w in all_wines) if all_wines else 1000
        }
    }
    (OUTPUT_DIR / "api" / "filters.json").write_text(json.dumps(filter_options), encoding='utf-8')
    
    logger.info(f"Static site generated in {OUTPUT_DIR}")
    logger.info(f"Total pages: {2 + len(toplists) + len(all_wines)}")
    
    return {
        'wines': len(all_wines),
        'toplists': len(toplists),
        'pages': 2 + len(toplists) + len(all_wines)
    }

if __name__ == "__main__":
    generate_static_site()
