"""
Main Bright Data scraper orchestrator.
"""

import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger

from ..models import Product, Platform, SearchQuery, SearchResult, ScrapingConfig
from ..utils import setup_logging, load_env_vars
from ..change_detector import create_change_detector
from .connection import BrightDataConfig
from .amazon_jp import BrightDataAmazonScraper
from .rakuten import BrightDataRakutenScraper
from .mercari import BrightDataMercariScraper
from .yahoo_shopping import BrightDataYahooShoppingScraper


class BrightDataMarketplaceScraper:
    """Main scraper orchestrator for Bright Data API."""
    
    def __init__(self, brightdata_config: BrightDataConfig, scraping_config: ScrapingConfig):
        self.brightdata_config = brightdata_config
        self.scraping_config = scraping_config
        
        # Initialize scrapers
        self.scrapers = {
            Platform.AMAZON_JP: BrightDataAmazonScraper(brightdata_config, scraping_config),
            Platform.RAKUTEN: BrightDataRakutenScraper(brightdata_config, scraping_config),
            Platform.MERCARI: BrightDataMercariScraper(brightdata_config, scraping_config),
            Platform.YAHOO_SHOPPING: BrightDataYahooShoppingScraper(brightdata_config, scraping_config),
        }
    
    async def search_platform(
        self, 
        platform: Platform, 
        keyword: str, 
        max_results: int = 20
    ) -> List[Product]:
        """Search a specific platform using Bright Data."""
        if platform not in self.scrapers:
            logger.warning(f"Platform {platform.value} not supported in Bright Data mode")
            return []
        
        scraper = self.scrapers[platform]
        
        try:
            # Use sync context manager since selenium is sync
            async with scraper:
                products = scraper.search(keyword, max_results)
                return products
        except Exception as e:
            logger.error(f"Error searching {platform.value} with Bright Data: {e}")
            return []
    
    async def search_all_platforms(
        self, 
        keyword: str, 
        max_results_per_platform: int = 20,
        platforms: Optional[List[Platform]] = None
    ) -> Dict[Platform, List[Product]]:
        """Search all available platforms using Bright Data."""
        if platforms is None:
            platforms = list(self.scrapers.keys())
        
        results = {}
        
        for platform in platforms:
            if platform in self.scrapers:
                logger.info(f"Searching {platform.value} with Bright Data...")
                products = await self.search_platform(
                    platform, 
                    keyword, 
                    max_results_per_platform
                )
                results[platform] = products
        
        return results
    
    def get_supported_platforms(self) -> List[Platform]:
        """Get list of supported platforms."""
        return list(self.scrapers.keys())


async def search_japanese_marketplaces_brightdata(
    keyword: str,
    platforms: Optional[List[Platform]] = None,
    max_results_per_platform: int = 20,
    brightdata_config: Optional[BrightDataConfig] = None,
    scraping_config: Optional[ScrapingConfig] = None
) -> SearchResult:
    """
    Search Japanese marketplaces using Bright Data API.
    
    Args:
        keyword: Search keyword
        platforms: List of platforms to search (defaults to all supported)
        max_results_per_platform: Maximum results per platform
        brightdata_config: Bright Data configuration
        scraping_config: Scraping configuration
    
    Returns:
        SearchResult containing all products found
    """
    setup_logging()
    
    # Load configurations if not provided
    if brightdata_config is None:
        env_vars = load_env_vars()
        brightdata_config = BrightDataConfig(
            zone=env_vars.get("BRIGHT_DATA_ZONE", "datacenter"),
            username=env_vars.get("BRIGHT_DATA_USERNAME", ""),
            password=env_vars.get("BRIGHT_DATA_PASSWORD", ""),
            session_id=env_vars.get("BRIGHT_DATA_SESSION_ID")
        )
    
    if scraping_config is None:
        from ..utils import load_config
        scraping_config = load_config()
    
    # Initialize scraper
    scraper = BrightDataMarketplaceScraper(brightdata_config, scraping_config)
    
    # Determine platforms to search
    available_platforms = scraper.get_supported_platforms()
    if platforms is None:
        platforms = available_platforms
    else:
        # Filter to only supported platforms
        platforms = [p for p in platforms if p in available_platforms]
    
    logger.info(f"Searching for '{keyword}' on {len(platforms)} platforms using Bright Data")
    
    # Search all platforms
    platform_results = await scraper.search_all_platforms(
        keyword, 
        max_results_per_platform, 
        platforms
    )
    
    # Combine all products
    all_products = []
    for platform, products in platform_results.items():
        all_products.extend(products)
    
    # Create search query
    query = SearchQuery(
        keyword=keyword,
        platforms=platforms,
        max_results_per_platform=max_results_per_platform
    )
    
    # Create and return search result
    result = SearchResult(
        query=query,
        products=all_products,
        total_found=len(all_products),
        platforms_searched=list(platform_results.keys())
    )
    
    logger.info(f"Bright Data search completed. Found {len(all_products)} products total")
    
    return result


