"""
Mercari scraper using Bright Data API.
"""

import urllib.parse
from typing import List, Optional
from selenium.webdriver.common.by import By
from loguru import logger

from ..models import Product, Platform
from .base import BrightDataBaseScraper


class BrightDataMercariScraper(BrightDataBaseScraper):
    """Mercari scraper using Bright Data."""
    
    def get_platform(self) -> Platform:
        return Platform.MERCARI
    
    def get_search_url(self, keyword: str, **kwargs) -> str:
        """Generate Mercari search URL."""
        encoded_keyword = urllib.parse.quote(keyword)
        return f"https://jp.mercari.com/search?keyword={encoded_keyword}"
    
    def parse_search_results(self, keyword: str) -> List[Product]:
        """Parse Mercari search results using JavaScript evaluation."""
        products = []
        
        # Wait for search results to load
        results_container = self.wait_for_element(
            By.CSS_SELECTOR, 
            '[data-testid="item-cell"]',
            timeout=15
        )
        
        if not results_container:
            logger.warning("No Mercari search results container found")
            return products
        
        # Use JavaScript to extract product data directly in browser context
        try:
            script = """
            return Array.from(document.querySelectorAll('[data-testid="item-cell"]')).map(el => {
                try {
                    // Extract title
                    let title = '';
                    const titleSelectors = ['[data-testid="item-name"]', '.item-name', 'h3', '.mer-item-name'];
                    for (const selector of titleSelectors) {
                        const titleEl = el.querySelector(selector);
                        if (titleEl && titleEl.innerText) {
                            title = titleEl.innerText.trim();
                            if (title) break;
                        }
                    }
                    
                    // If no title found via selectors, parse from element text
                    if (!title) {
                        const text = el.innerText || '';
                        const lines = text.split('\\n').map(line => line.trim()).filter(line => line);
                        
                        // For Mercari format: ¥, price, title
                        if (lines.length >= 3 && lines[0] === '¥') {
                            const potentialTitle = lines[2];
                            if (potentialTitle.length > 5 && !potentialTitle.match(/^[\\d,]+$/)) {
                                title = potentialTitle;
                            }
                        } else {
                            // Look for the longest meaningful line
                            for (const line of lines) {
                                if (line.length > 8 && 
                                    !line.startsWith('¥') && 
                                    !line.match(/^[\\d,]+$/) &&
                                    !line.match(/^[\\d,.]+$/) &&
                                    line !== 'SOLD') {
                                    title = line;
                                    break;
                                }
                            }
                        }
                    }
                    
                    // Extract URL
                    let url = '';
                    const linkEl = el.querySelector('a');
                    if (linkEl && linkEl.href) {
                        url = linkEl.href;
                        if (!url.startsWith('http')) {
                            url = 'https://jp.mercari.com' + url;
                        }
                    }
                    
                    // Extract price
                    let price = '';
                    const priceSelectors = ['[data-testid="item-price"]', '.item-price', '.price', '.mer-item-price'];
                    for (const selector of priceSelectors) {
                        const priceEl = el.querySelector(selector);
                        if (priceEl && priceEl.innerText) {
                            price = priceEl.innerText.trim();
                            break;
                        }
                    }
                    
                    // Extract image
                    const imgEl = el.querySelector('img');
                    const image = imgEl ? imgEl.src : '';
                    
                    // Extract condition/status
                    const statusEl = el.querySelector('[data-testid="item-status"]');
                    const status = statusEl ? statusEl.innerText.trim() : '';
                    
                    return {
                        title: title,
                        url: url,
                        price: price,
                        image: image,
                        status: status,
                        element_text: el.innerText ? el.innerText.substring(0, 300) : ''
                    };
                } catch (err) {
                    return {
                        error: err.message,
                        element_text: el.innerText ? el.innerText.substring(0, 200) : ''
                    };
                }
            });
            """
            
            raw_products = self.driver.execute_script(script)
            
            logger.info(f"JavaScript returned {len(raw_products)} raw Mercari products")
            
            # Debug first few products
            for i, raw_product in enumerate(raw_products[:3]):
                logger.info(f"Raw Mercari product {i+1}: {raw_product}")
            
            # Process the raw data into Product objects
            for raw_product in raw_products:
                if 'error' in raw_product:
                    logger.warning(f"JavaScript parsing error: {raw_product['error']}")
                    continue
                
                try:
                    product = self._create_product_from_raw_data(raw_product)
                    if product:
                        products.append(product)
                    else:
                        logger.warning(f"Failed to create Mercari product from: {raw_product}")
                except Exception as e:
                    logger.warning(f"Error creating Mercari product from raw data: {e}")
                    continue
            
            logger.info(f"Successfully parsed {len(products)} Mercari products from {len(raw_products)} elements")
            
        except Exception as e:
            logger.error(f"Error executing JavaScript for Mercari product parsing: {e}")
            # Fallback to old method if JavaScript fails
            return self._parse_search_results_fallback()
        
        return products
    
    def _create_product_from_raw_data(self, raw_data: dict) -> Optional[Product]:
        """Create Product object from raw JavaScript extracted data."""
        # Validate required fields
        title = raw_data.get('title', '').strip()
        url = raw_data.get('url', '').strip()
        
        # Debug log to see what we're getting
        logger.debug(f"Creating Mercari product: title='{title[:30]}...', url='{url[:50]}...'")
        
        if not title or len(title) < 5:
            # If no title from selectors, extract from element text
            if raw_data.get('element_text'):
                element_text = raw_data['element_text'].strip()
                # For Mercari, the title is usually after the price
                # Pattern: ¥\n{price}\n{title}
                lines = [line.strip() for line in element_text.split('\n') if line.strip()]
                
                if len(lines) >= 3 and lines[0] == '¥':
                    # Skip the ¥ and price, take the title (3rd line)
                    potential_title = lines[2]
                    if len(potential_title) > 5 and not potential_title.replace(',', '').isdigit():
                        title = potential_title
                elif len(lines) >= 2:
                    # Try to find the longest meaningful line that could be a title
                    for line in lines[1:]:  # Skip first line (usually price symbol)
                        if (len(line) > 8 and 
                            not line.startswith('¥') and 
                            not line.replace(',', '').isdigit() and
                            not line.replace('.', '').isdigit()):
                            title = line
                            break
            
            if not title or len(title) < 5:
                logger.debug(f"Skipping due to invalid title: '{title}', element_text sample: '{raw_data.get('element_text', '')[:100]}...'")
                return None
        
        # Skip if no valid URL
        if not url or not url.startswith('http'):
            logger.debug(f"Skipping due to invalid URL: '{url}'")
            return None
        
        # Extract price
        price_text = raw_data.get('price', '')
        price = self.extract_price_from_text(price_text)
        
        # If no price from selectors, try extracting from element text
        if not price and raw_data.get('element_text'):
            import re
            element_text = raw_data['element_text']
            # Look for Japanese yen prices (Mercari uses ¥ symbol)
            price_matches = re.findall(r'¥([\d,]+)', element_text)
            if not price_matches:
                # Look for standalone numbers that might be prices
                price_matches = re.findall(r'(\d{1,3}(?:,\d{3})*)', element_text)
            
            for match in price_matches:
                try:
                    potential_price = float(match.replace(',', ''))
                    # Reasonable price range for Mercari products (can be lower than other platforms)
                    if 50 <= potential_price <= 500000:
                        price = potential_price
                        break
                except:
                    continue
        
        # Mercari doesn't typically have ratings, but we'll check
        rating = None
        review_count = None
        
        return Product(
            title=title,
            price=price,
            url=url,
            platform=self.get_platform(),
            image_url=raw_data.get('image', ''),
            rating=rating,
            review_count=review_count,
            currency="JPY"
        )
    
    def _parse_search_results_fallback(self) -> List[Product]:
        """Fallback method using Selenium element parsing."""
        products = []
        
        # Find all product containers
        product_elements = self.safe_find_elements(
            By.CSS_SELECTOR, 
            '[data-testid="item-cell"]'
        )
        
        logger.info(f"Fallback: Found {len(product_elements)} Mercari product elements")
        
        for element in product_elements:
            try:
                product = self._parse_product_element(element)
                if product:
                    products.append(product)
            except Exception as e:
                logger.warning(f"Error parsing Mercari product in fallback: {e}")
                continue
        
        return products
    
    def _parse_product_element(self, element) -> Optional[Product]:
        """Parse individual product element from search results."""
        try:
            # Extract title
            title_elem = self._safe_find_element_in_parent(
                element, By.CSS_SELECTOR, '[data-testid="item-name"], .item-name, h3'
            )
            title = self.extract_text(title_elem) if title_elem else ""
            
            if not title:
                return None
            
            # Extract URL
            link_elem = self._safe_find_element_in_parent(element, By.CSS_SELECTOR, 'a')
            url = self.extract_attribute(link_elem, 'href') if link_elem else ""
            if url and not url.startswith('http'):
                url = f"https://jp.mercari.com{url}"
            
            if not url or not url.startswith('http'):
                return None
            
            # Extract price
            price_elem = self._safe_find_element_in_parent(
                element, By.CSS_SELECTOR, '[data-testid="item-price"], .item-price, .price'
            )
            price_text = self.extract_text(price_elem) if price_elem else ""
            price = self.extract_price_from_text(price_text)
            
            # Extract image
            image_elem = self._safe_find_element_in_parent(element, By.CSS_SELECTOR, 'img')
            image_url = self.extract_attribute(image_elem, 'src') if image_elem else ""
            
            return Product(
                title=title,
                price=price,
                url=url,
                platform=self.get_platform(),
                image_url=image_url,
                rating=None,
                review_count=None,
                currency="JPY"
            )
            
        except Exception as e:
            logger.warning(f"Error parsing Mercari product element: {e}")
            return None
    
    def parse_product_details(self, url: str) -> Optional[Product]:
        """Parse detailed product information from Mercari product page."""
        try:
            self.driver.get(url)
            
            # Wait for product details to load
            self.wait_for_element(By.CSS_SELECTOR, '.item-name, h1', timeout=10)
            
            # Use JavaScript to extract detailed product information
            script = """
            const result = {
                title: '',
                price: '',
                image: '',
                description: '',
                rating: '',
                reviews: '',
                seller: '',
                condition: ''
            };
            
            // Extract title
            const titleSelectors = ['.item-name', 'h1', '.product-name'];
            for (const selector of titleSelectors) {
                const el = document.querySelector(selector);
                if (el && el.innerText) {
                    result.title = el.innerText.trim();
                    break;
                }
            }
            
            // Extract price
            const priceSelectors = ['.price', '.item-price', '.product-price'];
            for (const selector of priceSelectors) {
                const el = document.querySelector(selector);
                if (el && el.innerText) {
                    result.price = el.innerText.trim();
                    break;
                }
            }
            
            // Extract main image
            const imgEl = document.querySelector('.item-image img, .main-image img, img');
            if (imgEl) result.image = imgEl.src;
            
            // Extract seller
            const sellerEl = document.querySelector('.seller-name, .seller, .user-name');
            if (sellerEl) result.seller = sellerEl.innerText.trim();
            
            // Extract condition (specific to Mercari)
            const conditionEl = document.querySelector('.item-condition, .condition');
            if (conditionEl) result.condition = conditionEl.innerText.trim();
            
            return result;
            """
            
            details = self.driver.execute_script(script)
            
            if not details.get('title'):
                logger.warning(f"Could not extract product details from {url}")
                return None
            
            # Extract price from text
            price = self.extract_price_from_text(details.get('price', ''))
            
            return Product(
                title=details['title'],
                price=price,
                url=url,
                platform=self.get_platform(),
                image_url=details.get('image', ''),
                seller=details.get('seller', ''),
                currency="JPY"
            )
            
        except Exception as e:
            logger.warning(f"Error parsing Mercari product details from {url}: {e}")
            return None
    
    def _safe_find_element_in_parent(self, parent, by: By, value: str):
        """Safely find element within parent element."""
        try:
            return parent.find_element(by, value)
        except:
            return None
