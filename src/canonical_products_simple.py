"""
Simplified Canonical Product Management without SQL - Just JSON files

This replaces the complex SQL-based approach with simple JSON file storage.
Much easier to understand, debug, and maintain.
"""

import json
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse, parse_qs
from loguru import logger


class SimpleCanonicalProducts:
    """Manages canonical products using JSON files instead of SQL"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.canonical_dir = self.data_dir / "canonical"
        self.canonical_dir.mkdir(exist_ok=True, parents=True)
        
        # Simple JSON files instead of SQL tables
        self.products_file = self.canonical_dir / "products.json"
        self.price_history_file = self.canonical_dir / "price_history.json" 
        self.sessions_file = self.canonical_dir / "sessions.json"
        
        # Load data into memory (fast for our scale)
        self.products = self._load_json(self.products_file, {})
        self.price_history = self._load_json(self.price_history_file, {})
        self.sessions = self._load_json(self.sessions_file, [])
    
    def _load_json(self, filepath: Path, default):
        """Load JSON file or return default if not exists"""
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading {filepath}: {e}")
        return default
    
    def _save_json(self, filepath: Path, data):
        """Save data to JSON file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _save_all(self):
        """Save all data to files"""
        self._save_json(self.products_file, self.products)
        self._save_json(self.price_history_file, self.price_history)
        self._save_json(self.sessions_file, self.sessions)
    
    def _get_canonical_id(self, product_data: Dict[str, Any]) -> Optional[str]:
        """Extract canonical ID from product (URL or title-based)"""
        # Try URL first (most reliable)
        url = product_data.get('url', '') or product_data.get('product_url', '')
        platform = product_data.get('platform', '').lower()
        
        if url:
            stable_id = self._extract_id_from_url(url, platform)
            if stable_id:
                return f"{platform}:{stable_id}"
        
        # Fallback to title-based ID
        title_id = self._extract_id_from_title(product_data)
        if title_id:
            return f"{platform}:title:{title_id}"
        
        return None
    
    def _extract_id_from_url(self, url: str, platform: str) -> Optional[str]:
        """Extract stable ID from URL based on platform"""
        if 'amazon' in platform:
            if '/dp/' in url:
                return url.split('/dp/')[1].split('/')[0].split('?')[0]
            elif '/gp/product/' in url:
                return url.split('/gp/product/')[1].split('/')[0].split('?')[0]
        
        elif 'rakuten' in platform:
            if '/product/' in url:
                return url.split('/product/')[1].split('/')[0].split('?')[0]
        
        elif 'mercari' in platform:
            if '/item/' in url:
                return url.split('/item/')[1].split('?')[0]
        
        elif 'yahoo' in platform:
            if 'store/' in url and 'item/' in url:
                parts = url.split('/')
                store_idx = next((i for i, part in enumerate(parts) if part == 'store'), -1)
                item_idx = next((i for i, part in enumerate(parts) if part == 'item'), -1)
                if store_idx >= 0 and item_idx >= 0:
                    store = parts[store_idx + 1]
                    item = parts[item_idx + 1].split('?')[0]
                    return f"{store}:{item}"
        
        return None
    
    def _extract_id_from_title(self, product_data: Dict[str, Any]) -> Optional[str]:
        """Extract stable ID from product title"""
        title = product_data.get('title', '').strip()
        if not title:
            return None
        
        # Same patterns as before for extracting model numbers
        stable_patterns = [
            r'\b(ILCE-\w+|α\d+\w*|X100\w*|EOS\s*\w+)\b',  # Camera models
            r'\b(RTX\s*\d+\w*|RX\s*\d+\w*|GeForce\s*\w+)\b',  # GPU models  
            r'\b(Ryzen\s*\d+\s*\w+|Core\s*i\d+\w*)\b',  # CPU models
            r'\b(ERNIE\s*BALL\s*\d+|Regular\s*Slinky|NYXL\s*[\d-]+|BOSS\s*\w+\s*\d*)\b',  # Music gear
            r'\b(\d+mm\s*[Ff]\d+\.?\d*|RF\d+mm|FE\s*\d+-\d+mm|DG\s*DN)\b',  # Lens models
        ]
        
        for pattern in stable_patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                model_id = match.group(1).upper().replace(' ', '_')
                # Add title hash for uniqueness
                title_hash = hashlib.md5(title.lower().encode()).hexdigest()[:6]
                return f"{model_id}_{title_hash}"
        
        # Last resort: normalized title hash
        normalized = re.sub(r'[^\w\s-]', '', title.lower())
        normalized = re.sub(r'\s+', '_', normalized.strip())[:30]
        title_hash = hashlib.md5(title.lower().encode()).hexdigest()[:8]
        return f"{normalized}_{title_hash}"
    
    def add_discovered_products(self, products_data: List[Dict[str, Any]], 
                              discovery_session_id: str) -> int:
        """Add newly discovered products from batch results"""
        timestamp = datetime.now().isoformat()
        added_count = 0
        
        for product_data in products_data:
            canonical_id = self._get_canonical_id(product_data)
            if not canonical_id:
                continue
            
            # Add to products if new
            if canonical_id not in self.products:
                self.products[canonical_id] = {
                    "canonical_id": canonical_id,
                    "platform": product_data.get('platform'),
                    "title": product_data.get('title'),
                    "brand": product_data.get('brand'),
                    "category": product_data.get('category'),
                    "url": product_data.get('url', '') or product_data.get('product_url', ''),
                    "discovered_via": f"discovery:{discovery_session_id}",
                    "first_seen": timestamp,
                    "last_seen": timestamp,
                    "is_active": True
                }
                added_count += 1
                logger.debug(f"Added canonical product: {canonical_id}")
            else:
                # Update last_seen for existing products
                self.products[canonical_id]["last_seen"] = timestamp
            
            # Always add price point
            self._add_price_point(canonical_id, product_data, timestamp)
        
        # Save all changes
        self._save_all()
        logger.info(f"Added {added_count} new canonical products")
        return added_count
    
    def _add_price_point(self, canonical_id: str, product_data: Dict[str, Any], timestamp: str):
        """Add a price point to history"""
        if canonical_id not in self.price_history:
            self.price_history[canonical_id] = []
        
        price_point = {
            "timestamp": timestamp,
            "price": product_data.get('price'),
            "availability": product_data.get('availability'),
            "rating": product_data.get('rating'),
            "review_count": product_data.get('review_count'),
            "url": product_data.get('url', '') or product_data.get('product_url', ''),
        }
        
        self.price_history[canonical_id].append(price_point)
    
    def get_all_products(self) -> List[Dict[str, Any]]:
        """Get all canonical products"""
        return list(self.products.values())
    
    def get_price_changes(self) -> List[Dict[str, Any]]:
        """Get products with price changes"""
        changes = []
        
        for canonical_id, history in self.price_history.items():
            if len(history) < 2:
                continue
            
            # Sort by timestamp and compare last two prices
            sorted_history = sorted(history, key=lambda x: x['timestamp'])
            current = sorted_history[-1]
            previous = sorted_history[-2]
            
            if (current.get('price') and previous.get('price') and 
                current['price'] != previous['price']):
                
                product = self.products.get(canonical_id, {})
                change_amount = float(current['price']) - float(previous['price'])
                change_percent = (change_amount / float(previous['price'])) * 100
                
                changes.append({
                    "canonical_id": canonical_id,
                    "title": product.get('title', ''),
                    "platform": product.get('platform', ''),
                    "url": current.get('url', ''),
                    "old_price": previous['price'],
                    "new_price": current['price'],
                    "change_amount": round(change_amount, 2),
                    "change_percent": round(change_percent, 2),
                    "change_timestamp": current['timestamp'],
                    "previous_timestamp": previous['timestamp']
                })
        
        return sorted(changes, key=lambda x: x['change_timestamp'], reverse=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        total_products = len(self.products)
        active_products = sum(1 for p in self.products.values() if p.get('is_active', True))
        total_price_points = sum(len(history) for history in self.price_history.values())
        products_with_changes = sum(1 for history in self.price_history.values() if len(history) > 1)
        
        return {
            "total_canonical_products": total_products,
            "active_products": active_products,
            "total_price_points": total_price_points,
            "products_with_price_history": products_with_changes,
            "discovery_sessions": len(self.sessions)
        }


def create_simple_canonical_manager(data_dir: str = "data") -> SimpleCanonicalProducts:
    """Factory function to create a simple canonical product manager"""
    return SimpleCanonicalProducts(data_dir)
