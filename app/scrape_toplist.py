#!/usr/bin/env python3
"""
Script to scrape a single Vivino toplist and update the local data.
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from vivino_scraper.scraper import get_toplist_items, deduplicate_wines

# Data directory
DATA_DIR = Path("/app/data") if Path("/app/data").exists() else Path(__file__).parent.parent / "data"


async def scrape_and_save_toplist(vivino_url: str, toplist_id: str, name: str, category: str = "general", description: str = ""):
    """Scrape a Vivino toplist and save to local data."""
    
    print(f"Scraping toplist: {name}")
    print(f"URL: {vivino_url}")
    print("-" * 50)
    
    # Scrape wines from Vivino
    wines = await get_toplist_items(vivino_url, max_concurrent=3)
    
    if not wines:
        print("No wines found!")
        return None
    
    # Deduplicate
    wines = deduplicate_wines(wines)
    print(f"Found {len(wines)} unique wines")
    
    # Print wines for verification
    for i, wine in enumerate(wines, 1):
        rating = wine.get('ratings_average', 'N/A')
        name_str = wine.get('name', 'Unknown')[:50]
        print(f"  {i}. {name_str} - Rating: {rating}")
    
    # Create toplist entry
    toplist = {
        "id": toplist_id,
        "name": name,
        "url": vivino_url,
        "category": category,
        "description": description,
        "wines": wines,  # Store full wine data
        "wine_count": len(wines),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    # Save to file
    toplists_file = DATA_DIR / "toplists.json"
    toplists_file.write_text(json.dumps([toplist], indent=2, ensure_ascii=False))
    print(f"\nSaved toplist to {toplists_file}")
    
    return toplist


if __name__ == "__main__":
    # Scrape the budget toplist
    asyncio.run(scrape_and_save_toplist(
        vivino_url="https://www.vivino.com/toplists/best-wines-under-100-kr-right-now-sweden",
        toplist_id="budget_under_100",
        name="Best Wines Under 100 SEK",
        category="budget",
        description="Top-rated wines under 100 SEK available at Systembolaget, as rated by Vivino users."
    ))
