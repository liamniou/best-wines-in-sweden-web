#!/bin/bash

# Best Wines Sweden - Web Application Startup Script

set -e

echo "🍷 Starting Best Wines Sweden Web Application..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  Creating .env file with default values..."
    cat > .env << EOF
# Database Configuration
POSTGRES_PASSWORD=postgres123

# Google Gemini API Key (optional - enables AI wine matching)
# Get yours at: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_gemini_api_key_here

# Wine Matching Threshold (default: 70.0)
# Only wines with matching scores above this percentage will be stored
MATCH_THRESHOLD=70.0

# Telegram Notifications (optional - enables notifications when lists are updated)
# Create a bot: https://t.me/BotFather
# Get chat ID: Send message to your bot, then visit: https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here

# Base URL for wine list links (optional - defaults to wines.tokyo3.eu)
WINE_BASE_URL=https://wines.tokyo3.eu

# Optional: Enable SQL debugging
SQL_ECHO=false
EOF
    echo "📝 Please edit .env file and add your API keys:"
    echo "   - Systembolaget API key (required)"
    echo "   - Gemini API key (optional, for AI wine matching)"
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Build and start services
echo "🔨 Building Docker images..."
docker-compose -f docker-compose.yaml build

echo "🚀 Starting database..."
docker-compose -f docker-compose.yaml up -d postgres

echo "⏳ Waiting for database to be ready..."
sleep 10

# Check if database is ready
until docker-compose -f docker-compose.yaml exec postgres pg_isready -U postgres -d best_wines > /dev/null 2>&1; do
    echo "⏳ Waiting for database..."
    sleep 3
done

echo "✅ Database is ready!"

# Initialize database
echo "🗄️  Initializing database..."
docker-compose -f docker-compose.yaml run --rm pipeline python data_pipeline.py --init-db

# Start web application
echo "🌐 Starting web application..."
docker-compose -f docker-compose.yaml up -d web

echo "⏳ Waiting for web application to start..."
sleep 5

# Check if web app is ready
until curl -s http://localhost:8000/health > /dev/null 2>&1; do
    echo "⏳ Waiting for web application..."
    sleep 3
done

echo ""
echo "🎉 Best Wines Sweden is now running!"
echo ""
echo "📍 Web Application: http://localhost:8000"
echo "🗄️  Database: localhost:5432 (postgres/postgres123)"
echo ""
echo "📊 To sync data from Vivino, run:"
echo "   docker-compose -f docker-compose.yaml run --rm pipeline python data_pipeline.py --sync-all"
echo ""
echo "📝 To view logs:"
echo "   docker-compose -f docker-compose.yaml logs -f"
echo ""
echo "🛑 To stop the application:"
echo "   docker-compose -f docker-compose.yaml down"
echo ""

# Optional: Open browser
if command -v open > /dev/null 2>&1; then
    echo "🌐 Opening web browser..."
    open http://localhost:8000
elif command -v xdg-open > /dev/null 2>&1; then
    echo "🌐 Opening web browser..."
    xdg-open http://localhost:8000
fi