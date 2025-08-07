"""
Database models for Best Wines Sweden application
"""

from sqlalchemy import Column, Integer, String, Text, DECIMAL, TIMESTAMP, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

Base = declarative_base()

class Toplist(Base):
    __tablename__ = "toplists"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False, unique=True)
    description = Column(Text)
    category = Column(String(100))
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    # Relationships
    toplist_wines = relationship("ToplistWine", back_populates="toplist")

class VivinoWine(Base):
    __tablename__ = "vivino_wines"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    rating = Column(DECIMAL(3,2), nullable=False)
    vintage_id = Column(String(50))
    wine_url = Column(String(500))
    image_url = Column(String(500))  # URL to wine bottle image from Vivino
    image_cached_at = Column(TIMESTAMP)  # When image was last fetched
    
    # Enhanced wine data from Vivino API
    country = Column(String(100))  # e.g., "New Zealand"
    country_code = Column(String(3))  # e.g., "nz"
    region = Column(String(200))  # e.g., "Marlborough"
    winery = Column(String(255))  # e.g., "Saint Clair Family Estate"
    wine_style = Column(String(255))  # e.g., "Nya Zeeland Sauvignon Blanc"
    simplified_wine_style = Column(String(50))  # AI-simplified style: "Red Wine", "White Wine", etc.
    wine_type_id = Column(Integer)  # e.g., 2 for white wine
    year = Column(Integer)  # Vintage year
    alcohol_content = Column(DECIMAL(4,2))  # Alcohol percentage
    body = Column(Integer)  # Body rating (1-5)
    acidity = Column(Integer)  # Acidity rating (1-5) 
    sweetness = Column(Integer)  # Sweetness rating (1-5)
    grape_varieties = Column(Text)  # JSON string of grape varieties
    food_pairings = Column(Text)  # JSON string of food pairings  
    simplified_food_pairings = Column(Text)  # AI-simplified pairing labels as JSON: ["fish", "poultry", "cheese"]
    description = Column(Text)  # Wine description
    closure_type = Column(String(50))  # e.g., "screw", "cork"
    is_organic = Column(Boolean, default=False)
    is_natural = Column(Boolean, default=False)
    
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    # Relationships
    toplist_wines = relationship("ToplistWine", back_populates="vivino_wine")
    wine_matches = relationship("WineMatch", back_populates="vivino_wine")

class SystembolagetProduct(Base):
    __tablename__ = "systembolaget_products"
    
    id = Column(Integer, primary_key=True)
    product_number = Column(String(50), unique=True, nullable=False)
    name_bold = Column(String(255))
    name_thin = Column(String(255))
    price = Column(DECIMAL(8,2))
    volume = Column(Integer)  # in ml
    category_level1 = Column(String(100))
    category_level2 = Column(String(100))
    country = Column(String(100))
    alcohol_percentage = Column(DECIMAL(4,2))
    producer = Column(String(255))
    year = Column(Integer)
    stock_status = Column(String(50))
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    # Relationships
    wine_matches = relationship("WineMatch", back_populates="systembolaget_product")
    
    @property
    def full_name(self):
        return f"{self.name_bold or ''} {self.name_thin or ''}".strip()

class ToplistWine(Base):
    __tablename__ = "toplist_wines"
    
    id = Column(Integer, primary_key=True)
    toplist_id = Column(Integer, ForeignKey("toplists.id", ondelete="CASCADE"))
    vivino_wine_id = Column(Integer, ForeignKey("vivino_wines.id", ondelete="CASCADE"))
    position = Column(Integer)
    created_at = Column(TIMESTAMP, default=func.now())
    
    # Relationships
    toplist = relationship("Toplist", back_populates="toplist_wines")
    vivino_wine = relationship("VivinoWine", back_populates="toplist_wines")

