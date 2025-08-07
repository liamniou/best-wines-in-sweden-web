"""
Database migration script to add AI reasoning columns to wine_matches table
"""

import logging
from sqlalchemy import text
from database import SessionLocal, engine

logger = logging.getLogger(__name__)

def migrate_wine_matches_table():
    """Add new AI-related columns to wine_matches table"""
    
    with SessionLocal() as db:
        try:
            # Check if columns already exist
            result = db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'wine_matches' 
                AND column_name IN ('ai_reasoning', 'match_method')
            """))
            
            existing_columns = [row[0] for row in result.fetchall()]
            
            if 'ai_reasoning' not in existing_columns:
                logger.info("Adding ai_reasoning column to wine_matches table...")
                db.execute(text("ALTER TABLE wine_matches ADD COLUMN ai_reasoning TEXT"))
                
            if 'match_method' not in existing_columns:
                logger.info("Adding match_method column to wine_matches table...")
                db.execute(text("ALTER TABLE wine_matches ADD COLUMN match_method VARCHAR(20) DEFAULT 'fallback'"))
            
            # Update existing records to have fallback method
            db.execute(text("""
                UPDATE wine_matches 
                SET match_method = 'fallback' 
                WHERE match_method IS NULL
            """))
            
            db.commit()
            logger.info("Migration completed successfully!")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Migration failed: {e}")
            raise

def recreate_wine_matches_view():
    """Recreate the wine_matches_with_details view with new columns"""
    
    with SessionLocal() as db:
        try:
            # Drop existing view
            db.execute(text("DROP VIEW IF EXISTS wine_matches_with_details"))
            
            # Recreate view with new columns
            db.execute(text("""
                CREATE VIEW wine_matches_with_details AS
                SELECT 
                    wm.id as match_id,
                    wm.match_score,
                    wm.match_type,
                    wm.verified,
                    wm.ai_reasoning,
                    wm.match_method,
                    vw.name as vivino_name,
                    vw.rating as vivino_rating,
                    CONCAT(sp.name_bold, ' ', sp.name_thin) as systembolaget_name,
                    sp.price,
                    sp.category_level2 as wine_style,
                    sp.country,
                    sp.product_number,
                    sp.alcohol_percentage,
                    sp.year,
                    sp.producer,
                    wm.created_at as match_created_at
                FROM wine_matches wm
                JOIN vivino_wines vw ON wm.vivino_wine_id = vw.id
                JOIN systembolaget_products sp ON wm.systembolaget_product_id = sp.id
            """))
            
            db.commit()
            logger.info("View recreated successfully!")
            
        except Exception as e:
            db.rollback()
            logger.error(f"View recreation failed: {e}")
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting AI columns migration...")
    
    migrate_wine_matches_table()
    recreate_wine_matches_view()
    
    logger.info("Migration completed!")