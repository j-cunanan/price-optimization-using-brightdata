#!/usr/bin/env python3
"""
Monitor canonical product system status and health.
"""
import sys
import os
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add src to Python path
sys.path.insert(0, str(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from canonical_products_simple import SimpleCanonicalProducts


def monitor_system(data_dir="data"):
    """Monitor the canonical product system."""
    try:
        canonical_manager = SimpleCanonicalProducts(data_dir)
        
        logger.info("🔍 Starting canonical system monitoring...")
        
        stats = canonical_manager.get_stats()
        price_changes = canonical_manager.get_price_changes()
        
        # Display status
        logger.info("📊 System Status:")
        logger.info(f"   Total canonical products: {stats['total_canonical_products']}")
        logger.info(f"   Active products: {stats['active_products']}")
        logger.info(f"   Total price points: {stats['total_price_points']}")
        logger.info(f"   Products with price history: {stats['products_with_price_history']}")
        logger.info(f"   Discovery sessions: {stats['discovery_sessions']}")
        
        # Recent price changes
        recent_changes = price_changes[:10]  # Last 10 changes
        if recent_changes:
            logger.info(f"💰 Recent Price Changes ({len(recent_changes)}/{len(price_changes)} shown):")
            for i, change in enumerate(recent_changes, 1):
                old_price = change.get('old_price', 'N/A')
                new_price = change.get('new_price', 'N/A')
                product_title = change.get('title', 'Unknown Product')[:50]  # Use 'title' not 'product_title'
                platform = change.get('platform', 'Unknown')
                logger.info(f"   {i}. [{platform}] {product_title} - ¥{old_price} → ¥{new_price}")
        else:
            logger.info("💰 No price changes detected")
        
        # Health check
        if stats['total_canonical_products'] > 0:
            logger.info("✅ System is healthy")
            return True
        else:
            logger.warning("⚠️ No canonical products found - system may need data")
            return False
            
    except Exception as e:
        logger.error(f"❌ Monitoring failed: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor canonical product system")
    parser.add_argument("--data-dir", default="data", help="Data directory (default: data)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    success = monitor_system(args.data_dir)
    
    if success:
        print("\n✅ Monitoring completed successfully")
    else:
        print("\n❌ Monitoring completed with issues")
        sys.exit(1)
