"""
Database migration script to add missing columns to vivino_wines table
"""

import logging
from sqlalchemy import text
from database import SessionLocal, engine

logger = logging.getLogger(__name__)

def migrate_vivino_wines_table():
    """Add missing columns to vivino_wines table to match the model"""
    
    with SessionLocal() as db:
        try:
            # Check which columns already exist
            result = db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'vivino_wines'
            """))
            
            existing_columns = [row[0] for row in result.fetchall()]
            logger.info(f"Existing columns: {existing_columns}")
            
            # Define all columns that should exist based on our model
            required_columns = {
                'image_url': 'VARCHAR(500)',
                'image_cached_at': 'TIMESTAMP',
                'country': 'VARCHAR(100)',
                'country_code': 'VARCHAR(5)',
                'region': 'VARCHAR(255)',
                'winery': 'VARCHAR(255)',
                'wine_style': 'VARCHAR(100)',
                'simplified_wine_style': 'VARCHAR(50)',
                'wine_type_id': 'INTEGER',
                'year': 'INTEGER',
                'alcohol_content': 'DECIMAL(4,2)',
                'body': 'INTEGER',
                'acidity': 'INTEGER',
                'sweetness': 'INTEGER',
                'grape_varieties': 'TEXT',
                'food_pairings': 'TEXT',
                'simplified_food_pairings': 'TEXT',
                'description': 'TEXT',
                'closure_type': 'VARCHAR(50)',
                'is_organic': 'BOOLEAN DEFAULT FALSE',
                'is_natural': 'BOOLEAN DEFAULT FALSE'
            }
            
            # Add missing columns
            for column_name, column_type in required_columns.items():
                if column_name not in existing_columns:
                    logger.info(f"Adding {column_name} column to vivino_wines table...")
                    db.execute(text(f"ALTER TABLE vivino_wines ADD COLUMN {column_name} {column_type}"))
            
            db.commit()
            logger.info("Vivino wines table migration completed successfully!")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Migration failed: {e}")
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate_vivino_wines_table()