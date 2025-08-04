# Price Change Dashboard

A beautiful, fast FastAPI dashboard for monitoring price changes across Japanese marketplaces using the canonical product system.

## Features

✨ **Real-time Data**: View latest price changes from canonical product system
🧠 **AI Insights**: Ask questions about your price data using OpenAI integration
📊 **Price Changes**: Monitor price fluctuations across all tracked products
🎯 **Product Details**: View detailed product information with platform data
📈 **Canonical System**: Smart product deduplication and change tracking
🔄 **Live Updates**: Dashboard updates automatically using HTMX

## Quick Start

## Quick Start

```bash
# From project root - start the dashboard
uv run uvicorn dashboard.app:app --host 0.0.0.0 --port 8000 --reload
```

### Using Python CLI

```bash
# From project root
uv run python dashboard/cli.py
```

## Dashboard URL

Once running, access the dashboard at: **http://localhost:8000**

## Dashboard Tabs

### 🧠 AI Insights Tab (Default)
- Ask natural language questions about your price data
- Powered by OpenAI API (optional - falls back to rule-based insights)
- Get insights on price trends, best deals, and market patterns
- Real-time analysis of your canonical product database

### � Price Changes Tab  
- Monitor price changes from the canonical product system
- See real-time price fluctuations with old vs new prices
- Track price changes across Amazon JP, Rakuten, Yahoo Shopping
- Filter changes by platform and view detailed product information

### 📋 Batch Results Tab
- View historical batch scraping results
- Browse by scraping sessions and keywords
- See product counts and platform coverage
- Click "View Products" to see detailed product listings

### 🏷️ Keywords Tab
- Browse all tracked keywords in the canonical system
- Click any keyword to view its price history and current products
- See platform distribution and price ranges

## Search Functionality

- Type in the search box on each tab for real-time filtering
- AI Insights: Ask questions in natural language
- Price Changes: Filter by product title or platform
- Batch Results: Filter by keyword or filename
- Keywords: Search through tracked keywords

## Data Sources

The dashboard loads data from:
- **Canonical System**: `data/canonical/products.json` - Master product database with price history
- **Batch Results**: `data/batch/results/` - Raw scraping session data
- **AI Integration**: OpenAI API for intelligent insights (optional)

## Configuration

Set up your environment variables in `.env`:
```bash
OPENAI_API_KEY=your_openai_api_key_here  # Optional, for AI insights
```

## Dependencies

Dashboard runs on the main project's UV environment with:
- FastAPI for the web framework
- Jinja2 for templating 
- HTMX for dynamic interactions
- Tailwind CSS for styling
- OpenAI API for intelligent insights (optional)

## Live Updates

- Uses HTMX for seamless UI updates without page refresh
- Canonical system data is loaded on-demand
- AI insights are generated in real-time
- Price changes update automatically as canonical database changes
