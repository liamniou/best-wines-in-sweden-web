"""
Database configuration and connection management
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from models import Base
import logging

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://user:password@localhost:5432/best_wines"
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    poolclass=StaticPool,
    pool_pre_ping=True,
    echo=bool(os.getenv("SQL_ECHO", False))
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Create all tables if they don't exist"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

def get_db() -> Session:
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_database():
    """Initialize database with default toplists"""
    from models import Toplist
    
    db = SessionLocal()
    try:
        # Check if we already have toplists
        existing_count = db.query(Toplist).count()
        if existing_count > 0:
            logger.info(f"Database already initialized with {existing_count} toplists")
            return
        
        # Default toplists from your compose.yaml
        default_toplists = [
            {
                "name": "Best Wines Under 100 SEK",
                "url": "https://www.vivino.com/toplists/best-wines-under-100-kr-right-now-sweden",
                "category": "budget",
                "description": "Top-rated wines under 100 SEK available in Sweden"
            },
            {
                "name": "Best Wines 100-200 SEK", 
                "url": "https://www.vivino.com/toplists/best-wines-between-100-kr-and-200-kr-right-now-sweden",
                "category": "mid-range",
                "description": "Premium wines between 100-200 SEK"
            },
            {
                "name": "Best Wines 200-400 SEK",
                "url": "https://www.vivino.com/toplists/best-wines-between-200-kr-and-400-kr-right-now-sweden", 
                "category": "premium",
                "description": "High-end wines between 200-400 SEK"
            },
            {
                "name": "Wines Worth Their Cost",
                "url": "https://www.vivino.com/toplists/top-10-wines-actually-worth-what-they-cost",
                "category": "value",
                "description": "Wines that offer exceptional value for money"
            },
            {
                "name": "Best Wines for Fish",
                "url": "https://www.vivino.com/toplists/top-10-wines-pair-fish",
                "category": "pairing",
                "description": "Perfect wines to pair with fish dishes"
            },
            {
                "name": "Beaujolais Nouveau",
                "url": "https://www.vivino.com/toplists/popular_2014_beaujolais_nouveau_wines",
                "category": "style",
                "description": "Popular Beaujolais Nouveau wines"
            },
            {
                "name": "Oregon Pinot Noir",
                "url": "https://www.vivino.com/toplists/10_oregon_pinots_to_try",
                "category": "regional",
                "description": "Must-try Pinot Noir wines from Oregon"
            },
            {
                "name": "Portuguese Reds Under 30",
                "url": "https://www.vivino.com/toplists/10_great_portugal_reds_under_30",
                "category": "regional",
                "description": "Great Portuguese red wines under $30"
            },
            {
                "name": "Hidden Portuguese Gems",
                "url": "https://www.vivino.com/toplists/hidden_portugiese_gems",
                "category": "discovery",
                "description": "Undiscovered Portuguese wine treasures"
            },
            {
                "name": "Top South African Wines",
                "url": "https://www.vivino.com/toplists/my-top-10-south-african-wines",
                "category": "regional", 
                "description": "Best wines from South Africa"
            },
            {
                "name": "Adventure & Discovery",
                "url": "https://www.vivino.com/toplists/adventure-discovery-wine-world-today",
                "category": "discovery",
                "description": "Adventurous wines for exploration"
            },
            {
                "name": "White Wines for Red Wine Drinkers",
                "url": "https://www.vivino.com/toplists/white-wines-red-wine-drinker",
                "category": "style",
                "description": "White wines that red wine lovers will enjoy"
            }
        ]
        
        for toplist_data in default_toplists:
            toplist = Toplist(**toplist_data)
            db.add(toplist)
        
        db.commit()
        logger.info(f"Initialized database with {len(default_toplists)} toplists")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        db.close()

def check_database_connection():
    """Check if database connection is working"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False