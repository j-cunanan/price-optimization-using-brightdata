"""
Discovery Pipeline

This pipeline handles discovering new products to track via keyword/category searches.
It runs periodically (weekly/monthly) to expand the product catalog.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import asdict
from loguru import logger

from src.models import Platform
from src.brightdata.scraper import search_japanese_marketplaces_brightdata
from src.canonical_products import create_canonical_manager


class DiscoveryPipeline:
    """Pipeline for discovering new products to track."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.canonical_manager = create_canonical_manager(data_dir)
        
        # Create discovery results directory
        self.discovery_dir = self.data_dir / "discovery"
        self.discovery_dir.mkdir(exist_ok=True)
    
    async def discover_from_keywords(
        self,
        keywords: List[str],
        platforms: Optional[List[Platform]] = None,
        max_results_per_platform: int = 30
    ) -> Dict[str, Any]:
        """
        Discover products from keyword searches.
        This is the main discovery method - use this to find new products to track.
        """
        logger.info(f"Starting keyword discovery for {len(keywords)} keywords")
        
        # Create discovery session
        query_str = ", ".join(keywords[:5]) + ("..." if len(keywords) > 5 else "")
        session_id = self.canonical_manager.create_discovery_session("keyword", query_str)
        
        results = {
            'session_id': session_id,
            'discovery_type': 'keyword',
            'started_at': datetime.now().isoformat(),
            'keywords': keywords,
            'platforms_searched': [p.value for p in platforms] if platforms else "all",
            'total_products_discovered': 0,
            'total_canonical_products_added': 0,
            'keyword_results': {}
        }
        
        total_discovered = 0
        total_added = 0
        
        for keyword in keywords:
            try:
                logger.info(f"Discovering products for keyword: {keyword}")
                
                # Search the keyword
                search_result = await search_japanese_marketplaces_brightdata(
                    keyword=keyword,
                    platforms=platforms,
                    max_results_per_platform=max_results_per_platform
                )
                
                if search_result and search_result.products:
                    # Convert SearchResult to list of dictionaries
                    products_data = [asdict(product) for product in search_result.products]
                    
                    # Add to canonical product database
                    added_count = self.canonical_manager.add_discovered_products(
                        products_data, session_id
                    )
                    
                    results['keyword_results'][keyword] = {
                        'products_discovered': len(products_data),
                        'canonical_products_added': added_count,
                        'search_time': search_result.search_time,
                        'platforms_found': list(set(p.platform for p in search_result.products)),
                        'status': 'success'
                    }
                    
                    total_discovered += len(products_data)
                    total_added += added_count
                    
                    logger.info(f"Keyword '{keyword}': {len(products_data)} discovered, {added_count} canonical added")
                    
                    # Save raw discovery results for reference
                    self._save_discovery_raw_results(session_id, keyword, search_result)
                
                else:
                    results['keyword_results'][keyword] = {
                        'products_discovered': 0,
                        'canonical_products_added': 0,
                        'status': 'no_results'
                    }
                    logger.warning(f"No products found for keyword: {keyword}")
                
                # Rate limiting between keywords
                await asyncio.sleep(3.0)
                
            except Exception as e:
                logger.error(f"Error discovering keyword '{keyword}': {e}")
                results['keyword_results'][keyword] = {
                    'products_discovered': 0,
                    'canonical_products_added': 0,
                    'status': 'error',
                    'error': str(e)
                }
        
        # Complete the session
        results['total_products_discovered'] = total_discovered
        results['total_canonical_products_added'] = total_added
        results['completed_at'] = datetime.now().isoformat()
        
        self.canonical_manager.complete_discovery_session(
            session_id, total_discovered, total_added
        )
        
        # Save discovery session results
        self._save_discovery_session_results(session_id, results)
        
        logger.info(f"Discovery completed: {total_discovered} products discovered, {total_added} canonical products added")
        return results
    
    async def discover_from_categories(
        self,
        categories: List[str],
        platforms: Optional[List[Platform]] = None,
        max_results_per_platform: int = 50
    ) -> Dict[str, Any]:
        """
        Discover products from category searches.
        Categories are broader than keywords and good for initial seeding.
        """
        logger.info(f"Starting category discovery for {len(categories)} categories")
        
        # Create discovery session
        query_str = ", ".join(categories[:3]) + ("..." if len(categories) > 3 else "")
        session_id = self.canonical_manager.create_discovery_session("category", query_str)
        
        results = {
            'session_id': session_id,
            'discovery_type': 'category',
            'started_at': datetime.now().isoformat(),
            'categories': categories,
            'platforms_searched': [p.value for p in platforms] if platforms else "all",
            'total_products_discovered': 0,
            'total_canonical_products_added': 0,
            'category_results': {}
        }
        
        total_discovered = 0
        total_added = 0
        
        for category in categories:
            try:
                logger.info(f"Discovering products for category: {category}")
                
                # For categories, we might use different search strategies
                # For now, treat them like keywords but with higher result limits
                search_result = await search_japanese_marketplaces_brightdata(
                    keyword=category,
                    platforms=platforms,
                    max_results_per_platform=max_results_per_platform
                )
                
                if search_result and search_result.products:
                    products_data = [asdict(product) for product in search_result.products]
                    
                    # Add category information to products
                    for product_data in products_data:
                        product_data['category'] = category
                    
                    added_count = self.canonical_manager.add_discovered_products(
                        products_data, session_id
                    )
                    
                    results['category_results'][category] = {
                        'products_discovered': len(products_data),
                        'canonical_products_added': added_count,
                        'search_time': search_result.search_time,
                        'status': 'success'
                    }
                    
                    total_discovered += len(products_data)
                    total_added += added_count
                    
                    logger.info(f"Category '{category}': {len(products_data)} discovered, {added_count} canonical added")
                    
                    # Save raw discovery results
                    self._save_discovery_raw_results(session_id, f"category_{category}", search_result)
                
                else:
                    results['category_results'][category] = {
                        'products_discovered': 0,
                        'canonical_products_added': 0,
                        'status': 'no_results'
                    }
                    logger.warning(f"No products found for category: {category}")
                
                # Longer delay for categories (they're broader searches)
                await asyncio.sleep(5.0)
                
            except Exception as e:
                logger.error(f"Error discovering category '{category}': {e}")
                results['category_results'][category] = {
                    'products_discovered': 0,
                    'canonical_products_added': 0,
                    'status': 'error',
                    'error': str(e)
                }
        
        # Complete the session
        results['total_products_discovered'] = total_discovered
        results['total_canonical_products_added'] = total_added
        results['completed_at'] = datetime.now().isoformat()
        
        self.canonical_manager.complete_discovery_session(
            session_id, total_discovered, total_added
        )
        
        self._save_discovery_session_results(session_id, results)
        
        logger.info(f"Category discovery completed: {total_discovered} products discovered, {total_added} canonical products added")
        return results
    
    def _save_discovery_raw_results(self, session_id: str, query: str, search_result):
        """Save raw search results for reference."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{session_id}_{query.replace(' ', '_')}_{timestamp}_raw.json"
        filepath = self.discovery_dir / filename
        
        # Convert SearchResult to serializable format
        raw_data = {
            'query': asdict(search_result.query),
            'products': [asdict(product) for product in search_result.products],
            'scraped_at': search_result.scraped_at,
            'search_time': search_result.search_time,
            'total_found': search_result.total_found
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved raw discovery results to {filepath}")
    
    def _save_discovery_session_results(self, session_id: str, results: Dict[str, Any]):
        """Save discovery session summary."""
        filename = f"{session_id}_session_summary.json"
        filepath = self.discovery_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved discovery session results to {filepath}")
    
    def get_discovery_stats(self) -> Dict[str, Any]:
        """Get statistics about recent discovery sessions."""
        stats = self.canonical_manager.get_canonical_stats()
        
        # Add discovery-specific stats
        stats['discovery_type'] = 'discovery_pipeline'
        stats['last_run'] = datetime.now().isoformat()
        
        return stats


def create_discovery_pipeline(data_dir: str = "data") -> DiscoveryPipeline:
    """Factory function to create a DiscoveryPipeline instance."""
    return DiscoveryPipeline(data_dir)
