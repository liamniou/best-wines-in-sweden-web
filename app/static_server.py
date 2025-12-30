"""
Simple Static Server for Best Wines Sweden
Serves pre-generated static HTML files - no database required
"""

import os
import json
import mimetypes
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Normalize text for fuzzy matching (lowercase, remove accents, etc.)"""
    if not text:
        return ""
    # Convert to lowercase
    text = text.lower().strip()
    # Replace common accent characters
    replacements = {
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'á': 'a', 'à': 'a', 'â': 'a', 'ä': 'a', 'ã': 'a',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
        'ó': 'o', 'ò': 'o', 'ô': 'o', 'ö': 'o', 'õ': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
        'ñ': 'n', 'ç': 'c'
    }
    for accented, plain in replacements.items():
        text = text.replace(accented, plain)
    return text


def fuzzy_match(search_term: str, text: str, threshold: float = 0.6) -> bool:
    """
    Check if search_term fuzzy matches text.
    Uses word-based matching with partial match support.
    
    Args:
        search_term: The term to search for
        text: The text to search in
        threshold: Minimum match ratio (0-1)
    
    Returns:
        True if there's a fuzzy match
    """
    if not search_term or not text:
        return False
    
    search_norm = normalize_text(search_term)
    text_norm = normalize_text(text)
    
    # Exact substring match
    if search_norm in text_norm:
        return True
    
    # Word-by-word matching
    search_words = search_norm.split()
    text_words = text_norm.split()
    
    # Check if all search words are contained in text (partial match)
    for search_word in search_words:
        found = False
        for text_word in text_words:
            # Allow partial word matches (at least 3 chars)
            if len(search_word) >= 3 and (search_word in text_word or text_word.startswith(search_word)):
                found = True
                break
            # For short words, require exact match
            elif len(search_word) < 3 and search_word == text_word:
                found = True
                break
        if not found:
            return False
    
    return True


def calculate_search_relevance(wine: Dict[str, Any], search_term: str) -> float:
    """
    Calculate a relevance score for a wine based on search term.
    Higher score = more relevant.
    """
    if not search_term:
        return 0
    
    search_norm = normalize_text(search_term)
    score = 0
    
    # Check different fields with different weights
    fields_weights = {
        'systembolaget_name': 10,
        'vivino_name': 8,
        'vivino_wine_style': 6,
        'wine_style': 6,
        'vivino_winery': 5,
        'producer': 5,
        'vivino_country': 3,
        'country': 3,
        'vivino_region': 3,
    }
    
    for field, weight in fields_weights.items():
        value = wine.get(field) or ''
        value_norm = normalize_text(value)
        
        # Exact match in name = highest score
        if search_norm == value_norm:
            score += weight * 3
        # Search term is in the value
        elif search_norm in value_norm:
            score += weight * 2
        # Partial word match
        elif fuzzy_match(search_norm, value):
            score += weight
    
    return score

app = FastAPI(
    title="Best Wines Sweden",
    description="Static wine discovery site",
    version="3.0.0"
)

# Paths
BASE_DIR = Path(__file__).parent
STATIC_SITE_DIR = BASE_DIR / "static_site"
STATIC_ASSETS_DIR = STATIC_SITE_DIR / "static"
IMAGES_DIR = STATIC_SITE_DIR / "images"

# Mount static assets
if STATIC_ASSETS_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_ASSETS_DIR)), name="static")

# Mount images directory (for wine bottle images)
if IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "mode": "static"}

@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve homepage"""
    index_path = STATIC_SITE_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding='utf-8'))
    raise HTTPException(status_code=404, detail="Site not generated. Run static_site_generator.py first.")

@app.get("/filters", response_class=HTMLResponse)
@app.get("/filters.html", response_class=HTMLResponse)
async def filters():
    """Serve filters page"""
    filters_path = STATIC_SITE_DIR / "filters.html"
    if filters_path.exists():
        return HTMLResponse(content=filters_path.read_text(encoding='utf-8'))
    raise HTTPException(status_code=404, detail="Filters page not found")

@app.get("/toplists", response_class=HTMLResponse)
@app.get("/toplists.html", response_class=HTMLResponse)
async def toplists():
    """Serve toplists page"""
    toplists_path = STATIC_SITE_DIR / "toplists.html"
    if toplists_path.exists():
        return HTMLResponse(content=toplists_path.read_text(encoding='utf-8'))
    raise HTTPException(status_code=404, detail="Toplists page not found")

@app.get("/toplist/{toplist_id}", response_class=HTMLResponse)
async def toplist_detail(toplist_id: str):
    """Serve individual toplist page"""
    toplist_path = STATIC_SITE_DIR / "toplist" / f"{toplist_id}.html"
    if toplist_path.exists():
        return HTMLResponse(content=toplist_path.read_text(encoding='utf-8'))
    raise HTTPException(status_code=404, detail="Toplist not found")

