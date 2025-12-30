# Makefile for Best Wines Sweden

.PHONY: help build generate start stop restart logs clean scrape scrape-url fix-images fix-image match update

# Default target
help:
	@echo "Best Wines Sweden - Available Commands:"
	@echo ""
	@echo "  make scrape             - Scrape all URLs from scrape_urls.json"
	@echo "  make scrape-url URL=... - Add URL to list and scrape it"
	@echo "  make fix-images         - Add missing images interactively"
	@echo "  make fix-image ID=... URL=... - Fix specific wine image"
	@echo "  make match              - Match Vivino wines with Systembolaget"
	@echo "  make generate       - Generate static site from JSON data"
	@echo "  make update         - Full update: scrape → match → generate → restart"
	@echo ""
	@echo "  make build          - Build Docker images"
	@echo "  make start          - Start the web server"
	@echo "  make stop           - Stop all containers"
	@echo "  make restart        - Restart the web server"
	@echo "  make logs           - View web server logs"
	@echo "  make shell          - Open shell in web container"
	@echo "  make clean          - Remove generated files and containers"
	@echo ""
	@echo "Legacy (with PostgreSQL):"
	@echo "  make legacy-start   - Start with PostgreSQL"
	@echo "  make legacy-stop    - Stop PostgreSQL stack"
	@echo ""

# Build Docker images
build:
	docker compose build

# Scrape saved Vivino toplist with images
scrape:
	@echo "Scraping Vivino toplists..."
	docker compose run --rm generator python scrape_vivino_toplist.py
	@echo "Scraping complete!"

# Scrape specific Vivino toplist URL (adds to scrape_urls.json)
scrape-url:
ifndef URL
	@echo "Usage: make scrape-url URL=https://www.vivino.com/toplists/..."
	@exit 1
endif
	@echo "Scraping: $(URL)"
	docker compose run --rm generator python scrape_vivino_toplist.py --url "$(URL)"
	@echo "Scraping complete!"

# Fix missing images interactively
fix-images:
	@echo "Fixing missing images interactively..."
	docker compose run --rm -it generator python scrape_vivino_toplist.py --fix-images
	@echo "Done!"

# Fix specific wine image
# Usage: make fix-image ID=toplist_vivino_under_100_21 URL=https://...
fix-image:
ifndef ID
	@echo "Usage: make fix-image ID=<wine_id> URL=<image_url>"
	@echo "Example: make fix-image ID=toplist_vivino_under_100_21 URL=https://images.vivino.com/thumbs/xxx_pb_x300.png"
	@exit 1
endif
ifndef URL
	@echo "Usage: make fix-image ID=<wine_id> URL=<image_url>"
	@exit 1
endif
	docker compose run --rm generator python scrape_vivino_toplist.py --fix-image "$(ID)" "$(URL)"
	@echo "Done! Run 'make generate' to update the site."

# Match Vivino wines with Systembolaget
match:
	@echo "Matching wines with Systembolaget..."
	docker compose run --rm generator python match_toplist_wines.py
	@echo "Matching complete!"

# Generate static site
generate:
	@echo "Generating static site..."
	docker compose run --rm generator python static_site_generator.py
	@echo "Static site generated successfully!"

# Full update: scrape → match → generate → restart
update: scrape match generate restart
	@echo "Full update complete! Site available at http://localhost:8005"

# Start web server
start:
	docker compose up -d web
	@echo "Web server started at http://localhost:8005"

# Stop all containers
stop:
	docker compose down

# Restart web server
restart:
	docker compose restart web

# View logs
logs:
	docker compose logs -f web

# Open shell in container
shell:
	docker compose exec web /bin/bash

# Clean up
clean:
	docker compose down -v
	rm -rf app/static_site/*
	@echo "Cleaned up containers and generated files"

# Full rebuild (without scraping)
rebuild: build generate restart
	@echo "Rebuild complete!"

# Full rebuild with fresh data
rebuild-full: build scrape match generate restart
	@echo "Full rebuild with fresh data complete!"

# Legacy mode with PostgreSQL
legacy-start:
	docker compose --profile legacy up -d

legacy-stop:
	docker compose --profile legacy down

# Development helpers
dev-generate:
	cd app && python static_site_generator.py

dev-serve:
	cd app && python -m uvicorn static_server:app --reload --port 8000
