# Makefile for Best Wines Sweden

.PHONY: help build generate start stop restart logs clean scrape scrape-url fix-image match update clear-data clear-toplists clear-toplist

# Default target
help:
	@echo "Best Wines Sweden - Available Commands:"
	@echo ""
	@echo "Data Pipeline (interactive or with args):"
	@echo "  make scrape [LIST=<id>] [ALL=1]  - Scrape toplists"
	@echo "  make scrape-url [URL=<url>]      - Add new toplist"
	@echo "  make match [LIST=<id>] [ALL=1]   - Match wines with Systembolaget"
	@echo "  make fix-image [ID=<id>] [URL=<url>] - Fix wine image"
	@echo "  make generate                    - Generate static site"
	@echo "  make update                      - Full: scrape → match → generate → restart"
	@echo ""
	@echo "Server:"
	@echo "  make build      - Build Docker images"
	@echo "  make start      - Start the web server"
	@echo "  make stop       - Stop all containers"
	@echo "  make restart    - Restart the web server"
	@echo "  make logs       - View web server logs"
	@echo "  make shell      - Open shell in container"
	@echo ""
	@echo "Data Management (interactive or with args):"
	@echo "  make clear-toplist [ID=<id>]  - Remove specific toplist"
	@echo "  make clear-data [YES=1]       - Remove ALL data"
	@echo "  make clear-toplists [YES=1]   - Remove all toplists"
	@echo "  make clean                    - Remove generated HTML and containers"
	@echo ""

# Build Docker images
build:
	docker compose build

# Scrape saved Vivino toplist with images
# Usage: make scrape [LIST=<id>] [ALL=1]
scrape:
ifdef LIST
	@echo "Scraping toplist: $(LIST)..."
	docker compose run --rm generator python scrape_vivino_toplist.py --list "$(LIST)"
	@echo "Scraping complete!"
else ifdef ALL
	@echo "Scraping all toplists..."
	docker compose run --rm generator python scrape_vivino_toplist.py
	@echo "Scraping complete!"
else
	@echo "Available toplists:"
	@cat data/toplists.json 2>/dev/null | python3 -c "import sys,json; [print(f'  - {t[\"id\"]}') for t in json.load(sys.stdin)]" || echo "  (none)"
	@echo ""
	@read -p "Select [a=all, list_id, Enter=cancel]: " choice; \
	if [ "$$choice" = "a" ] || [ "$$choice" = "A" ]; then \
		echo "Scraping all toplists..."; \
		docker compose run --rm generator python scrape_vivino_toplist.py; \
		echo "Scraping complete!"; \
	elif [ -n "$$choice" ]; then \
		echo "Scraping toplist: $$choice..."; \
		docker compose run --rm generator python scrape_vivino_toplist.py --list "$$choice"; \
		echo "Scraping complete!"; \
	else \
		echo "Cancelled."; \
	fi
endif

# Scrape specific Vivino toplist URL (adds to toplists.json)
scrape-url:
ifdef URL
	@echo "Scraping: $(URL)"
	docker compose run --rm generator python scrape_vivino_toplist.py --url "$(URL)"
	@echo "Scraping complete!"
else
	@read -p "Enter Vivino toplist URL: " url; \
	if [ -n "$$url" ]; then \
		echo "Scraping: $$url"; \
		docker compose run --rm generator python scrape_vivino_toplist.py --url "$$url"; \
		echo "Scraping complete!"; \
	else \
		echo "Cancelled."; \
	fi
endif

# Fix specific wine image
fix-image:
ifdef ID
ifdef URL
	docker compose run --rm generator python scrape_vivino_toplist.py --fix-image "$(ID)" "$(URL)"
	@echo "Done! Run 'make generate' to update the site."
else
	@read -p "Enter image URL: " url; \
	if [ -n "$$url" ]; then \
		docker compose run --rm generator python scrape_vivino_toplist.py --fix-image "$(ID)" "$$url"; \
		echo "Done! Run 'make generate' to update the site."; \
	else \
		echo "Cancelled."; \
	fi
endif
else
	@echo "Wine ID format: toplist_<toplist_id>_<rank>"
	@echo "Example: toplist_best_wines_under_150_21"
	@echo ""
	@read -p "Enter wine ID: " id; \
	if [ -n "$$id" ]; then \
		read -p "Enter image URL: " url; \
		if [ -n "$$url" ]; then \
			docker compose run --rm generator python scrape_vivino_toplist.py --fix-image "$$id" "$$url"; \
			echo "Done! Run 'make generate' to update the site."; \
		else \
			echo "Cancelled."; \
		fi; \
	else \
		echo "Cancelled."; \
	fi
endif

# Match Vivino wines with Systembolaget
# Usage: make match [LIST=<id>] [ALL=1]
match:
ifdef LIST
	@echo "Matching toplist: $(LIST)..."
	docker compose run --rm generator python match_toplist_wines.py --list "$(LIST)"
	@echo "Matching complete!"
else ifdef ALL
	@echo "Matching all toplists..."
	docker compose run --rm generator python match_toplist_wines.py
	@echo "Matching complete!"