@app.get("/wine/{wine_id}", response_class=HTMLResponse)
async def wine_detail(wine_id: str):
    """Serve individual wine detail page"""
    wine_path = STATIC_SITE_DIR / "wine" / f"{wine_id}.html"
    if wine_path.exists():
        return HTMLResponse(content=wine_path.read_text(encoding='utf-8'))
    raise HTTPException(status_code=404, detail="Wine not found")

# API endpoints for filtering
@app.get("/api/wines")
async def api_wines(
    search_term: str = None,
    min_price: float = None,
    max_price: float = None,
    min_rating: float = None,
    max_rating: float = None,
    wine_style: str = None,
    country: str = None,
    sort_by: str = "rating",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20
):
    """Return filtered wines as JSON with fuzzy search support"""
    wines_path = STATIC_SITE_DIR / "api" / "wines.json"
    if not wines_path.exists():
        return []
    
    wines = json.loads(wines_path.read_text(encoding='utf-8'))
    
    # Apply fuzzy search filter
    search_active = False
    if search_term and search_term.strip() and search_term.strip().lower() != 'undefined':
        search_active = True
        search_clean = search_term.strip()
        
        # Calculate relevance scores for all wines
        scored_wines = []
        for wine in wines:
            relevance = calculate_search_relevance(wine, search_clean)
            if relevance > 0:
                wine['_search_relevance'] = relevance
                scored_wines.append(wine)
        
        # Also include wines that match with basic fuzzy matching but might have low score
        remaining_wines = [w for w in wines if w not in scored_wines]
        for wine in remaining_wines:
            # Check multiple fields with fuzzy matching
            fields_to_check = [
                wine.get('systembolaget_name'),
                wine.get('vivino_name'),
                wine.get('vivino_wine_style'),
                wine.get('wine_style'),
                wine.get('vivino_winery'),
                wine.get('producer'),
                wine.get('vivino_country'),
                wine.get('country'),
            ]
            
            for field in fields_to_check:
                if field and fuzzy_match(search_clean, field):
                    wine['_search_relevance'] = 1  # Low relevance but still a match
                    scored_wines.append(wine)
                    break
        
        wines = scored_wines
        logger.info(f"Search '{search_clean}' found {len(wines)} matches")
    
    # Apply price filter
    if min_price is not None:
        wines = [w for w in wines if (w.get('price') or 0) >= min_price]
    if max_price is not None:
        wines = [w for w in wines if (w.get('price') or 9999) <= max_price]
    
    # Apply rating filter
    if min_rating is not None:
        wines = [w for w in wines if (w.get('vivino_rating') or 0) >= min_rating]
    if max_rating is not None:
        wines = [w for w in wines if (w.get('vivino_rating') or 5) <= max_rating]
    
    # Apply wine style filter with fuzzy matching
    if wine_style and wine_style.strip():
        style_clean = wine_style.strip()
        wines = [w for w in wines if fuzzy_match(style_clean, w.get('vivino_wine_style') or w.get('wine_style') or '')]
    
    # Apply country filter with fuzzy matching
    if country and country.strip():
        country_clean = country.strip()
        wines = [w for w in wines if fuzzy_match(country_clean, w.get('vivino_country') or w.get('country') or '')]
    
    # Sort - if search is active, sort by relevance first
    if search_active:
        # Sort by relevance, then by rating
        wines = sorted(wines, key=lambda w: (w.get('_search_relevance', 0), w.get('vivino_rating') or 0), reverse=True)
        # Clean up temporary field
        for wine in wines:
            wine.pop('_search_relevance', None)
    else:
        sort_key = {
            'rating': lambda w: w.get('vivino_rating') or 0,
            'price': lambda w: w.get('price') or 0,
            'match_score': lambda w: w.get('match_score') or 0,
            'name': lambda w: (w.get('systembolaget_name') or '').lower()
        }.get(sort_by, lambda w: w.get('vivino_rating') or 0)
        
        wines = sorted(wines, key=sort_key, reverse=(sort_order == 'desc'))
    
    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    
    return wines[start:end]

@app.get("/api/filters/options")
async def api_filter_options():
    """Return filter options"""
    filters_path = STATIC_SITE_DIR / "api" / "filters.json"
    if filters_path.exists():
        return json.loads(filters_path.read_text(encoding='utf-8'))
    return {"wine_styles": [], "countries": []}

@app.on_event("startup")
async def startup():
    """Check if static site exists on startup"""
    if not STATIC_SITE_DIR.exists():
        logger.warning(f"Static site directory not found: {STATIC_SITE_DIR}")
        logger.warning("Run 'python static_site_generator.py' to generate the site")
    else:
        index_path = STATIC_SITE_DIR / "index.html"
        if index_path.exists():
            logger.info("Static site ready to serve")
        else:
            logger.warning("index.html not found - run static_site_generator.py")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
