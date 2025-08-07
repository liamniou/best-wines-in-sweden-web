"""
FastAPI web application for Best Wines Sweden
"""

from fastapi import FastAPI, Depends, HTTPException, Query, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func, text
from typing import List, Optional
import os
import logging
from models import (
    WineMatchResponse, ToplistResponse, WineFilters,
    WineMatch, VivinoWine, SystembolagetProduct, Toplist, ToplistWine, UpdateLog
)
from database import get_db, create_tables, init_database, check_database_connection, SessionLocal
from auth import verify_credentials, create_access_token, get_current_admin
from datetime import timedelta
import asyncio
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Best Wines Sweden",
    description="Find the best wines from Vivino available at Systembolaget",
    version="2.0.0"
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Starting Best Wines Sweden application...")
    
    if not check_database_connection():
        raise Exception("Database connection failed")
    
    create_tables()
    init_database()
    logger.info("Application started successfully")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    """Home page with wine listings"""
    try:
        # Get summary statistics
        total_wines = db.query(WineMatch).count()
        total_toplists = db.query(Toplist).count()
        avg_rating = db.query(func.avg(VivinoWine.rating)).scalar() or 0
        
        # Get recent wine matches
        recent_matches = (
            db.query(WineMatch, VivinoWine, SystembolagetProduct)
            .join(VivinoWine, WineMatch.vivino_wine_id == VivinoWine.id)
            .join(SystembolagetProduct, WineMatch.systembolaget_product_id == SystembolagetProduct.id)
            .order_by(desc(WineMatch.created_at))
            .limit(10)
            .all()
        )
        
        wines = []
        for match, vivino, sb in recent_matches:
            # Parse grape varieties if available
            grape_varieties = None
            if vivino.grape_varieties:
                try:
                    import json
                    grape_varieties = json.loads(vivino.grape_varieties)
                except:
                    grape_varieties = None
            
            # Parse simplified food pairings if available
            simplified_food_pairings = None
            if vivino.simplified_food_pairings:
                try:
                    import json
                    simplified_food_pairings = json.loads(vivino.simplified_food_pairings)
                except:
                    simplified_food_pairings = None
            
            wines.append(WineMatchResponse(
                match_id=match.id,
                match_score=float(match.match_score) if match.match_score else None,
                verified=match.verified,
                vivino_name=vivino.name,
                vivino_rating=float(vivino.rating),
                systembolaget_name=sb.full_name,
                price=float(sb.price) if sb.price else None,
                wine_style=sb.category_level2,
                country=sb.country,
                product_number=sb.product_number,
                alcohol_percentage=float(sb.alcohol_percentage) if sb.alcohol_percentage else None,
                year=sb.year,
                producer=sb.producer,
                image_url=vivino.image_url,
                # Enhanced wine data
                vivino_country=vivino.country,
                vivino_region=vivino.region,
                vivino_winery=vivino.winery,
                vivino_wine_style=vivino.wine_style,
                simplified_wine_style=vivino.simplified_wine_style,
                vivino_alcohol_content=float(vivino.alcohol_content) if vivino.alcohol_content else None,
                body=vivino.body,
                acidity=vivino.acidity,
                sweetness=vivino.sweetness,
                grape_varieties=grape_varieties,
                simplified_food_pairings=simplified_food_pairings,
                description=vivino.description
            ))
        
        return templates.TemplateResponse("index.html", {
            "request": request,
            "total_wines": total_wines,
            "total_toplists": total_toplists,
            "avg_rating": round(avg_rating, 1),
            "wines": wines
        })
    except Exception as e:
        logger.error(f"Error loading home page: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/test-images", response_class=HTMLResponse)
async def test_images(request: Request, db: Session = Depends(get_db)):
    """Test page to show wine images"""
    try:
        # Get wines with images
        wines = db.query(VivinoWine).filter(VivinoWine.image_url.isnot(None)).limit(12).all()
        return templates.TemplateResponse("test_images.html", {"request": request, "wines": wines})
    except Exception as e:
        logger.error(f"Error loading test images page: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/toplists", response_model=List[ToplistResponse])
async def get_toplists(db: Session = Depends(get_db)):
    """Get all toplists with statistics"""
    try:
        query = text("""
            SELECT 
                t.id,
                t.name,
                t.category,
                COUNT(DISTINCT tw.vivino_wine_id) as wine_count,
                COUNT(DISTINCT wm.id) as match_count,
                AVG(vw.rating) as avg_rating,
                t.updated_at
            FROM toplists t
            LEFT JOIN toplist_wines tw ON t.id = tw.toplist_id
            LEFT JOIN vivino_wines vw ON tw.vivino_wine_id = vw.id
            LEFT JOIN wine_matches wm ON vw.id = wm.vivino_wine_id
            GROUP BY t.id, t.name, t.category, t.updated_at
            ORDER BY t.name
        """)
        
        result = db.execute(query)
        toplists = []
        
        for row in result:
            toplists.append(ToplistResponse(
                id=row.id,
                name=row.name,
                category=row.category or "general",
                wine_count=row.wine_count or 0,
                match_count=row.match_count or 0,
                avg_rating=float(row.avg_rating) if row.avg_rating else None,
                updated_at=row.updated_at
            ))
        
        return toplists
    except Exception as e:
        logger.error(f"Error fetching toplists: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch toplists")

