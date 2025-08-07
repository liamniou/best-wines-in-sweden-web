"""
Database migration script to add image columns to vivino_wines table
"""

import logging
from sqlalchemy import text
from database import SessionLocal

logger = logging.getLogger(__name__)

def migrate_vivino_wine_images():
    """Add image columns to vivino_wines table"""
    
    with SessionLocal() as db:
        try:
            # Check if columns already exist
            result = db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'vivino_wines' 
                AND column_name IN ('image_url', 'image_cached_at')
            """))
            
            existing_columns = [row[0] for row in result.fetchall()]
            
            if 'image_url' not in existing_columns:
                logger.info("Adding image_url column to vivino_wines table...")
                db.execute(text("ALTER TABLE vivino_wines ADD COLUMN image_url VARCHAR(500)"))
                
            if 'image_cached_at' not in existing_columns:
                logger.info("Adding image_cached_at column to vivino_wines table...")
                db.execute(text("ALTER TABLE vivino_wines ADD COLUMN image_cached_at TIMESTAMP"))
            
            db.commit()
            logger.info("Image columns migration completed successfully!")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Migration failed: {e}")
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting image columns migration...")
    
    migrate_vivino_wine_images()
    
    logger.info("Migration completed!")