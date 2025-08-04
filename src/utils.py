"""
Utility functions for the Japanese marketplace scraper.
"""

import os
import json
import csv
import asyncio
import random
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger
from fake_useragent import UserAgent

from .models import Product, SearchResult, ScrapingConfig


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """Set up logging configuration."""
    logger.remove()  # Remove default handler
    
    # Console logging
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True
    )
    
    # File logging
    if log_file:
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=log_level,
            rotation="10 MB",
            retention="7 days"
        )


def load_config() -> ScrapingConfig:
    """Load configuration from environment variables."""
    load_dotenv()
    
    return ScrapingConfig(
        request_delay=float(os.getenv("REQUEST_DELAY", "1.0")),
        max_concurrent_requests=int(os.getenv("MAX_CONCURRENT_REQUESTS", "5")),
        timeout=int(os.getenv("TIMEOUT", "30")),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        rotate_user_agents=os.getenv("ROTATE_USER_AGENTS", "true").lower() == "true",
        headless_browser=os.getenv("HEADLESS_BROWSER", "true").lower() == "true",
        cache_enabled=os.getenv("CACHE_ENABLED", "true").lower() == "true",
        cache_duration=int(os.getenv("CACHE_DURATION", "3600")),
    )


def load_env_vars() -> Dict[str, Any]:
    """Load environment variables as dictionary."""
    load_dotenv()
    return dict(os.environ)


class UserAgentRotator:
    """User agent rotation utility."""
    
    def __init__(self):
        self.ua = UserAgent()
        self._agents = [
            # Common Japanese user agents
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ]
    
    def get_random_agent(self) -> str:
        """Get a random user agent."""
        return random.choice(self._agents)
    
    def get_chrome_agent(self) -> str:
        """Get a Chrome user agent."""
        try:
            return self.ua.chrome
        except Exception:
            return self._agents[0]


class RateLimiter:
    """Simple rate limiter for requests."""
    
    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.last_request = 0.0
    
    async def wait(self) -> None:
        """Wait if necessary to respect rate limit."""
        now = asyncio.get_event_loop().time()
        time_since_last = now - self.last_request
        
        if time_since_last < self.delay:
            await asyncio.sleep(self.delay - time_since_last)
        
        self.last_request = asyncio.get_event_loop().time()


def save_results_to_csv(results: SearchResult, filename: str) -> None:
    """Save search results to CSV file."""
    filepath = Path(filename)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        if not results.products:
            return  # No products to save
            
        fieldnames = [
            'title', 'price', 'original_price', 'currency', 'url', 'image_url',
            'platform', 'seller', 'rating', 'review_count', 'availability',
            'shipping_cost', 'estimated_delivery', 'description', 'category', 'brand',
            'condition', 'scraped_at'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for product in results.products:
            row = product.dict()
            # Convert datetime to string
            row['scraped_at'] = row['scraped_at'].isoformat()
            writer.writerow(row)
    
    logger.info(f"Saved {len(results.products)} products to {filename}")


def save_results_to_json(results: SearchResult, filename: str) -> None:
    """Save search results to JSON file."""
    filepath = Path(filename)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to dictionary and handle datetime serialization
    data = results.dict()
    data['scraped_at'] = data['scraped_at'].isoformat()
    data['query']['platforms'] = [p.value if hasattr(p, 'value') else p for p in data['query']['platforms']]
    
    for product in data['products']:
        product['scraped_at'] = product['scraped_at'].isoformat() if isinstance(product['scraped_at'], datetime) else product['scraped_at']
        # Convert HttpUrl objects to strings
        if 'url' in product and product['url']:
            product['url'] = str(product['url'])
        if 'image_url' in product and product['image_url']:
            product['image_url'] = str(product['image_url'])
    
    with open(filepath, 'w', encoding='utf-8') as jsonfile:
        json.dump(data, jsonfile, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved search results to {filename}")


def clean_price_string(price_str: str) -> Optional[float]:
    """Extract numeric price from price string."""
    if not price_str:
        return None
    
    # Remove common Japanese price characters and extract numbers
    import re
    
    # Remove non-numeric characters except decimal point and comma
    cleaned = re.sub(r'[^\d.,]', '', price_str)
    
    # Handle Japanese number format (comma as thousands separator)
    cleaned = cleaned.replace(',', '')
    
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def extract_rating(rating_str: str) -> Optional[float]:
    """Extract numeric rating from rating string."""
    if not rating_str:
        return None
    
    import re
    
    # Look for patterns like "4.5", "★★★★☆", etc.
    numbers = re.findall(r'\d+\.?\d*', rating_str)
    if numbers:
        try:
            rating = float(numbers[0])
            # Normalize to 5-point scale if needed
            if rating > 5:
                rating = rating / 2  # Assume 10-point scale
            return min(rating, 5.0)
        except ValueError:
            pass
    
    # Count stars
    star_count = rating_str.count('★') + rating_str.count('⭐')
    if star_count > 0:
        return float(star_count)
    
    return None


def create_data_directory() -> Path:
    """Create and return the data directory path."""
    data_dir = Path(os.getenv("DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


async def send_price_alert(product: Product, target_price: float, email: str) -> None:
    """Send price alert email (placeholder implementation)."""
    # This would integrate with an email service
    logger.info(f"Price alert: {product.title} is now ¥{product.price} (target: ¥{target_price})")
    # TODO: Implement actual email sending with SMTP


def export_to_csv(products: List[Product], filename: str) -> None:
    """Export products to CSV file."""
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        if not products:
            return
        
        fieldnames = ['title', 'price', 'currency', 'url', 'platform', 'image_url', 'rating', 'review_count']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for product in products:
            # Handle platform attribute safely
            try:
                platform_value = product.platform.value if hasattr(product.platform, 'value') else str(product.platform)
            except (AttributeError, TypeError):
                platform_value = str(product.platform)
            
            row = {
                'title': product.title,
                'price': product.price,
                'currency': product.currency,
                'url': str(product.url) if product.url else '',
                'platform': platform_value,
                'image_url': str(product.image_url) if product.image_url else '',
                'rating': product.rating,
                'review_count': product.review_count
            }
            writer.writerow(row)


def export_to_json(products: List[Product], filename: str) -> None:
    """Export products to JSON file."""
    with open(filename, 'w', encoding='utf-8') as jsonfile:
        # Convert products to dictionaries for JSON serialization
        product_dicts = []
        for product in products:
            # Handle platform attribute safely
            try:
                platform_value = product.platform.value if hasattr(product.platform, 'value') else str(product.platform)
            except (AttributeError, TypeError):
                platform_value = str(product.platform)
            
            product_dict = {
                'title': product.title,
                'price': product.price,
                'currency': product.currency,
                'url': str(product.url) if product.url else '',
                'platform': platform_value,
                'image_url': str(product.image_url) if product.image_url else '',
                'rating': product.rating,
                'review_count': product.review_count
            }
            product_dicts.append(product_dict)
        
        json.dump(product_dicts, jsonfile, indent=2, ensure_ascii=False)
