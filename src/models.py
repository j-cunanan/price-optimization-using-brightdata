"""
Data models for the Japanese marketplace scraper.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, HttpUrl, Field


class Platform(str, Enum):
    """Supported marketplace platforms."""
    AMAZON_JP = "amazon_jp"
    RAKUTEN = "rakuten"
    MERCARI = "mercari"
    YAHOO_SHOPPING = "yahoo_shopping"
    QOO10 = "qoo10"
    AU_PAY_MARKET = "au_pay_market"


class Product(BaseModel):
    """Product information model."""
    title: str = Field(..., description="Product title")
    price: Optional[float] = Field(None, description="Product price in JPY")
    original_price: Optional[float] = Field(None, description="Original price before discount")
    currency: str = Field(default="JPY", description="Price currency")
    url: HttpUrl = Field(..., description="Product URL")
    image_url: Optional[HttpUrl] = Field(None, description="Product image URL")
    platform: Platform = Field(..., description="Source platform")
    seller: Optional[str] = Field(None, description="Seller name")
    rating: Optional[float] = Field(None, description="Product rating (0-5)")
    review_count: Optional[int] = Field(None, description="Number of reviews")
    availability: Optional[str] = Field(None, description="Stock availability")
    shipping_cost: Optional[float] = Field(None, description="Shipping cost")
    estimated_delivery: Optional[str] = Field(None, description="Estimated delivery time")
    description: Optional[str] = Field(None, description="Product description")
    category: Optional[str] = Field(None, description="Product category")
    brand: Optional[str] = Field(None, description="Product brand")
    condition: Optional[str] = Field(None, description="Product condition (new, used, etc.)")
    scraped_at: datetime = Field(default_factory=datetime.now, description="Scraping timestamp")
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        
    def get_effective_price(self) -> Optional[float]:
        """Get the effective price (current price or original price)."""
        return self.price or self.original_price
    
    def has_discount(self) -> bool:
        """Check if product has a discount."""
        return (self.price is not None and 
                self.original_price is not None and 
                self.price < self.original_price)
    
    def discount_percentage(self) -> Optional[float]:
        """Calculate discount percentage."""
        if not self.has_discount():
            return None
        return ((self.original_price - self.price) / self.original_price) * 100


class SearchQuery(BaseModel):
    """Search query parameters."""
    keyword: str = Field(..., description="Search keyword")
    platforms: List[Platform] = Field(default_factory=lambda: list(Platform), description="Platforms to search")
    max_results_per_platform: int = Field(default=20, description="Maximum results per platform")
    min_price: Optional[float] = Field(None, description="Minimum price filter")
    max_price: Optional[float] = Field(None, description="Maximum price filter")
    category: Optional[str] = Field(None, description="Category filter")
    condition: Optional[str] = Field(None, description="Condition filter")
    sort_by: str = Field(default="price_asc", description="Sort order")
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True


class SearchResult(BaseModel):
    """Search result container."""
    query: SearchQuery = Field(..., description="Original search query")
    products: List[Product] = Field(default_factory=list, description="Found products")
    total_found: int = Field(0, description="Total products found")
    search_time: float = Field(0.0, description="Search duration in seconds")
    errors: List[str] = Field(default_factory=list, description="Search errors")
    scraped_at: datetime = Field(default_factory=datetime.now, description="Search timestamp")
    platforms_searched: List[Platform] = Field(default_factory=list, description="Platforms that were searched")
    
    def get_lowest_price_product(self) -> Optional[Product]:
        """Get the product with the lowest price."""
        products_with_price = [p for p in self.products if p.get_effective_price() is not None]
        if not products_with_price:
            return None
        return min(products_with_price, key=lambda p: p.get_effective_price())
    
    def get_products_by_platform(self, platform: Platform) -> List[Product]:
        """Get products from a specific platform."""
        return [p for p in self.products if p.platform == platform]
    
    def get_products_with_discount(self) -> List[Product]:
        """Get products that have discounts."""
        return [p for p in self.products if p.has_discount()]
    
    def sort_by_price(self, ascending: bool = True) -> List[Product]:
        """Sort products by price."""
        products_with_price = [p for p in self.products if p.get_effective_price() is not None]
        return sorted(products_with_price, 
                     key=lambda p: p.get_effective_price(), 
                     reverse=not ascending)


class ScrapingConfig(BaseModel):
    """Scraping configuration."""
    request_delay: float = Field(default=1.0, description="Delay between requests in seconds")
    max_concurrent_requests: int = Field(default=5, description="Maximum concurrent requests")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    rotate_user_agents: bool = Field(default=True, description="Whether to rotate user agents")
    headless_browser: bool = Field(default=True, description="Run browser in headless mode")
    cache_enabled: bool = Field(default=True, description="Enable response caching")
    cache_duration: int = Field(default=3600, description="Cache duration in seconds")
    
    class Config:
        """Pydantic configuration."""
        validate_assignment = True
