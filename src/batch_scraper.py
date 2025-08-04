"""
Batch scraper for processing large lists of SKUs/keywords.
Handles 1000s of products with proper rate limiting, concurrency, and progress tracking.
"""

import asyncio
import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Callable
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import threading
from loguru import logger

from src.models import Platform, SearchResult
from src.brightdata.scraper import search_japanese_marketplaces_brightdata
from src.change_detector import create_change_detector
from src.utils import setup_logging, export_to_json


@dataclass
class BatchConfig:
    """Configuration for batch processing."""
    # Concurrency settings
    max_concurrent: int = 5  # Max concurrent searches
    max_platform_concurrent: int = 2  # Max concurrent platforms per search
    
    # Rate limiting
    delay_between_searches: float = 2.0  # Seconds between searches
    delay_between_platforms: float = 1.0  # Seconds between platform searches
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 5.0
    
    # Output settings
    batch_size: int = 100  # Save results every N products
    save_individual_results: bool = True  # Save each product result individually
    save_batch_summary: bool = True  # Save batch summary
    
    # Resume settings
    enable_resume: bool = True  # Allow resuming interrupted batches
    checkpoint_interval: int = 10  # Save checkpoint every N products


@dataclass
class BatchProgress:
    """Track batch processing progress."""
    total_items: int
    completed_items: int
    failed_items: int
    skipped_items: int
    start_time: datetime
    current_item: Optional[str] = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    @property
    def completion_percentage(self) -> float:
        if self.total_items == 0:
            return 0.0
        return (self.completed_items / self.total_items) * 100
    
    @property
    def elapsed_time(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()
    
    @property
    def estimated_time_remaining(self) -> float:
        if self.completed_items == 0:
            return 0.0
        avg_time_per_item = self.elapsed_time / self.completed_items
        remaining_items = self.total_items - self.completed_items
        return avg_time_per_item * remaining_items


class BatchScraper:
    """Batch scraper for processing large lists of SKUs/keywords."""
    
    def __init__(self, config: BatchConfig = None, data_dir: str = "data"):
        self.config = config or BatchConfig()
        self.data_dir = Path(data_dir)
        self.batch_dir = self.data_dir / "batch"
        self.batch_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.batch_dir / "results").mkdir(exist_ok=True)
        (self.batch_dir / "checkpoints").mkdir(exist_ok=True)
        (self.batch_dir / "summaries").mkdir(exist_ok=True)
        (self.batch_dir / "failed").mkdir(exist_ok=True)
        
        # Threading locks
        self._progress_lock = threading.Lock()
        self._file_lock = threading.Lock()
        
        setup_logging()
    
    def load_keywords_from_file(self, filepath: Union[str, Path]) -> List[str]:
        """Load keywords from CSV or text file."""
        filepath = Path(filepath)
        keywords = []
        
        if filepath.suffix.lower() == '.csv':
            with open(filepath, 'r', encoding='utf-8') as f:
                # Try to detect if there's a header
                sample = f.read(1024)
                f.seek(0)
                
                sniffer = csv.Sniffer()
                has_header = sniffer.has_header(sample)
                
                reader = csv.reader(f)
                if has_header:
                    next(reader)  # Skip header
                
                for row in reader:
                    if row and row[0].strip():  # First column contains keywords
                        keywords.append(row[0].strip())
        else:
            # Text file - one keyword per line
            with open(filepath, 'r', encoding='utf-8') as f:
                keywords = [line.strip() for line in f if line.strip()]
        
        logger.info(f"Loaded {len(keywords)} keywords from {filepath}")
        return keywords
    
    def save_checkpoint(self, batch_id: str, progress: BatchProgress, completed_keywords: List[str]):
        """Save checkpoint for resume capability."""
        if not self.config.enable_resume:
            return
        
        checkpoint_file = self.batch_dir / "checkpoints" / f"{batch_id}_checkpoint.json"
        
        # Convert progress to dict with datetime serialization
        progress_dict = asdict(progress)
        progress_dict['start_time'] = progress.start_time.isoformat()
        
        checkpoint_data = {
            "batch_id": batch_id,
            "progress": progress_dict,
            "completed_keywords": completed_keywords,
            "timestamp": datetime.now().isoformat()
        }
        
        with self._file_lock:
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
    
    def load_checkpoint(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Load checkpoint for resuming."""
        checkpoint_file = self.batch_dir / "checkpoints" / f"{batch_id}_checkpoint.json"
        
        if not checkpoint_file.exists():
            return None
        
        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")
            return None
    
    async def search_single_keyword(
        self, 
        keyword: str, 
        platforms: Optional[List[Platform]] = None,
        max_results: int = 20
    ) -> Optional[SearchResult]:
        """Search a single keyword with retry logic."""
        
        for attempt in range(self.config.max_retries + 1):
            try:
                result = await search_japanese_marketplaces_brightdata(
                    keyword=keyword,
                    platforms=platforms,
                    max_results_per_platform=max_results
                )
                return result
            
            except Exception as e:
                if attempt < self.config.max_retries:
                    logger.warning(f"Attempt {attempt + 1} failed for '{keyword}': {e}. Retrying in {self.config.retry_delay}s...")
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    logger.error(f"All attempts failed for '{keyword}': {e}")
                    return None
    
    def save_individual_result(self, batch_id: str, keyword: str, result: SearchResult):
        """Save individual search result."""
        if not self.config.save_individual_results:
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        filename = f"{batch_id}_{keyword.replace(' ', '_')}_{timestamp}.json"
        filepath = self.batch_dir / "results" / filename
        
        # Convert to dict format (similar to change_detector format)
        result_dict = {
            "query": {
                "keyword": keyword,
                "platforms": [p.value if hasattr(p, 'value') else str(p) for p in result.query.platforms] if result.query.platforms else [],
                "max_results_per_platform": result.query.max_results_per_platform,
            },
            "products": [
                {
                    "title": p.title,
                    "price": p.price,
                    "currency": p.currency,
                    "url": str(p.url),
                    "platform": p.platform.value if hasattr(p.platform, 'value') else str(p.platform),
                    "image_url": str(p.image_url) if p.image_url else None,
                    "rating": p.rating,
                    "review_count": p.review_count,
                    "scraped_at": p.scraped_at.isoformat() if p.scraped_at else None
                }
                for p in result.products
            ],
            "total_found": result.total_found,
            "search_time": result.search_time,
            "scraped_at": result.scraped_at.isoformat() if result.scraped_at else None
        }
        
        with self._file_lock:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(result_dict, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved result for '{keyword}' to {filepath}")
            except Exception as e:
                logger.error(f"Failed to save result for '{keyword}': {e}")
    
    def save_failed_keyword(self, batch_id: str, keyword: str, error: str):
        """Save failed keyword for later retry."""
        failed_file = self.batch_dir / "failed" / f"{batch_id}_failed.csv"
        
        with self._file_lock:
            file_exists = failed_file.exists()
            with open(failed_file, 'a', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['keyword', 'error', 'timestamp'])
                writer.writerow([keyword, error, datetime.now().isoformat()])
    
    def update_progress_display(self, progress: BatchProgress):
        """Update progress display."""
        print(f"\r🔍 Progress: {progress.completed_items}/{progress.total_items} "
              f"({progress.completion_percentage:.1f}%) | "
              f"Failed: {progress.failed_items} | "
              f"ETA: {progress.estimated_time_remaining/60:.1f}min | "
              f"Current: {progress.current_item or 'N/A'}", end='', flush=True)
    
    async def process_batch(
        self,
        keywords: List[str],
        platforms: Optional[List[Platform]] = None,
        max_results_per_keyword: int = 20,
        batch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a batch of keywords."""
        
        if not batch_id:
            batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"Starting batch processing: {batch_id}")
        logger.info(f"Total keywords: {len(keywords)}")
        logger.info(f"Max concurrent: {self.config.max_concurrent}")
        logger.info(f"Platforms: {[p.value for p in platforms] if platforms else 'All'}")
        
        # Check for resume
        completed_keywords = []
        checkpoint = self.load_checkpoint(batch_id) if self.config.enable_resume else None
        
        if checkpoint:
            completed_keywords = checkpoint.get('completed_keywords', [])
            keywords = [k for k in keywords if k not in completed_keywords]
            logger.info(f"Resuming batch: {len(completed_keywords)} already completed, {len(keywords)} remaining")
        
        # Initialize progress
        progress = BatchProgress(
            total_items=len(keywords) + len(completed_keywords),
            completed_items=len(completed_keywords),
            failed_items=0,
            skipped_items=0,
            start_time=datetime.now()
        )
        
        # Batch results
        batch_results = []
        
        # Semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        async def process_keyword(keyword: str) -> Dict[str, Any]:
            async with semaphore:
                progress.current_item = keyword
                self.update_progress_display(progress)
                
                # Rate limiting
                await asyncio.sleep(self.config.delay_between_searches)
                
                # Search
                result = await self.search_single_keyword(keyword, platforms, max_results_per_keyword)
                
                with self._progress_lock:
                    if result:
                        # Save individual result
                        self.save_individual_result(batch_id, keyword, result)
                        
                        progress.completed_items += 1
                        completed_keywords.append(keyword)
                        
                        # Create result summary
                        result_summary = {
                            "keyword": keyword,
                            "products_found": len(result.products),
                            "platforms_searched": len(result.platforms_searched) if hasattr(result, 'platforms_searched') else 1,
                            "search_time": result.search_time,
                            "status": "success",
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        return result_summary
                    else:
                        progress.failed_items += 1
                        self.save_failed_keyword(batch_id, keyword, "Search failed after retries")
                        
                        failed_summary = {
                            "keyword": keyword,
                            "products_found": 0,
                            "status": "failed",
                            "error": "Search failed after retries",
                            "timestamp": datetime.now().isoformat()
                        }
                        return failed_summary
        
        # Process all keywords
        tasks = [process_keyword(keyword) for keyword in keywords]
        
        # Process in batches to avoid overwhelming the system
        batch_size = min(self.config.max_concurrent * 2, 50)
        
        for i in range(0, len(tasks), batch_size):
            batch_tasks = tasks[i:i + batch_size]
            results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Process results and handle exceptions
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Task failed with exception: {result}")
                    progress.failed_items += 1
                else:
                    batch_results.append(result)
            
            # Update progress display
            self.update_progress_display(progress)
            
            # Save checkpoint
            if self.config.enable_resume and (i // batch_size) % self.config.checkpoint_interval == 0:
                self.save_checkpoint(batch_id, progress, completed_keywords)
        
        print()  # New line after progress display
        
        # Generate batch summary
        summary = {
            "batch_id": batch_id,
            "total_keywords": progress.total_items,
            "completed": progress.completed_items,
            "failed": progress.failed_items,
            "success_rate": (progress.completed_items / progress.total_items) * 100 if progress.total_items > 0 else 0,
            "total_time": progress.elapsed_time,
            "avg_time_per_keyword": progress.elapsed_time / progress.completed_items if progress.completed_items > 0 else 0,
            "start_time": progress.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "config": asdict(self.config),
            "results": [r for r in batch_results if not isinstance(r, Exception)]
        }
        
        # Save batch summary
        if self.config.save_batch_summary:
            summary_file = self.batch_dir / "summaries" / f"{batch_id}_summary.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Batch processing completed: {batch_id}")
        logger.info(f"Success: {progress.completed_items}/{progress.total_items} ({summary['success_rate']:.1f}%)")
        logger.info(f"Total time: {progress.elapsed_time/60:.1f} minutes")
        
        return summary


# CLI function for batch processing
async def main_batch():
    """CLI entry point for batch processing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch Japanese Marketplace Scraper")
    parser.add_argument("input_file", help="CSV or text file containing keywords (one per line)")
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
        help="Maximum results per keyword per platform"
    )
    parser.add_argument(
        "--max-concurrent", 
        type=int, 
        default=5,
        help="Maximum concurrent searches"
    )
    parser.add_argument(
        "--delay", 
        type=float, 
        default=2.0,
        help="Delay between searches (seconds)"
    )
    parser.add_argument(
        "--batch-id",
        help="Custom batch ID (for resume)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume previous batch"
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory to store results"
    )
    
    args = parser.parse_args()
    
    try:
        # Create batch config
        config = BatchConfig(
            max_concurrent=args.max_concurrent,
            delay_between_searches=args.delay,
            enable_resume=True
        )
        
        # Initialize batch scraper
        scraper = BatchScraper(config, args.data_dir)
        
        # Load keywords
        keywords = scraper.load_keywords_from_file(args.input_file)
        
        if not keywords:
            logger.error("No keywords found in input file")
            return
        
        # Convert platform strings to enums
        platforms = None
        if args.platforms:
            platforms = [Platform(p) for p in args.platforms]
        
        # Process batch
        summary = await scraper.process_batch(
            keywords=keywords,
            platforms=platforms,
            max_results_per_keyword=args.max_results,
            batch_id=args.batch_id
        )
        
        print(f"\n✅ Batch processing completed!")
        print(f"📊 Results: {summary['completed']}/{summary['total_keywords']} ({summary['success_rate']:.1f}%)")
        print(f"⏱️  Total time: {summary['total_time']/60:.1f} minutes")
        print(f"📁 Results saved to: {scraper.batch_dir}")
        
    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main_batch())
