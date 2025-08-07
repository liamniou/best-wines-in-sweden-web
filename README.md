# 🍷 Best Wines Sweden

A modern web application that finds the best wines from Vivino toplists available at Systembolaget (Swedish alcohol retailer). Features advanced filtering, real-time search, and detailed wine information.

## ✨ Features

- **🔍 Advanced Filtering** - Filter by price, rating, country, wine style
- **📱 Mobile Optimized** - Perfect experience on all devices  
- **⚡ Real-time Search** - Instant results as you type
- **🍷 Wine Details** - Comprehensive wine information pages
- **🔗 Direct Purchase** - Links to buy at Systembolaget
- **📊 Rich Analytics** - Wine statistics and insights

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Google Gemini API key ([Get one here](https://aistudio.google.com/app/apikey)) - Optional but recommended for AI-powered wine matching

### Installation

1. **Clone and start the application:**
   ```bash
   ./start_web.sh
   ```

2. **Open in browser:**
   ```
   http://localhost:8000
   ```

3. **Sync wine data:**
   ```bash
   docker-compose -f docker-compose.yaml run --rm pipeline python data_pipeline.py --sync-all
   ```

## ⚙️ Configuration

Create a `.env` file with your settings:

```bash
# Database
POSTGRES_PASSWORD=your_secure_password

# Google Gemini AI (optional - enables intelligent wine matching)
GEMINI_API_KEY=your_gemini_api_key

# Wine Matching Threshold (default: 70.0)
# Only wines with matching scores above this percentage will be stored
MATCH_THRESHOLD=70.0

# Telegram Notifications (optional - get notified when lists are updated)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# Base URL for wine list links (optional - defaults to wines.tokyo3.eu)
WINE_BASE_URL=https://wines.tokyo3.eu
```

### Setting up Telegram Notifications (Optional)

1. **Create a Telegram Bot**:
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Use `/newbot` command and follow instructions
   - Save the bot token

2. **Get Your Chat ID**:
   - Send a message to your bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your chat ID in the response

## 📊 Wine Data Management

```bash
# Sync all toplists
docker-compose -f docker-compose.yaml run --rm pipeline python data_pipeline.py --sync-all

# Sync specific toplist
docker-compose -f docker-compose.yaml run --rm pipeline python data_pipeline.py --sync-toplist 1

# Check sync status
docker-compose -f docker-compose.yaml run --rm pipeline python data_pipeline.py --status
```

## 🛠️ Development

- **Web App**: FastAPI backend with modern Bootstrap frontend
- **Database**: PostgreSQL with optimized schema
- **Data Pipeline**: Automated sync from Vivino to database

## 🤖 AI Configuration

The application supports AI-powered wine matching and food pairing suggestions with automatic fallback:

### Primary AI Service (Gemini)
```bash
export GEMINI_API_KEY="your_gemini_api_key_here"
```

### Fallback AI Service (OpenAI)
```bash
export OPENAI_API_KEY="your_openai_api_key_here"
```

**Fallback Behavior**: If Gemini fails or is unavailable, the system automatically falls back to OpenAI. If both are unavailable, it uses rule-based fallback logic.

## 📚 Documentation

- [Migration Guide](migration_guide.md) - Detailed setup instructions
- [Migration Summary](MIGRATION_SUMMARY.md) - Complete feature overview

---

**Enjoy discovering amazing wines! 🍷**