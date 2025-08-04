"""
Product Tracking Batch Scraper for Price Change Detection

This scraper focuses on tracking specific products over time rather than
keyword-based discovery. It maintains a database of products to track
and scrapes them consistently for price change detection.
"""

import asyncio
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, asdict
from urllib.parse import urlparse
from loguru import logger

from src.models import Platform, Product
from src.brightdata.scraper import search_japanese_marketplaces_brightdata
from src.change_detector import create_change_detector


@dataclass
class TrackedProduct:
    """A product that's being tracked for price changes."""
    id: str  # Unique identifier (hash of URL + platform)
    url: str
    platform: Platform
    title: str
    initial_price: Optional[float]
    last_seen_price: Optional[float]
    first_tracked: str  # ISO timestamp
    last_updated: str  # ISO timestamp
    track_reason: str  # Why we're tracking this (e.g., "keyword:ERNIE_BALL_2221")
    is_active: bool = True


class ProductTracker:
    """Manages a database of products to track for price changes."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.tracking_dir = self.data_dir / "tracking"
        self.tracking_dir.mkdir(exist_ok=True)
        
        self.db_path = self.tracking_dir / "tracked_products.db"
        self.change_detector = create_change_detector(data_dir)
        
        self._init_database()
    
    def _init_database(self):
        """Initialize the SQLite database for tracking products."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tracked_products (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    title TEXT NOT NULL,
                    initial_price REAL,
                    last_seen_price REAL,
                    first_tracked TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    track_reason TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    UNIQUE(url, platform)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tracking_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    products_tracked INTEGER DEFAULT 0,
                    products_found INTEGER DEFAULT 0,
                    products_changed INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running'
                )
            """)
            
            conn.commit()
    
    def add_products_from_search_result(self, search_result: Dict, keyword: str) -> int:
        """Add products from a search result to the tracking database."""
        added_count = 0
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            for product_data in search_result.get('products', []):
                try:
                    # Create product ID from URL + platform
                    product_id = self._generate_product_id(product_data['url'], product_data['platform'])
                    
                    conn.execute("""
                        INSERT OR IGNORE INTO tracked_products 
                        (id, url, platform, title, initial_price, last_seen_price, 
                         first_tracked, last_updated, track_reason)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        product_id,
                        product_data['url'],
                        product_data['platform'],
                        product_data['title'],
                        product_data.get('price'),
                        product_data.get('price'),
                        timestamp,
                        timestamp,
                        f"keyword:{keyword}"
                    ))
                    
                    if conn.total_changes > 0:
                        added_count += 1
                        logger.debug(f"Added product to tracking: {product_data['title'][:50]}...")
                
                except Exception as e:
                    logger.warning(f"Failed to add product to tracking: {e}")
                    continue
            
            conn.commit()
        
        logger.info(f"Added {added_count} new products to tracking database")
        return added_count
    
    def get_tracked_products(self, limit: Optional[int] = None, active_only: bool = True) -> List[TrackedProduct]:
        """Get list of tracked products."""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM tracked_products"
            params = []
            
            if active_only:
                query += " WHERE is_active = 1"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            # Convert to TrackedProduct objects
            products = []
            columns = [desc[0] for desc in cursor.description]
            
            for row in rows:
                row_dict = dict(zip(columns, row))
                products.append(TrackedProduct(**row_dict))
            
            return products
    
    def update_product_price(self, product_id: str, new_price: Optional[float], title: str = None):
        """Update the last seen price for a tracked product."""
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            if title:
                conn.execute("""
                    UPDATE tracked_products 
                    SET last_seen_price = ?, last_updated = ?, title = ?
                    WHERE id = ?
                """, (new_price, timestamp, title, product_id))
            else:
                conn.execute("""
                    UPDATE tracked_products 
                    SET last_seen_price = ?, last_updated = ?
                    WHERE id = ?
                """, (new_price, timestamp, product_id))
            
            conn.commit()
    
    def get_tracking_stats(self) -> Dict[str, Any]:
        """Get statistics about tracked products."""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            
            # Total products
            cursor = conn.execute("SELECT COUNT(*) FROM tracked_products WHERE is_active = 1")
            stats['total_active'] = cursor.fetchone()[0]
            
            # Products by platform
            cursor = conn.execute("""
                SELECT platform, COUNT(*) 
                FROM tracked_products 
                WHERE is_active = 1 
                GROUP BY platform
            """)
            stats['by_platform'] = dict(cursor.fetchall())
            
            # Products with prices
            cursor = conn.execute("""
                SELECT COUNT(*) 
                FROM tracked_products 
                WHERE is_active = 1 AND last_seen_price IS NOT NULL
            """)
            stats['with_prices'] = cursor.fetchone()[0]
            
            # Recent tracking sessions
            cursor = conn.execute("""
                SELECT COUNT(*) 
                FROM tracking_sessions 
                WHERE started_at > datetime('now', '-7 days')
            """)
            stats['recent_sessions'] = cursor.fetchone()[0]
            
            return stats
    
    def _generate_product_id(self, url: str, platform: str) -> str:
        """Generate a unique product ID from URL and platform."""
        import hashlib
        
        # Clean URL (remove query parameters that might change)
        parsed = urlparse(url)
        clean_url = f"{parsed.netloc}{parsed.path}"
        
        # Create hash
        content = f"{clean_url}_{platform}"
        return hashlib.md5(content.encode()).hexdigest()[:16]


