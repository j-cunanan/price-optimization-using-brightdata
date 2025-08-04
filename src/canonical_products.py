"""
Canonical Product Management System

This module handles the separation of discovery and monitoring:
1. Discovery: Find new products via keyword searches
2. Canonical mapping: Create stable product IDs based on unique identifiers
3. Monitoring: Track specific products by their canonical IDs over time
"""

import json
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs
from loguru import logger

from src.models import Platform, Product


@dataclass
class CanonicalProduct:
    """A canonical product with stable identifiers."""
    canonical_id: str  # Our internal stable ID
    platform: Platform
    platform_id: str  # Platform-specific stable ID (ASIN, JAN, etc.)
    url_pattern: str  # Clean URL pattern for monitoring
    title: str
    brand: Optional[str] = None
    model: Optional[str] = None
    category: Optional[str] = None
    discovered_via: str = ""  # How we found this product
    first_seen: str = ""
    last_monitored: str = ""
    is_active: bool = True


@dataclass
class PricePoint:
    """A price observation for a canonical product."""
    canonical_id: str
    price: Optional[float]
    currency: str
    observed_at: str
    title_at_time: str  # Title when observed (can change)
    availability: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None


class CanonicalProductManager:
    """Manages canonical product mapping and price tracking."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.canonical_dir = self.data_dir / "canonical"
        self.canonical_dir.mkdir(exist_ok=True)
        
        self.db_path = self.canonical_dir / "canonical_products.db"
        self._init_database()
    
    def _init_database(self):
        """Initialize the canonical products database."""
        with sqlite3.connect(self.db_path) as conn:
            # Canonical products table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS canonical_products (
                    canonical_id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    platform_id TEXT NOT NULL,
                    url_pattern TEXT NOT NULL,
                    title TEXT NOT NULL,
                    brand TEXT,
                    model TEXT,
                    category TEXT,
                    discovered_via TEXT DEFAULT '',
                    first_seen TEXT NOT NULL,
                    last_monitored TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    UNIQUE(platform, platform_id)
                )
            """)
            
            # Price history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical_id TEXT NOT NULL,
                    price REAL,
                    currency TEXT DEFAULT 'JPY',
                    observed_at TEXT NOT NULL,
                    title_at_time TEXT NOT NULL,
                    availability TEXT,
                    rating REAL,
                    review_count INTEGER,
                    FOREIGN KEY (canonical_id) REFERENCES canonical_products (canonical_id)
                )
            """)
            
            # Discovery sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS discovery_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    discovery_type TEXT NOT NULL,  -- 'keyword', 'category', 'manual'
                    query TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    products_found INTEGER DEFAULT 0,
                    products_added INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running'
                )
            """)
            
            # Monitoring sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS monitoring_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    products_monitored INTEGER DEFAULT 0,
                    products_found INTEGER DEFAULT 0,
                    price_changes_detected INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running'
                )
            """)
            
            # Indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_price_history_canonical_id ON price_history(canonical_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_price_history_observed_at ON price_history(observed_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_canonical_products_platform ON canonical_products(platform)")
            
            conn.commit()
    
    def _extract_platform_id(self, product_data: Dict[str, Any]) -> Optional[str]:
        """Extract stable platform-specific ID from product data."""
        platform = product_data.get('platform', '').lower()
        
        # Try both 'url' and 'product_url' fields
        url = product_data.get('url', '') or product_data.get('product_url', '')
        
        if not url:
            # No URL available, try to extract from title
            return self._extract_id_from_title(product_data)
        
        if 'amazon' in platform:
            # Extract ASIN from Amazon URL
            if '/dp/' in url:
                asin = url.split('/dp/')[1].split('/')[0].split('?')[0]
                return asin
            elif '/gp/product/' in url:
                asin = url.split('/gp/product/')[1].split('/')[0].split('?')[0]
                return asin
            elif 'asin=' in url:
                parsed = urlparse(url)
                query_params = parse_qs(parsed.query)
                if 'asin' in query_params:
                    return query_params['asin'][0]
        
        elif 'rakuten' in platform:
            # Extract item code from Rakuten URL
            if '/product/' in url:
                return url.split('/product/')[1].split('/')[0].split('?')[0]
            elif 'item/' in url:
                return url.split('item/')[1].split('/')[0].split('?')[0]
        
        elif 'mercari' in platform:
            # Extract item ID from Mercari URL
            if '/item/' in url:
                return url.split('/item/')[1].split('?')[0]
            elif '/shops/product/' in url:
                return url.split('/shops/product/')[1].split('?')[0]
        
        elif 'yahoo' in platform:
            # Extract store and item from Yahoo Shopping URL
            if 'store/' in url and 'item/' in url:
                parts = url.split('/')
                store_idx = next((i for i, part in enumerate(parts) if part == 'store'), -1)
                item_idx = next((i for i, part in enumerate(parts) if part == 'item'), -1)
                if store_idx >= 0 and item_idx >= 0 and store_idx < len(parts) - 1 and item_idx < len(parts) - 1:
                    store = parts[store_idx + 1]
                    item = parts[item_idx + 1].split('?')[0]
                    return f"{store}:{item}"
        
        # If URL doesn't match platform patterns, try extracting from title
        return self._extract_id_from_title(product_data)
    
    def _extract_id_from_title(self, product_data: Dict[str, Any]) -> Optional[str]:
        """Extract stable ID from product title when URL is not available."""
        import re
        
        title = product_data.get('title', '').strip()
        if not title:
            return None
        
        # Platform-specific title patterns
        platform = product_data.get('platform', '').lower()
        
        # Try to extract meaningful model numbers or product identifiers
        stable_patterns = [
            # Camera models
            r'\b(ILCE-\w+|α\d+\w*|X100\w*|EOS\s*\w+)\b',
            # GPU models  
            r'\b(RTX\s*\d+\w*|RX\s*\d+\w*|GeForce\s*\w+)\b',
            # CPU models
            r'\b(Ryzen\s*\d+\s*\w+|Core\s*i\d+\w*)\b',
            # Guitar strings and music gear
            r'\b(ERNIE\s*BALL\s*\d+|Regular\s*Slinky|NYXL\s*[\d-]+|BOSS\s*\w+\s*\d*)\b',
            # Lens models
            r'\b(\d+mm\s*[Ff]\d+\.?\d*|RF\d+mm|FE\s*\d+-\d+mm|DG\s*DN)\b',
            # Nintendo/PlayStation models
            r'\b(Nintendo\s*Switch\s*\w*|PS\d+\s*\w*|OLED\s*\w*)\b',
            # General model numbers (letters + numbers)
            r'\b([A-Z]{2,}\d+[A-Z]*\w*)\b'
        ]
        
        for pattern in stable_patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                model_id = match.group(1).upper().replace(' ', '_')
                # Create a hash of the full title to make it more unique
                import hashlib
                title_hash = hashlib.md5(title.lower().encode()).hexdigest()[:6]
                return f"{model_id}_{title_hash}"
        
        # Last resort: create normalized title-based ID
        normalized_title = self._normalize_title_for_id(title)
        if len(normalized_title) > 10:
            # Create a hash to ensure uniqueness while keeping it manageable
            import hashlib
            title_hash = hashlib.md5(title.lower().encode()).hexdigest()[:8]
            return f"{normalized_title[:30]}_{title_hash}"
        
        return None
    
    def _normalize_title_for_id(self, title: str) -> str:
        """Normalize title to create a stable ID."""
        import re
        
        # Convert to lowercase and remove special characters
        normalized = re.sub(r'[^\w\s-]', '', title.lower())
        
        # Remove common promotional/variable text
        promotional_patterns = [
            r'\s*amazon\.?co\.?jp\s*exclusive',
            r'\s*\d+年.*保証',  # warranty terms
            r'\s*送料無料',      # free shipping
            r'\s*新品',         # new item
            r'\s*中古',         # used item
            r'\s*\d+%\s*off',   # discount percentages
            r'\s*限定',         # limited
            r'\s*セット',       # set
        ]
        
        for pattern in promotional_patterns:
            normalized = re.sub(pattern, '', normalized)
        
        # Replace spaces with underscores and clean up
        normalized = re.sub(r'\s+', '_', normalized.strip())
        normalized = re.sub(r'_+', '_', normalized)  # Multiple underscores to single
        normalized = normalized.strip('_')
        
        return normalized

    def _generate_canonical_id(self, platform: str, platform_id: str) -> str:
        """Generate canonical ID from platform and platform ID."""
        content = f"{platform}:{platform_id}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _create_url_pattern(self, url: str, platform: str) -> str:
        """Create a clean URL pattern for monitoring."""
        parsed = urlparse(url)
        
        if platform == 'amazon_jp':
            # Keep only essential parts for Amazon
            path_parts = parsed.path.split('/')
            if '/dp/' in url:
                dp_idx = path_parts.index('dp')
                if dp_idx < len(path_parts) - 1:
                    asin = path_parts[dp_idx + 1]
                    return f"https://www.amazon.co.jp/dp/{asin}"
        
        elif platform == 'rakuten':
            # Keep the core product URL
            if '/product/' in url:
                return url.split('?')[0]
        
        # Default: clean URL without query parameters
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    def add_discovered_products(self, products_data: List[Dict[str, Any]], discovery_session_id: str) -> int:
        """Add discovered products to canonical tracking."""
        added_count = 0
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            for product_data in products_data:
                try:
                    platform = product_data.get('platform')
                    platform_id = self._extract_platform_id(product_data)
                    
                    if not platform_id:
                        logger.debug(f"No stable ID found for product: {product_data.get('title', '')[:50]}...")
                        continue
                    
                    canonical_id = self._generate_canonical_id(platform, platform_id)
                    url_pattern = self._create_url_pattern(
                        product_data.get('url', '') or product_data.get('product_url', ''), 
                        platform
                    )
                    
                    # Try to insert canonical product
                    conn.execute("""
                        INSERT OR IGNORE INTO canonical_products 
                        (canonical_id, platform, platform_id, url_pattern, title, brand, 
                         category, discovered_via, first_seen, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        canonical_id,
                        platform,
                        platform_id,
                        url_pattern,
                        product_data.get('title', ''),
                        product_data.get('brand'),
                        product_data.get('category'),
                        f"discovery:{discovery_session_id}",
                        timestamp,
                        True
                    ))
                    
                    if conn.total_changes > 0:
                        added_count += 1
                        logger.debug(f"Added canonical product: {canonical_id}")
                    
                    # Always add price point (even for existing products)
                    self._add_price_point(conn, canonical_id, product_data, timestamp)
                
                except Exception as e:
                    logger.warning(f"Failed to add product to canonical tracking: {e}")
                    continue
            
            conn.commit()
        
        logger.info(f"Added {added_count} new canonical products")
        return added_count
    
    def _add_price_point(self, conn, canonical_id: str, product_data: Dict[str, Any], timestamp: str):
        """Add a price observation to the history."""
        conn.execute("""
            INSERT INTO price_history 
            (canonical_id, price, currency, observed_at, title_at_time, 
             availability, rating, review_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            canonical_id,
            product_data.get('price'),
            product_data.get('currency', 'JPY'),
            timestamp,
            product_data.get('title', ''),
            product_data.get('availability'),
            product_data.get('rating'),
            product_data.get('review_count')
        ))
    
    def get_products_for_monitoring(self, limit: Optional[int] = None, platform: Optional[str] = None) -> List[CanonicalProduct]:
        """Get canonical products that should be monitored."""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM canonical_products WHERE is_active = 1"
            params = []
            
            if platform:
                query += " AND platform = ?"
                params.append(platform)
            
            # Order by last_monitored to prioritize least recently checked
            query += " ORDER BY last_monitored ASC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            products = []
            columns = [desc[0] for desc in cursor.description]
            
            for row in rows:
                row_dict = dict(zip(columns, row))
                products.append(CanonicalProduct(**row_dict))
            
            return products
    
    def update_monitoring_result(self, canonical_id: str, product_data: Optional[Dict[str, Any]], monitoring_session_id: str):
        """Update a canonical product with monitoring results."""
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            # Update last_monitored time
            conn.execute("""
                UPDATE canonical_products 
                SET last_monitored = ?
                WHERE canonical_id = ?
            """, (timestamp, canonical_id))
            
            # If product was found, add price point
            if product_data:
                self._add_price_point(conn, canonical_id, product_data, timestamp)
                
                # Update title if it has changed significantly
                current_title = product_data.get('title', '')
                if current_title and len(current_title) > 10:  # Only update if we have a good title
                    conn.execute("""
                        UPDATE canonical_products 
                        SET title = ?
                        WHERE canonical_id = ? AND title != ?
                    """, (current_title, canonical_id, current_title))
            
            conn.commit()
    
    def get_price_changes(self, hours_back: int = 24, min_change_percent: float = 5.0) -> List[Dict[str, Any]]:
        """Get recent price changes above a threshold."""
        with sqlite3.connect(self.db_path) as conn:
            # Find products with price changes in the specified time window
            query = """
                WITH recent_prices AS (
                    SELECT 
                        p1.canonical_id,
                        p1.price as new_price,
                        p1.observed_at as new_time,
                        p1.title_at_time as current_title,
                        LAG(p1.price) OVER (PARTITION BY p1.canonical_id ORDER BY p1.observed_at) as old_price,
                        LAG(p1.observed_at) OVER (PARTITION BY p1.canonical_id ORDER BY p1.observed_at) as old_time
                    FROM price_history p1
                    WHERE p1.observed_at > datetime('now', '-{} hours')
                    AND p1.price IS NOT NULL
                    ORDER BY p1.canonical_id, p1.observed_at
                )
                SELECT 
                    rp.canonical_id,
                    cp.platform,
                    cp.platform_id,
                    cp.url_pattern,
                    rp.current_title,
                    rp.old_price,
                    rp.new_price,
                    rp.old_time,
                    rp.new_time,
                    ROUND(((rp.new_price - rp.old_price) / rp.old_price) * 100, 2) as change_percent,
                    ROUND(rp.new_price - rp.old_price, 2) as change_amount
                FROM recent_prices rp
                JOIN canonical_products cp ON rp.canonical_id = cp.canonical_id
                WHERE rp.old_price IS NOT NULL 
                AND rp.old_price != rp.new_price
                AND ABS(((rp.new_price - rp.old_price) / rp.old_price) * 100) >= ?
                ORDER BY ABS(change_percent) DESC
            """.format(hours_back)
            
            cursor = conn.execute(query, (min_change_percent,))
            columns = [desc[0] for desc in cursor.description]
            
            changes = []
            for row in cursor.fetchall():
                changes.append(dict(zip(columns, row)))
            
            return changes
    
    def get_canonical_stats(self) -> Dict[str, Any]:
        """Get statistics about canonical products."""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            
            # Total canonical products
            cursor = conn.execute("SELECT COUNT(*) FROM canonical_products WHERE is_active = 1")
            stats['total_active_products'] = cursor.fetchone()[0]
            
            # Products by platform
            cursor = conn.execute("""
                SELECT platform, COUNT(*) 
                FROM canonical_products 
                WHERE is_active = 1 
                GROUP BY platform
            """)
            stats['by_platform'] = dict(cursor.fetchall())
            
            # Recent price observations
            cursor = conn.execute("""
                SELECT COUNT(*) 
                FROM price_history 
                WHERE observed_at > datetime('now', '-24 hours')
            """)
            stats['price_observations_24h'] = cursor.fetchone()[0]
            
            # Products with recent monitoring
            cursor = conn.execute("""
                SELECT COUNT(*) 
                FROM canonical_products 
                WHERE is_active = 1 
                AND last_monitored > datetime('now', '-24 hours')
            """)
            stats['monitored_24h'] = cursor.fetchone()[0]
            
            # Recent discovery sessions
            cursor = conn.execute("""
                SELECT COUNT(*) 
                FROM discovery_sessions 
                WHERE started_at > datetime('now', '-7 days')
            """)
            stats['discovery_sessions_7d'] = cursor.fetchone()[0]
            
            # Recent price changes
            cursor = conn.execute("""
                SELECT COUNT(DISTINCT canonical_id)
                FROM price_history p1
                WHERE p1.observed_at > datetime('now', '-24 hours')
                AND EXISTS (
                    SELECT 1 FROM price_history p2 
                    WHERE p2.canonical_id = p1.canonical_id 
                    AND p2.observed_at < p1.observed_at 
                    AND p2.price != p1.price
                    AND p1.price IS NOT NULL 
                    AND p2.price IS NOT NULL
                )
            """)
            stats['products_with_price_changes_24h'] = cursor.fetchone()[0]
            
            return stats
    
    def create_discovery_session(self, discovery_type: str, query: str) -> str:
        """Create a new discovery session and return its ID."""
        session_id = f"{discovery_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO discovery_sessions 
                (session_id, discovery_type, query, started_at, status)
                VALUES (?, ?, ?, ?, 'running')
            """, (session_id, discovery_type, query, timestamp))
            conn.commit()
        
        return session_id
    
    def complete_discovery_session(self, session_id: str, products_found: int, products_added: int):
        """Mark a discovery session as completed."""
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE discovery_sessions 
                SET completed_at = ?, products_found = ?, products_added = ?, status = 'completed'
                WHERE session_id = ?
            """, (timestamp, products_found, products_added, session_id))
            conn.commit()
    
    def create_monitoring_session(self) -> str:
        """Create a new monitoring session and return its ID."""
        session_id = f"monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO monitoring_sessions 
                (session_id, started_at, status)
                VALUES (?, ?, 'running')
            """, (session_id, timestamp))
            conn.commit()
        
        return session_id
    
    def complete_monitoring_session(self, session_id: str, products_monitored: int, products_found: int, price_changes: int):
        """Mark a monitoring session as completed."""
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE monitoring_sessions 
                SET completed_at = ?, products_monitored = ?, products_found = ?, 
                    price_changes_detected = ?, status = 'completed'
                WHERE session_id = ?
            """, (timestamp, products_monitored, products_found, price_changes, session_id))
            conn.commit()


def create_canonical_manager(data_dir: str = "data") -> CanonicalProductManager:
    """Factory function to create a CanonicalProductManager instance."""
    return CanonicalProductManager(data_dir)
