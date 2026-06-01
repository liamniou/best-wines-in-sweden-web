#!/usr/bin/env python3
"""
Scrape Vivino toplist using Camoufox headless browser.
Extracts wine data and downloads wine images locally.
"""
import asyncio
import json
import re
import httpx
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Data directory
DATA_DIR = Path("/app/data") if Path("/app/data").exists() else Path(__file__).parent.parent / "data"

# Static images directory for downloaded wine images
IMAGES_DIR = Path("/app/static_site/images/wines") if Path("/app/static_site").exists() else Path(__file__).parent / "static" / "images" / "wines"


async def download_image(url: str, save_path: Path) -> bool:
    """Download an image from URL and save it locally."""
    # Handle protocol-relative URLs (starting with //)
    if url.startswith('//'):
        url = 'https:' + url
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, follow_redirects=True)
            if response.status_code == 200:
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_bytes(response.content)
                return True
    except Exception as e:
        print(f"    Error downloading {url}: {e}")
    return False


def extract_image_id_from_url(url: str) -> Optional[str]:
    """Extract the image hash/ID from a Vivino image URL.
    
    Example: https://images.vivino.com/thumbs/r4HpYORxQGa9uNUVjutIqg_pb_x300.png
    Returns: r4HpYORxQGa9uNUVjutIqg
    """
    if not url:
        return None
    match = re.search(r'/thumbs/([a-zA-Z0-9_-]+)_', url)
    if match:
        return match.group(1)
    return None


