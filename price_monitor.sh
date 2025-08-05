#!/bin/bash
# Price Monitor - Complete automated workflow for Japanese marketplace price tracking
# Usage: ./price_monitor.sh [OPTIONS]

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data"
KEYWORDS_FILE="$SCRIPT_DIR/sample_keywords.txt"
DASHBOARD_PORT=8000
LOG_FILE="$DATA_DIR/monitor.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Emojis
EMOJI_SEARCH="🔍"
EMOJI_IMPORT="📊"
EMOJI_MONITOR="💰"
EMOJI_DASHBOARD="🌐"
EMOJI_SUCCESS="✅"
EMOJI_ERROR="❌"
EMOJI_WARNING="⚠️"
EMOJI_INFO="ℹ️"

# Default options
SCRAPE_LIMIT=30
SKIP_SCRAPE=false
SKIP_IMPORT=false
SKIP_MONITOR=false
START_DASHBOARD=false
QUIET=false
PLATFORMS="amazon_jp rakuten yahoo_shopping"

# Logging function
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    if [[ ! $QUIET == true ]]; then
        case $level in
            "INFO")  echo -e "${BLUE}${EMOJI_INFO}${NC} $message" ;;
            "SUCCESS") echo -e "${GREEN}${EMOJI_SUCCESS}${NC} $message" ;;
            "ERROR") echo -e "${RED}${EMOJI_ERROR}${NC} $message" ;;
            "WARNING") echo -e "${YELLOW}${EMOJI_WARNING}${NC} $message" ;;
        esac
    fi
    
    # Always log to file
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}

# Help function
show_help() {
    cat << EOF
${CYAN}Price Monitor - Japanese Marketplace Price Tracking${NC}

${YELLOW}USAGE:${NC}
    ./price_monitor.sh [OPTIONS]

${YELLOW}OPTIONS:${NC}
    -h, --help              Show this help message
    -l, --limit N           Set scraping limit per keyword (default: 30)
    -k, --keywords FILE     Keywords file to use (default: sample_keywords.txt)
    -p, --platforms LIST    Platforms to scrape (default: "amazon_jp rakuten yahoo_shopping")
    -d, --dashboard         Start dashboard after monitoring
    -q, --quiet             Suppress console output (still logs to file)
    
    --skip-scrape          Skip the scraping phase
    --skip-import          Skip the import phase  
    --skip-monitor         Skip the monitoring phase
    --scrape-only          Only run scraping (skip import and monitor)
    --import-only          Only run import (skip scraping and monitor)
    --monitor-only         Only run monitoring (skip scraping and import)
    --dashboard-only       Only start dashboard (skip all other phases)

${YELLOW}EXAMPLES:${NC}
    ./price_monitor.sh                          # Full workflow with defaults
    ./price_monitor.sh -l 50 -d                # Scrape 50 per keyword, start dashboard
    ./price_monitor.sh --monitor-only -d       # Check status and start dashboard  
    ./price_monitor.sh --dashboard-only        # Just start dashboard
    ./price_monitor.sh --scrape-only -l 20     # Just scrape with limit 20
    ./price_monitor.sh -p "amazon_jp rakuten"     # Only scrape Amazon and Rakuten
    ./price_monitor.sh -q                      # Run quietly (log to file only)

${YELLOW}WORKFLOW:${NC}
    1. ${EMOJI_SEARCH} Discovery: Scrape new products from keywords
    2. ${EMOJI_IMPORT} Import: Process results into canonical system
    3. ${EMOJI_MONITOR} Monitor: Check for price changes and system health
    4. ${EMOJI_DASHBOARD} Dashboard: Optionally start web interface

${YELLOW}FILES:${NC}
    Log:           $LOG_FILE
    Keywords:      $KEYWORDS_FILE
    Data:          $DATA_DIR/
    Dashboard:     http://localhost:$DASHBOARD_PORT

EOF
}

# Check dependencies
check_dependencies() {
    log "INFO" "Checking dependencies..."
    
    if ! command -v uv &> /dev/null; then
        log "ERROR" "UV package manager not found. Please install UV first."
        exit 1
    fi
    
    if [[ ! -f "$KEYWORDS_FILE" ]]; then
        log "WARNING" "Keywords file not found: $KEYWORDS_FILE"
        log "INFO" "Creating sample keywords file..."
        cat > "$KEYWORDS_FILE" << 'EOF'
FUJIFILM X100V BODY JP
SONY A7 IV BODY JP
CANON RF 35MM F1.8 MACRO JP
SIGMA 24 70 DG DN SONY JP
NINTENDO SWITCH OLED POKEMON EDITION
PS5 SLIM FF7R BUNDLE
EOF
        log "SUCCESS" "Created sample keywords file: $KEYWORDS_FILE"
    fi
    
    # Check if virtual environment exists and Python packages are available
    if ! uv run python -c "from src.canonical_products_simple import SimpleCanonicalProducts" &> /dev/null; then
        log "ERROR" "Python dependencies not properly installed. Run 'uv sync' first."
        exit 1
    fi
    
    log "SUCCESS" "Dependencies check passed"
}

