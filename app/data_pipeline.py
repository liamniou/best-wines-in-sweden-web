"""
Data pipeline to migrate from Telegraph pages to database
Integrates existing scrapers with new database models
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from database import SessionLocal, init_database
from models import (
    Toplist, VivinoWine, SystembolagetProduct, 
    ToplistWine, WineMatch, UpdateLog
)
from wine_utils import (
    VivinoItem, SbSearchResult, 
    iteratively_search_sb, parse_vivino_toplist,
    calculate_match_rating, determine_wine_style,
    wine_style_to_emoji, country_name_to_emoji
)
from ai_matcher import ai_simplify_wine_style, ai_generate_food_pairings
from telegram_notifier import notify_list_update, notify_error

logger = logging.getLogger(__name__)

# Configurable matching threshold - only store matches above this score
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "70.0"))  # Default 70%

class DataPipeline:
    def __init__(self):
        self.db = SessionLocal()
        logger.info(f"Initialized DataPipeline with match threshold: {MATCH_THRESHOLD}%")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.db.close()
    
    async def sync_toplist(self, toplist_id: int) -> bool:
        """Synchronize a single toplist with latest data from Vivino"""
        sync_start_time = datetime.utcnow()
        toplist_name = None
        
        try:
            toplist = self.db.query(Toplist).filter(Toplist.id == toplist_id).first()
            if not toplist:
                logger.error(f"Toplist {toplist_id} not found")
                return False
            
            toplist_name = toplist.name
            
            # Create update log entry
            update_log = UpdateLog(
                toplist_id=toplist_id,
                status="in_progress",
                started_at=sync_start_time
            )
            self.db.add(update_log)
            self.db.commit()
            
            logger.info(f"Starting sync for toplist: {toplist.name}")
            
            # Get wines from Vivino
            vivino_items = await parse_vivino_toplist(toplist.url)
            logger.info(f"Found {len(vivino_items)} wines from Vivino")
            
            wines_found = len(vivino_items)
            matches_found = 0
            new_wines = 0
            updated_wines = 0
            
            # Process each wine
            for position, vivino_item in enumerate(vivino_items, 1):
                try:
                    # Skip None items (failed API calls)
                    if vivino_item is None:
                        logger.warning(f"Skipping None wine item at position {position}")
                        continue
                    
                    # Store or update Vivino wine
                    vivino_wine, is_new_wine = await self._store_vivino_wine(vivino_item)
                    
                    # Track new vs updated wines
                    if is_new_wine:
                        new_wines += 1
                    else:
                        updated_wines += 1
                    
                    # Link wine to toplist
                    await self._link_wine_to_toplist(vivino_wine.id, toplist_id, position)
                    
                    # Search for matches in Systembolaget
                    search_results = await iteratively_search_sb(vivino_item)
                    
                    if search_results:
                        for sb_result in search_results:
                            # Store Systembolaget product
                            sb_product = await self._store_systembolaget_product(sb_result)
                            
                            # Create wine match (only if score meets threshold)
                            wine_match = await self._create_wine_match(vivino_wine.id, sb_product.id, sb_result)
                            if wine_match:
                                matches_found += 1
                    
                    # Commit after each wine to avoid large transactions
                    self.db.commit()
                    
                except Exception as e:
                    logger.error(f"Error processing wine {vivino_item.name}: {e}")
                    self.db.rollback()
                    continue
            
            # Update toplist timestamp
            toplist.updated_at = datetime.utcnow()
            
            # Complete update log
            update_log.status = "success"
            update_log.wines_found = wines_found
            update_log.matches_found = matches_found
            update_log.completed_at = datetime.utcnow()
            
            self.db.commit()
            logger.info(f"Completed sync for {toplist.name}: {wines_found} wines, {matches_found} matches")
            
            # Send Telegram notification
            sync_duration = (datetime.utcnow() - sync_start_time).total_seconds()
            try:
                await notify_list_update(
                    toplist_name=toplist.name,
                    wines_count=wines_found,
                    matches_count=matches_found,
                    new_wines=new_wines,
                    updated_wines=updated_wines,
                    sync_duration=sync_duration
                )
            except Exception as notification_error:
                logger.warning(f"Failed to send Telegram notification: {notification_error}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error syncing toplist {toplist_id}: {e}")
            
            # Update log with error
            update_log.status = "failed"
            update_log.error_message = str(e)
            update_log.completed_at = datetime.utcnow()
            self.db.commit()
            
            # Send error notification
            try:
                await notify_error(
                    error_message=str(e),
                    toplist_name=toplist_name
                )
            except Exception as notification_error:
                logger.warning(f"Failed to send Telegram error notification: {notification_error}")
            
            return False
    
    async def _get_simplified_wine_style(self, wine_style: str) -> str:
        """Get simplified wine style using AI"""
        if not wine_style:
            return None
            
        try:
            result = await ai_simplify_wine_style(wine_style)
            logger.info(f"Simplified '{wine_style}' → '{result.simplified_style}' (confidence: {result.confidence_score}%)")
            return result.simplified_style
        except Exception as e:
            logger.error(f"Failed to simplify wine style '{wine_style}': {e}")
            return None
    
    async def _get_simplified_food_pairings(self, vivino_item: VivinoItem, simplified_style: str = None) -> str:
        """Get simplified food pairings using AI"""
        try:
            # Parse grape varieties from JSON if available
            grape_varieties = None
            if hasattr(vivino_item, 'grape_varieties') and vivino_item.grape_varieties:
                try:
                    import json
                    grape_varieties = json.loads(vivino_item.grape_varieties)
                    if isinstance(grape_varieties, list):
                        grape_varieties = grape_varieties[:3]  # Limit to top 3 grapes
                except:
                    grape_varieties = None
            
            result = await ai_generate_food_pairings(
                wine_style=simplified_style or getattr(vivino_item, 'wine_style', None),
                wine_name=vivino_item.name,
                country=getattr(vivino_item, 'country', None),
                grape_varieties=grape_varieties,
                body=getattr(vivino_item, 'body', None),
                acidity=getattr(vivino_item, 'acidity', None)
            )
            
            # Store as JSON string
            import json
            pairings_json = json.dumps(result.pairings, ensure_ascii=False)
            logger.info(f"Generated pairings for '{vivino_item.name}': {result.pairings} (confidence: {result.confidence_score}%)")
            return pairings_json
            
        except Exception as e:
            logger.error(f"Failed to generate food pairings for '{vivino_item.name}': {e}")
            return None
    
    async def _store_vivino_wine(self, vivino_item: VivinoItem) -> tuple[VivinoWine, bool]:
        """Store or update a Vivino wine in database
        
        Returns:
            tuple: (VivinoWine, is_new_wine)
        """
        # Get simplified wine style and food pairings first
        simplified_style = await self._get_simplified_wine_style(getattr(vivino_item, 'wine_style', None))
        simplified_pairings = await self._get_simplified_food_pairings(vivino_item, simplified_style)
        
        # Check if wine already exists
        existing_wine = (
            self.db.query(VivinoWine)
            .filter(VivinoWine.name == vivino_item.name)
            .first()
        )
        
        if existing_wine:
            # Update all wine data
            existing_wine.rating = vivino_item.rating
            if hasattr(vivino_item, 'image_url') and vivino_item.image_url:
                existing_wine.image_url = vivino_item.image_url
                existing_wine.image_cached_at = datetime.utcnow()
            
            # Update enhanced wine data
            if hasattr(vivino_item, 'country'):
                existing_wine.country = vivino_item.country
            if hasattr(vivino_item, 'country_code'):
                existing_wine.country_code = vivino_item.country_code
            if hasattr(vivino_item, 'region'):
                existing_wine.region = vivino_item.region
            if hasattr(vivino_item, 'winery'):
                existing_wine.winery = vivino_item.winery
            if hasattr(vivino_item, 'wine_style'):
                existing_wine.wine_style = vivino_item.wine_style
            if hasattr(vivino_item, 'wine_type_id'):
                existing_wine.wine_type_id = vivino_item.wine_type_id
            if hasattr(vivino_item, 'year'):
                existing_wine.year = vivino_item.year
            if hasattr(vivino_item, 'alcohol_content'):
                existing_wine.alcohol_content = vivino_item.alcohol_content
            if hasattr(vivino_item, 'body'):
                existing_wine.body = vivino_item.body
            if hasattr(vivino_item, 'acidity'):
                existing_wine.acidity = vivino_item.acidity
            if hasattr(vivino_item, 'sweetness'):
                existing_wine.sweetness = vivino_item.sweetness
            if hasattr(vivino_item, 'grape_varieties'):
                existing_wine.grape_varieties = vivino_item.grape_varieties
            if hasattr(vivino_item, 'food_pairings'):
                existing_wine.food_pairings = vivino_item.food_pairings
            if hasattr(vivino_item, 'description'):
                existing_wine.description = vivino_item.description
            if hasattr(vivino_item, 'closure_type'):
                existing_wine.closure_type = vivino_item.closure_type
            if hasattr(vivino_item, 'is_organic'):
                existing_wine.is_organic = vivino_item.is_organic
            if hasattr(vivino_item, 'is_natural'):
                existing_wine.is_natural = vivino_item.is_natural
            
            # Update AI-generated fields
            if simplified_style:
                existing_wine.simplified_wine_style = simplified_style
            if simplified_pairings:
                existing_wine.simplified_food_pairings = simplified_pairings
                
            existing_wine.updated_at = datetime.utcnow()
            return existing_wine, False  # False = not a new wine
        else:
            # Create new wine with enhanced data
            new_wine = VivinoWine(
                name=vivino_item.name,
                rating=vivino_item.rating,
                vintage_id=getattr(vivino_item, 'vintage_id', None),
                wine_url=getattr(vivino_item, 'wine_url', None),
                image_url=getattr(vivino_item, 'image_url', None),
                image_cached_at=datetime.utcnow() if getattr(vivino_item, 'image_url', None) else None,
                
                # Enhanced wine data
                country=getattr(vivino_item, 'country', None),
                country_code=getattr(vivino_item, 'country_code', None),
                region=getattr(vivino_item, 'region', None),
                winery=getattr(vivino_item, 'winery', None),
                wine_style=getattr(vivino_item, 'wine_style', None),
                wine_type_id=getattr(vivino_item, 'wine_type_id', None),
                year=getattr(vivino_item, 'year', None),
                alcohol_content=getattr(vivino_item, 'alcohol_content', None),
                body=getattr(vivino_item, 'body', None),
                acidity=getattr(vivino_item, 'acidity', None),
                sweetness=getattr(vivino_item, 'sweetness', None),
                grape_varieties=getattr(vivino_item, 'grape_varieties', None),
                food_pairings=getattr(vivino_item, 'food_pairings', None),
                simplified_food_pairings=simplified_pairings,  # AI-generated pairings
                description=getattr(vivino_item, 'description', None),
                closure_type=getattr(vivino_item, 'closure_type', None),
                is_organic=getattr(vivino_item, 'is_organic', False),
                is_natural=getattr(vivino_item, 'is_natural', False),
                
                # AI-generated fields
                simplified_wine_style=simplified_style
            )
            self.db.add(new_wine)
            self.db.flush()  # Get ID without committing
            return new_wine, True  # True = new wine
    
    async def _link_wine_to_toplist(self, wine_id: int, toplist_id: int, position: int):
        """Link a wine to a toplist with position"""
        # Check if link already exists
        existing_link = (
            self.db.query(ToplistWine)
            .filter(
                and_(
                    ToplistWine.toplist_id == toplist_id,
                    ToplistWine.vivino_wine_id == wine_id
                )
            )
            .first()
        )
        
        if existing_link:
            # Update position
            existing_link.position = position
        else:
            # Create new link
            new_link = ToplistWine(
                toplist_id=toplist_id,
                vivino_wine_id=wine_id,
                position=position
            )
            self.db.add(new_link)
    
    async def _store_systembolaget_product(self, sb_result: SbSearchResult) -> SystembolagetProduct:
        """Store or update a Systembolaget product"""
        # Extract product number from href
        product_number = sb_result.href.split('q=')[-1] if '?q=' in sb_result.href else None
        
        if not product_number:
            # Generate product number from name if not available
            product_number = f"temp_{hash(sb_result.name) % 1000000}"
        
        # Check if product already exists
        existing_product = (
            self.db.query(SystembolagetProduct)
            .filter(SystembolagetProduct.product_number == product_number)
            .first()
        )
        
        if existing_product:
            # Update product details
            existing_product.name_bold = sb_result.name.split()[0] if sb_result.name else None
            existing_product.name_thin = ' '.join(sb_result.name.split()[1:]) if sb_result.name and len(sb_result.name.split()) > 1 else None
            existing_product.price = float(sb_result.price.replace(' SEK', '')) if sb_result.price and 'SEK' in sb_result.price else None
            existing_product.category_level2 = sb_result.style.replace('🍇', '').replace('🥂', '').replace('🍾', '').strip() if sb_result.style else None
            existing_product.country = sb_result.country
            existing_product.updated_at = datetime.utcnow()
            return existing_product
        else:
            # Create new product
            price_value = None
            if sb_result.price and 'SEK' in sb_result.price:
                try:
                    price_value = float(sb_result.price.replace(' SEK', '').replace(',', ''))
                except ValueError:
                    pass
            
            new_product = SystembolagetProduct(
                product_number=product_number,
                name_bold=sb_result.name.split()[0] if sb_result.name else None,
                name_thin=' '.join(sb_result.name.split()[1:]) if sb_result.name and len(sb_result.name.split()) > 1 else None,
                price=price_value,
                volume=750,  # Default wine bottle size
                category_level1="Vin",
                category_level2=sb_result.style.replace('🍇', '').replace('🥂', '').replace('🍾', '').strip() if sb_result.style else None,
                country=sb_result.country
            )
            self.db.add(new_product)
            self.db.flush()  # Get ID without committing
            return new_product
    
    async def _create_wine_match(self, vivino_wine_id: int, sb_product_id: int, sb_result: SbSearchResult):
        """Create a wine match between Vivino and Systembolaget"""
        # Check if match already exists
        existing_match = (
            self.db.query(WineMatch)
            .filter(
                and_(
                    WineMatch.vivino_wine_id == vivino_wine_id,
                    WineMatch.systembolaget_product_id == sb_product_id
                )
            )
            .first()
        )
        
        if existing_match:
            # Update match score if needed
            if hasattr(sb_result, 'match_score'):
                existing_match.match_score = sb_result.match_score
                existing_match.updated_at = datetime.utcnow()
            return existing_match
        else:
            # Calculate match score using AI
            vivino_wine = self.db.query(VivinoWine).filter(VivinoWine.id == vivino_wine_id).first()
            sb_product = self.db.query(SystembolagetProduct).filter(SystembolagetProduct.id == sb_product_id).first()
            
            match_score = None
            match_type = "uncertain"
            
            if vivino_wine and sb_product:
                try:
                    # Use AI matching with full context
                    from ai_matcher import ai_calculate_match_rating
                    from wine_utils import calculate_string_similarity
                    
                    match_score, match_type, reasoning = await ai_calculate_match_rating(
                        vivino_wine.name,
                        sb_product.full_name,
                        vivino_rating=float(vivino_wine.rating),
                        sb_price=float(sb_product.price) if sb_product.price else None,
                        sb_country=sb_product.country,
                        sb_style=sb_product.category_level2
                    )
                    
                    # Validate AI response
                    if match_score is None or not isinstance(match_score, (int, float)) or not (0 <= match_score <= 100):
                        logger.warning(f"AI returned invalid score ({match_score}), using string similarity fallback")
                        match_score = calculate_string_similarity(vivino_wine.name, sb_product.full_name)
                        reasoning = f"String similarity fallback: {match_score:.1f}% similarity between normalized names"
                        # Determine match type from score
                        if match_score >= 95:
                            match_type = "exact"
                        elif match_score >= 75:
                            match_type = "partial"
                        elif match_score >= 50:
                            match_type = "uncertain"
                        else:
                            match_type = "different"
                    
                    logger.info(f"AI wine match: {vivino_wine.name} <-> {sb_product.full_name}")
                    logger.info(f"Score: {match_score}%, Type: {match_type}")
                    logger.info(f"Reasoning: {reasoning[:150]}...")
                    
                except Exception as e:
                    logger.error(f"AI matching failed, using string similarity fallback: {e}")
                    from wine_utils import calculate_string_similarity
                    match_score = calculate_string_similarity(vivino_wine.name, sb_product.full_name)
                    reasoning = f"String similarity fallback: {match_score:.1f}% similarity between normalized names"
                    # Determine match type from score
                    if match_score >= 95:
                        match_type = "exact"
                    elif match_score >= 75:
                        match_type = "partial"
                    elif match_score >= 50:
                        match_type = "uncertain"
                    else:
                        match_type = "different"
            
            # Check if match score meets the threshold
            if match_score and match_score >= MATCH_THRESHOLD:
                logger.info(f"Match score {match_score}% meets threshold {MATCH_THRESHOLD}%, creating match")
                new_match = WineMatch(
                    vivino_wine_id=vivino_wine_id,
                    systembolaget_product_id=sb_product_id,
                    match_score=match_score,
                    match_type=match_type,
                    verified=False,  # Manual verification can be done later
                    ai_reasoning=reasoning if 'reasoning' in locals() else None,
                    match_method="ai" if 'reasoning' in locals() else "fallback"
                )
                self.db.add(new_match)
                return new_match
            else:
                logger.info(f"Match score {match_score}% below threshold {MATCH_THRESHOLD}%, skipping match")
                return None
    
    async def sync_all_toplists(self) -> dict:
        """Synchronize all toplists"""
        toplists = self.db.query(Toplist).all()
        results = {
            'total': len(toplists),
            'successful': 0,
            'failed': 0,
            'details': []
        }
        
        for toplist in toplists:
            success = await self.sync_toplist(toplist.id)
            if success:
                results['successful'] += 1
                results['details'].append(f"✅ {toplist.name}")
            else:
                results['failed'] += 1
                results['details'].append(f"❌ {toplist.name}")
        
        return results
    
    def get_sync_status(self) -> dict:
        """Get current synchronization status"""
        total_wines = self.db.query(VivinoWine).count()
        total_products = self.db.query(SystembolagetProduct).count()
        total_matches = self.db.query(WineMatch).count()
        verified_matches = self.db.query(WineMatch).filter(WineMatch.verified == True).count()
        
        # Recent updates
        recent_updates = (
            self.db.query(UpdateLog)
            .order_by(UpdateLog.started_at.desc())
            .limit(10)
            .all()
        )
        
        return {
            'statistics': {
                'total_wines': total_wines,
                'total_products': total_products,
                'total_matches': total_matches,
                'verified_matches': verified_matches,
                'verification_rate': round(verified_matches / total_matches * 100, 1) if total_matches > 0 else 0
            },
            'recent_updates': [
                {
                    'toplist_id': log.toplist_id,
                    'status': log.status,
                    'wines_found': log.wines_found,
                    'matches_found': log.matches_found,
                    'started_at': log.started_at,
                    'completed_at': log.completed_at,
                    'error_message': log.error_message
                }
                for log in recent_updates
            ]
        }

# CLI functions for manual execution
async def main():
    """Main function for running data pipeline"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Best Wines Data Pipeline')
    parser.add_argument('--sync-all', action='store_true', help='Sync all toplists')
    parser.add_argument('--sync-toplist', type=int, help='Sync specific toplist by ID')
    parser.add_argument('--status', action='store_true', help='Show sync status')
    parser.add_argument('--init-db', action='store_true', help='Initialize database')
    
    args = parser.parse_args()
    
    if args.init_db:
        logger.info("Initializing database...")
        init_database()
        logger.info("Database initialized successfully")
        return
    
    async with DataPipeline() as pipeline:
        if args.status:
            status = pipeline.get_sync_status()
            print("\n=== SYNC STATUS ===")
            print(f"Total Wines: {status['statistics']['total_wines']}")
            print(f"Total Products: {status['statistics']['total_products']}")
            print(f"Total Matches: {status['statistics']['total_matches']}")
            print(f"Verified Matches: {status['statistics']['verified_matches']}")
            print(f"Verification Rate: {status['statistics']['verification_rate']}%")
            
            print("\n=== RECENT UPDATES ===")
            for update in status['recent_updates'][:5]:
                print(f"Toplist {update['toplist_id']}: {update['status']} "
                      f"({update['wines_found']} wines, {update['matches_found']} matches)")
        
        elif args.sync_all:
            logger.info("Syncing all toplists...")
            results = await pipeline.sync_all_toplists()
            print(f"\n=== SYNC RESULTS ===")
            print(f"Total: {results['total']}")
            print(f"Successful: {results['successful']}")
            print(f"Failed: {results['failed']}")
            
            print("\n=== DETAILS ===")
            for detail in results['details']:
                print(detail)
        
        elif args.sync_toplist:
            logger.info(f"Syncing toplist {args.sync_toplist}...")
            success = await pipeline.sync_toplist(args.sync_toplist)
            if success:
                print(f"✅ Successfully synced toplist {args.sync_toplist}")
            else:
                print(f"❌ Failed to sync toplist {args.sync_toplist}")
        
        else:
            parser.print_help()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())