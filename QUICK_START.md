# 🚀 **Single Command Price Monitor**

You now have **ONE SCRIPT** that does everything: `./price_monitor.sh`

## 🎯 **Most Common Commands**

### **Complete Workflow (Recommended)**
```bash
# Run everything: scrape → import → monitor → dashboard
./price_monitor.sh -d
```

### **Quick Status Check**
```bash
# Just check current price changes and system status
./price_monitor.sh --monitor-only
```

### **Daily Update**
```bash
# Scrape new data and update canonical system (no dashboard)
./price_monitor.sh
```

### **Large Discovery Session**  
```bash
# Scrape more products per keyword and start dashboard
./price_monitor.sh -l 50 -d
```

## 📋 **All Available Options**

| Command | Description |
|---------|-------------|
| `./price_monitor.sh` | Full workflow (scrape → import → monitor) |
| `./price_monitor.sh -d` | Full workflow + start dashboard |
| `./price_monitor.sh --monitor-only` | Just check current status |
| `./price_monitor.sh --scrape-only -l 20` | Just scrape (20 per keyword) |
| `./price_monitor.sh --import-only` | Just process existing batch files |
| `./price_monitor.sh -p "amazon rakuten"` | Only scrape specific platforms |
| `./price_monitor.sh -q` | Run quietly (log to file only) |
| `./price_monitor.sh -l 100 -d -q` | Big scrape, quiet, with dashboard |

## 🔄 **What The Script Does**

**Phase 1: Discovery 🔍**
- Scrapes your keywords from `sample_keywords.txt`
- Searches Amazon JP, Rakuten, Yahoo Shopping
- Saves results to `data/batch/results/`

**Phase 2: Import 📊** 
- Processes all batch results
- Deduplicates products using URLs/titles
- Detects price changes since last run
- Updates canonical database

**Phase 3: Monitor 💰**
- Shows current system stats
- Lists recent price changes with details
- Provides recommendations
- Displays platform distribution

**Phase 4: Dashboard 🌐** (Optional with `-d`)
- Starts web interface at http://localhost:8000
- Visual charts and tables
- Real-time price change tracking

## 📁 **Files Created**

- **Log**: `data/monitor.log` - All activity logged here
- **Keywords**: `sample_keywords.txt` - Products to search for
- **Data**: `data/canonical/` - Your product database
- **Batches**: `data/batch/results/` - Raw scraping results

## ⚡ **Quick Examples**

```bash
# Morning check (30 seconds)
./price_monitor.sh --monitor-only

# Weekly update (5-10 minutes)  
./price_monitor.sh -l 40 -d

# Emergency check on specific products
echo "SONY A7 IV" > temp_keywords.txt
./price_monitor.sh -k temp_keywords.txt -l 10
```

## 🎯 **Recommended Schedule**

**Daily (1 minute):**
```bash
./price_monitor.sh --monitor-only
```

**Weekly (10 minutes):**
```bash  
./price_monitor.sh -d
```

**As Needed:**
```bash
# Add new keywords to sample_keywords.txt, then:
./price_monitor.sh -l 50
```

---

**🏆 You now have a SINGLE COMMAND that handles your entire price monitoring workflow!**