async def scrape_toplist_with_images(url: str, toplist_id: str, name: str, category: str = "budget", description: str = ""):
    """Scrape wines from a Vivino toplist page including images."""
    
    print(f"Scraping: {name}")
    print(f"URL: {url}")
    print("-" * 60)
    
    try:
        from camoufox.async_api import AsyncCamoufox
    except ImportError:
        print("ERROR: Camoufox not installed. Run: pip install camoufox")
        return None
    
    wines = []
    
    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        
        print("Opening page...")
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        
        # Handle cookie consent
        print("Looking for cookie consent...")
        try:
            agree_button = await page.query_selector('button:has-text("Agree")')
            if agree_button:
                print("Clicking Agree...")
                await agree_button.click()
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Cookie dialog handling: {e}")
        
        # Wait for wines to load
        print("Waiting for wines to load...")
        await asyncio.sleep(3)
        
        # Scroll down to load more wines
        print("Scrolling to load all wines...")
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
        
        # Scroll back to top
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1)
        
        # Extract wine cards using JavaScript
        print("\nExtracting wine data with images...")
        wine_data = await page.evaluate("""
            () => {
                const wines = [];
                
                // Find all wine links on the toplist
                const wineLinks = document.querySelectorAll('a[data-testid="vintagePageLink"]');
                
                wineLinks.forEach((link, index) => {
                    const wine = { rank: index + 1 };
                    
                    // Get wine page URL
                    wine.vivino_url = link.href;
                    
                    // Find the image within or near this element
                    // Look for wine bottle image
                    const container = link.closest('[class*="toplistCard"]') || link.parentElement?.parentElement?.parentElement;
                    
                    if (container) {
                        // Find image - Vivino uses specific image classes
                        const img = container.querySelector('img[src*="images.vivino.com"]') || 
                                    container.querySelector('img[class*="wineImage"]') ||
                                    container.querySelector('picture img') ||
                                    link.querySelector('img');
                        
                        if (img && img.src) {
                            wine.image_url = img.src;
                        }
                        
                        // Also try to find image in background style
                        const bgElement = container.querySelector('[style*="background-image"]');
                        if (bgElement && !wine.image_url) {
                            const style = bgElement.getAttribute('style');
                            const match = style.match(/url\\(['"]*([^'"\\)]+)['"]*\\)/);
                            if (match) {
                                wine.image_url = match[1];
                            }
                        }
                    }
                    
                    // Get text content for name, winery, etc.
                    const textContent = link.innerText || link.textContent;
                    wine.text_content = textContent;
                    
                    wines.push(wine);
                });
                
                return wines;
            }
        """)
        
        print(f"Found {len(wine_data)} wine cards with potential images")
        
        # Also get the full page text for detailed parsing
        page_text = await page.inner_text('body')
        
        await page.close()
    
    # Parse wines from text and merge with image data
    print("\nParsing wine details...")
    parsed_wines = parse_wines_from_text(page_text)
    
    # Merge image URLs with parsed wine data
    for i, wine in enumerate(parsed_wines):
        if i < len(wine_data) and wine_data[i].get('image_url'):
            wine['vivino_image_url'] = wine_data[i]['image_url']
        if i < len(wine_data) and wine_data[i].get('vivino_url'):
            wine['vivino_url'] = wine_data[i]['vivino_url']
    
    # Download images locally
    print("\nDownloading wine images...")
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    
    for wine in parsed_wines:
        image_url = wine.get('vivino_image_url')
        
        # Skip flag images (Vivino shows country flags when no bottle image available)
        if image_url and ('countryFlags' in image_url or '/flags/' in image_url.lower()):
            print(f"  #{wine['rank']}: Skipping flag image (no bottle image available)")
            wine['vivino_image_url'] = None  # Clear the flag URL
            image_url = None
        
        if image_url:
            # Create folder per toplist, filename is just rank + wine name
            safe_name = re.sub(r'[^\w\s-]', '', f"{wine.get('winery', '')}_{wine.get('name', '')}").strip().replace(' ', '_')[:50]
            image_filename = f"{wine['rank']}_{safe_name}.png"
            toplist_images_dir = IMAGES_DIR / toplist_id
            toplist_images_dir.mkdir(parents=True, exist_ok=True)
            image_path = toplist_images_dir / image_filename
            
            print(f"  Downloading image for #{wine['rank']}: {wine.get('winery', '')} - {wine.get('name', '')}...")
            
            if await download_image(image_url, image_path):
                wine['local_image'] = f"/images/wines/{toplist_id}/{image_filename}"
                print(f"    ✅ Saved: {toplist_id}/{image_filename}")
            else:
                print(f"    ❌ Failed to download")
        else:
            print(f"  #{wine['rank']}: No image URL found")
    
    print(f"\nExtracted {len(parsed_wines)} wines:")
    for wine in parsed_wines:
        price_str = f"{wine.get('price', 'N/A')} SEK" if wine.get('price') else 'N/A'
        has_image = "🖼️" if wine.get('local_image') else "❌"
        print(f"  {wine['rank']}. {has_image} {wine['winery']} {wine['name']} - {wine['rating']} ⭐ - {price_str}")
    
    # Create toplist
    toplist = {
        'id': toplist_id,
        'name': name,
        'url': url,
        'category': category,
        'description': description,
        'scraped_wines': parsed_wines,
        'wines': [],  # Will be populated with match IDs after matching
        'wine_count': len(parsed_wines),
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    
    # Save - append to existing toplists or update existing entry
    toplists_file = DATA_DIR / "toplists.json"
    existing_toplists = []
    if toplists_file.exists():
        try:
            with open(toplists_file, 'r', encoding='utf-8') as f:
                existing_toplists = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            existing_toplists = []
    
    # Find and update existing toplist or add new one
    toplist_updated = False
    for i, existing in enumerate(existing_toplists):
        if existing.get('id') == toplist['id']:
            # Keep created_at from existing, update the rest
            toplist['created_at'] = existing.get('created_at', toplist['created_at'])
            existing_toplists[i] = toplist
            toplist_updated = True
            print(f"\nUpdated existing toplist: {toplist['id']}")
            break
    
    if not toplist_updated:
        existing_toplists.append(toplist)
        print(f"\nAdded new toplist: {toplist['id']}")
    
    toplists_file.write_text(json.dumps(existing_toplists, indent=2, ensure_ascii=False))
    print(f"Saved to {toplists_file} ({len(existing_toplists)} toplists)")
    
    return toplist


def parse_wines_from_text(page_text: str) -> list:
    """Parse wine data from page text content."""
    wines = []
    lines = page_text.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for wine rank pattern (#1, #2, etc.)
        if re.match(r'^#(\d+)$', line):
            rank = int(line[1:])
            wine = {'rank': rank}
            
            # Next lines should be: winery, wine name, region/country, rating
            i += 1
            parts_collected = []
            
            while i < len(lines) and len(parts_collected) < 10:
                next_line = lines[i].strip()
                
                # Skip empty lines
                if not next_line:
                    i += 1
                    continue
                
                # Stop if we hit the next wine or a separator
                if re.match(r'^#\d+$', next_line):
                    break
                
                # Skip certain lines
                if next_line in ['save', 'Average price']:
                    i += 1
                    continue
                
                # Check for rating (X.X format followed by ratings count)
                rating_match = re.match(r'^(\d+\.\d+)$', next_line)
                if rating_match and 'rating' not in wine:
                    wine['rating'] = float(rating_match.group(1))
                    # Look for ratings count on next line
                    if i + 1 < len(lines):
                        count_match = re.match(r'^\((\d+(?:,\d+)*)\s*ratings?\)', lines[i + 1].strip())
                        if count_match:
                            wine['ratings_count'] = int(count_match.group(1).replace(',', ''))
                            i += 1
                    i += 1
                    continue
                
                # Check for price (XXX kr format)
                price_match = re.match(r'^(\d+(?:,\d+)?(?:\.\d+)?)\s*kr$', next_line.replace(' ', ''))
                if price_match and 'price' not in wine:
                    wine['price'] = float(price_match.group(1).replace(',', '.'))
                    i += 1
                    continue
                
                # Check for percentage (save XX%)
                if next_line.endswith('%') or 'discount' in next_line.lower():
                    i += 1
                    continue
                
                # Collect wine info parts
                parts_collected.append(next_line)
                i += 1
            
            # Parse collected parts
            if len(parts_collected) >= 2:
                wine['winery'] = parts_collected[0]
                wine['name'] = parts_collected[1]
                
                # Third part is usually region, country
                if len(parts_collected) >= 3:
                    location = parts_collected[2]
                    # Parse "Region, Country" format
                    if ', ' in location:
                        parts = location.rsplit(', ', 1)
                        wine['region'] = parts[0]
                        wine['country'] = parts[1]
                    else:
                        wine['region'] = location
            
            if 'name' in wine and 'rating' in wine:
                wines.append(wine)
                print(f"  #{wine['rank']}: {wine.get('winery', 'Unknown')} - {wine['name']} - {wine['rating']} ⭐ ({wine.get('country', 'Unknown')})")
            
            continue
        
        i += 1
    
    return wines


# Alternative: Direct image extraction from wine card HTML
async def extract_wine_images_directly(page) -> Dict[int, str]:
    """Extract wine images directly using more specific selectors."""
    
    images = await page.evaluate("""
        () => {
            const result = {};
            
            // Method 1: Find all images with Vivino CDN URL
            document.querySelectorAll('img').forEach(img => {
                if (img.src && img.src.includes('images.vivino.com')) {
                    // Try to find associated rank
                    const card = img.closest('[class*="card"]') || img.closest('a');
                    if (card) {
                        const rankText = card.innerText.match(/#(\\d+)/);
                        if (rankText) {
                            result[parseInt(rankText[1])] = img.src;
                        }
                    }
                }
            });
            
            // Method 2: Look for picture elements
            document.querySelectorAll('picture source').forEach(source => {
                if (source.srcset && source.srcset.includes('images.vivino.com')) {
                    const card = source.closest('[class*="card"]') || source.closest('a');
                    if (card) {
                        const rankText = card.innerText.match(/#(\\d+)/);
                        if (rankText) {
                            const srcsetParts = source.srcset.split(',');
                            // Get the largest image
                            const lastSrc = srcsetParts[srcsetParts.length - 1].trim().split(' ')[0];
                            result[parseInt(rankText[1])] = lastSrc;
                        }
                    }
                }
            });
            
            return result;
        }
    """)
    
    return images


def interactive_mode():
    """Interactive mode for scraping toplists."""
    print("\n" + "=" * 60)
    print("VIVINO TOPLIST SCRAPER - Interactive Mode")
    print("=" * 60)
    
    # Default values
    default_url = "https://www.vivino.com/toplists/best-wines-under-100-kr-right-now-sweden"
    
    print("\n1. Enter Vivino toplist URL")
    print(f"   (Press Enter for default: {default_url[:50]}...)")
    url = input("   URL: ").strip() or default_url
    
    # Generate toplist_id from URL
    url_path = url.split('/')[-1] if '/' in url else url
    default_id = re.sub(r'[^a-z0-9]+', '_', url_path.lower())[:30]
    
    print(f"\n2. Enter toplist ID (for filenames)")
    print(f"   (Press Enter for: {default_id})")
    toplist_id = input("   ID: ").strip() or default_id
    
    print("\n3. Enter toplist name/title")
    default_name = url_path.replace('-', ' ').title()
    print(f"   (Press Enter for: {default_name})")
    name = input("   Name: ").strip() or default_name
    
    print("\n4. Enter description")
    default_desc = f"Wines from Vivino toplist: {name}"
    print(f"   (Press Enter for: {default_desc})")
    description = input("   Description: ").strip() or default_desc
    
    print("\n5. Enter category (budget/premium/region/style)")
    print("   (Press Enter for: budget)")
    category = input("   Category: ").strip() or "budget"
    
    print("\n" + "=" * 60)
    print(f"Scraping: {name}")
    print(f"URL: {url}")
    print(f"ID: {toplist_id}")
    print("=" * 60 + "\n")
    
    return url, toplist_id, name, category, description


async def main():
    """Main entry point with interactive options."""
    import sys
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--fix-image':
            # Fix single image: --fix-image <wine_id> <image_url>
            if len(sys.argv) < 4:
                print("Usage: python scrape_vivino_toplist.py --fix-image <wine_id> <image_url>")
                print("Example: python scrape_vivino_toplist.py --fix-image toplist_vivino_under_100_21 https://images.vivino.com/...")
                return
            
            wine_id = sys.argv[2]  # e.g., toplist_vivino_under_100_21
            image_url = sys.argv[3]
            
            # Handle protocol-relative URLs
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            
            # Skip flag images
            if 'countryFlags' in image_url or '/flags/' in image_url.lower():
                print("❌ Cannot use flag images. Please provide a wine bottle image URL.")
                return
            
            # Parse wine_id to get toplist_id and rank
            # Format: toplist_<toplist_id>_<rank> e.g., toplist_vivino_under_100_21
            parts = wine_id.split('_')
            if len(parts) < 3 or parts[0] != 'toplist':
                print(f"❌ Invalid wine ID format: {wine_id}")
                print("   Expected format: toplist_<toplist_id>_<rank>")
                print("   Example: toplist_vivino_under_100_21")
                return
            
            try:
                rank = int(parts[-1])
                toplist_id = '_'.join(parts[1:-1])  # e.g., vivino_under_100
            except ValueError:
                print(f"❌ Could not parse rank from: {wine_id}")
                return
            
            print(f"Fixing image for: {wine_id}")
            print(f"  Toplist ID: {toplist_id}")
            print(f"  Rank: {rank}")
            print(f"  Image URL: {image_url}")
            
            # Load toplists to find the wine
            toplists_file = DATA_DIR / "toplists.json"
            if not toplists_file.exists():
                print("❌ No toplists.json found. Run scraper first.")
                return
            
            with open(toplists_file, 'r', encoding='utf-8') as f:
                toplists = json.load(f)
            
            # Find the wine and update it
            wine_found = False
            for toplist in toplists:
                if toplist.get('id') == toplist_id:
                    wines = toplist.get('scraped_wines', [])
                    for wine in wines:
                        if wine.get('rank') == rank:
                            wine_found = True
                            # Download the image to toplist folder
                            safe_name = re.sub(r'[^\w\s-]', '', f"{wine.get('winery', '')}_{wine.get('name', '')}").strip().replace(' ', '_')[:50]
                            toplist_images_dir = IMAGES_DIR / toplist_id
                            toplist_images_dir.mkdir(parents=True, exist_ok=True)
                            image_filename = f"{rank}_{safe_name}.png"
                            image_path = toplist_images_dir / image_filename
                            local_image_path = f"/images/wines/{toplist_id}/{image_filename}"
                            
                            print(f"  Downloading to: {toplist_id}/{image_filename}")
                            
                            if await download_image(image_url, image_path):
                                wine['local_image'] = local_image_path
                                wine['vivino_image_url'] = image_url
                                print(f"  ✅ Saved!")
                                
                                # Also update wines.json if it exists
                                wines_file = DATA_DIR / "wines.json"
                                if wines_file.exists():
                                    with open(wines_file, 'r', encoding='utf-8') as f:
                                        wines_data = json.load(f)
                                    updated = False
                                    for w in wines_data:
                                        # Try match by match_id first
                                        if w.get('match_id') == wine_id:
                                            w['image_url'] = local_image_path
                                            updated = True
                                            print(f"  ✅ Updated wines.json (by match_id)")
                                            break
                                        # Also try by vivino_rank + winery
                                        if (w.get('vivino_rank') == rank and 
                                            w.get('winery') == wine.get('winery')):
                                            w['image_url'] = local_image_path
                                            updated = True
                                            print(f"  ✅ Updated wines.json (by vivino_rank)")
                                            break
                                    if not updated:
                                        print(f"  ⚠️ Wine not found in wines.json")
                                    with open(wines_file, 'w', encoding='utf-8') as f:
                                        json.dump(wines_data, f, indent=2, ensure_ascii=False)
                            else:
                                print(f"  ❌ Failed to download image")
                            break
                    break
            
            if not wine_found:
                print(f"❌ Wine not found: {wine_id}")
                print(f"   Searched in toplist: {toplist_id}, rank: {rank}")
                return
            
            # Save updated toplist data
            with open(toplists_file, 'w', encoding='utf-8') as f:
                json.dump(toplists, f, indent=2, ensure_ascii=False)
            print("✅ Done!")
            return
        
        elif sys.argv[1] == '--url' and len(sys.argv) > 2:
            # Direct URL mode - scrape and add/update in toplists.json
            url = sys.argv[2]
            url_path = url.split('/')[-1]
            toplist_id = re.sub(r'[^a-z0-9]+', '_', url_path.lower())[:30]
            name = url_path.replace('-', ' ').title()
            description = f"Wines from Vivino toplist: {name}"
            category = "default"
            
            # Check if already exists in toplists.json
            toplists_file = DATA_DIR / "toplists.json"
            existing_toplists = []
            if toplists_file.exists():
                try:
                    with open(toplists_file, 'r', encoding='utf-8') as f:
                        existing_toplists = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    existing_toplists = []
            
            existing_urls = [t.get('url') for t in existing_toplists]
            if url in existing_urls:
                print(f"ℹ️  URL already in toplists.json, will update")
        
        elif sys.argv[1] == '--fix-image' and len(sys.argv) >= 4:
            # Direct fix single image: --fix-image <wine_id> <image_url>
            wine_id = sys.argv[2]  # e.g., toplist_vivino_under_100_21
            image_url = sys.argv[3]
            
            print(f"Fixing image for: {wine_id}")
            print(f"Image URL: {image_url}")
            
            # Handle protocol-relative URLs
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            
            # Skip flag images
            if 'countryFlags' in image_url or '/flags/' in image_url.lower():
                print("ERROR: This appears to be a country flag, not a wine image.")
                return
            
            # Parse wine_id to get toplist_id and rank
            # Format: toplist_<toplist_id>_<rank> e.g., toplist_vivino_under_100_21
            parts = wine_id.split('_')
            if len(parts) < 3 or parts[0] != 'toplist':
                print(f"ERROR: Invalid wine ID format. Expected: toplist_<id>_<rank>")
                print(f"Example: toplist_vivino_under_100_21")
                return
            
            try:
                rank = int(parts[-1])
                tl_id = '_'.join(parts[1:-1])  # e.g., vivino_under_100
            except ValueError:
                print(f"ERROR: Could not parse rank from wine ID: {wine_id}")
                return
            
            print(f"  Toplist ID: {tl_id}")
            print(f"  Rank: {rank}")
            
            # Download the image to toplist folder
            toplist_images_dir = IMAGES_DIR / tl_id
            toplist_images_dir.mkdir(parents=True, exist_ok=True)
            image_filename = f"{rank}_manual.png"
            image_path = toplist_images_dir / image_filename
            
            print(f"  Downloading...")
            if await download_image(image_url, image_path):
                local_image = f"/images/wines/{tl_id}/{image_filename}"
                print(f"  Saved: {tl_id}/{image_filename}")
                
                # Update wines.json
                wines_file = DATA_DIR / "wines.json"
                if wines_file.exists():
                    with open(wines_file, 'r', encoding='utf-8') as f:
                        wines = json.load(f)
                    
                    updated = False
                    for w in wines:
                        if w.get('match_id') == wine_id:
                            w['image_url'] = local_image
                            updated = True
                            print(f"  Updated wines.json for {wine_id}")
                            break
                    
                    if updated:
                        with open(wines_file, 'w', encoding='utf-8') as f:
                            json.dump(wines, f, indent=2, ensure_ascii=False)
                    else:
                        print(f"  Warning: Wine {wine_id} not found in wines.json")
                
                # Also update toplists.json
                toplists_file = DATA_DIR / "toplists.json"
                if toplists_file.exists():
                    with open(toplists_file, 'r', encoding='utf-8') as f:
                        toplists = json.load(f)
                    
                    for toplist in toplists:
                        if toplist.get('id') == tl_id:
                            for w in toplist.get('scraped_wines', []):
                                if w.get('rank') == rank:
                                    w['local_image'] = local_image
                                    w['vivino_image_url'] = image_url
                                    print(f"  Updated toplists.json for rank {rank}")
                                    break
                    
                    with open(toplists_file, 'w', encoding='utf-8') as f:
                        json.dump(toplists, f, indent=2, ensure_ascii=False)
                
                print("Done!")
            else:
                print("  ERROR: Failed to download image")
            return
        
        else:
            print("Usage:")
            print("  python scrape_vivino_toplist.py                           # Re-scrape all toplists")
            print("  python scrape_vivino_toplist.py --url <URL>               # Add and scrape new toplist")
            print("  python scrape_vivino_toplist.py --fix-image <ID> <URL>    # Fix specific wine image")
            print("")
            print("Examples:")
            print("  python scrape_vivino_toplist.py --url https://www.vivino.com/toplists/...")
            print("  python scrape_vivino_toplist.py --fix-image toplist_vivino_under_100_21 https://images.vivino.com/...")
            return
    else:
        # Default mode: re-scrape all toplists from toplists.json
        toplists_file = DATA_DIR / "toplists.json"
        if toplists_file.exists():
            try:
                with open(toplists_file, 'r', encoding='utf-8') as f:
                    toplists = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                toplists = []
            
            if toplists:
                print(f"\n📋 Re-scraping {len(toplists)} toplist(s) from toplists.json\n")
                for i, toplist in enumerate(toplists, 1):
                    url = toplist.get('url')
                    toplist_id = toplist.get('id')
                    name = toplist.get('name')
                    category = toplist.get('category', 'default')
                    description = toplist.get('description', '')
                    
                    print(f"\n{'='*60}")
                    print(f"[{i}/{len(toplists)}] Scraping: {name}")
                    print(f"{'='*60}")
                    
                    await scrape_toplist_with_images(
                        url=url,
                        toplist_id=toplist_id,
                        name=name,
                        category=category,
                        description=description
                    )
                
                print(f"\n✅ Finished re-scraping all {len(toplists)} toplists!")
                return
        
        # Fallback to interactive mode if no toplists exist
        try:
            url, toplist_id, name, category, description = interactive_mode()
        except (EOFError, KeyboardInterrupt):
            print("\nNo toplists found. Add a new toplist with:")
            print("  make scrape-url URL=https://www.vivino.com/toplists/...")
            return
    
    # Run scraper for single URL mode
    await scrape_toplist_with_images(
        url=url,
        toplist_id=toplist_id,
        name=name,
        category=category,
        description=description
    )


if __name__ == "__main__":
    asyncio.run(main())
