"""
JSON-based data storage system - replaces PostgreSQL database
All data stored in JSON files in data/ directory
"""

import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

DATA_DIR = Path("/app/data" if os.path.exists("/app") else "data")
WINES_FILE = DATA_DIR / "wines.json"
TOPLISTS_FILE = DATA_DIR / "toplists.json"
MATCHES_FILE = DATA_DIR / "matches.json"
STATS_FILE = DATA_DIR / "stats.json"


def ensure_data_dir():
    """Ensure data directory exists"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Data directory: {DATA_DIR}")


def load_json(file_path: Path, default=None):
    """Load JSON from file with error handling"""
    if default is None:
        default = []
    
    if not file_path.exists():
        logger.info(f"Creating new file: {file_path}")
        save_json(file_path, default)
        return default
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Error loading {file_path}: {e}")
        return default
    except Exception as e:
        logger.error(f"Unexpected error loading {file_path}: {e}")
        return default


def save_json(file_path: Path, data):
    """Save JSON to file with error handling"""
    try:
        # Write to temp file first, then rename (atomic operation)
        temp_file = file_path.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_file.rename(file_path)
        logger.debug(f"Saved {file_path}")
    except Exception as e:
        logger.error(f"Error saving {file_path}: {e}")
        raise


class WineStorage:
    """Manage wine data in JSON format"""
    
    def __init__(self):
        ensure_data_dir()
        self.wines = load_json(WINES_FILE, [])
        self.toplists = load_json(TOPLISTS_FILE, [])
        self.matches = load_json(MATCHES_FILE, [])
        self.stats = load_json(STATS_FILE, {})
    
    def save_all(self):
        """Save all data to disk"""
        save_json(WINES_FILE, self.wines)
        save_json(TOPLISTS_FILE, self.toplists)
        save_json(MATCHES_FILE, self.matches)
        save_json(STATS_FILE, self.stats)
        logger.info("All data saved to disk")
    
    def add_wine(self, wine_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add or update a wine"""
        wine_id = wine_data.get('id') or wine_data.get('vivino_id')
        
        if not wine_id:
            # Generate ID from name
            wine_id = f"wine_{len(self.wines) + 1}"
            wine_data['id'] = wine_id
        
        wine_data['updated_at'] = datetime.utcnow().isoformat()
        
        # Check if wine exists
        for i, wine in enumerate(self.wines):
            if wine.get('id') == wine_id or wine.get('vivino_id') == wine_id:
                self.wines[i] = wine_data
                logger.debug(f"Updated wine: {wine_data.get('name')}")
                return wine_data
        
        # Add new wine
        self.wines.append(wine_data)
        logger.debug(f"Added wine: {wine_data.get('name')}")
        return wine_data
    
    def add_toplist(self, toplist_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add or update a toplist"""
        toplist_id = toplist_data.get('id')
        
        if not toplist_id:
            toplist_id = f"toplist_{len(self.toplists) + 1}"
            toplist_data['id'] = toplist_id
        
        toplist_data['updated_at'] = datetime.utcnow().isoformat()
        
        # Check if toplist exists
        for i, toplist in enumerate(self.toplists):
            if toplist.get('id') == toplist_id:
                toplist_data['wines'] = toplist_data.get('wines', toplist.get('wines', []))
                self.toplists[i] = toplist_data
                logger.debug(f"Updated toplist: {toplist_data.get('name')}")
                return toplist_data
        
        # Add new toplist
        self.toplists.append(toplist_data)
        logger.debug(f"Added toplist: {toplist_data.get('name')}")
        return toplist_data
    
    def add_match(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add or update a wine match"""
        match_id = match_data.get('id')
        
        if not match_id:
            match_id = f"match_{len(self.matches) + 1}"
            match_data['id'] = match_id
        
        match_data['updated_at'] = datetime.utcnow().isoformat()
        
        # Check if match exists
        vivino_id = match_data.get('vivino_wine_id')
        sb_id = match_data.get('systembolaget_product_id')
        
        for i, match in enumerate(self.matches):
            if (match.get('id') == match_id or 
                (match.get('vivino_wine_id') == vivino_id and 
                 match.get('systembolaget_product_id') == sb_id)):
                self.matches[i] = match_data
                logger.debug(f"Updated match: {match_id}")
                return match_data
        
        # Add new match
        self.matches.append(match_data)
        logger.debug(f"Added match: {match_id}")
        return match_data
    
    def get_wine_by_id(self, wine_id: str) -> Optional[Dict[str, Any]]:
        """Get wine by ID"""
        for wine in self.wines:
            if wine.get('id') == wine_id or wine.get('vivino_id') == wine_id:
                return wine
        return None
    
    def get_toplist_by_id(self, toplist_id: str) -> Optional[Dict[str, Any]]:
        """Get toplist by ID"""
        for toplist in self.toplists:
            if toplist.get('id') == toplist_id:
                return toplist
        return None
    
    def get_wines_for_toplist(self, toplist_id: str) -> List[Dict[str, Any]]:
        """Get all wines for a toplist"""
        toplist = self.get_toplist_by_id(toplist_id)
        if not toplist:
            return []
        
        wine_ids = toplist.get('wines', [])
        wines = []
        for wine_id in wine_ids:
            wine = self.get_wine_by_id(wine_id)
            if wine:
                wines.append(wine)
        return wines
    
    def get_match_for_wine(self, wine_id: str) -> Optional[Dict[str, Any]]:
        """Get match for a wine"""
        for match in self.matches:
            if match.get('vivino_wine_id') == wine_id:
                return match
        return None
    
    def get_all_wines(self) -> List[Dict[str, Any]]:
        """Get all wines"""
        return self.wines
    
    def get_all_toplists(self) -> List[Dict[str, Any]]:
        """Get all toplists"""
        return self.toplists
    
    def get_all_matches(self) -> List[Dict[str, Any]]:
        """Get all matches"""
        return self.matches
    
    def update_stats(self):
        """Update statistics"""
        self.stats = {
            'total_wines': len(self.wines),
            'total_toplists': len(self.toplists),
            'total_matches': len(self.matches),
            'avg_rating': sum(w.get('rating', 0) for w in self.wines) / max(len(self.wines), 1),
            'last_updated': datetime.utcnow().isoformat()
        }
        save_json(STATS_FILE, self.stats)
    
    def delete_toplist(self, toplist_id: str):
        """Delete a toplist"""
        self.toplists = [t for t in self.toplists if t.get('id') != toplist_id]
        logger.info(f"Deleted toplist: {toplist_id}")
    
    def clear_all(self):
        """Clear all data (use with caution!)"""
        self.wines = []
        self.toplists = []
        self.matches = []
        self.stats = {}
        self.save_all()
        logger.warning("Cleared all data")


# Global storage instance
_storage = None

def get_storage() -> WineStorage:
    """Get the global storage instance"""
    global _storage
    if _storage is None:
        _storage = WineStorage()
    return _storage

