# 🍷 Best Wines Sweden

Website that finds the best wines from Vivino toplists available at Systembolaget (Swedish alcohol retailer).

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose

### First Time Setup (from scratch)
```bash
# 1. Build Docker images
make build

# 2. Add your first Vivino toplist (prompts for URL)
make scrape-url

# 3. Match wines with Systembolaget (type 'a' for all)
make match

# 4. Generate the static website
make generate

# 5. Start the web server
make start
```

Then open: http://localhost:8005

### Daily Commands
```bash
make start    # Start server
make stop     # Stop server
make scrape   # Re-scrape toplists (interactive)
make match    # Re-match wines (interactive)
make generate # Regenerate HTML pages
make update   # Full pipeline: scrape → match → generate → restart
make logs     # View server logs
```

### Add a New Toplist
```bash
make scrape-url # Prompts for URL
make match      # Prompts: match all or specific list
make generate
```

## 📋 Available Commands

All commands are interactive when run without arguments.

### Data Pipeline
```bash
make scrape                    # Interactive: prompts for selection
make scrape ALL=1              # Non-interactive: scrape all toplists
make scrape LIST=<id>          # Non-interactive: scrape specific toplist

make scrape-url                # Interactive: prompts for URL
make scrape-url URL=<url>      # Non-interactive: add specific URL

make match                     # Interactive: prompts for selection
make match ALL=1               # Non-interactive: match all toplists
make match LIST=<id>           # Non-interactive: match specific toplist

make fix-image                 # Interactive: prompts for ID and URL
make fix-image ID=<id> URL=<url>  # Non-interactive

make generate                  # Generate static HTML site
make update                    # Full pipeline (non-interactive): scrape → match → generate → restart
```

### Server Management

```bash
make build   # Build Docker images
make start   # Start the web server (http://localhost:8005)
make stop    # Stop all containers
make restart # Restart the web server
make logs    # View web server logs
make shell   # Open shell in container
make clean   # Remove generated files and containers
make rebuild # Full rebuild and restart
```

## 🔄 Updating Content

### Full Data Refresh

Re-scrape all toplists, re-match with Systembolaget, and regenerate site:
```bash
make update # Full pipeline: scrape → match → generate → restart
```

### Adding a New Toplist

```bash
make scrape-url # Prompts for Vivino URL
make match      # Select the new toplist when prompted
make generate
```

### Refresh Existing Toplists Only
```bash
make scrape   # Prompts: scrape all or specific toplist
make match    # Prompts: match all or specific toplist
make generate # Regenerate HTML
```

### Data Management
```bash
make clear-toplist         # Interactive: prompts for selection
make clear-toplist ID=<id> # Non-interactive: remove specific toplist

make clear-data            # Interactive: prompts for confirmation
make clear-data YES=1      # Non-interactive: remove all data

make clear-toplists        # Interactive: prompts for confirmation
make clear-toplists YES=1  # Non-interactive: remove all toplists
```

### After Manual JSON Edits

```bash
make generate # Regenerate HTML
make restart  # Restart server
```

## ⚙️ Configuration

The static site requires no configuration for basic operation.

Optional environment variables for development:
```bash
# Telegram Notifications (for data pipeline)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
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
