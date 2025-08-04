"""
Amazon.jp scraper using Bright Data API.
"""

import urllib.parse
from typing import List, Optional
from selenium.webdriver.common.by import By
from loguru import logger

from ..models import Product, Platform
from .base import BrightDataBaseScraper


class BrightDataAmazonScraper(BrightDataBaseScraper):
    """Amazon.jp scraper using Bright Data."""
    
    def get_platform(self) -> Platform:
        return Platform.AMAZON_JP
    
    def get_search_url(self, keyword: str, **kwargs) -> str:
        """Generate Amazon.jp search URL."""
        encoded_keyword = urllib.parse.quote(keyword)
        return f"https://www.amazon.co.jp/s?k={encoded_keyword}&ref=nb_sb_noss"
    
    def parse_search_results(self, keyword: str) -> List[Product]:
        """Parse Amazon search results using JavaScript evaluation."""
        products = []
        
        # Wait for search results to load with multiple selectors
        results_container = None
        selectors_to_try = [
            '[data-component-type="s-search-result"]',
            '.s-result-item',
            '[data-testid="result-info-bar"]',
            '.s-search-results'
        ]
        
        for selector in selectors_to_try:
            results_container = self.wait_for_element(By.CSS_SELECTOR, selector, timeout=10)
            if results_container:
                logger.info(f"Found search results with selector: {selector}")
                break
        
        if not results_container:
            logger.warning("No search results container found with any selector")
            return products
        
        # Wait for dynamic content to load
        import time
        time.sleep(3)
        
        # Use JavaScript to extract product data directly in browser context
        try:
            script = """
            // Wait for products to be fully loaded
            function waitForProducts() {
                return new Promise((resolve) => {
                    let attempts = 0;
                    const maxAttempts = 10;
                    
                    function checkProducts() {
                        const products = document.querySelectorAll('[data-component-type="s-search-result"], .s-result-item');
                        if (products.length > 0 || attempts >= maxAttempts) {
                            resolve(products);
                        } else {
                            attempts++;
                            setTimeout(checkProducts, 500);
                        }
                    }
                    checkProducts();
                });
            }
            
            const productElements = await waitForProducts();
            
            return Array.from(productElements).map((el, index) => {
                try {
                    // Extract title with robust selectors
                    let title = '';
                    const titleSelectors = [
                        'h2 a span[aria-label]',
                        'h2 a span:not([class*="text-decoration-line-through"])',
                        'h2 span[data-cy="title-recipe-title"]',
                        '.s-size-mini span',
                        'h2 a span',
                        'h2 span'
                    ];
                    
                    for (const selector of titleSelectors) {
                        const titleEl = el.querySelector(selector);
                        if (titleEl) {
                            const candidateTitle = titleEl.innerText || titleEl.textContent || '';
                            if (candidateTitle && 
                                candidateTitle.trim().length > 5 && 
                                !['スポンサー', '結果', 'Sponsored', "Amazon's Choice", 'AD'].includes(candidateTitle.trim())) {
                                title = candidateTitle.trim();
                                break;
                            }
                        }
                    }
                    
                    // Fallback: extract title from element structure
                    if (!title) {
                        const h2Element = el.querySelector('h2');
                        if (h2Element) {
                            const allSpans = h2Element.querySelectorAll('span');
                            for (const span of allSpans) {
                                const text = (span.innerText || span.textContent || '').trim();
                                if (text.length > 5 && !['スポンサー', '結果', 'Sponsored', "Amazon's Choice", 'AD'].includes(text)) {
                                    title = text;
                                    break;
                                }
                            }
                        }
                    }
                    
                    // Extract URL with validation
                    let url = '';
                    const urlSelectors = ['h2 a[href]', 'a[href*="/dp/"]', 'a[href*="/gp/"]'];
                    for (const selector of urlSelectors) {
                        const urlEl = el.querySelector(selector);
                        if (urlEl) {
                            const href = urlEl.getAttribute('href');
                            if (href && !href.includes('javascript:') && !href.includes('void(0)')) {
                                url = href.startsWith('http') ? href : 'https://www.amazon.co.jp' + href;
                                break;
                            }
                        }
                    }
                    
                    // Extract price with comprehensive selectors
                    let price = '';
                    const priceSelectors = [
                        '.a-price > .a-offscreen',
                        '.a-price-whole',
                        '.s-price-instruction-style .a-offscreen',
                        '.a-price .a-price-whole',
                        '[data-cy="price-recipe"] .a-offscreen',
                        '.a-price-symbol + .a-price-whole'
                    ];
                    
                    for (const selector of priceSelectors) {
                        const priceEl = el.querySelector(selector);
                        if (priceEl) {
                            const priceText = priceEl.innerText || priceEl.textContent || '';
                            if (priceText && priceText.trim()) {
                                price = priceText.trim();
                                break;
                            }
                        }
                    }
                    
                    // Extract image with quality preference
                    let image = '';
                    const imgSelectors = ['.s-image[src]', 'img[data-src]', 'img[src]'];
                    for (const selector of imgSelectors) {
                        const imgEl = el.querySelector(selector);
                        if (imgEl) {
                            const src = imgEl.getAttribute('src') || imgEl.getAttribute('data-src') || '';
                            if (src && src.startsWith('http') && !src.includes('1x1_transparent')) {
                                image = src;
                                break;
                            }
                        }
                    }
                    
                    // Extract rating with multiple formats
                    let rating = '';
                    const ratingSelectors = [
                        '[aria-label*="stars" i]',
                        '[aria-label*="つ星" i]',
                        '.a-icon-alt[aria-label]',
                        '[data-cy="reviews-ratings-slot"] [aria-label]'
                    ];
                    
                    for (const selector of ratingSelectors) {
                        const ratingEl = el.querySelector(selector);
                        if (ratingEl) {
                            const ariaLabel = ratingEl.getAttribute('aria-label') || '';
                            if (ariaLabel) {
                                rating = ariaLabel;
                                break;
                            }
                        }
                    }
                    
                    // Get element text for fallback parsing
                    const elementText = el.innerText || el.textContent || '';
                    
                    return {
                        title: title,
                        url: url,
                        price: price,
                        image: image,
                        rating: rating,
                        element_text: elementText.substring(0, 300),
                        index: index,
                        has_title: !!title,
                        has_url: !!url,
                        has_price: !!price
                    };
                } catch (err) {
                    return {
                        error: err.message,
                        element_text: (el.innerText || el.textContent || '').substring(0, 200),
                        index: index
                    };
                }
            });
            """
            
            raw_products = self.execute_script_with_retry(script)
            
            if not raw_products:
                logger.error("Failed to execute JavaScript - falling back to traditional parsing")
                return self._parse_search_results_fallback()
            
            logger.info(f"JavaScript returned {len(raw_products)} raw products")
            
            # Filter out products with errors first
            valid_products = []
            error_count = 0
            
            for i, raw_product in enumerate(raw_products):
                if 'error' in raw_product:
                    logger.warning(f"JavaScript parsing error at index {i}: {raw_product['error']}")
                    error_count += 1
                    continue
                valid_products.append(raw_product)
            
            logger.info(f"Found {len(valid_products)} valid products, {error_count} errors")
            
            # Debug product quality
            quality_stats = {
                'has_title': sum(1 for p in valid_products if p.get('has_title')),
                'has_url': sum(1 for p in valid_products if p.get('has_url')), 
                'has_price': sum(1 for p in valid_products if p.get('has_price'))
            }
            logger.info(f"Product quality: {quality_stats}")
            
            # Debug first few products
            for i, raw_product in enumerate(valid_products[:3]):
                logger.info(f"Raw product {i+1}: title='{raw_product.get('title', '')[:50]}...', has_url={raw_product.get('has_url')}, has_price={raw_product.get('has_price')}")
            
            # Process the raw data into Product objects
            for raw_product in valid_products:
                try:
                    product = self._create_product_from_raw_data(raw_product)
                    if product:
                        products.append(product)
                    else:
                        logger.debug(f"Failed to create product from: title='{raw_product.get('title', '')[:30]}...'")
                except Exception as e:
                    logger.warning(f"Error creating product from raw data: {e}")
                    continue
            
            logger.info(f"Successfully parsed {len(products)} products from {len(valid_products)} valid elements")
            
        except Exception as e:
            logger.error(f"Error executing JavaScript for product parsing: {e}")
            # Fallback to old method if JavaScript fails
            return self._parse_search_results_fallback()
        
        return products
    
    def _create_product_from_raw_data(self, raw_data: dict) -> Optional[Product]:
        """Create Product object from raw JavaScript extracted data."""
        # Validate required fields
        title = raw_data.get('title', '').strip()
        url = raw_data.get('url', '').strip()
        
        # More strict validation
        if not title or len(title) < 8:
            logger.debug(f"Skipping due to invalid title: '{title}'")
            return None
            
        # Skip obvious non-product titles
        skip_patterns = ['スポンサー', '結果', 'Sponsored', "Amazon's Choice", 'AD', '広告']
        if any(pattern in title for pattern in skip_patterns):
            logger.debug(f"Skipping promotional/ad content: '{title}'")
            return None
        
        # Validate URL - must be a proper Amazon product URL
        if not url:
            logger.debug(f"Skipping due to missing URL for: '{title[:30]}...'")
            return None
            
        if 'javascript:' in url or 'void(0)' in url or not (url.startswith('http') or url.startswith('/')):
            logger.debug(f"Skipping due to invalid URL: '{url}' for title: '{title[:30]}...'")
            return None
        
        # Extract price with enhanced logic
        price_text = raw_data.get('price', '')
        price = self.extract_price_from_text(price_text)
        
        # Enhanced price extraction from element text
        if not price and raw_data.get('element_text'):
            price = self._extract_price_from_element_text(raw_data['element_text'])
        
        # Extract rating with enhanced parsing
        rating_text = raw_data.get('rating', '')
        rating = self.extract_rating_from_text(rating_text)
        
        # Extract review count from element text
        review_count = None
        if raw_data.get('element_text'):
            review_count = self._extract_review_count_from_text(raw_data['element_text'])
        
        # Ensure URL is absolute
        if url and not url.startswith('http'):
            url = f"https://www.amazon.co.jp{url}" if url.startswith('/') else f"https://www.amazon.co.jp/{url}"
        
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
    
    def _extract_price_from_element_text(self, element_text: str) -> Optional[float]:
        """Enhanced price extraction from element text."""
        if not element_text:
            return None
            
        import re
        
        # Try different price patterns
        patterns = [
            r'¥([\d,]+(?:\.\d{2})?)',  # ¥1,234 or ¥1,234.56
            r'￥([\d,]+(?:\.\d{2})?)', # Alternative yen symbol
            r'(\d{1,3}(?:,\d{3})+)円',  # 1,234円
            r'(\d{1,3}(?:,\d{3})+)\s*$',  # Just numbers at end of line
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, element_text)
            for match in matches:
                try:
                    potential_price = float(match.replace(',', ''))
                    # Reasonable price range for Amazon products
                    if 50 <= potential_price <= 1000000:
                        return potential_price
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _extract_review_count_from_text(self, element_text: str) -> Optional[int]:
        """Enhanced review count extraction."""
        if not element_text:
            return None
            
        import re
        
        # Try different review count patterns
        patterns = [
            r'(\d+(?:,\d+)*)\s*(?:件|個|reviews?|ratings?)',
            r'(\d+(?:,\d+)*)\s*(?:レビュー|評価)',
            r'\((\d+(?:,\d+)*)\)',  # Numbers in parentheses
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, element_text, re.IGNORECASE)
            for match in matches:
                try:
                    count = int(match.replace(',', ''))
                    if 1 <= count <= 100000:  # Reasonable review count range
                        return count
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _parse_search_results_fallback(self) -> List[Product]:
        """Fallback method using Selenium element parsing."""
        products = []
        
        # Find all product containers
        product_elements = self.safe_find_elements(
            By.CSS_SELECTOR, 
            '[data-component-type="s-search-result"]'
        )
        
        logger.info(f"Fallback: Found {len(product_elements)} product elements")
        
        for element in product_elements:
            try:
                product = self._parse_product_element(element)
                if product:
                    products.append(product)
            except Exception as e:
                logger.warning(f"Error parsing Amazon product in fallback: {e}")
                continue
        
        return products
    
    def _parse_product_element(self, element) -> Optional[Product]:
        """Parse individual product element from search results."""
        try:
            # Get all text first to debug
            element_text = self.extract_text(element)
            
            # Extract title - try multiple selectors
            title_elem = None
            title = ""
            title_selectors = [
                'h2 a span',
                '.s-size-mini span', 
                'h2 span',
                '[data-cy="title-recipe-title"]',
                'h2 a'  # Fallback to just the link
            ]
            
            for selector in title_selectors:
                title_elem = self._safe_find_element_in_parent(element, By.CSS_SELECTOR, selector)
                if title_elem:
                    title = self.extract_text(title_elem)
                    if title and title not in ['スポンサー', '結果', 'Sponsored', 'Amazon\'s Choice']:
                        break
            
            # If no title found via selectors, try extracting from element text
            if not title and element_text:
                lines = element_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and line not in ['Sponsored', 'スポンサー', '結果', 'Amazon\'s Choice'] and len(line) > 10:
                        # Look for lines that seem like product titles
                        if any(keyword in line for keyword in ['Nintendo Switch', 'Switch', 'ニンテンドー', '任天堂']):
                            title = line
                            break
            
            if not title:
                return None
            
            # Extract URL
            url_elem = self._safe_find_element_in_parent(element, By.CSS_SELECTOR, 'h2 a')
            url = self.extract_attribute(url_elem, 'href') if url_elem else ""
            if url and not url.startswith('http'):
                url = f"https://www.amazon.co.jp{url}" if url.startswith('/') else ""
            
            # Skip if no valid URL
            if not url or url == "" or "javascript:" in url:
                return None
            
            # Extract price from element text if selectors don't work
            price = None
            price_selectors = [
                '.a-price-whole',
                '.a-offscreen',
                '.a-price .a-offscreen',
                '.s-price-instruction-style .a-offscreen'
            ]
            
            for selector in price_selectors:
                price_elem = self._safe_find_element_in_parent(element, By.CSS_SELECTOR, selector)
                if price_elem:
                    price_text = self.extract_text(price_elem)
                    price = self.extract_price_from_text(price_text)
                    if price:
                        break
            
            # Try extracting price from element text if selectors failed
            if not price and element_text:
                import re
                # Look for Japanese yen prices in text
                price_matches = re.findall(r'¥([\d,]+)', element_text)
                if not price_matches:
                    # Look for just numbers that might be prices
                    price_matches = re.findall(r'(\d{1,3}(?:,\d{3})*)', element_text)
                
                for match in price_matches:
                    try:
                        potential_price = float(match.replace(',', ''))
                        # Reasonable price range for Nintendo Switch products
                        if 1000 <= potential_price <= 100000:
                            price = potential_price
                            break
                    except:
                        continue
            
            # Extract image
            image_elem = self._safe_find_element_in_parent(element, By.CSS_SELECTOR, '.s-image, img')
            image_url = self.extract_attribute(image_elem, 'src') if image_elem else ""
            
            # Extract rating
            rating_elem = self._safe_find_element_in_parent(
                element, 
                By.CSS_SELECTOR, 
                '.a-icon-alt, [aria-label*="stars"], [aria-label*="つ星"]'
            )
            rating_text = self.extract_attribute(rating_elem, 'aria-label') if rating_elem else ""
            rating = self.extract_rating_from_text(rating_text)
            
            # Extract review count from text
            review_count = None
            if element_text:
                import re
                # Look for review counts in Japanese format
                review_matches = re.findall(r'(\d+(?:,\d+)*)\s*(?:件|個)', element_text)
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
                image_url=image_url,
                rating=rating,
                review_count=review_count,
                currency="JPY"
            )
            
        except Exception as e:
            logger.warning(f"Error parsing Amazon product element: {e}")
            return None
    
    def _safe_find_element_in_parent(self, parent, by: By, value: str):
        """Safely find element within parent element."""
        try:
            return parent.find_element(by, value)
        except:
            return None
    
    def _extract_review_count(self, review_text: str) -> Optional[int]:
        """Extract review count from text."""
        if not review_text:
            return None
        
        import re
        
        # Look for numbers in parentheses or just numbers
        numbers = re.findall(r'[\d,]+', review_text.replace(',', ''))
        if numbers:
            try:
                return int(numbers[0])
            except ValueError:
                pass
        
        return None
    
    def parse_product_details(self, url: str) -> Optional[Product]:
        """Parse detailed product information from Amazon product page."""
        if not self.navigate_to_url(url):
            return None
        
        try:
            # Wait for product page to load
            product_title = self.wait_for_element(
                By.ID, "productTitle", timeout=15
            )
            
            if not product_title:
                return None
            
            title = self.extract_text(product_title)
            
            # Extract price
            price_elem = self.safe_find_element(By.CSS_SELECTOR, '.a-price-whole, .a-offscreen')
            price_text = self.extract_text(price_elem) if price_elem else ""
            price = self.extract_price_from_text(price_text)
            
            # Extract image
            image_elem = self.safe_find_element(By.CSS_SELECTOR, '#landingImage, .a-dynamic-image')
            image_url = self.extract_attribute(image_elem, 'src') if image_elem else ""
            
            # Extract rating
            rating_elem = self.safe_find_element(By.CSS_SELECTOR, '.a-icon-alt')
            rating_text = self.extract_attribute(rating_elem, 'aria-label') if rating_elem else ""
            rating = self.extract_rating_from_text(rating_text)
            
            # Extract review count
            review_elem = self.safe_find_element(By.CSS_SELECTOR, '#acrCustomerReviewText')
            review_text = self.extract_text(review_elem) if review_elem else ""
            review_count = self._extract_review_count(review_text)
            
            return Product(
                title=title,
                price=price,
                url=url,
                platform=self.get_platform(),
                image_url=image_url,
                rating=rating,
                review_count=review_count,
                currency="JPY"
            )
            
        except Exception as e:
            logger.error(f"Error parsing Amazon product details: {e}")
            return None