# CLI function for Bright Data scraping
async def main_brightdata():
    """CLI entry point for Bright Data scraping."""
    import argparse
    import sys
    from ..utils import export_to_csv, export_to_json
    
    parser = argparse.ArgumentParser(description="Japanese Marketplace Scraper (Bright Data)")
    parser.add_argument("keyword", help="Search keyword")
    parser.add_argument(
        "--platforms", 
        nargs="+", 
        choices=[p.value for p in Platform],
        help="Platforms to search"
    )
    parser.add_argument(
        "--max-results", 
        type=int, 
        default=20,
        help="Maximum results per platform"
    )
    parser.add_argument(
        "--output", 
        choices=["json", "csv"],
        default="json",
        help="Output format"
    )
    parser.add_argument(
        "--output-file",
        help="Output file path"
    )
    parser.add_argument(
        "--auto-save",
        action="store_true",
        help="Automatically save results with timestamp in data folder"
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory to store results (when using --auto-save)"
    )
    
    args = parser.parse_args()
    
    try:
        # Convert platform strings to enums
        platforms = None
        if args.platforms:
            platforms = [Platform(p) for p in args.platforms]
        
        # Perform search
        result = await search_japanese_marketplaces_brightdata(
            keyword=args.keyword,
            platforms=platforms,
            max_results_per_platform=args.max_results
        )
        
        # Convert result to dictionary format for change detection
        result_dict = {
            "query": {
                "keyword": args.keyword,
                "platforms": [p.value if hasattr(p, 'value') else str(p) for p in (platforms or [])],
                "max_results_per_platform": args.max_results,
                "min_price": None,
                "max_price": None,
                "category": None,
                "condition": None,
                "sort_by": "relevance"
            },
            "products": [
                {
                    "title": p.title,
                    "price": p.price,
                    "original_price": p.original_price,
                    "currency": p.currency,
                    "url": str(p.url),
                    "image_url": str(p.image_url) if p.image_url else None,
                    "platform": p.platform.value if hasattr(p.platform, 'value') else str(p.platform),
                    "seller": p.seller,
                    "rating": p.rating,
                    "review_count": p.review_count,
                    "availability": p.availability,
                    "shipping_cost": p.shipping_cost,
                    "estimated_delivery": p.estimated_delivery,
                    "description": p.description,
                    "category": p.category,
                    "brand": p.brand,
                    "condition": p.condition,
                    "scraped_at": p.scraped_at.isoformat() if p.scraped_at else None
                }
                for p in result.products
            ],
            "total_found": result.total_found,
            "search_time": result.search_time,
            "errors": [str(e) for e in result.errors],
            "scraped_at": result.scraped_at.isoformat() if result.scraped_at else None
        }
        
        # Handle auto-save
        if args.auto_save:
            change_detector = create_change_detector(args.data_dir)
            results_filepath = change_detector.save_results_only(result_dict, args.keyword)
            logger.info(f"Results automatically saved with timestamp: {results_filepath}")
        
        # Export results (original functionality)
        if args.output_file:
            if args.output == "csv":
                export_to_csv(result.products, args.output_file)
            else:
                export_to_json(result.products, args.output_file)
            
            logger.info(f"Results saved to {args.output_file}")
        else:
            # Print to stdout
            if args.output == "json":
                import json
                # Convert products to JSON-serializable format using export utility
                from ..utils import export_to_json
                import tempfile
                import os
                
                # Create a temporary file to use the existing export function
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                
                try:
                    # Use the existing export function which handles serialization correctly
                    export_to_json(result.products, tmp_path)
                    
                    # Read and print the contents
                    with open(tmp_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        print(content)
                finally:
                    # Clean up the temporary file
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
            else:
                # Simple text output
                for product in result.products:
                    try:
                        platform_name = product.platform.value if hasattr(product.platform, 'value') else str(product.platform)
                    except AttributeError:
                        platform_name = str(product.platform)
                    print(f"{platform_name}: {product.title} - ¥{product.price} - {product.url}")
    
    except Exception as e:
        logger.error(f"Search failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main_brightdata())
