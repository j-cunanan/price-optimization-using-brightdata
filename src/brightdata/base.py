"""
Base scraper for Bright Data API integration.
"""

import time
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from selenium.webdriver import Remote
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from loguru import logger

from ..models import Product, Platform, ScrapingConfig
from .connection import BrightDataConnection, BrightDataConfig


class BrightDataBaseScraper(ABC):
    """Base class for Bright Data-powered scrapers."""
    
    def __init__(self, brightdata_config: BrightDataConfig, scraping_config: ScrapingConfig):
        self.brightdata_config = brightdata_config
        self.scraping_config = scraping_config
        self.connection: Optional[BrightDataConnection] = None
        self.driver: Optional[Remote] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.start_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.close_session()
    
    def start_session(self) -> None:
        """Start Bright Data session."""
        self.connection = BrightDataConnection(self.brightdata_config)
        self.driver = self.connection.connect()
    
    def close_session(self) -> None:
        """Close Bright Data session."""
        if self.connection:
            self.connection.disconnect()
    
    def wait_for_element(self, by: By, value: str, timeout: int = 10) -> Any:
        """Wait for element to be present."""
        try:
            wait = WebDriverWait(self.driver, timeout)
            return wait.until(EC.presence_of_element_located((by, value)))
        except TimeoutException:
            logger.warning(f"Element not found: {by}={value}")
            return None
    
    def safe_find_element(self, by: By, value: str) -> Optional[Any]:
        """Safely find element without throwing exception."""
        try:
            return self.driver.find_element(by, value)
        except NoSuchElementException:
            return None
    
    def safe_find_elements(self, by: By, value: str) -> List[Any]:
        """Safely find elements without throwing exception."""
        try:
            return self.driver.find_elements(by, value)
        except NoSuchElementException:
            return []
    
    def extract_text(self, element: Any) -> str:
        """Safely extract text from element."""
        try:
            return element.text.strip() if element else ""
        except Exception:
            return ""
    
    def extract_attribute(self, element: Any, attribute: str) -> str:
        """Safely extract attribute from element."""
        try:
            return element.get_attribute(attribute) if element else ""
        except Exception:
            return ""
    
    def navigate_to_url(self, url: str) -> bool:
        """Navigate to URL with error handling."""
        try:
            logger.info(f"Navigating to: {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(self.scraping_config.request_delay)
            
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to {url}: {e}")
            return False
    
    def take_screenshot(self, filename: str) -> bool:
        """Take screenshot for debugging."""
        try:
            self.driver.get_screenshot_as_file(filename)
            logger.info(f"Screenshot saved: {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return False
    
    @abstractmethod
    def get_platform(self) -> Platform:
        """Return the platform this scraper handles."""
        pass
        
    @abstractmethod
    def get_search_url(self, keyword: str, **kwargs) -> str:
        """Generate search URL for the given keyword."""
        pass
    
    @abstractmethod
    def parse_search_results(self, keyword: str) -> List[Product]:
        """Parse search results from the current page."""
        pass
    
    @abstractmethod
    def parse_product_details(self, url: str) -> Optional[Product]:
        """Parse detailed product information from product page."""
        pass
    
    def search(self, keyword: str, max_results: int = 20, **kwargs) -> List[Product]:
        """Search for products on this platform using Bright Data."""
        products = []
        
        try:
            search_url = self.get_search_url(keyword, **kwargs)
            
            if not self.navigate_to_url(search_url):
                return products
            
            # Wait for page to stabilize
            self._wait_for_page_stability()
            
            # Parse search results
            products = self.parse_search_results(keyword)
            
            # Limit results
            if len(products) > max_results:
                products = products[:max_results]
            
            logger.info(f"Found {len(products)} products on {self.get_platform().value} via Bright Data")
            
        except Exception as e:
            logger.error(f"Error searching {self.get_platform().value} via Bright Data: {e}")
            
        return products
    
    def _wait_for_page_stability(self, timeout: int = 10) -> bool:
        """Wait for page to be stable and fully loaded."""
        try:
            # Wait for document ready state
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Wait for no network activity (simplified)
            time.sleep(2)
            
            # Check if page has expected content patterns
            return self._verify_page_loaded()
            
        except Exception as e:
            logger.warning(f"Page stability check failed: {e}")
            return False
    
    def _verify_page_loaded(self) -> bool:
        """Verify that the page has loaded expected content."""
        try:
            # Check for common loading indicators
            loading_indicators = [
                '[data-testid="loading"]',
                '.loading',
                '.spinner',
                '[aria-label*="loading" i]'
            ]
            
            for indicator in loading_indicators:
                elements = self.safe_find_elements(By.CSS_SELECTOR, indicator)
                if elements:
                    logger.debug(f"Page still loading (found {indicator})")
                    return False
            
            return True
        except Exception as e:
            logger.warning(f"Page verification failed: {e}")
            return True  # Default to proceed
    
    def execute_script_with_retry(self, script: str, max_retries: int = 3) -> Any:
        """Execute JavaScript with retry logic for Bright Data stability."""
        for attempt in range(max_retries):
            try:
                result = self.driver.execute_script(script)
                return result
            except Exception as e:
                logger.warning(f"Script execution attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    raise
        return None
    
    def extract_price_from_text(self, price_text: str) -> Optional[float]:
        """Extract price from text."""
        if not price_text:
            return None
        
        import re
        
        # Remove non-numeric characters except decimal point and comma
        cleaned = re.sub(r'[^\d.,]', '', price_text)
        
        # Handle Japanese number format (comma as thousands separator)
        cleaned = cleaned.replace(',', '')
        
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    
    def extract_rating_from_text(self, rating_text: str) -> Optional[float]:
        """Extract numeric rating from rating string."""
        if not rating_text:
            return None
        
        import re
        
        # Look for patterns like "4.5", "★★★★☆", etc.
        numbers = re.findall(r'\d+\.?\d*', rating_text)
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
        star_count = rating_text.count('★') + rating_text.count('⭐')
        if star_count > 0:
            return float(star_count)
        
        return None