# Phase 1: Discovery (Scraping)
run_scraping() {
    if [[ $SKIP_SCRAPE == true ]]; then
        log "INFO" "Skipping scraping phase"
        return 0
    fi
    
    log "INFO" "${EMOJI_SEARCH} Starting discovery phase (scraping)..."
    log "INFO" "Keywords file: $KEYWORDS_FILE"
    log "INFO" "Limit per keyword: $SCRAPE_LIMIT"
    log "INFO" "Platforms: $PLATFORMS"
    
    local start_time=$(date +%s)
    
    # Run batch scraper
    if uv run python src/batch_scraper.py \
        "$KEYWORDS_FILE" \
        --platforms $PLATFORMS \
        --max-results "$SCRAPE_LIMIT"; then
        
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log "SUCCESS" "Scraping completed in ${duration}s"
        
        # Count new files
        local new_files=$(find "$DATA_DIR/batch/results" -name "*.json" -newer "$LOG_FILE" 2>/dev/null | wc -l || echo "0")
        log "INFO" "New batch files created: $new_files"
    else
        log "ERROR" "Scraping failed"
        return 1
    fi
}

# Phase 2: Import and Analysis
run_import() {
    if [[ $SKIP_IMPORT == true ]]; then
        log "INFO" "Skipping import phase"
        return 0
    fi
    
    log "INFO" "${EMOJI_IMPORT} Starting import phase (canonical processing)..."
    
    local start_time=$(date +%s)
    
    # Run import script
    if uv run python src/cli/import_batch_results.py --data-dir "$DATA_DIR"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log "SUCCESS" "Import completed in ${duration}s"
        
        # Get quick stats
        local stats=$(uv run python -c "
from src.canonical_products_simple import SimpleCanonicalProducts
import json
manager = SimpleCanonicalProducts('data')
stats = manager.get_stats()
changes = manager.get_price_changes()
print(f\"Products: {stats['total_canonical_products']}, Changes: {len(changes)}\")
" 2>/dev/null || echo "Stats unavailable")
        
        log "INFO" "Canonical system status: $stats"
    else
        log "ERROR" "Import failed"
        return 1
    fi
}

# Phase 3: Monitoring and Analysis
run_monitoring() {
    if [[ $SKIP_MONITOR == true ]]; then
        log "INFO" "Skipping monitoring phase"
        return 0
    fi
    
    log "INFO" "${EMOJI_MONITOR} Starting monitoring phase..."
    
    # Run monitoring script
    if uv run python src/cli/monitor_canonical.py --data-dir "$DATA_DIR"; then
        log "SUCCESS" "Monitoring completed"
    else
        log "ERROR" "Monitoring failed"
        return 1
    fi
}

# Phase 4: Dashboard (Optional)
run_dashboard() {
    if [[ $START_DASHBOARD == false ]]; then
        return 0
    fi
    
    log "INFO" "${EMOJI_DASHBOARD} Starting dashboard..."
    
    # Check if dashboard is already running
    if lsof -ti:$DASHBOARD_PORT &> /dev/null; then
        log "INFO" "Dashboard already running on port $DASHBOARD_PORT"
        log "INFO" "Access it at: http://localhost:$DASHBOARD_PORT"
        
        # If this is dashboard-only mode, wait for user to stop it
        if [[ $SKIP_SCRAPE == true && $SKIP_IMPORT == true && $SKIP_MONITOR == true ]]; then
            log "INFO" "Dashboard is running. Press Ctrl+C to stop."
            wait
        fi
        return 0
    fi
    
    # Start dashboard
    log "INFO" "Starting dashboard on port $DASHBOARD_PORT..."
    
    # If this is the only thing we're doing, run in foreground
    if [[ $SKIP_SCRAPE == true && $SKIP_IMPORT == true && $SKIP_MONITOR == true ]]; then
        log "SUCCESS" "Dashboard starting in foreground mode"
        log "INFO" "Access dashboard at: http://localhost:$DASHBOARD_PORT"
        log "INFO" "Press Ctrl+C to stop the dashboard"
        
        # Run in foreground - will be killed when user presses Ctrl+C
        uv run python dashboard/app.py
    else
        # Run in background and continue with other tasks
        nohup uv run python dashboard/app.py > "$DATA_DIR/dashboard.log" 2>&1 &
        local dashboard_pid=$!
        
        # Wait a moment and check if it started successfully
        sleep 3
        if kill -0 $dashboard_pid 2>/dev/null; then
            log "SUCCESS" "Dashboard started successfully (PID: $dashboard_pid)"
            log "INFO" "Access dashboard at: http://localhost:$DASHBOARD_PORT"
            echo $dashboard_pid > "$DATA_DIR/dashboard.pid"
            
            log "INFO" "Dashboard will continue running in background"
            log "INFO" "To stop it later, run: kill $dashboard_pid"
            log "INFO" "Or use: pkill -f 'dashboard/app.py'"
        else
            log "ERROR" "Dashboard failed to start"
            return 1
        fi
    fi
}

# Cleanup function
cleanup() {
    log "INFO" "Cleaning up..."
    
    # Always stop dashboard when script exits (Ctrl+C or completion)
    if [[ -f "$DATA_DIR/dashboard.pid" ]]; then
        local pid=$(cat "$DATA_DIR/dashboard.pid")
        if kill -0 $pid 2>/dev/null; then
            log "INFO" "Stopping dashboard (PID: $pid)"
            kill $pid 2>/dev/null || true
        fi
        rm -f "$DATA_DIR/dashboard.pid"
    fi
    
    # Also kill any dashboard processes that might be running
    pkill -f 'dashboard/app.py' 2>/dev/null || true
}

# Main execution function
main() {
    local start_time=$(date +%s)
    
    log "INFO" "🚀 Starting Price Monitor Workflow"
    log "INFO" "Timestamp: $(date)"
    log "INFO" "Working directory: $SCRIPT_DIR"
    
    # Setup cleanup trap
    trap cleanup EXIT
    
    # Check dependencies (skip for dashboard-only mode)
    if [[ ! ($SKIP_SCRAPE == true && $SKIP_IMPORT == true && $SKIP_MONITOR == true && $START_DASHBOARD == true) ]]; then
        check_dependencies
    fi
    
    # Run phases
    run_scraping
    run_import  
    run_monitoring
    run_dashboard
    
    # If dashboard is running in foreground, we don't reach here
    local end_time=$(date +%s)
    local total_duration=$((end_time - start_time))
    
    log "SUCCESS" "🎉 Price Monitor Workflow completed in ${total_duration}s"
    log "INFO" "Log file: $LOG_FILE"
    
    if [[ $START_DASHBOARD == true ]]; then
        log "INFO" "Dashboard: http://localhost:$DASHBOARD_PORT"
        
        # If dashboard was started in background, keep script alive until user stops it
        if [[ -f "$DATA_DIR/dashboard.pid" ]]; then
            log "INFO" "Keeping script alive while dashboard runs..."
            log "INFO" "Press Ctrl+C to stop everything"
            
            # Wait for user interrupt
            while true; do
                sleep 1
                # Check if dashboard is still running
                local pid=$(cat "$DATA_DIR/dashboard.pid" 2>/dev/null)
                if [[ -n "$pid" ]] && ! kill -0 $pid 2>/dev/null; then
                    log "INFO" "Dashboard stopped externally"
                    break
                fi
            done
        fi
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -l|--limit)
            SCRAPE_LIMIT="$2"
            shift 2
            ;;
        -k|--keywords)
            KEYWORDS_FILE="$2"
            shift 2
            ;;
        -p|--platforms)
            PLATFORMS="$2"
            shift 2
            ;;
        -d|--dashboard)
            START_DASHBOARD=true
            shift
            ;;
        -q|--quiet)
            QUIET=true
            shift
            ;;
        --skip-scrape)
            SKIP_SCRAPE=true
            shift
            ;;
        --skip-import)
            SKIP_IMPORT=true
            shift
            ;;
        --skip-monitor)
            SKIP_MONITOR=true
            shift
            ;;
        --scrape-only)
            SKIP_IMPORT=true
            SKIP_MONITOR=true
            shift
            ;;
        --import-only)
            SKIP_SCRAPE=true
            SKIP_MONITOR=true
            shift
            ;;
        --monitor-only)
            SKIP_SCRAPE=true
            SKIP_IMPORT=true
            shift
            ;;
        --dashboard-only)
            SKIP_SCRAPE=true
            SKIP_IMPORT=true
            SKIP_MONITOR=true
            START_DASHBOARD=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Run main function
main
