# Japanese Marketplace Scraper - Bright Data Edition

## 🚀 Overview
A comprehensive Python scraping solution for Japanese e-commerce marketplaces powered by Bright Data's premium proxy network and browser automation.

## 🏪 Supported Marketplaces

### Bright Data Scrapers  
- **Amazon Japan** (`amazon_jp`) - ✅ Fully tested & validated
- **Rakuten** (`rakuten`) - ✅ Implemented with JavaScript parsing
- **Mercari** (`mercari`) - ✅ Implemented with JavaScript parsing
- **Yahoo Shopping** (`yahoo_shopping`) - ✅ Implemented with JavaScript parsing

## 🔧 Technical Features

### Architecture
- **Bright Data Integration**: Premium proxy network with built-in anti-bot detection
- **Browser Automation**: Selenium-based scraping with Chrome extension proxy authentication
- **JavaScript Execution**: Full JavaScript rendering for dynamic content
- **Error Handling**: Comprehensive retry logic and error recovery
- **Logging**: Detailed logging with loguru
- **Configuration**: Environment-based configuration

### Data Extraction
- **Product Information**: Title, price, URL, images, ratings, reviews
- **Price Parsing**: Intelligent Japanese yen price extraction
- **Rating Extraction**: Star ratings and review counts
- **Seller Information**: Store/seller name extraction

### Bright Data Features
- **Proxy Authentication**: Automatic Chrome extension for proxy auth
- **JavaScript Parsing**: Browser-based JavaScript execution for reliable extraction
- **Anti-Bot Evasion**: Built-in proxy rotation and session management
- **Dynamic Content**: Handles JavaScript-rendered content

## 📊 Batch Processing Capabilities

### Performance Features
- **Concurrent Processing**: Configurable concurrent request limits
- **Rate Limiting**: Intelligent delays between requests
- **Progress Tracking**: Real-time progress monitoring with ETA
- **Resume Support**: Checkpoint-based resumption of interrupted batches
- **Error Recovery**: Automatic retry with exponential backoff

### Scalability
- **Batch Sizes**: Handle 1000+ products efficiently
- **Memory Management**: Checkpoint-based memory optimization
- **Result Storage**: JSON-based result persistence
- **Failed Item Tracking**: Separate tracking for retry operations

## 🛠️ Dependencies & Setup

### Core Dependencies
```toml
[dependencies]
aiohttp = "^3.9.0"
beautifulsoup4 = "^4.12.0"
selenium = "^4.15.0"
loguru = "^0.7.0"
pydantic = "^2.5.0"
python-dotenv = "^1.0.0"
tenacity = "^8.2.0"
```

### Environment Configuration
```bash
# Bright Data Configuration
BRIGHT_DATA_USERNAME=your_username
BRIGHT_DATA_PASSWORD=your_password
BRIGHT_DATA_ZONE=datacenter
BRIGHT_DATA_SESSION_ID=optional_session_id
```

## 🚦 Usage Examples

### Basic Bright Data Scraping
```python
from src.brightdata.scraper import BrightDataMarketplaceScraper
from src.brightdata.connection import BrightDataConfig
from src.models import Platform

config = BrightDataConfig.from_env()
scraper = BrightDataMarketplaceScraper(config)
products = await scraper.search_platform(Platform.AMAZON_JP, "iPhone", 10)
```

### Batch Processing
```bash
# Process a file with 1000 keywords
uv run python batch_scraper_cli.py sample_keywords.txt --max-concurrent 5 --delay 2.0

# Search specific platforms only
uv run python batch_scraper_cli.py keywords.csv --platforms amazon_jp rakuten --max-results 10

# Resume interrupted batch
uv run python batch_scraper_cli.py keywords.txt --batch-id my_batch --resume
```

### Price Monitoring Dashboard
```bash
# Start the dashboard
uv run uvicorn dashboard.app:app --host 0.0.0.0 --port 8000 --reload

# Access at http://localhost:8000
# View price changes, trends, and AI insights
```

## 🔍 Key Innovations

### Bright Data Integration
1. **Chrome Extension Proxy Auth**: Eliminates manual proxy authentication
2. **JavaScript-in-Browser Parsing**: More reliable than HTML parsing
3. **Dynamic Element Detection**: Adapts to changing website structures
4. **Session Management**: Maintains consistent browsing sessions

### Error Resilience
1. **Multi-Level Fallbacks**: JavaScript → Selenium → Basic parsing
2. **Retry Logic**: Configurable retry attempts with exponential backoff
3. **Graceful Degradation**: Continues with partial results on failures
4. **Detailed Logging**: Comprehensive error tracking and debugging

## 📈 Performance Characteristics

### Bright Data Scrapers
- **Speed**: Optimized with intelligent rate limiting  
- **Resource Usage**: Moderate (browser automation + proxy overhead)
- **Reliability**: Excellent for dynamic content and anti-bot evasion
- **Success Rate**: High success rates due to premium proxy infrastructure
- **Cost**: Paid service with superior success rates and compliance

### Batch Processing Performance
- **Throughput**: 3-5 seconds per product per platform
- **Concurrency**: Configurable (3-15 concurrent requests recommended)
- **Memory Usage**: 2-4GB for 1000+ products with checkpointing
- **Recovery**: Automatic resumption from checkpoints

## 🎯 Use Cases

### E-commerce Price Monitoring
- **Multi-platform price comparison**
- **Stock availability tracking**
- **Historical price analysis**

### Market Research
- **Product trend analysis**
- **Competitor monitoring**
- **Market share analysis**

### Business Intelligence
- **Pricing strategy optimization**
- **Product catalog expansion**
- **Customer sentiment analysis**

## 🔄 Future Enhancements

### Planned Features
- [ ] Real-time WebSocket updates for price changes
- [ ] Advanced filtering and search criteria
- [ ] API endpoint for external integrations
- [ ] Enhanced dashboard with more visualizations
- [ ] Mobile-responsive dashboard design
- [ ] Email/SMS price alert notifications

### Additional Marketplaces
- [ ] Qoo10 Japan
- [ ] AU PAY Market
- [ ] Lotte Shopping
- [ ] Wowma! (au PAY Market)

## 🛠️ Core Components

### Main Scripts
- `batch_scraper_cli.py` - CLI for batch processing operations
- `dashboard/app.py` - FastAPI dashboard with AI insights
- `price_monitor.sh` - Bash automation script

### Core Modules
- `src/brightdata/` - Bright Data scraper implementations
- `src/batch_scraper.py` - Batch processing engine
- `src/canonical_products_simple.py` - Product deduplication and tracking
- `src/change_detector.py` - Price change detection system
- `src/models.py` - Data models and schemas
