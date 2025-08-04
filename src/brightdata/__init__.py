"""
Bright Data API integration for web scraping.
"""

from .connection import BrightDataConfig, BrightDataConnection, test_brightdata_connection
from .base import BrightDataBaseScraper
from .amazon_jp import BrightDataAmazonScraper
from .scraper import BrightDataMarketplaceScraper, search_japanese_marketplaces_brightdata

__all__ = [
    "BrightDataConfig",
    "BrightDataConnection", 
    "test_brightdata_connection",
    "BrightDataBaseScraper",
    "BrightDataAmazonScraper",
    "BrightDataMarketplaceScraper",
    "search_japanese_marketplaces_brightdata"
]

import os
from typing import Optional
from dataclasses import dataclass
from selenium.webdriver import Remote, ChromeOptions
from selenium.webdriver.chromium.remote_connection import ChromiumRemoteConnection
from loguru import logger


@dataclass
class BrightDataConfig:
    """Configuration for Bright Data API."""
    customer_id: str
    zone_name: str
    zone_password: str
    endpoint: str = "brd.superproxy.io:9515"
    
    @property
    def auth_string(self) -> str:
        """Generate authentication string."""
        return f"brd-customer-{self.customer_id}-zone-{self.zone_name}:{self.zone_password}"
    
    @property
    def webdriver_url(self) -> str:
        """Generate WebDriver URL."""
        return f"https://{self.auth_string}@{self.endpoint}"


class BrightDataConnection:
    """Manages Bright Data browser connection."""
    
    def __init__(self, config: BrightDataConfig):
        self.config = config
        self.driver: Optional[Remote] = None
        self.connection: Optional[ChromiumRemoteConnection] = None
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def connect(self) -> Remote:
        """Establish connection to Bright Data browser."""
        try:
            logger.info("Connecting to Bright Data Browser API...")
            
            # Create Chrome options
            options = ChromeOptions()
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions')
            
            # Create connection
            self.connection = ChromiumRemoteConnection(
                self.config.webdriver_url, 
                'goog', 
                'chrome'
            )
            
            # Create driver
            self.driver = Remote(self.connection, options=options)
            
            logger.info("Successfully connected to Bright Data Browser API")
            return self.driver
            
        except Exception as e:
            logger.error(f"Failed to connect to Bright Data: {e}")
            raise
    
    def disconnect(self):
        """Close connection."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Disconnected from Bright Data Browser API")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
    
    def get_driver(self) -> Remote:
        """Get the WebDriver instance."""
        if not self.driver:
            raise RuntimeError("Not connected. Call connect() first.")
        return self.driver


def load_brightdata_config() -> BrightDataConfig:
    """Load Bright Data configuration from environment variables."""
    customer_id = os.getenv("BRIGHTDATA_CUSTOMER_ID")
    zone_name = os.getenv("BRIGHTDATA_ZONE_NAME", "scraping_browser1")
    zone_password = os.getenv("BRIGHTDATA_ZONE_PASSWORD")
    
    if not customer_id or not zone_password:
        raise ValueError(
            "Missing Bright Data credentials. Please set:\n"
            "- BRIGHTDATA_CUSTOMER_ID\n"
            "- BRIGHTDATA_ZONE_PASSWORD\n"
            "- BRIGHTDATA_ZONE_NAME (optional, defaults to 'scraping_browser1')"
        )
    
    return BrightDataConfig(
        customer_id=customer_id,
        zone_name=zone_name,
        zone_password=zone_password
    )


# Example usage function
def test_brightdata_connection():
    """Test Bright Data connection."""
    try:
        config = load_brightdata_config()
        
        with BrightDataConnection(config) as conn:
            driver = conn.get_driver()
            
            print("Testing connection...")
            driver.get('https://example.com')
            
            print(f"Page title: {driver.title}")
            print("Connection test successful!")
            
    except Exception as e:
        print(f"Connection test failed: {e}")


if __name__ == "__main__":
    test_brightdata_connection()