class WineMatch(Base):
    __tablename__ = "wine_matches"
    
    id = Column(Integer, primary_key=True)
    vivino_wine_id = Column(Integer, ForeignKey("vivino_wines.id", ondelete="CASCADE"))
    systembolaget_product_id = Column(Integer, ForeignKey("systembolaget_products.id", ondelete="CASCADE"))
    match_score = Column(DECIMAL(5,2))
    match_type = Column(String(50))
    verified = Column(Boolean, default=False)
    ai_reasoning = Column(Text)  # Store AI reasoning for matches
    match_method = Column(String(20), default="ai")  # "ai" or "fallback"
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    # Relationships
    vivino_wine = relationship("VivinoWine", back_populates="wine_matches")
    systembolaget_product = relationship("SystembolagetProduct", back_populates="wine_matches")

class UserFavorite(Base):
    __tablename__ = "user_favorites"
    
    id = Column(Integer, primary_key=True)
    user_session = Column(String(255))
    wine_match_id = Column(Integer, ForeignKey("wine_matches.id", ondelete="CASCADE"))
    created_at = Column(TIMESTAMP, default=func.now())

class UpdateLog(Base):
    __tablename__ = "update_log"
    
    id = Column(Integer, primary_key=True)
    toplist_id = Column(Integer, ForeignKey("toplists.id"))
    status = Column(String(50))
    wines_found = Column(Integer)
    matches_found = Column(Integer)
    error_message = Column(Text)
    started_at = Column(TIMESTAMP, default=func.now())
    completed_at = Column(TIMESTAMP)

# Pydantic models for API
class ToplistResponse(BaseModel):
    id: int
    name: str
    category: Optional[str]
    wine_count: int
    match_count: int
    avg_rating: Optional[float]
    updated_at: datetime
    
    class Config:
        from_attributes = True

class WineMatchResponse(BaseModel):
    match_id: int
    match_score: Optional[float]
    verified: bool
    vivino_name: str
    vivino_rating: float
    systembolaget_name: str
    price: Optional[float]
    wine_style: Optional[str]
    country: Optional[str]
    product_number: str
    alcohol_percentage: Optional[float]
    year: Optional[int]
    producer: Optional[str]
    image_url: Optional[str]
    
    # Enhanced wine data
    vivino_country: Optional[str]
    vivino_region: Optional[str]
    vivino_winery: Optional[str]
    vivino_wine_style: Optional[str]
    simplified_wine_style: Optional[str] = None  # AI-simplified style category
    vivino_alcohol_content: Optional[float]
    body: Optional[int]
    acidity: Optional[int]
    sweetness: Optional[int] = None
    grape_varieties: Optional[List[str]]
    simplified_food_pairings: Optional[List[str]] = None  # AI-simplified pairing labels
    description: Optional[str]
    
    class Config:
        from_attributes = True

class WineFilters(BaseModel):
    # Price and rating filters
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_rating: Optional[float] = None
    max_rating: Optional[float] = None
    
    # Basic wine info
    wine_style: Optional[str] = None
    country: Optional[str] = None
    search_term: Optional[str] = None
    toplist_id: Optional[int] = None
    verified_only: bool = False
    
    # Enhanced Vivino filters
    vivino_country: Optional[str] = None
    vivino_region: Optional[str] = None
    vivino_winery: Optional[str] = None
    vivino_wine_style: Optional[str] = None
    simplified_wine_style: Optional[str] = None  # AI-simplified wine style filter
    
    # Wine characteristics
    min_alcohol: Optional[float] = None
    max_alcohol: Optional[float] = None
    body: Optional[int] = None  # 1-5 scale
    acidity: Optional[int] = None  # 1-5 scale
    sweetness: Optional[int] = None  # 1-5 scale
    
    # Year filters
    min_year: Optional[int] = None
    max_year: Optional[int] = None
    
    # Wine type filters
    grape_variety: Optional[str] = None
    food_pairing: Optional[str] = None  # AI-generated pairing filter
    is_organic: Optional[bool] = None
    is_natural: Optional[bool] = None
    
    # Match quality filters
    min_match_score: Optional[float] = None
    match_method: Optional[str] = None  # "ai" or "fallback"
    
    # Sorting and pagination
    sort_by: str = "rating"  # rating, price, match_score, alcohol_content, year
    sort_order: str = "desc"  # asc, desc
    page: int = 1
    page_size: int = 20