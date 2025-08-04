"""
Rakuten scraper using Bright Data API.
"""

import urllib.parse
from typing import List, Optional
from selenium.webdriver.common.by import By
from loguru import logger

from ..models import Product, Platform
from .base import BrightDataBaseScraper


class BrightDataRakutenScraper(BrightDataBaseScraper):
    """Rakuten scraper using Bright Data."""
    
    def get_platform(self) -> Platform:
        return Platform.RAKUTEN
    
    def get_search_url(self, keyword: str, **kwargs) -> str:
        """Generate Rakuten search URL."""
        encoded_keyword = urllib.parse.quote(keyword)
        return f"https://search.rakuten.co.jp/search/mall/{encoded_keyword}/"
    
    def parse_search_results(self, keyword: str) -> List[Product]:
        """Parse Rakuten search results using JavaScript evaluation."""
        products = []
        
        # Try multiple selectors for search results
        search_result_selectors = [
            '.searchresultitem',
            '.item',
            '[data-ratid="searchresultitem"]',
            '.search-result-item'
        ]
        
        results_container = None
        for selector in search_result_selectors:
            results_container = self.wait_for_element(
                By.CSS_SELECTOR, 
                selector,
                timeout=5
            )
            if results_container:
                logger.info(f"Found Rakuten results with selector: {selector}")
                break
        
        if not results_container:
            logger.warning("No Rakuten search results container found with any selector")
            return products
        
        # Wait for page stability
        self._wait_for_page_stability()
        
        # Use enhanced JavaScript to extract product data
        try:
            script = """
            return Array.from(document.querySelectorAll('.searchresultitem, .item, [data-ratid="searchresultitem"]')).map(el => {
                try {
                    // Extract title with multiple fallbacks
                    let title = '';
                    const titleSelectors = [
                        '.content.title h2 a', 
                        '.title a', 
                        'h2 a', 
                        '.item_name a',
                        '.itemName a',
                        'a[href*="/item/"]'
                    ];
                    for (const selector of titleSelectors) {
                        const titleEl = el.querySelector(selector);
                        if (titleEl && titleEl.innerText && titleEl.innerText.trim()) {
                            title = titleEl.innerText.trim();
                            if (title.length > 3) break;
                        }
                    }
                    
                    // Extract URL with multiple fallbacks
                    let url = '';
                    for (const selector of titleSelectors) {
                        const urlEl = el.querySelector(selector);
                        if (urlEl && urlEl.href && urlEl.href.startsWith('http')) {
                            url = urlEl.href;
                            break;
                        }
                    }
                    
                    // Extract price with enhanced selectors
                    let price = '';
                    const priceSelectors = [
                        '.important', 
                        '.price', 
                        '.item_price', 
                        '.priceArea .important',
                        '.priceNum',
                        '[class*="price"]'
                    ];
                    for (const selector of priceSelectors) {
                        const priceEl = el.querySelector(selector);
                        if (priceEl && priceEl.innerText && priceEl.innerText.trim()) {
                            price = priceEl.innerText.trim();
                            // Prefer prices with yen symbols or numbers
                            if (price.includes('¥') || price.includes('円') || /\d{2,}/.test(price)) {
                                break;
                            }
                        }
                    }
                    
                    // Extract image with fallbacks
                    let image = '';
                    const imgSelectors = ['img[src*="jpg"]', 'img[src*="png"]', 'img[src*="jpeg"]', 'img'];
                    for (const selector of imgSelectors) {
                        const imgEl = el.querySelector(selector);
                        if (imgEl && imgEl.src && imgEl.src.startsWith('http')) {
                            image = imgEl.src;
                            break;
                        }
                    }
                    
                    // Extract rating
                    let rating = '';
                    const ratingSelectors = ['.star_rating', '.rating', '[class*="rating"]', '[class*="star"]'];
                    for (const selector of ratingSelectors) {
                        const ratingEl = el.querySelector(selector);
                        if (ratingEl) {
                            rating = ratingEl.getAttribute('title') || ratingEl.innerText || '';
                            if (rating.trim()) break;
                        }
                    }
                    
                    // Extract shop name
                    let shop = '';
                    const shopSelectors = ['.merchant a', '.shop_name a', '.store a', '[class*="shop"] a'];
                    for (const selector of shopSelectors) {
                        const shopEl = el.querySelector(selector);
                        if (shopEl && shopEl.innerText && shopEl.innerText.trim()) {
                            shop = shopEl.innerText.trim();
                            break;
                        }
                    }
                    
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
                        element_text: el.innerText ? el.innerText.substring(0, 200) : '',
                        title: '',
                        url: '',
                        price: ''
                    };
                }
            });
            """
            
            raw_products = self.execute_script_with_retry(script)
            
            logger.info(f"JavaScript returned {len(raw_products)} raw Rakuten products")
            
            # Filter out invalid products and collect stats
            valid_products = [p for p in raw_products if not p.get('error')]
            error_count = len(raw_products) - len(valid_products)
            
            logger.info(f"Found {len(valid_products)} valid Rakuten products, {error_count} errors")
            
            # Quality statistics
            quality_stats = {
                'has_title': sum(1 for p in valid_products if p.get('title') and len(p['title']) > 3),
                'has_url': sum(1 for p in valid_products if p.get('url') and p['url'].startswith('http')),
                'has_price': sum(1 for p in valid_products if p.get('price') and p['price'].strip())
            }
            logger.info(f"Rakuten product quality: {quality_stats}")
            
            # Debug first few products
            for i, raw_product in enumerate(raw_products[:3]):
                title_preview = raw_product.get('title', '')[:50] + '...' if raw_product.get('title') else 'No title'
                has_url = bool(raw_product.get('url') and raw_product['url'].startswith('http'))
                has_price = bool(raw_product.get('price') and raw_product['price'].strip())
                logger.info(f"Raw Rakuten product {i+1}: title='{title_preview}', has_url={has_url}, has_price={has_price}")
            
            # Process the raw data into Product objects
            for raw_product in valid_products:
                try:
                    product = self._create_product_from_raw_data(raw_product)
                    if product:
                        products.append(product)
                    else:
                        title_preview = raw_product.get('title', '')[:50] + '...' if raw_product.get('title') else 'No title'
                        logger.debug(f"Failed to create Rakuten product from: title='{title_preview}'")
                except Exception as e:
                    logger.warning(f"Error creating Rakuten product from raw data: {e}")
                    continue
            
            logger.info(f"Successfully parsed {len(products)} Rakuten products from {len(valid_products)} valid elements")
            
        except Exception as e:
            logger.error(f"Error executing JavaScript for Rakuten product parsing: {e}")
            # Fallback to old method if JavaScript fails
            return self._parse_search_results_fallback()
        
        return products
    
    def _create_product_from_raw_data(self, raw_data: dict) -> Optional[Product]:
        """Create Product object from raw JavaScript extracted data with enhanced validation."""
        # Validate required fields
        title = raw_data.get('title', '').strip()
        url = raw_data.get('url', '').strip()
        
        # Debug log to see what we're getting
        title_preview = title[:50] + '...' if len(title) > 50 else title
        url_preview = url[:50] + '...' if len(url) > 50 else url
        logger.debug(f"Creating Rakuten product: title='{title_preview}', url='{url_preview}'")
        
        # Skip invalid titles
        if not title or len(title) < 3 or title in ['...', '']:
            logger.debug(f"Skipping due to invalid title: '{title}'")
            return None
        
        # Skip promotional/ad content
        promotional_keywords = ['整備済み品', 'スポンサー', '広告', 'AD', 'Sponsored']
        if any(keyword in title for keyword in promotional_keywords):
            logger.debug(f"Skipping promotional/ad content: '{title}'")
            return None
        
        # Skip if no valid URL
        if not url or not url.startswith('http'):
            logger.debug(f"Skipping due to missing URL for: '{title_preview}'")
            return None
        
        # Make URL absolute if needed
        if url.startswith('/'):
            url = f"https://search.rakuten.co.jp{url}"
        elif not url.startswith('http'):
            url = f"https://search.rakuten.co.jp/{url}"
        
        # Extract and validate price
        price_text = raw_data.get('price', '')
        price = self._extract_price_robustly(price_text, raw_data.get('element_text', ''))
        
        # Extract and validate rating
        rating_text = raw_data.get('rating', '')
        rating = self._extract_rating_robustly(rating_text)
        
        # Extract review count from element text
        review_count = self._extract_review_count(raw_data.get('element_text', ''))
        
        # Validate image URL
        image_url = raw_data.get('image', '')
        if image_url and not image_url.startswith('http'):
            image_url = None
        
        return Product(
            title=title,
            price=price,
            url=url,
            platform=self.get_platform(),
            image_url=image_url,
            rating=rating,
            review_count=review_count,
            seller=raw_data.get('shop', ''),
            currency="JPY"
        )
    
    def _extract_price_robustly(self, price_text: str, element_text: str = '') -> Optional[float]:
        """Extract price with multiple fallback strategies."""
        import re
        
        # First try the direct price text
        price = self.extract_price_from_text(price_text)
        if price:
            return price
        
        # Try extracting from element text with various patterns
        combined_text = f"{price_text} {element_text}"
        
        # Pattern 1: Japanese yen with symbols
        yen_patterns = [
            r'¥([\d,]+)',
            r'([\d,]+)円',
            r'価格[：:\s]*([\d,]+)',
            r'([\d,]+)\s*円'
        ]
        
        for pattern in yen_patterns:
            matches = re.findall(pattern, combined_text)
            for match in matches:
                try:
                    potential_price = float(match.replace(',', ''))
                    # Reasonable price range for products (100 yen to 500,000 yen)
                    if 100 <= potential_price <= 500000:
                        return potential_price
                except:
                    continue
        
        # Pattern 2: Look for standalone numbers that might be prices
        number_matches = re.findall(r'(\d{1,3}(?:,\d{3})+|\d{3,6})', combined_text)
        for match in number_matches:
            try:
                potential_price = float(match.replace(',', ''))
                # More restrictive range for standalone numbers
                if 500 <= potential_price <= 500000:
                    return potential_price
            except:
                continue
        
        return None
    
    def _extract_rating_robustly(self, rating_text: str) -> Optional[float]:
        """Extract rating with enhanced parsing."""
        if not rating_text:
            return None
        
        import re
        
        # Try direct extraction first
        rating = self.extract_rating_from_text(rating_text)
        if rating:
            return rating
        
        # Try extracting from various formats
        rating_patterns = [
            r'(\d+\.?\d*)\s*(?:点|stars?|★)',
            r'評価[：:\s]*(\d+\.?\d*)',
            r'星(\d+\.?\d*)',
            r'(\d+\.?\d*)/5'
        ]
        
        for pattern in rating_patterns:
            matches = re.findall(pattern, rating_text)
            for match in matches:
                try:
                    rating_val = float(match)
                    if 0 <= rating_val <= 5:
                        return rating_val
                except:
                    continue
        
        return None
    
    def _extract_review_count(self, element_text: str) -> Optional[int]:
        """Extract review count from element text."""
        if not element_text:
            return None
        
        import re
        
        # Japanese review count patterns
        review_patterns = [
            r'(\d+(?:,\d+)*)\s*(?:件|個|レビュー|reviews?)',
            r'レビュー[：:\s]*(\d+(?:,\d+)*)',
            r'評価数[：:\s]*(\d+(?:,\d+)*)'
        ]
        
        for pattern in review_patterns:
            matches = re.findall(pattern, element_text)
            for match in matches:
                try:
                    count = int(match.replace(',', ''))
                    if count > 0:
                        return count
                except:
                    continue
        
        return None
    
    def _parse_search_results_fallback(self) -> List[Product]:
        """Fallback method using Selenium element parsing."""
        products = []
        
        # Find all product containers
        product_elements = self.safe_find_elements(
            By.CSS_SELECTOR, 
            '.searchresultitem'
        )
        
        logger.info(f"Fallback: Found {len(product_elements)} Rakuten product elements")
        
        for element in product_elements:
            try:
                product = self._parse_product_element(element)
                if product:
                    products.append(product)
            except Exception as e:
                logger.warning(f"Error parsing Rakuten product in fallback: {e}")
                continue
        
        return products
    
    def _parse_product_element(self, element) -> Optional[Product]:
        """Parse individual product element from search results."""
        try:
            # Extract title
            title_elem = self._safe_find_element_in_parent(
                element, By.CSS_SELECTOR, '.content.title h2 a, .title a, h2 a'
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
                element, By.CSS_SELECTOR, '.important, .price'
            )
            price_text = self.extract_text(price_elem) if price_elem else ""
            price = self.extract_price_from_text(price_text)
            
            # Extract image
            image_elem = self._safe_find_element_in_parent(element, By.CSS_SELECTOR, 'img')
            image_url = self.extract_attribute(image_elem, 'src') if image_elem else ""
            
            # Extract rating
            rating_elem = self._safe_find_element_in_parent(
                element, By.CSS_SELECTOR, '.star_rating, .rating'
            )
            rating_text = self.extract_attribute(rating_elem, 'title') or self.extract_text(rating_elem) if rating_elem else ""
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
            logger.warning(f"Error parsing Rakuten product element: {e}")
            return None
    
    def parse_product_details(self, url: str) -> Optional[Product]:
        """Parse detailed product information from Rakuten product page."""
        try:
            self.driver.get(url)
            
            # Wait for product details to load
            self.wait_for_element(By.CSS_SELECTOR, '.itemName, h1', timeout=10)
            
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
            const titleSelectors = ['.itemName', 'h1', '.item_name'];
            for (const selector of titleSelectors) {
                const el = document.querySelector(selector);
                if (el && el.innerText) {
                    result.title = el.innerText.trim();
                    break;
                }
            }
            
            // Extract price
            const priceSelectors = ['.price', '.item_price', '.product_price'];
            for (const selector of priceSelectors) {
                const el = document.querySelector(selector);
                if (el && el.innerText) {
                    result.price = el.innerText.trim();
                    break;
                }
            }
            
            // Extract main image
            const imgEl = document.querySelector('.item_image img, .main_image img, img');
            if (imgEl) result.image = imgEl.src;
            
            // Extract seller
            const sellerEl = document.querySelector('.shop_name, .seller, .store_name');
            if (sellerEl) result.seller = sellerEl.innerText.trim();
            
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
            logger.warning(f"Error parsing Rakuten product details from {url}: {e}")
            return None
    
    def _safe_find_element_in_parent(self, parent, by: By, value: str):
        """Safely find element within parent element."""
        try:
            return parent.find_element(by, value)
        except:
            return None