class TrackingBatchScraper:
    """Batch scraper that focuses on tracking specific products over time."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.tracker = ProductTracker(data_dir)
        self.change_detector = create_change_detector(data_dir)
    
    async def discover_products_from_keywords(
        self,
        keywords: List[str],
        platforms: Optional[List[Platform]] = None,
        max_results_per_platform: int = 20
    ) -> Dict[str, Any]:
        """
        Use keyword searches to discover new products to track.
        This is typically run once to build the initial tracking database.
        """
        logger.info(f"Discovering products from {len(keywords)} keywords")
        
        session_id = f"discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        total_discovered = 0
        
        results = {
            'session_id': session_id,
            'started_at': datetime.now().isoformat(),
            'keywords_processed': 0,
            'products_discovered': 0,
            'products_added_to_tracking': 0,
            'keyword_results': {}
        }
        
        for keyword in keywords:
            try:
                logger.info(f"Searching keyword: {keyword}")
                
                search_result = await search_japanese_marketplaces_brightdata(
                    keyword=keyword,
                    platforms=platforms,
                    max_results_per_platform=max_results_per_platform
                )
                
                if search_result and search_result.products:
                    # Convert SearchResult to dictionary format
                    search_dict = {
                        'products': [asdict(product) for product in search_result.products],
                        'query': asdict(search_result.query),
                        'scraped_at': search_result.scraped_at,
                        'search_time': search_result.search_time,
                        'total_found': search_result.total_found
                    }
                    
                    products_count = len(search_dict['products'])
                    added_count = self.tracker.add_products_from_search_result(search_dict, keyword)
                    
                    results['keyword_results'][keyword] = {
                        'products_found': products_count,
                        'products_added': added_count,
                        'status': 'success'
                    }
                    
                    results['products_discovered'] += products_count
                    results['products_added_to_tracking'] += added_count
                    total_discovered += products_count
                    
                    logger.info(f"Found {products_count} products for '{keyword}', added {added_count} new ones")
                else:
                    results['keyword_results'][keyword] = {
                        'products_found': 0,
                        'products_added': 0,
                        'status': 'no_results'
                    }
                    logger.warning(f"No results found for keyword: {keyword}")
                
                results['keywords_processed'] += 1
                
                # Small delay between keyword searches
                await asyncio.sleep(2.0)
                
            except Exception as e:
                logger.error(f"Error searching keyword '{keyword}': {e}")
                results['keyword_results'][keyword] = {
                    'products_found': 0,
                    'products_added': 0,
                    'status': 'error',
                    'error': str(e)
                }
        
        results['completed_at'] = datetime.now().isoformat()
        
        # Save discovery session results
        session_file = self.data_dir / "tracking" / f"{session_id}_discovery.json"
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Discovery completed: {total_discovered} products found, {results['products_added_to_tracking']} added to tracking")
        return results
    
    async def track_products_batch(self, max_products: Optional[int] = None) -> Dict[str, Any]:
        """
        Track all products in the database by re-scraping them.
        This is the main function for ongoing price monitoring.
        """
        session_id = f"tracking_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Starting tracking session: {session_id}")
        
        # Get products to track
        tracked_products = self.tracker.get_tracked_products(limit=max_products)
        
        if not tracked_products:
            logger.warning("No products found to track")
            return {'error': 'No products to track'}
        
        logger.info(f"Tracking {len(tracked_products)} products")
        
        results = {
            'session_id': session_id,
            'started_at': datetime.now().isoformat(),
            'products_to_track': len(tracked_products),
            'products_found': 0,
            'products_with_price_changes': 0,
            'tracking_results': {},
            'change_detection_results': {}
        }
        
        # Group products by platform and keyword for efficient processing
        products_by_keyword = {}
        for product in tracked_products:
            # Extract keyword from track_reason
            if product.track_reason.startswith('keyword:'):
                keyword = product.track_reason[8:]  # Remove 'keyword:' prefix
                if keyword not in products_by_keyword:
                    products_by_keyword[keyword] = []
                products_by_keyword[keyword].append(product)
        
        # Re-scrape each keyword and match products
        for keyword, keyword_products in products_by_keyword.items():
            try:
                logger.info(f"Re-scraping keyword: {keyword} ({len(keyword_products)} tracked products)")
                
                # Search for current results
                search_result = await search_japanese_marketplaces_brightdata(
                    keyword=keyword,
                    platforms=None,  # Search all platforms
                    max_results_per_platform=50  # Get more results for better matching
                )
                
                if not search_result or not search_result.products:
                    logger.warning(f"No current results for keyword: {keyword}")
                    continue
                
                # Convert SearchResult to dictionary format and match tracked products
                current_products = {}
                for product in search_result.products:
                    product_dict = asdict(product)
                    product_id = self.tracker._generate_product_id(product_dict['url'], product_dict['platform'])
                    current_products[product_id] = product_dict
                
                # Update tracked products with current data
                found_count = 0
                for tracked_product in keyword_products:
                    if tracked_product.id in current_products:
                        current_data = current_products[tracked_product.id]
                        new_price = current_data.get('price')
                        
                        # Update in database
                        self.tracker.update_product_price(
                            tracked_product.id,
                            new_price,
                            current_data.get('title')
                        )
                        
                        found_count += 1
                        logger.debug(f"Updated product: {current_data.get('title', '')[:50]}... Price: {new_price}")
                
                results['products_found'] += found_count
                results['tracking_results'][keyword] = {
                    'tracked_products': len(keyword_products),
                    'found_products': found_count,
                    'missing_products': len(keyword_products) - found_count
                }
                
                # Save current results in batch format for change detection
                if search_result.products:
                    # Convert to dictionary format for saving
                    search_dict = {
                        'products': [asdict(product) for product in search_result.products],
                        'query': asdict(search_result.query),
                        'scraped_at': search_result.scraped_at,
                        'search_time': search_result.search_time,
                        'total_found': search_result.total_found
                    }
                    
                    batch_filename = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{keyword}_{datetime.now().isoformat()}.json"
                    batch_path = self.data_dir / "batch" / "results" / batch_filename
                    
                    with open(batch_path, 'w', encoding='utf-8') as f:
                        json.dump(search_dict, f, indent=2, ensure_ascii=False)
                
                await asyncio.sleep(3.0)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error tracking keyword '{keyword}': {e}")
                results['tracking_results'][keyword] = {
                    'error': str(e)
                }
        
        # Run change detection for each keyword
        for keyword in products_by_keyword.keys():
            try:
                change_result = self.change_detector.detect_changes_for_keyword(keyword)
                results['change_detection_results'][keyword] = change_result
                
                if change_result.get('changes_detected'):
                    results['products_with_price_changes'] += change_result.get('comparison_summary', {}).get('price_changes', 0)
                
            except Exception as e:
                logger.error(f"Error in change detection for '{keyword}': {e}")
                results['change_detection_results'][keyword] = {'error': str(e)}
        
        results['completed_at'] = datetime.now().isoformat()
        
        # Save tracking session results
        session_file = self.data_dir / "tracking" / f"{session_id}_tracking.json"
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Tracking session completed: {results['products_found']}/{results['products_to_track']} products found")
        return results


def create_tracking_scraper(data_dir: str = "data") -> TrackingBatchScraper:
    """Factory function to create a TrackingBatchScraper instance."""
    return TrackingBatchScraper(data_dir)
