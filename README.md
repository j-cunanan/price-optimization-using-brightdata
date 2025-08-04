# 🚀 Japanese Marketplace Price Monitor

A comprehensive price monitoring ```
scrape_everything/
├── 🚀 price_monitor.sh           # Main automation script
├── 📋 QUICK_START.md             # Complete usage guide  
├── 📊 sample_keywords.txt        # Your search keywords
├── 🌐 dashboard/                 # Web interface
├── 📁 data/
│   ├── canonical/                # Master product database
│   ├── batch/results/           # Raw scraping results  
│   └── monitor.log              # Activity logs
└── 🔧 src/                      # Core scraping engine
    ├── cli/                     # Command-line tools
    │   ├── import_batch_results.py  # Import batch data
    │   └── monitor_canonical.py     # Monitor system
    ├── brightdata/              # Bright Data integration
    └── canonical_products_simple.py # Product management
```anese e-commerce platforms (Amazon.jp, Rakuten, Yahoo Shopping) powered by Bright Data's premium proxy network.

## ⚡ Quick Start

**Want to get started immediately?** See [QUICK_START.md](QUICK_START.md) for the single-command setup!

```bash
# Complete workflow: scrape → import → monitor → dashboard
./price_monitor.sh -d
```

## 🎯 Key Features

- **🏪 Multi-platform**: Amazon JP, Rakuten, Yahoo Shopping  
- **💰 Price Tracking**: Automatic price change detection
- **📊 Dashboard**: Real-time web interface at http://localhost:8000
- **🔄 Automation**: Single command handles entire workflow
- **🌐 Bright Data**: Premium proxy network with anti-detection
- **📈 Canonical System**: Smart product deduplication and tracking

## 📋 Prerequisites

- Python 3.10+ 
- UV package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Chrome/Chromium browser
- Bright Data account (for premium features)

## 🚀 Installation

```bash
git clone <your-repo-url>
cd scrape_everything
uv sync
cp .env.example .env  # Add your Bright Data credentials
```

**Most Common Use Cases:**

```bash
# Daily status check (30 seconds)
./price_monitor.sh --monitor-only

# Weekly full update (5-10 minutes)  
./price_monitor.sh -d

# Check specific products
echo "iPhone 15 Pro" > temp_keywords.txt
./price_monitor.sh -k temp_keywords.txt -l 20
```

**See [QUICK_START.md](QUICK_START.md) for all commands and options!**

## 📊 What You Get

- **📁 Product Database**: `data/canonical/products.json` - Your master product catalog
- **💰 Price Changes**: Real-time detection of price drops and increases  
- **📈 Dashboard**: Beautiful web interface at http://localhost:8000
- **📋 Reports**: Detailed logs in `data/monitor.log`
- **🔄 Automation**: Runs completely hands-free

## 🏗️ Architecture

```
./price_monitor.sh
├── 🔍 Discovery: Scrape marketplaces using Bright Data
├── � Import: Process results into canonical database  
├── � Monitor: Detect price changes and trends
└── 🌐 Dashboard: Visualize data in web interface
```

## 📁 Project Structure

```
scrape_everything/
├── 🚀 price_monitor.sh           # Main automation script
├── 📋 QUICK_START.md             # Complete usage guide  
├── 📊 sample_keywords.txt        # Your search keywords
├── 🌐 dashboard/                 # Web interface
├── 📁 data/
│   ├── canonical/                # Master product database
│   ├── batch/results/           # Raw scraping results  
│   └── monitor.log              # Activity logs
└── � src/                      # Core scraping engine
    ├── brightdata/              # Bright Data integration
    └── canonical_products_simple.py # Product management
```

## 🚀 Next Steps

1. **Start here**: Read [QUICK_START.md](QUICK_START.md) 
2. **Dashboard**: Check [dashboard/README.md](dashboard/README.md)
3. **First run**: `./price_monitor.sh --monitor-only`
4. **Weekly update**: `./price_monitor.sh -d`

## 📞 Support

For questions about Bright Data integration or advanced features, check the inline documentation or logs at `data/monitor.log`.

---

**🎯 This system is designed for simplicity: One script, one command, complete price monitoring!**
TIMEOUT=30

# User agent rotation
ROTATE_USER_AGENTS=true

# Output settings
DEFAULT_OUTPUT_FORMAT=csv
SAVE_IMAGES=false

# Email alerts (optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USER=your@email.com
EMAIL_PASS=your_app_password
```

## CLI Options

```bash
# Search options
--search, -s KEYWORD          Search keyword (required)
--platforms, -p PLATFORMS     Specific platforms: amazon_jp, rakuten, mercari, yahoo_shopping
--max-results, -m NUMBER      Maximum results per platform (default: 20)

# Filters
--min-price PRICE            Minimum price in JPY
--max-price PRICE            Maximum price in JPY
--condition CONDITION        Product condition: new, like_new, good, acceptable, poor

# Output options
--output, -o FILE            Output file (CSV/JSON based on extension)
--format, -f FORMAT          Output format: csv, json (default: csv)
--show-top NUMBER           Show top N lowest price products (default: 10)
--show-comparison           Show platform comparison statistics

# Configuration
--log-level LEVEL           Logging level: DEBUG, INFO, WARNING, ERROR
--concurrent NUMBER         Max concurrent requests (default: 5)
--delay SECONDS            Delay between requests (default: 1.0)
```

## Scraping Method Comparison

| Feature | DIY Scraping | Bright Data API |
|---------|-------------|-----------------|
| **Cost** | Free | Paid service |
| **Setup** | Quick, no external dependencies | Requires account setup |
| **Speed** | Very fast (direct HTTP) | Moderate (browser-based) |
| **Reliability** | Good for simple sites | Excellent for complex sites |
| **Anti-detection** | Basic (user agents, delays) | Advanced (residential IPs, browser profiles) |
| **Blocking resistance** | Moderate | High |
| **Maintenance** | Requires updates for site changes | Managed by Bright Data |
| **Proxy network** | None | Global proxy network |
| **JavaScript support** | Limited | Full (real browser) |

### When to use DIY Scraping:
- ✅ Learning and development
- ✅ Simple, stable websites
- ✅ High-volume, fast scraping
- ✅ Budget constraints
- ✅ Full control over logic

### When to use Bright Data:
- ✅ Production environments
- ✅ Complex, anti-bot protected sites
- ✅ Long-term stability requirements
- ✅ Compliance and legal considerations
- ✅ Reduced maintenance overhead

## Examples

### Search Nintendo Switch across all platforms (DIY)
```bash
uv run python main.py --search "Nintendo Switch" --max-results 5
```

### Search with Bright Data
```bash
uv run python -m src.brightdata.scraper "Nintendo Switch" --max-results 5
```

### Compare both methods
```bash
uv run python compare_scrapers.py "iPhone 15" --platforms amazon --output-file comparison.json
```

### Compare prices on Amazon and Rakuten
```bash
uv run python main.py --search "iPhone 15" --platforms amazon_jp rakuten --show-comparison
```

### Filter by price range and export to CSV
```bash
uv run python main.py --search "MacBook" --min-price 100000 --max-price 300000 --output macbooks.csv
```

### Search used items with condition filter
```bash
uv run python main.py --search "Camera" --condition good --platforms mercari --max-results 10
```

## Legal Notice

This scraper is for educational and research purposes only. Please:
- Respect robots.txt files
- Follow platform terms of service
- Use reasonable request rates
- Don't overload servers
- Consider using official APIs when available
- Review Bright Data's terms of service for commercial usage

## License

MIT License - see LICENSE file for details.