@app.get("/api/wines", response_model=List[WineMatchResponse])
async def get_wines(
    filters: WineFilters = Depends(),
    db: Session = Depends(get_db)
):
    """Get wines with filtering and pagination"""
    try:
        # Base query with joins
        query = (
            db.query(WineMatch, VivinoWine, SystembolagetProduct)
            .join(VivinoWine, WineMatch.vivino_wine_id == VivinoWine.id)
            .join(SystembolagetProduct, WineMatch.systembolaget_product_id == SystembolagetProduct.id)
        )
        
        # Apply filters
        if filters.min_price is not None:
            query = query.filter(SystembolagetProduct.price >= filters.min_price)
        
        if filters.max_price is not None:
            query = query.filter(SystembolagetProduct.price <= filters.max_price)
        
        if filters.min_rating is not None:
            query = query.filter(VivinoWine.rating >= filters.min_rating)
        
        if filters.max_rating is not None:
            query = query.filter(VivinoWine.rating <= filters.max_rating)
        
        if filters.wine_style:
            query = query.filter(SystembolagetProduct.category_level2.ilike(f"%{filters.wine_style}%"))
        
        if filters.country:
            query = query.filter(SystembolagetProduct.country.ilike(f"%{filters.country}%"))
        
        if filters.search_term:
            search = f"%{filters.search_term}%"
            query = query.filter(
                or_(
                    VivinoWine.name.ilike(search),
                    SystembolagetProduct.name_bold.ilike(search),
                    SystembolagetProduct.name_thin.ilike(search),
                    SystembolagetProduct.producer.ilike(search)
                )
            )
        
        if filters.toplist_id:
            query = query.join(ToplistWine, VivinoWine.id == ToplistWine.vivino_wine_id)
            query = query.filter(ToplistWine.toplist_id == filters.toplist_id)
        
        if filters.verified_only:
            query = query.filter(WineMatch.verified == True)
        
        # Enhanced Vivino filters
        if filters.vivino_country:
            query = query.filter(VivinoWine.country.ilike(f"%{filters.vivino_country}%"))
        
        if filters.vivino_region:
            query = query.filter(VivinoWine.region.ilike(f"%{filters.vivino_region}%"))
        
        if filters.vivino_winery:
            query = query.filter(VivinoWine.winery.ilike(f"%{filters.vivino_winery}%"))
        
        if filters.vivino_wine_style:
            query = query.filter(VivinoWine.wine_style.ilike(f"%{filters.vivino_wine_style}%"))
        
        if filters.simplified_wine_style:
            query = query.filter(VivinoWine.simplified_wine_style == filters.simplified_wine_style)
        
        # Wine characteristics filters
        if filters.min_alcohol is not None:
            query = query.filter(
                or_(
                    VivinoWine.alcohol_content >= filters.min_alcohol,
                    SystembolagetProduct.alcohol_percentage >= filters.min_alcohol
                )
            )
        
        if filters.max_alcohol is not None:
            query = query.filter(
                or_(
                    VivinoWine.alcohol_content <= filters.max_alcohol,
                    SystembolagetProduct.alcohol_percentage <= filters.max_alcohol
                )
            )
        
        if filters.body is not None:
            query = query.filter(VivinoWine.body == filters.body)
        
        if filters.acidity is not None:
            query = query.filter(VivinoWine.acidity == filters.acidity)
        
        if filters.sweetness is not None:
            query = query.filter(VivinoWine.sweetness == filters.sweetness)
        
        # Year filters
        if filters.min_year is not None:
            query = query.filter(
                or_(
                    VivinoWine.year >= filters.min_year,
                    SystembolagetProduct.year >= filters.min_year
                )
            )
        
        if filters.max_year is not None:
            query = query.filter(
                or_(
                    VivinoWine.year <= filters.max_year,
                    SystembolagetProduct.year <= filters.max_year
                )
            )
        
        # Grape variety filter
        if filters.grape_variety:
            query = query.filter(VivinoWine.grape_varieties.ilike(f"%{filters.grape_variety}%"))
        
        # Food pairing filter
        if filters.food_pairing:
            query = query.filter(VivinoWine.simplified_food_pairings.ilike(f"%{filters.food_pairing}%"))
        
        # Organic/Natural filters
        if filters.is_organic is not None:
            query = query.filter(VivinoWine.is_organic == filters.is_organic)
        
        if filters.is_natural is not None:
            query = query.filter(VivinoWine.is_natural == filters.is_natural)
        
        # Match quality filters
        if filters.min_match_score is not None:
            query = query.filter(WineMatch.match_score >= filters.min_match_score)
        
        if filters.match_method:
            query = query.filter(WineMatch.match_method == filters.match_method)
        
        # Apply sorting
        if filters.sort_by == "rating":
            sort_col = VivinoWine.rating
        elif filters.sort_by == "price":
            sort_col = SystembolagetProduct.price
        elif filters.sort_by == "match_score":
            sort_col = WineMatch.match_score
        elif filters.sort_by == "alcohol_content":
            sort_col = VivinoWine.alcohol_content
        elif filters.sort_by == "year":
            sort_col = VivinoWine.year
        else:
            sort_col = VivinoWine.rating
        
        if filters.sort_order == "asc":
            query = query.order_by(asc(sort_col))
        else:
            query = query.order_by(desc(sort_col))
        
        # Apply pagination
        offset = (filters.page - 1) * filters.page_size
        results = query.offset(offset).limit(filters.page_size).all()
        
        # Convert to response format
        wines = []
        for match, vivino, sb in results:
            # Parse grape varieties if available
            grape_varieties = None
            if vivino.grape_varieties:
                try:
                    import json
                    grape_varieties = json.loads(vivino.grape_varieties)
                except:
                    grape_varieties = None
            
            # Parse simplified food pairings if available
            simplified_food_pairings = None
            if vivino.simplified_food_pairings:
                try:
                    import json
                    simplified_food_pairings = json.loads(vivino.simplified_food_pairings)
                except:
                    simplified_food_pairings = None
            
            wines.append(WineMatchResponse(
                match_id=match.id,
                match_score=float(match.match_score) if match.match_score else None,
                verified=match.verified,
                vivino_name=vivino.name,
                vivino_rating=float(vivino.rating),
                systembolaget_name=sb.full_name,
                price=float(sb.price) if sb.price else None,
                wine_style=sb.category_level2,
                country=sb.country,
                product_number=sb.product_number,
                alcohol_percentage=float(sb.alcohol_percentage) if sb.alcohol_percentage else None,
                year=sb.year,
                producer=sb.producer,
                image_url=vivino.image_url,
                # Enhanced wine data
                vivino_country=vivino.country,
                vivino_region=vivino.region,
                vivino_winery=vivino.winery,
                vivino_wine_style=vivino.wine_style,
                simplified_wine_style=vivino.simplified_wine_style,
                vivino_alcohol_content=float(vivino.alcohol_content) if vivino.alcohol_content else None,
                body=vivino.body,
                acidity=vivino.acidity,
                sweetness=vivino.sweetness,
                grape_varieties=grape_varieties,
                simplified_food_pairings=simplified_food_pairings,
                description=vivino.description
            ))
        
        return wines
    except Exception as e:
        logger.error(f"Error fetching wines: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch wines")

