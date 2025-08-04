"""
Yahoo Shopping scraper using Bright Data API.
"""

import urllib.parse
from typing import List, Optional
from selenium.webdriver.common.by import By
from loguru import logger

from ..models import Product, Platform
from .base import BrightDataBaseScraper


class BrightDataYahooShoppingScraper(BrightDataBaseScraper):
    """Yahoo Shopping scraper using Bright Data."""
    
    def get_platform(self) -> Platform:
        return Platform.YAHOO_SHOPPING
    
    def get_search_url(self, keyword: str, **kwargs) -> str:
        """Generate Yahoo Shopping search URL."""
        encoded_keyword = urllib.parse.quote(keyword)
        return f"https://shopping.yahoo.co.jp/search?p={encoded_keyword}"
    
    def parse_search_results(self, keyword: str) -> List[Product]:
        """Parse Yahoo Shopping search results using JavaScript evaluation."""
        products = []
        
        # Wait for search results to load - try multiple selectors
        results_container = None
        container_selectors = [
            '.Product',
            '[data-testid="item"]',
            '.item',
            '.searchresult',
            '.result',
            '.srp-item'
        ]
        
        for selector in container_selectors:
            results_container = self.wait_for_element(
                By.CSS_SELECTOR, 
                selector,
                timeout=5
            )
            if results_container:
                logger.info(f"Found Yahoo Shopping results with selector: {selector}")
                break
        
        if not results_container:
            logger.warning("No Yahoo Shopping search results container found with any selector")
            return products
        
        # Use JavaScript to extract product data directly in browser context
        try:
            script = """
            // Try multiple selectors for product containers
            const containerSelectors = ['.Product', '[data-testid="item"]', '.item', '.searchresult', '.result', '.srp-item'];
            let products = [];
            
            for (const containerSelector of containerSelectors) {
                const elements = document.querySelectorAll(containerSelector);
                if (elements.length > 0) {
                    products = Array.from(elements);
                    break;
                }
            }
            
            return products.map(el => {
                try {
                    // Extract title - try multiple selectors
                    let title = '';
                    const titleSelectors = [
                        '.Product__titleLink', 
                        '.Product__title a', 
                        '.title a', 
                        'h3 a',
                        'a[href*="/item/"]',
                        '.productTitle',
                        '.itemTitle'
                    ];
                    for (const selector of titleSelectors) {
                        const titleEl = el.querySelector(selector);
                        if (titleEl) {
                            // Try title attribute first, then innerText
                            if (titleEl.title) {
                                title = titleEl.title.trim();
                            } else if (titleEl.innerText) {
                                title = titleEl.innerText.trim();
                            }
                            if (title) break;
                        }
                    }
                    
                    // If no title from selectors, try element text parsing
                    if (!title) {
                        const text = el.innerText || '';
                        const lines = text.split('\\n').map(line => line.trim()).filter(line => line);
                        // Look for likely title (not price, not short text)
                        for (const line of lines) {
                            if (line.length > 10 && 
                                !line.match(/^[¥$]?\\d+([,.]\\d+)*[円¥]?$/) && 
                                !line.match(/^\\d+%/) &&
                                !line.match(/送料|ポイント|評価/)) {
                                title = line;
                                break;
                            }
                        }
                    }
                    
                    // Extract URL
                    let url = '';
                    const urlSelectors = [
                        '.Product__titleLink', 
                        '.Product__title a', 
                        '.title a', 
                        'h3 a',
                        'a[href*="/item/"]',
                        'a[href*="shopping.yahoo.co.jp"]',
                        'a[href*="/p/"]',
                        'a'
                    ];
                    for (const selector of urlSelectors) {
                        const urlEl = el.querySelector(selector);
                        if (urlEl && urlEl.href) {
                            url = urlEl.href;
                            if (url.includes('yahoo.co.jp') || url.includes('/item/')) {
                                break;
                            }
                        }
                    }
                    
                    // If no specific URL found, look for any link
                    if (!url) {
                        const anyLink = el.querySelector('a');
                        if (anyLink && anyLink.href) {
                            url = anyLink.href;
                        }
                    }
                    
                    // Extract price
                    let price = '';
                    const priceSelectors = ['.Product__priceValue', '.price', '.Product__price', '.priceArea'];
                    for (const selector of priceSelectors) {
                        const priceEl = el.querySelector(selector);
                        if (priceEl && priceEl.innerText) {
                            price = priceEl.innerText.trim();
                            break;
                        }
                    }
                    
                    // If no price from selectors, parse from element text
                    if (!price) {
                        const text = el.innerText || '';
                        const lines = text.split('\\n').map(line => line.trim()).filter(line => line);
                        
                        for (const line of lines) {
                            // Look for price patterns (numbers with 円)
                            if (line.match(/^[\\d,]+\\s*円$/)) {
                                price = line;
                                break;
                            } else if (line.match(/^[\\d,]+$/)) {
                                // Just numbers (common in Yahoo auctions)
                                const nextLineIndex = lines.indexOf(line) + 1;
                                if (nextLineIndex < lines.length && lines[nextLineIndex] === '円') {
                                    price = line + '円';
                                    break;
                                }
                            }
                        }
                    }
                    
                    // Extract image
                    const imgEl = el.querySelector('.Product__imageLink img, img');
                    const image = imgEl ? imgEl.src : '';
                    
                    // Extract rating
                    const ratingEl = el.querySelector('.Product__review, .review, .rating');
                    const rating = ratingEl ? ratingEl.innerText.trim() : '';
                    
                    // Extract shop name
                    const shopEl = el.querySelector('.Product__shop, .shop, .store');
                    const shop = shopEl ? shopEl.innerText.trim() : '';
                    
                    return {
                        title: title,
                        url: url,
                        price: price,
                        image: image,
                        rating: rating,
                        shop: shop,
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
            
            logger.info(f"JavaScript returned {len(raw_products)} raw Yahoo Shopping products")
            
            # Debug first few products
            for i, raw_product in enumerate(raw_products[:3]):
                logger.info(f"Raw Yahoo Shopping product {i+1}: {raw_product}")
            
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
                        logger.warning(f"Failed to create Yahoo Shopping product from: {raw_product}")
                except Exception as e:
                    logger.warning(f"Error creating Yahoo Shopping product from raw data: {e}")
                    continue
            
            logger.info(f"Successfully parsed {len(products)} Yahoo Shopping products from {len(raw_products)} elements")
            
        except Exception as e:
            logger.error(f"Error executing JavaScript for Yahoo Shopping product parsing: {e}")
            # Fallback to old method if JavaScript fails
            return self._parse_search_results_fallback()
        
        return products
    
    def _create_product_from_raw_data(self, raw_data: dict) -> Optional[Product]:
        """Create Product object from raw JavaScript extracted data."""
        # Validate required fields
        title = raw_data.get('title', '').strip()
        url = raw_data.get('url', '').strip()
        
        # Debug log to see what we're getting
        logger.debug(f"Creating Yahoo Shopping product: title='{title[:30]}...', url='{url[:50]}...'")
        
        if not title or len(title) < 5:
            logger.debug(f"Skipping due to invalid title: '{title}'")
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
            # Look for Japanese yen prices
            price_matches = re.findall(r'¥?([\d,]+)円?', element_text)
            if not price_matches:
                # Look for standalone numbers that might be prices
                price_matches = re.findall(r'(\d{1,3}(?:,\d{3})*)', element_text)
            
            for match in price_matches:
                try:
                    potential_price = float(match.replace(',', ''))
                    # Reasonable price range for products
                    if 100 <= potential_price <= 500000:
                        price = potential_price
                        break
                except:
                    continue
        
        # Extract rating
        rating_text = raw_data.get('rating', '')
        rating = self.extract_rating_from_text(rating_text)
        
        # Extract review count from element text
        review_count = None
        if raw_data.get('element_text'):
            import re
            review_matches = re.findall(r'(\d+(?:,\d+)*)\s*(?:件|個|レビュー)', raw_data['element_text'])
            if review_matches:
                try:
                    review_count = int(review_matches[0].replace(',', ''))
                except:
                    pass
        
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
            '.Product'
        )
        
        logger.info(f"Fallback: Found {len(product_elements)} Yahoo Shopping product elements")
        
        for element in product_elements:
            try:
                product = self._parse_product_element(element)
                if product:
                    products.append(product)
            except Exception as e:
                logger.warning(f"Error parsing Yahoo Shopping product in fallback: {e}")
                continue
        
        return products
    
    def _parse_product_element(self, element) -> Optional[Product]:
        """Parse individual product element from search results."""
        try:
            # Extract title
            title_elem = self._safe_find_element_in_parent(
                element, By.CSS_SELECTOR, '.Product__titleLink, .Product__title a, .title a'
            )
            title = self.extract_text(title_elem) if title_elem else ""
            
            if not title:
                return None
            
            # Extract URL
            url = self.extract_attribute(title_elem, 'href') if title_elem else ""
            if not url or not url.startswith('http'):
                return None
            
            # Extract price
            price_elem = self._safe_find_element_in_parent(
                element, By.CSS_SELECTOR, '.Product__priceValue, .price, .Product__price'
            )
            price_text = self.extract_text(price_elem) if price_elem else ""
            price = self.extract_price_from_text(price_text)
            
            # Extract image
            image_elem = self._safe_find_element_in_parent(element, By.CSS_SELECTOR, '.Product__imageLink img, img')
            image_url = self.extract_attribute(image_elem, 'src') if image_elem else ""
            
            # Extract rating
            rating_elem = self._safe_find_element_in_parent(
                element, By.CSS_SELECTOR, '.Product__review, .review, .rating'
            )
            rating_text = self.extract_text(rating_elem) if rating_elem else ""
            rating = self.extract_rating_from_text(rating_text)
            
            return Product(
                title=title,
                price=price,
                url=url,
                platform=self.get_platform(),
                image_url=image_url,
                rating=rating,
                review_count=None,
                currency="JPY"
            )
            
        except Exception as e:
            logger.warning(f"Error parsing Yahoo Shopping product element: {e}")
            return None
    
    def parse_product_details(self, url: str) -> Optional[Product]:
        """Parse detailed product information from Yahoo Shopping product page."""
        try:
            self.driver.get(url)
            
            # Wait for product details to load
            self.wait_for_element(By.CSS_SELECTOR, '.ProductTitle, h1', timeout=10)
            
            # Use JavaScript to extract detailed product information
            script = """
            const result = {
                title: '',
                price: '',
                image: '',
                description: '',
                rating: '',
                reviews: '',
                seller: ''
            };
            
            // Extract title
            const titleSelectors = ['.ProductTitle', 'h1', '.product-title'];
            for (const selector of titleSelectors) {
                const el = document.querySelector(selector);
                if (el && el.innerText) {
                    result.title = el.innerText.trim();
                    break;
                }
            }
            
            // Extract price
            const priceSelectors = ['.Price, .price', '.product-price'];
            for (const selector of priceSelectors) {
                const el = document.querySelector(selector);
                if (el && el.innerText) {
                    result.price = el.innerText.trim();
                    break;
                }
            }
            
            // Extract main image
            const imgEl = document.querySelector('.ProductImage img, .main-image img, img');
            if (imgEl) result.image = imgEl.src;
            
            // Extract seller/shop
            const sellerEl = document.querySelector('.Store, .shop-name, .seller');
            if (sellerEl) result.seller = sellerEl.innerText.trim();
            
            // Extract rating
            const ratingEl = document.querySelector('.Rating, .rating, .review-rating');
            if (ratingEl) result.rating = ratingEl.innerText.trim();
            
            return result;
            """
            
            details = self.driver.execute_script(script)
            
            if not details.get('title'):
                logger.warning(f"Could not extract product details from {url}")
                return None
            
            # Extract price and rating from text
            price = self.extract_price_from_text(details.get('price', ''))
            rating = self.extract_rating_from_text(details.get('rating', ''))
            
            return Product(
                title=details['title'],
                price=price,
                url=url,
                platform=self.get_platform(),
                image_url=details.get('image', ''),
                seller=details.get('seller', ''),
                rating=rating,
                currency="JPY"
            )
            
        except Exception as e:
            logger.warning(f"Error parsing Yahoo Shopping product details from {url}: {e}")
            return None
    
    def _safe_find_element_in_parent(self, parent, by: By, value: str):
        """Safely find element within parent element."""
        try:
            return parent.find_element(by, value)
        except:
            return None
