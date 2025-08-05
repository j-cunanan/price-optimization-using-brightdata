# 🚀 Japanese Marketplace Price Monitor

A comprehensive price monitoring system for Japanese e-commerce platforms (Amazon.jp, Rakuten, Yahoo Shopping) powered by Bright Data's premium proxy network.

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
cd price-optimization-using-brightdata
uv sync
cp .env.example .env  # Add your Bright Data credentials
```

**Most Common Use Cases:**

```bash
# Daily status check and view results (30 seconds + dashboard stays open)
./price_monitor.sh --monitor-only -d

# Weekly full update with dashboard (5-10 minutes + dashboard stays open)  
./price_monitor.sh -d

# Just start the dashboard (stays open until Ctrl+C)
./price_monitor.sh --dashboard-only

# Check specific products with dashboard
echo "iPhone 15 Pro" > temp_keywords.txt
./price_monitor.sh -k temp_keywords.txt -l 20 -d
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
├── 📦 Import: Process results into canonical database  
├── 📊 Monitor: Detect price changes and trends
└── 🌐 Dashboard: Visualize data in web interface
```

## 📁 Project Structure

```
price-optimization-using-brightdata/
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
```

## 🚀 Next Steps

1. **Start here**: Read [QUICK_START.md](QUICK_START.md) 
2. **Dashboard**: Check [dashboard/README.md](dashboard/README.md)
3. **First run**: `./price_monitor.sh --monitor-only`
4. **Weekly update**: `./price_monitor.sh -d`

## 📞 Support

For questions about Bright Data integration or advanced features, check the inline documentation or logs at `data/monitor.log`.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚖️ Legal Notice

This software is for educational and research purposes. Please:
- Respect robots.txt and terms of service
- Use reasonable request rates
- Review Bright Data's terms for commercial usage
- Comply with applicable laws and regulations

---

**🎯 This system is designed for simplicity: One script, one command, complete price monitoring!**