@app.get("/api/filters/options")
async def get_filter_options(db: Session = Depends(get_db)):
    """Get available filter options"""
    try:
        # Get unique wine styles (both Systembolaget and Vivino)
        wine_styles = (
            db.query(SystembolagetProduct.category_level2)
            .filter(SystembolagetProduct.category_level2.isnot(None))
            .distinct()
            .all()
        )
        
        vivino_wine_styles = (
            db.query(VivinoWine.wine_style)
            .filter(VivinoWine.wine_style.isnot(None))
            .distinct()
            .all()
        )
        
        # Get unique countries (prefer Vivino data)
        countries = (
            db.query(SystembolagetProduct.country)
            .filter(SystembolagetProduct.country.isnot(None))
            .distinct()
            .all()
        )
        
        vivino_countries = (
            db.query(VivinoWine.country)
            .filter(VivinoWine.country.isnot(None))
            .distinct()
            .all()
        )
        
        # Get unique regions
        regions = (
            db.query(VivinoWine.region)
            .filter(VivinoWine.region.isnot(None))
            .distinct()
            .limit(50)  # Limit to avoid too many options
            .all()
        )
        
        # Get unique wineries
        wineries = (
            db.query(VivinoWine.winery)
            .filter(VivinoWine.winery.isnot(None))
            .distinct()
            .limit(100)  # Limit to avoid too many options
            .all()
        )
        
        # Get price range
        price_stats = (
            db.query(
                func.min(SystembolagetProduct.price),
                func.max(SystembolagetProduct.price)
            )
            .filter(SystembolagetProduct.price.isnot(None))
            .first()
        )
        
        # Get rating range
        rating_stats = (
            db.query(
                func.min(VivinoWine.rating),
                func.max(VivinoWine.rating)
            )
            .first()
        )
        
        # Get additional filter data
        # Alcohol content range
        alcohol_stats = (
            db.query(
                func.min(VivinoWine.alcohol_content),
                func.max(VivinoWine.alcohol_content)
            )
            .filter(VivinoWine.alcohol_content.isnot(None))
            .first()
        )
        
        # Year range
        year_stats = (
            db.query(
                func.min(VivinoWine.year),
                func.max(VivinoWine.year)
            )
            .filter(VivinoWine.year.isnot(None))
            .first()
        )
        
        # Grape varieties (get top 50 most common)
        grape_varieties = (
            db.query(VivinoWine.grape_varieties)
            .filter(VivinoWine.grape_varieties.isnot(None))
            .filter(VivinoWine.grape_varieties != '[]')
            .limit(200)
            .all()
        )
        
        # Extract and count grape varieties
        all_grapes = set()
        for grape_json in grape_varieties:
            if grape_json[0]:
                try:
                    import json
                    grapes = json.loads(grape_json[0])
                    all_grapes.update(grapes)
                except:
                    pass
        
        # Food pairings from AI-generated simplified_food_pairings
        food_pairings = (
            db.query(VivinoWine.simplified_food_pairings)
            .filter(VivinoWine.simplified_food_pairings.isnot(None))
            .filter(VivinoWine.simplified_food_pairings != '[]')
            .limit(200)
            .all()
        )
        
        # Extract and count food pairings
        all_pairings = set()
        for pairing_json in food_pairings:
            if pairing_json[0]:
                try:
                    import json
                    pairings = json.loads(pairing_json[0])
                    if isinstance(pairings, list):
                        all_pairings.update([p.lower() for p in pairings])
                except:
                    pass
        
        # Food pairing emoji mapping
        pairing_emojis = {
            'beef': '🥩',
            'pork': '🥓',
            'lamb': '🐑',
            'game': '🦌',
            'poultry': '🐔',
            'chicken': '🐔',
            'duck': '🦆',
            'fish': '🐟',
            'shellfish': '🦐',
            'seafood': '🦐',
            'salmon': '🐟',
            'tuna': '🐟',
            'cheese': '🧀',
            'brie': '🧀',
            'cheddar': '🧀',
            'goat': '🐐',
            'blue': '🧀',
            'vegetables': '🥬',
            'salads': '🥗',
            'mushrooms': '🍄',
            'pasta': '🍝',
            'fruit': '🍎',
            'berries': '🫐',
            'citrus': '🍊',
            'tropical': '🥭',
            'chocolate': '🍫',
            'desserts': '🍰',
            'sweets': '🍬',
            'cake': '🎂',
            'bread': '🍞',
            'crackers': '🍪',
            'nuts': '🥜',
            'herbs': '🌿',
            'spices': '🌶️',
            'garlic': '🧄',
            'pepper': '🌶️',
            'rice': '🍚',
            'grains': '🌾',
            'appetizers': '🥂',
            'tapas': '🍤'
        }
        
        # Create pairing options with emojis
        pairing_options = []
        for pairing in sorted(all_pairings):
            emoji = pairing_emojis.get(pairing, '🍽️')
            pairing_options.append({
                'value': pairing,
                'label': f"{emoji} {pairing.title()}"
            })
        
        # Match score range
        match_score_stats = (
            db.query(
                func.min(WineMatch.match_score),
                func.max(WineMatch.match_score)
            )
            .filter(WineMatch.match_score.isnot(None))
            .first()
        )
        
        # Combine and sort options
        all_wine_styles = set([style[0] for style in wine_styles if style[0]]) | set([style[0] for style in vivino_wine_styles if style[0]])
        all_countries = set([country[0] for country in countries if country[0]]) | set([country[0] for country in vivino_countries if country[0]])
        
        return {
            # Basic options
            "wine_styles": sorted(list(all_wine_styles)),
            "vivino_wine_styles": sorted([style[0] for style in vivino_wine_styles if style[0]]),
            "countries": sorted(list(all_countries)),
            "vivino_countries": sorted([country[0] for country in vivino_countries if country[0]]),
            "regions": sorted([region[0] for region in regions if region[0]]),
            "wineries": sorted([winery[0] for winery in wineries if winery[0]]),
            
            # Grape varieties (top 30 most common)
            "grape_varieties": sorted(list(all_grapes))[:30],
            
            # Food pairings (AI-generated with emojis)
            "food_pairings": pairing_options,
            
            # Ranges
            "price_range": {
                "min": float(price_stats[0]) if price_stats[0] else 0,
                "max": float(price_stats[1]) if price_stats[1] else 1000
            },
            "rating_range": {
                "min": float(rating_stats[0]) if rating_stats[0] else 0,
                "max": float(rating_stats[1]) if rating_stats[1] else 5
            },
            "alcohol_range": {
                "min": float(alcohol_stats[0]) if alcohol_stats[0] else 0,
                "max": float(alcohol_stats[1]) if alcohol_stats[1] else 15
            },
            "year_range": {
                "min": int(year_stats[0]) if year_stats[0] else 2000,
                "max": int(year_stats[1]) if year_stats[1] else 2024
            },
            "match_score_range": {
                "min": float(match_score_stats[0]) if match_score_stats[0] else 0,
                "max": float(match_score_stats[1]) if match_score_stats[1] else 100
            },
            
            # Characteristic options
            "body_options": [
                {"value": 1, "label": "Light"},
                {"value": 2, "label": "Light-Medium"},
                {"value": 3, "label": "Medium"},
                {"value": 4, "label": "Medium-Full"},
                {"value": 5, "label": "Full"}
            ],
            "acidity_options": [
                {"value": 1, "label": "Low"},
                {"value": 2, "label": "Low-Medium"},
                {"value": 3, "label": "Medium"},
                {"value": 4, "label": "Medium-High"},
                {"value": 5, "label": "High"}
            ],
            "sweetness_options": [
                {"value": 1, "label": "Bone Dry"},
                {"value": 2, "label": "Dry"},
                {"value": 3, "label": "Off-Dry"},
                {"value": 4, "label": "Medium Sweet"},
                {"value": 5, "label": "Sweet"}
            ],
            
            # Boolean options
            "organic_options": [
                {"value": True, "label": "Organic Only"},
                {"value": False, "label": "Include Non-Organic"}
            ],
            "natural_options": [
                {"value": True, "label": "Natural Only"},
                {"value": False, "label": "Include Conventional"}
            ],
            
            # Match method options
            "match_method_options": [
                {"value": "ai", "label": "AI Matched"},
                {"value": "fallback", "label": "String Matched"}
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching filter options: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch filter options")

@app.get("/filters", response_class=HTMLResponse)
async def filters_page(request: Request, db: Session = Depends(get_db)):
    """Dedicated filters page"""
    try:
        # Get comprehensive filter options
        filter_options = await get_filter_options(db)
        
        return templates.TemplateResponse("filters.html", {
            "request": request,
            "filter_options": filter_options
        })
    except Exception as e:
        logger.error(f"Error loading filters page: {e}")
        raise HTTPException(status_code=500, detail="Failed to load filters page")

@app.get("/toplists", response_class=HTMLResponse)
async def toplists_index(request: Request, category: Optional[str] = None, db: Session = Depends(get_db)):
    """Toplists index page with optional category filtering"""
    try:
        # Base query for toplists with statistics
        query = (
            db.query(
                Toplist,
                func.count(ToplistWine.id).label('wine_count'),
                func.count(WineMatch.id).label('match_count'),
                func.avg(VivinoWine.rating).label('avg_rating')
            )
            .outerjoin(ToplistWine, Toplist.id == ToplistWine.toplist_id)
            .outerjoin(VivinoWine, ToplistWine.vivino_wine_id == VivinoWine.id)
            .outerjoin(WineMatch, VivinoWine.id == WineMatch.vivino_wine_id)
        )
        
        # Apply category filter if provided
        if category:
            query = query.filter(Toplist.category == category)
            
        toplists = (
            query
            .group_by(Toplist.id)
            .order_by(Toplist.name)
            .all()
        )
        
        # Convert to response format
        toplist_data = []
        for toplist, wine_count, match_count, avg_rating in toplists:
            toplist_data.append({
                'id': toplist.id,
                'name': toplist.name,
                'category': toplist.category,
                'description': toplist.description,
                'wine_count': wine_count or 0,
                'match_count': match_count or 0,
                'avg_rating': round(float(avg_rating), 1) if avg_rating else None
            })
        
        # Get all toplists for category filtering (regardless of current filter)
        all_toplists = db.query(Toplist).all()
        
        return templates.TemplateResponse("toplists.html", {
            "request": request,
            "toplists": toplist_data,
            "all_toplists": all_toplists,  # For category filtering
            "total_toplists": len(toplist_data),
            "current_category": category,
            "showing_all": category is None
        })
    except Exception as e:
        logger.error(f"Error loading toplists: {e}")
        raise HTTPException(status_code=500, detail="Failed to load toplists")

@app.get("/toplist/{toplist_id}", response_class=HTMLResponse)
async def toplist_detail(request: Request, toplist_id: int, db: Session = Depends(get_db)):
    """Toplist detail page"""
    try:
        # Get toplist information
        toplist = db.query(Toplist).filter(Toplist.id == toplist_id).first()
        if not toplist:
            raise HTTPException(status_code=404, detail="Toplist not found")
        
        # Get wines in this toplist with their matches
        results = (
            db.query(WineMatch, VivinoWine, SystembolagetProduct)
            .join(VivinoWine, WineMatch.vivino_wine_id == VivinoWine.id)
            .join(SystembolagetProduct, WineMatch.systembolaget_product_id == SystembolagetProduct.id)
            .join(ToplistWine, VivinoWine.id == ToplistWine.vivino_wine_id)
            .filter(ToplistWine.toplist_id == toplist_id)
            .order_by(desc(VivinoWine.rating))
            .all()
        )
        
        # Convert to response format
        wines = []
        for match, vivino, sb in results:
            # Parse grape varieties if available
            grape_varieties = None
            if vivino.grape_varieties:
                try:
                    import json
                    grape_varieties = json.loads(vivino.grape_varieties)
                except:
                    grape_varieties = None
            
            # Parse simplified food pairings if available
            simplified_food_pairings = None
            if vivino.simplified_food_pairings:
                try:
                    import json
                    simplified_food_pairings = json.loads(vivino.simplified_food_pairings)
                except:
                    simplified_food_pairings = None
            
            wines.append(WineMatchResponse(
                match_id=match.id,
                match_score=float(match.match_score) if match.match_score else None,
                verified=match.verified,
                vivino_name=vivino.name,
                vivino_rating=float(vivino.rating),
                systembolaget_name=sb.full_name,
                price=float(sb.price) if sb.price else None,
                wine_style=sb.category_level2,
                country=sb.country,
                product_number=sb.product_number,
                alcohol_percentage=float(sb.alcohol_percentage) if sb.alcohol_percentage else None,
                year=sb.year,
                producer=sb.producer,
                image_url=vivino.image_url,
                # Enhanced wine data
                vivino_country=vivino.country,
                vivino_region=vivino.region,
                vivino_winery=vivino.winery,
                vivino_wine_style=vivino.wine_style,
                simplified_wine_style=vivino.simplified_wine_style,
                vivino_alcohol_content=float(vivino.alcohol_content) if vivino.alcohol_content else None,
                body=vivino.body,
                acidity=vivino.acidity,
                sweetness=vivino.sweetness,
                grape_varieties=grape_varieties,
                simplified_food_pairings=simplified_food_pairings,
                description=vivino.description
            ))
        
        # Calculate toplist statistics
        avg_rating = sum(wine.vivino_rating for wine in wines) / len(wines) if wines else 0
        avg_price = sum(wine.price for wine in wines if wine.price) / len([w for w in wines if w.price]) if wines else 0
        
        return templates.TemplateResponse("toplist.html", {
            "request": request,
            "toplist": toplist,
            "wines": wines,
            "wine_count": len(wines),
            "avg_rating": round(avg_rating, 1),
            "avg_price": round(avg_price, 0) if avg_price else None
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading toplist {toplist_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load toplist")

@app.get("/wine/{wine_id}", response_class=HTMLResponse)
async def wine_detail(request: Request, wine_id: int, db: Session = Depends(get_db)):
    """Wine detail page"""
    try:
        result = (
            db.query(WineMatch, VivinoWine, SystembolagetProduct)
            .join(VivinoWine, WineMatch.vivino_wine_id == VivinoWine.id)
            .join(SystembolagetProduct, WineMatch.systembolaget_product_id == SystembolagetProduct.id)
            .filter(WineMatch.id == wine_id)
            .first()
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Wine not found")
        
        match, vivino, sb = result
        
        # Parse grape varieties if available
        grape_varieties = None
        if vivino.grape_varieties:
            try:
                import json
                grape_varieties = json.loads(vivino.grape_varieties)
            except:
                grape_varieties = None
        
        # Parse simplified food pairings if available
        simplified_food_pairings = None
        if vivino.simplified_food_pairings:
            try:
                import json
                simplified_food_pairings = json.loads(vivino.simplified_food_pairings)
            except:
                simplified_food_pairings = None
        
        wine = WineMatchResponse(
            match_id=match.id,
            match_score=float(match.match_score) if match.match_score else None,
            verified=match.verified,
            vivino_name=vivino.name,
            vivino_rating=float(vivino.rating),
            systembolaget_name=sb.full_name,
            price=float(sb.price) if sb.price else None,
            wine_style=sb.category_level2,
            country=sb.country,
            product_number=sb.product_number,
            alcohol_percentage=float(sb.alcohol_percentage) if sb.alcohol_percentage else None,
            year=sb.year,
            producer=sb.producer,
            image_url=vivino.image_url,
            # Enhanced wine data
            vivino_country=vivino.country,
            vivino_region=vivino.region,
            vivino_winery=vivino.winery,
            vivino_wine_style=vivino.wine_style,
            simplified_wine_style=vivino.simplified_wine_style,
            vivino_alcohol_content=float(vivino.alcohol_content) if vivino.alcohol_content else None,
            body=vivino.body,
            acidity=vivino.acidity,
            sweetness=vivino.sweetness,
            grape_varieties=grape_varieties,
            simplified_food_pairings=simplified_food_pairings,
            description=vivino.description
        )
        
        return templates.TemplateResponse("wine_detail.html", {
            "request": request,
            "wine": wine
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading wine detail: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        db_healthy = check_database_connection()
        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "database": "connected" if db_healthy else "disconnected"
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.get("/api/wines/{wine_id}/similar", response_model=List[WineMatchResponse])
async def get_similar_wines(wine_id: int, db: Session = Depends(get_db)):
    """Get wines similar to the specified wine based on style, acidity, and sweetness"""
    try:
        # Get the reference wine
        result = (
            db.query(WineMatch, VivinoWine, SystembolagetProduct)
            .join(VivinoWine, WineMatch.vivino_wine_id == VivinoWine.id)
            .join(SystembolagetProduct, WineMatch.systembolaget_product_id == SystembolagetProduct.id)
            .filter(WineMatch.id == wine_id)
            .first()
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Wine not found")
        
        reference_match, reference_vivino, reference_sb = result
        
        # Build similarity query
        query = (
            db.query(WineMatch, VivinoWine, SystembolagetProduct)
            .join(VivinoWine, WineMatch.vivino_wine_id == VivinoWine.id)
            .join(SystembolagetProduct, WineMatch.systembolaget_product_id == SystembolagetProduct.id)
            .filter(WineMatch.id != wine_id)  # Exclude the reference wine itself
        )
        
        # Filter by simplified wine style (exact match)
        if reference_vivino.simplified_wine_style:
            query = query.filter(VivinoWine.simplified_wine_style == reference_vivino.simplified_wine_style)
        
        # Filter by similar acidity (±1 level)
        if reference_vivino.acidity:
            query = query.filter(
                VivinoWine.acidity.between(
                    max(1, reference_vivino.acidity - 1),
                    min(5, reference_vivino.acidity + 1)
                )
            )
        
        # Filter by similar sweetness (±1 level)
        if reference_vivino.sweetness:
            query = query.filter(
                VivinoWine.sweetness.between(
                    max(1, reference_vivino.sweetness - 1),
                    min(5, reference_vivino.sweetness + 1)
                )
            )
        
        # Order by rating and limit results
        results = (
            query.order_by(desc(VivinoWine.rating))
            .limit(6)
            .all()
        )
        
        # Convert to response format
        similar_wines = []
        for match, vivino, sb in results:
            # Parse grape varieties if available
            grape_varieties = None
            if vivino.grape_varieties:
                try:
                    import json
                    grape_varieties = json.loads(vivino.grape_varieties)
                except:
                    grape_varieties = None
            
            # Parse simplified food pairings if available
            simplified_food_pairings = None
            if vivino.simplified_food_pairings:
                try:
                    import json
                    simplified_food_pairings = json.loads(vivino.simplified_food_pairings)
                except:
                    simplified_food_pairings = None
            
            similar_wines.append(WineMatchResponse(
                match_id=match.id,
                match_score=float(match.match_score) if match.match_score else None,
                verified=match.verified,
                vivino_name=vivino.name,
                vivino_rating=float(vivino.rating),
                systembolaget_name=sb.full_name,
                price=float(sb.price) if sb.price else None,
                wine_style=sb.category_level2,
                country=sb.country,
                product_number=sb.product_number,
                alcohol_percentage=float(sb.alcohol_percentage) if sb.alcohol_percentage else None,
                year=sb.year,
                producer=sb.producer,
                image_url=vivino.image_url,
                # Enhanced wine data
                vivino_country=vivino.country,
                vivino_region=vivino.region,
                vivino_winery=vivino.winery,
                vivino_wine_style=vivino.wine_style,
                simplified_wine_style=vivino.simplified_wine_style,
                vivino_alcohol_content=float(vivino.alcohol_content) if vivino.alcohol_content else None,
                body=vivino.body,
                acidity=vivino.acidity,
                sweetness=vivino.sweetness,
                grape_varieties=grape_varieties,
                simplified_food_pairings=simplified_food_pairings,
                description=vivino.description
            ))
        
        return similar_wines
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar wines for wine {wine_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to find similar wines")

# Admin routes
@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin login page"""
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.post("/admin/login")
async def admin_login(request: Request, username: str = Depends(verify_credentials)):
    """Handle admin login"""
    # Create access token
    access_token_expires = timedelta(minutes=480)  # 8 hours
    access_token = create_access_token(
        data={"sub": username}, expires_delta=access_token_expires
    )
    
    # Create response with redirect
    response = RedirectResponse(url="/admin/toplists", status_code=303)
    response.set_cookie(
        key="admin_token", 
        value=access_token, 
        max_age=480*60,  # 8 hours in seconds
        httponly=True,
        secure=False  # Set to True in production with HTTPS
    )
    return response

@app.get("/admin/logout")
async def admin_logout():
    """Handle admin logout"""
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(key="admin_token")
    return response

@app.get("/admin/toplists", response_class=HTMLResponse)
async def admin_toplists(request: Request, db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    """Admin toplists management page"""
    try:
        # Get all toplists
        toplists = db.query(Toplist).order_by(Toplist.created_at.desc()).all()
        
        return templates.TemplateResponse("admin_toplists.html", {
            "request": request,
            "toplists": toplists,
            "admin_user": admin
        })
        
    except Exception as e:
        logger.error(f"Error loading admin toplists: {e}")
        raise HTTPException(status_code=500, detail="Failed to load admin page")

@app.post("/admin/toplists/add")
async def admin_add_toplist(
    request: Request,
    name: str = Form(...),
    url: str = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Add new toplist via admin interface"""
    try:
        # Check if URL already exists
        existing = db.query(Toplist).filter(Toplist.url == url).first()
        if existing:
            raise HTTPException(status_code=400, detail="Toplist with this URL already exists")
        
        # Create new toplist
        new_toplist = Toplist(
            name=name,
            url=url,
            category=category,
            description=description
        )
        db.add(new_toplist)
        db.commit()
        
        logger.info(f"Admin {admin} added new toplist: {name}")
        return RedirectResponse(url="/admin/toplists", status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding toplist: {e}")
        raise HTTPException(status_code=500, detail="Failed to add toplist")

@app.post("/admin/toplists/{toplist_id}/delete")
async def admin_delete_toplist(
    toplist_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Delete toplist via admin interface"""
    try:
        toplist = db.query(Toplist).filter(Toplist.id == toplist_id).first()
        if not toplist:
            raise HTTPException(status_code=404, detail="Toplist not found")
        
        toplist_name = toplist.name
        
        # Delete related update log entries first (foreign key constraint issue)
        update_logs = db.query(UpdateLog).filter(UpdateLog.toplist_id == toplist_id).all()
        for update_log in update_logs:
            db.delete(update_log)
        
        # Now delete the toplist (ToplistWine entries should cascade automatically)
        db.delete(toplist)
        db.commit()
        
        logger.info(f"Admin {admin} deleted toplist: {toplist_name} (and {len(update_logs)} related update log entries)")
        return RedirectResponse(url="/admin/toplists", status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting toplist: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete toplist")

@app.post("/admin/toplists/{toplist_id}/edit")
async def admin_edit_toplist(
    toplist_id: int,
    name: str = Form(...),
    url: str = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Edit toplist via admin interface"""
    try:
        toplist = db.query(Toplist).filter(Toplist.id == toplist_id).first()
        if not toplist:
            raise HTTPException(status_code=404, detail="Toplist not found")
        
        # Check if URL already exists for another toplist
        existing = db.query(Toplist).filter(Toplist.url == url, Toplist.id != toplist_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Another toplist with this URL already exists")
        
        # Update toplist
        toplist.name = name
        toplist.url = url
        toplist.category = category
        toplist.description = description
        db.commit()
        
        logger.info(f"Admin {admin} edited toplist: {name}")
        return RedirectResponse(url="/admin/toplists", status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error editing toplist: {e}")
        raise HTTPException(status_code=500, detail="Failed to edit toplist")

@app.post("/admin/sync/all")
async def admin_sync_all(
    admin: str = Depends(get_current_admin)
):
    """Sync all toplists via admin interface"""
    try:
        # Import here to avoid circular imports
        from data_pipeline import DataPipeline
        
        logger.info(f"Admin {admin} initiated sync for all toplists")
        
        # Create separate session for DataPipeline to avoid transaction conflicts
        async with DataPipeline() as pipeline:
            results = await pipeline.sync_all_toplists()
        
        logger.info(f"Sync completed: {results['successful']} successful, {results['failed']} failed")
        return RedirectResponse(url="/admin/toplists", status_code=303)
        
    except Exception as e:
        logger.error(f"Error syncing all toplists: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync toplists")

@app.post("/admin/sync/{toplist_id}")
async def admin_sync_toplist(
    toplist_id: int,
    admin: str = Depends(get_current_admin)
):
    """Sync specific toplist via admin interface"""
    try:
        # First validate toplist exists using a separate session
        from database import SessionLocal
        toplist_name = None
        with SessionLocal() as db:
            toplist = db.query(Toplist).filter(Toplist.id == toplist_id).first()
            if not toplist:
                raise HTTPException(status_code=404, detail="Toplist not found")
            toplist_name = toplist.name
        
        # Import here to avoid circular imports
        from data_pipeline import DataPipeline
        
        logger.info(f"Admin {admin} initiated sync for toplist: {toplist_name}")
        
        # Create separate session for DataPipeline to avoid transaction conflicts
        async with DataPipeline() as pipeline:
            success = await pipeline.sync_toplist(toplist_id)
        
        if success:
            logger.info(f"Successfully synced toplist: {toplist_name}")
        else:
            logger.error(f"Failed to sync toplist: {toplist_name}")
            
        return RedirectResponse(url="/admin/toplists", status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing toplist {toplist_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync toplist")

@app.get("/admin/sync/status")
async def admin_sync_status(
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Get sync status via admin interface"""
    try:
        from data_pipeline import DataPipeline
        
        async with DataPipeline() as pipeline:
            status = pipeline.get_sync_status()
        
        return {"status": status}
        
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get sync status")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)