else
	@echo "Available toplists:"
	@cat data/toplists.json 2>/dev/null | python3 -c "import sys,json; [print(f'  - {t[\"id\"]}') for t in json.load(sys.stdin)]" || echo "  (none)"
	@echo ""
	@read -p "Select [a=all, list_id, Enter=cancel]: " choice; \
	if [ "$$choice" = "a" ] || [ "$$choice" = "A" ]; then \
		echo "Matching all toplists..."; \
		docker compose run --rm generator python match_toplist_wines.py; \
		echo "Matching complete!"; \
	elif [ -n "$$choice" ]; then \
		echo "Matching toplist: $$choice..."; \
		docker compose run --rm generator python match_toplist_wines.py --list "$$choice"; \
		echo "Matching complete!"; \
	else \
		echo "Cancelled."; \
	fi
endif

# Generate static site
generate:
	@echo "Generating static site..."
	docker compose run --rm generator python static_site_generator.py
	@echo "Static site generated successfully!"

# Full update: scrape → match → generate → restart (non-interactive)
update:
	@echo "Scraping all toplists..."
	@docker compose run --rm generator python scrape_vivino_toplist.py
	@echo "Matching all toplists..."
	@docker compose run --rm generator python match_toplist_wines.py
	@echo "Generating static site..."
	@docker compose run --rm generator python static_site_generator.py
	@docker compose restart web
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

# Clean up generated HTML
clean:
	docker compose down -v
	rm -rf app/static_site/*
	@echo "Cleaned up containers and generated files"

# Clear ALL data - start completely fresh
# Usage: make clear-data [YES=1]
clear-data:
ifdef YES
	@echo "Clearing ALL data..."
	@mkdir -p data
	@rm -f data/toplists.json data/wines.json data/matches.json data/stats.json
	@rm -rf app/static_site/images/wines/*
	@rm -rf app/static_site/wine/*
	@rm -rf app/static_site/toplist/*
	@echo '[]' > data/toplists.json
	@echo '[]' > data/wines.json
	@echo '[]' > data/matches.json
	@echo "✅ All data cleared! Run 'make scrape-url' to add a toplist."
else
	@echo "⚠️  This will remove ALL data (toplists, wines, matches, images)"
	@read -p "Are you sure? [y/N]: " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		echo "Clearing ALL data..."; \
		mkdir -p data; \
		rm -f data/toplists.json data/wines.json data/matches.json data/stats.json; \
		rm -rf app/static_site/images/wines/*; \
		rm -rf app/static_site/wine/*; \
		rm -rf app/static_site/toplist/*; \
		echo '[]' > data/toplists.json; \
		echo '[]' > data/wines.json; \
		echo '[]' > data/matches.json; \
		echo "✅ All data cleared! Run 'make scrape-url' to add a toplist."; \
	else \
		echo "Cancelled."; \
	fi
endif

# Clear toplists only
# Usage: make clear-toplists [YES=1]
clear-toplists:
ifdef YES
	@echo "Clearing toplists..."
	@mkdir -p data
	@rm -f data/toplists.json
	@rm -rf app/static_site/images/wines/*
	@rm -rf app/static_site/toplist/*
	@echo '[]' > data/toplists.json
	@echo "✅ Toplists cleared! Run 'make scrape-url' to add a toplist."
else
	@echo "⚠️  This will remove ALL toplists and their images"
	@read -p "Are you sure? [y/N]: " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		echo "Clearing toplists..."; \
		mkdir -p data; \
		rm -f data/toplists.json; \
		rm -rf app/static_site/images/wines/*; \
		rm -rf app/static_site/toplist/*; \
		echo '[]' > data/toplists.json; \
		echo "✅ Toplists cleared! Run 'make scrape-url' to add a toplist."; \
	else \
		echo "Cancelled."; \
	fi
endif

# Clear specific toplist by ID
clear-toplist:
ifdef ID
	@echo "Removing toplist: $(ID)..."
	@if [ -f data/toplists.json ]; then \
		python3 -c "import json; data=json.load(open('data/toplists.json')); data=[t for t in data if t['id']!='$(ID)']; json.dump(data,open('data/toplists.json','w'),indent=2)"; \
	fi
	@rm -rf app/static_site/images/wines/$(ID)
	@rm -f app/static_site/toplist/$(ID).html
	@echo "✅ Toplist '$(ID)' removed! Run 'make match && make generate' to update the site."
else
	@echo "Available toplists:"
	@cat data/toplists.json 2>/dev/null | python3 -c "import sys,json; [print(f'  - {t[\"id\"]}') for t in json.load(sys.stdin)]" || echo "  (none)"
	@echo ""
	@read -p "Enter toplist ID to remove (or press Enter to cancel): " id; \
	if [ -n "$$id" ]; then \
		echo "Removing toplist: $$id..."; \
		if [ -f data/toplists.json ]; then \
			python3 -c "import json; data=json.load(open('data/toplists.json')); data=[t for t in data if t['id']!='$$id']; json.dump(data,open('data/toplists.json','w'),indent=2)"; \
		fi; \
		rm -rf app/static_site/images/wines/$$id; \
		rm -f app/static_site/toplist/$$id.html; \
		echo "✅ Toplist '$$id' removed! Run 'make match && make generate' to update the site."; \
	else \
		echo "Cancelled."; \
	fi
endif

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
