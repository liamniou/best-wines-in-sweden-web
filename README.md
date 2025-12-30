# 🍷 Best Wines Sweden

A modern static website that finds the best wines from Vivino toplists available at Systembolaget (Swedish alcohol retailer). Features advanced filtering, real-time search, and detailed wine information.

## ✨ Features

- **🔍 Advanced Filtering** - Filter by price, rating, country, wine style, food pairings
- **📱 Mobile Optimized** - Perfect experience on all devices  
- **⚡ Client-side Search** - Instant filtering without server requests
- **🍷 Wine Details** - Comprehensive wine information pages
- **🔗 Direct Purchase** - Links to buy at Systembolaget
- **📊 Match Scores** - Color-coded match percentage badges
- **🥩 Food Pairings** - Emoji-based food pairing suggestions

## 🏗️ Architecture

This is a **static site** - no database required at runtime!

```
JSON Data → Static Site Generator → HTML Files → Static Server
```

- **Data**: Stored in `data/*.json` files
- **Generator**: Builds 150+ HTML pages from templates
- **Server**: Lightweight FastAPI serving static files

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose

### First Time Setup
```bash
make build          # Build Docker images
make update         # Full pipeline: scrape → match → generate → restart
```

Then open: http://localhost:8005

### Daily Commands
```bash
make start          # Start server
make stop           # Stop server
make update         # Refresh all data from Vivino
make logs           # View server logs
```

### Fix a Missing Image
```bash
make fix-image ID=toplist_vivino_under_100_21 URL=https://images.vivino.com/thumbs/xxx.png
make generate
```

## 📋 Available Commands

### Data Pipeline
```bash
make scrape                 # Scrape default Vivino toplist (interactive)
make scrape-url URL=<url>   # Scrape specific Vivino toplist URL
make match                  # Match scraped wines with Systembolaget
make generate               # Generate static HTML site from JSON data
make update                 # Full pipeline: scrape → match → generate → restart
```

### Image Management
```bash
make fix-images             # Fix missing images interactively
make fix-image ID=<id> URL=<url>  # Set specific wine image
```

Example:
```bash
make fix-image ID=toplist_vivino_under_100_21 URL=https://images.vivino.com/thumbs/xxx_pb_x300.png
```

### Server Management
```bash
make build      # Build Docker images
make start      # Start the web server (http://localhost:8005)
make stop       # Stop all containers
make restart    # Restart the web server
make logs       # View web server logs
make shell      # Open shell in container
make clean      # Remove generated files and containers
make rebuild    # Full rebuild and restart
```

## 📁 Project Structure

```
best_wines/
├── app/
│   ├── static/              # CSS, JS assets
│   ├── static_site/         # Generated HTML (output)
│   ├── templates/           # Jinja2 templates
│   ├── static_server.py     # FastAPI static server
│   ├── static_site_generator.py  # Site generator
│   └── json_storage.py      # JSON data helpers
├── data/
│   ├── wines.json           # Wine data
│   ├── matches.json         # Wine-Systembolaget matches
│   ├── toplists.json        # Toplist metadata
│   └── stats.json           # Statistics
├── docker-compose.yaml
├── Dockerfile.web
└── Makefile
```

## 🔄 Updating Content

### Full Data Refresh
Scrape new wines from Vivino and match with Systembolaget:
```bash
make update     # Full pipeline: scrape → match → generate → restart
```

### Adding a New Toplist
```bash
make scrape-url URL=https://www.vivino.com/toplists/your-toplist-here
make match
make generate
make restart
```

### Fix Missing Wine Images

**Finding the Wine ID:**
The wine ID format is `toplist_<toplist_id>_<rank>`. You can find it:
- In the browser URL: `http://localhost:8005/wine/toplist_vivino_under_100_21`
- From the wine detail page title

**Finding the Image URL:**
1. Go to the wine page on [Vivino.com](https://www.vivino.com)
2. Right-click on the wine bottle image
3. Select "Copy image address"
4. The URL should look like: `https://images.vivino.com/thumbs/xxxxxx_pb_x300.png`

**Commands:**
```bash
# Interactive mode - prompts for each missing image
make fix-images

# Direct mode - set specific wine image
make fix-image ID=toplist_vivino_under_100_21 URL=https://images.vivino.com/thumbs/xxx_pb_x300.png

# Then regenerate the site
make generate
```

**Example workflow:**
```bash
# 1. Find the wine that needs an image
#    Visit: http://localhost:8005/wine/toplist_vivino_under_100_21
#    Note: Shows "No image available"

# 2. Find the Vivino image URL
#    Search Vivino for "Giacosa Fratelli Nebbiolo"
#    Right-click bottle image → Copy image address

# 3. Set the image
make fix-image ID=toplist_vivino_under_100_21 URL=https://images.vivino.com/thumbs/abc123_pb_x300.png

# 4. Regenerate site
make generate
```

### After Manual JSON Edits
```bash
make generate   # Regenerate HTML
make restart    # Restart server
```

## ⚙️ Configuration

The static site requires no configuration for basic operation.

Optional environment variables for development:
```bash
# Telegram Notifications (for data pipeline)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

## 🎨 Design

Modern, clean UI inspired by qui design system:
- Light theme optimized for wine images
- Color-coded match percentage badges
- Emoji-based food pairings
- Responsive mobile design
- Smooth transitions and shadows

## 🛠️ Development

### Local Development (without Docker)

```bash
cd app
pip install -r requirements_web.txt
python static_site_generator.py  # Generate site
python -m uvicorn static_server:app --reload --port 8000
```

### Template Changes

Templates are in `app/templates/`:
- `base.html` - Base layout
- `index.html` - Homepage
- `filters.html` - Filter page with client-side search
- `toplist.html` - Individual toplist pages
- `wine_detail.html` - Wine detail pages

After template changes:
```bash
make generate
```

## 📊 Data Format

### wines.json
```json
{
  "id": "vivino_123",
  "name": "Wine Name",
  "rating": 4.2,
  "country": "France",
  "image_url": "https://...",
  "simplified_food_pairings": ["beef", "cheese"]
}
```

### matches.json
```json
{
  "vivino_wine_id": "vivino_123",
  "systembolaget_product_id": "7727601",
  "match_score": 85.5,
  "systembolaget_product": {
    "full_name": "Wine at Systembolaget",
    "price": 149.0
  }
}
```

---

**Enjoy discovering amazing wines! 🍷**
