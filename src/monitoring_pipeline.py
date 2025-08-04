"""
Monitoring Pipeline

This pipeline handles monitoring known products for price changes.
It runs frequently (daily/hourly) to track price changes on products already in our canonical database.
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import asdict
from loguru import logger

from src.models import Platform
from src.tracking_scraper import TrackingScraper
from src.canonical_products import create_canonical_manager


class MonitoringPipeline:
    """Pipeline for monitoring known products for price changes."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.canonical_manager = create_canonical_manager(data_dir)
        self.tracking_scraper = TrackingScraper(data_dir)
        
        # Create monitoring results directory
        self.monitoring_dir = self.data_dir / "monitoring"
        self.monitoring_dir.mkdir(exist_ok=True)
    
    async def monitor_all_active_products(self, max_concurrent: int = 5) -> Dict[str, Any]:
        """
        Monitor all active products in the canonical database.
        This is the main monitoring method - run this daily/hourly.
        """
        logger.info("Starting monitoring run for all active products")
        
        # Get all active canonical products
        active_products = self.canonical_manager.get_active_products()
        
        if not active_products:
            logger.warning("No active products found to monitor")
            return {
                'session_id': None,
                'status': 'no_products',
                'message': 'No active products found to monitor'
            }
        
        logger.info(f"Found {len(active_products)} active products to monitor")
        
        # Create monitoring session
        session_id = self.canonical_manager.create_monitoring_session(len(active_products))
        
        results = {
            'session_id': session_id,
            'started_at': datetime.now().isoformat(),
            'total_products': len(active_products),
            'monitored_successfully': 0,
            'price_changes_detected': 0,
            'errors': 0,
            'product_results': []
        }
        
        # Process products in batches to control concurrency
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = []
        
        for product in active_products:
            task = self._monitor_single_product(semaphore, product, results)
            tasks.append(task)
        
        # Wait for all monitoring tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Complete the monitoring session
        results['completed_at'] = datetime.now().isoformat()
        
        self.canonical_manager.complete_monitoring_session(
            session_id,
            results['monitored_successfully'],
            results['price_changes_detected']
        )
        
        # Save monitoring session results
        self._save_monitoring_session_results(session_id, results)
        
        logger.info(
            f"Monitoring completed: {results['monitored_successfully']}/{results['total_products']} "
            f"products monitored, {results['price_changes_detected']} price changes detected"
        )
        
        return results
    
    async def monitor_products_by_ids(
        self,
        canonical_ids: List[str],
        max_concurrent: int = 3
    ) -> Dict[str, Any]:
        """
        Monitor specific products by their canonical IDs.
        Useful for targeted monitoring or testing.
        """
        logger.info(f"Starting monitoring for {len(canonical_ids)} specific products")
        
        # Get products by IDs
        products = []
        for canonical_id in canonical_ids:
            product = self.canonical_manager.get_canonical_product(canonical_id)
            if product:
                products.append(product)
            else:
                logger.warning(f"Canonical product not found: {canonical_id}")
        
        if not products:
            logger.warning("No valid products found to monitor")
            return {
                'session_id': None,
                'status': 'no_products',
                'message': 'No valid products found to monitor'
            }
        
        # Create monitoring session
        session_id = self.canonical_manager.create_monitoring_session(len(products))
        
        results = {
            'session_id': session_id,
            'started_at': datetime.now().isoformat(),
            'requested_ids': canonical_ids,
            'total_products': len(products),
            'monitored_successfully': 0,
            'price_changes_detected': 0,
            'errors': 0,
            'product_results': []
        }
        
        # Process products with controlled concurrency
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = []
        
        for product in products:
            task = self._monitor_single_product(semaphore, product, results)
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Complete session
        results['completed_at'] = datetime.now().isoformat()
        
        self.canonical_manager.complete_monitoring_session(
            session_id,
            results['monitored_successfully'],
            results['price_changes_detected']
        )
        
        self._save_monitoring_session_results(session_id, results)
        
        logger.info(f"Targeted monitoring completed: {results['monitored_successfully']} monitored, {results['price_changes_detected']} changes detected")
        
        return results
    
    async def monitor_recent_products(
        self,
        days_back: int = 7,
        max_concurrent: int = 5
    ) -> Dict[str, Any]:
        """
        Monitor products discovered in the last N days.
        Useful for monitoring newly discovered products more frequently.
        """
        logger.info(f"Starting monitoring for products discovered in last {days_back} days")
        
        # Get recent products
        cutoff_date = datetime.now() - timedelta(days=days_back)
        recent_products = self.canonical_manager.get_products_since(cutoff_date)
        
        if not recent_products:
            logger.warning(f"No products found discovered in last {days_back} days")
            return {
                'session_id': None,
                'status': 'no_products',
                'message': f'No products discovered in last {days_back} days'
            }
        
        logger.info(f"Found {len(recent_products)} products discovered in last {days_back} days")
        
        # Create monitoring session
        session_id = self.canonical_manager.create_monitoring_session(len(recent_products))
        
        results = {
            'session_id': session_id,
            'started_at': datetime.now().isoformat(),
            'days_back': days_back,
            'cutoff_date': cutoff_date.isoformat(),
            'total_products': len(recent_products),
            'monitored_successfully': 0,
            'price_changes_detected': 0,
            'errors': 0,
            'product_results': []
        }
        
        # Process products
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = []
        
        for product in recent_products:
            task = self._monitor_single_product(semaphore, product, results)
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Complete session
        results['completed_at'] = datetime.now().isoformat()
        
        self.canonical_manager.complete_monitoring_session(
            session_id,
            results['monitored_successfully'],
            results['price_changes_detected']
        )
        
        self._save_monitoring_session_results(session_id, results)
        
        logger.info(f"Recent products monitoring completed: {results['monitored_successfully']} monitored, {results['price_changes_detected']} changes detected")
        
        return results
    
    async def _monitor_single_product(
        self,
        semaphore: asyncio.Semaphore,
        product: Dict[str, Any],
        results: Dict[str, Any]
    ):
        """Monitor a single product and update results."""
        async with semaphore:
            canonical_id = product['canonical_id']
            product_url = product['product_url']
            platform = product['platform']
            
            try:
                logger.debug(f"Monitoring product {canonical_id} on {platform}")
                
                # Use tracking scraper to get current product data
                if platform.lower() == 'amazon':
                    current_data = await self.tracking_scraper.track_amazon_product(product_url)
                elif platform.lower() == 'rakuten':
                    current_data = await self.tracking_scraper.track_rakuten_product(product_url)
                elif platform.lower() == 'yahoo':
                    current_data = await self.tracking_scraper.track_yahoo_product(product_url)
                else:
                    # Generic tracking
                    current_data = await self.tracking_scraper.track_generic_product(product_url, platform)
                
                if current_data:
                    # Update canonical product with latest data
                    price_changed = self.canonical_manager.update_product_data(
                        canonical_id, current_data
                    )
                    
                    # Track the monitoring result
                    product_result = {
                        'canonical_id': canonical_id,
                        'platform': platform,
                        'status': 'success',
                        'price_changed': price_changed,
                        'current_price': current_data.get('price'),
                        'monitored_at': datetime.now().isoformat()
                    }
                    
                    results['monitored_successfully'] += 1
                    if price_changed:
                        results['price_changes_detected'] += 1
                        logger.info(f"Price change detected for {canonical_id}: {current_data.get('price')}")
                    
                else:
                    # Product not found or error
                    product_result = {
                        'canonical_id': canonical_id,
                        'platform': platform,
                        'status': 'not_found',
                        'price_changed': False,
                        'monitored_at': datetime.now().isoformat()
                    }
                    results['errors'] += 1
                    logger.warning(f"Product not found during monitoring: {canonical_id}")
                
                results['product_results'].append(product_result)
                
                # Rate limiting between products
                await asyncio.sleep(2.0)
                
            except Exception as e:
                logger.error(f"Error monitoring product {canonical_id}: {e}")
                
                product_result = {
                    'canonical_id': canonical_id,
                    'platform': platform,
                    'status': 'error',
                    'error': str(e),
                    'price_changed': False,
                    'monitored_at': datetime.now().isoformat()
                }
                results['product_results'].append(product_result)
                results['errors'] += 1
    
    def _save_monitoring_session_results(self, session_id: str, results: Dict[str, Any]):
        """Save monitoring session results."""
        filename = f"{session_id}_monitoring_session.json"
        filepath = self.monitoring_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved monitoring session results to {filepath}")
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get statistics about recent monitoring sessions."""
        stats = self.canonical_manager.get_canonical_stats()
        
        # Add monitoring-specific stats
        stats['pipeline_type'] = 'monitoring_pipeline'
        stats['last_run'] = datetime.now().isoformat()
        
        return stats
    
    def get_price_changes(self, days_back: int = 7) -> List[Dict[str, Any]]:
        """Get recent price changes."""
        return self.canonical_manager.get_recent_price_changes(days_back)
    
    def get_products_needing_monitoring(self, hours_since_last_check: int = 24) -> List[Dict[str, Any]]:
        """Get products that haven't been monitored recently."""
        cutoff_time = datetime.now() - timedelta(hours=hours_since_last_check)
        return self.canonical_manager.get_products_not_monitored_since(cutoff_time)


def create_monitoring_pipeline(data_dir: str = "data") -> MonitoringPipeline:
    """Factory function to create a MonitoringPipeline instance."""
    return MonitoringPipeline(data_dir)
