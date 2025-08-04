"""
Change Detection System for Japanese Marketplace Scraper

This module provides functionality to detect changes in scraped product data,
automatically save results with ISO 8601 timestamps, and maintain historical records.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, asdict
from loguru import logger

from .models import Product


@dataclass
class ChangeInfo:
    """Information about a detected change"""
    change_type: str  # 'price_change', 'new_product', 'removed_product', 'availability_change'
    product_id: str  # Usually title + platform combination
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    timestamp: str = ""
    platform: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class ComparisonResult:
    """Result of comparing two scraping sessions"""
    has_changes: bool
    changes: List[ChangeInfo]
    new_products: int
    removed_products: int
    price_changes: int
    availability_changes: int
    total_products_before: int
    total_products_after: int
    comparison_timestamp: str
    
    def __post_init__(self):
        if not self.comparison_timestamp:
            self.comparison_timestamp = datetime.now().isoformat()


class ChangeDetector:
    """Detects changes between scraping sessions and manages historical data"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Subdirectories for organization
        self.results_dir = self.data_dir / "batch" / "results"  # Use batch results directory
        self.changes_dir = self.data_dir / "changes"
        self.summaries_dir = self.data_dir / "summaries"
        
        for directory in [self.results_dir, self.changes_dir, self.summaries_dir]:
            directory.mkdir(exist_ok=True)
    
    def generate_timestamp_filename(self, keyword: str, extension: str = "json") -> str:
        """Generate a filename with ISO 8601 timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_keyword = safe_keyword.replace(' ', '_')
        return f"{safe_keyword}_{timestamp}.{extension}"
    
    def get_product_id(self, product: Product) -> str:
        """Generate a unique ID for a product based on normalized title and platform"""
        # Normalize title for better matching across scrapes
        normalized_title = self._normalize_title(product.title)
        return f"{normalized_title}_{product.platform}"
    
    def _normalize_title(self, title: str) -> str:
        """Normalize product title for consistent matching"""
        import re
        
        # Convert to lowercase for case-insensitive matching
        title = title.lower()
        
        # Remove only the most obviously dynamic promotional text
        promotional_patterns = [
            r'\s*\(amazon\.co\.jp exclusive\)',
            r'\s*amazon\.co\.jp\s*exclusive',
            r'\s*\+.*cloth\s*$',  # Remove "+ cloth" additions at the end only
            r'\s*お得な.*セット\s*$',  # "advantageous set" at the end only
        ]
        
        for pattern in promotional_patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
        # Normalize whitespace and basic variations
        title = re.sub(r'\s+', ' ', title)  # Multiple spaces to single
        title = re.sub(r'ernie\s*ball', 'ernie ball', title)  # Normalize brand
        title = re.sub(r'regular\s*slinky', 'regular slinky', title)  # Normalize product line
        
        return title.strip()
    
    def save_results(self, results: Dict, keyword: str) -> str:
        """Save scraping results with timestamp and return the filename"""
        filename = self.generate_timestamp_filename(keyword)
        filepath = self.results_dir / filename
        
        # Add metadata to results
        enhanced_results = {
            **results,
            "saved_at": datetime.now().isoformat(),
            "filename": filename
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(enhanced_results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to {filepath}")
        return str(filepath)
    
    def load_latest_results(self, keyword: str) -> Optional[Dict]:
        """Load the most recent results for a given keyword"""
        safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_keyword = safe_keyword.replace(' ', '_')
        
        # Find all files matching the keyword pattern (handle batch format)
        pattern = f"*{safe_keyword}_*.json"
        matching_files = list(self.results_dir.glob(pattern))
        
        if not matching_files:
            logger.info(f"No previous results found for keyword: {keyword}")
            return None
        
        # Sort by filename (timestamp) to get the latest
        latest_file = sorted(matching_files)[-1]
        
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            logger.info(f"Loaded previous results from {latest_file}")
            return results
        except Exception as e:
            logger.error(f"Error loading previous results: {e}")
            return None
    
    def load_second_latest_results(self, keyword: str) -> Optional[Dict]:
        """Load the second most recent results for a given keyword"""
        safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_keyword = safe_keyword.replace(' ', '_')
        
        # Find all files matching the keyword pattern (handle batch format)
        pattern = f"*{safe_keyword}_*.json"
        matching_files = list(self.results_dir.glob(pattern))
        
        if len(matching_files) < 2:
            logger.info(f"Not enough previous results found for comparison (need at least 2)")
            return None
        
        # Sort by filename (timestamp) to get the second latest
        second_latest_file = sorted(matching_files)[-2]
        
        try:
            with open(second_latest_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            logger.info(f"Loaded second latest results from {second_latest_file}")
            return results
        except Exception as e:
            logger.error(f"Error loading second latest results: {e}")
            return None
    
    def compare_results(self, old_results: Dict, new_results: Dict) -> ComparisonResult:
        """Compare two result sets and detect changes"""
        changes = []
        
        # Convert products to dictionaries for easier comparison
        old_products = {self.get_product_id(Product(**p)): Product(**p) 
                       for p in old_results.get('products', [])}
        new_products = {self.get_product_id(Product(**p)): Product(**p) 
                       for p in new_results.get('products', [])}
        
        old_ids = set(old_products.keys())
        new_ids = set(new_products.keys())
        
        # Detect new products
        new_product_ids = new_ids - old_ids
        for product_id in new_product_ids:
            product = new_products[product_id]
            changes.append(ChangeInfo(
                change_type="new_product",
                product_id=product_id,
                new_value=product.title,
                platform=product.platform
            ))
        
        # Detect removed products
        removed_product_ids = old_ids - new_ids
        for product_id in removed_product_ids:
            product = old_products[product_id]
            changes.append(ChangeInfo(
                change_type="removed_product",
                product_id=product_id,
                old_value=product.title,
                platform=product.platform
            ))
        
        # Detect changes in existing products
        common_ids = old_ids & new_ids
        for product_id in common_ids:
            old_product = old_products[product_id]
            new_product = new_products[product_id]
            
            # Price changes
            if old_product.price != new_product.price:
                changes.append(ChangeInfo(
                    change_type="price_change",
                    product_id=product_id,
                    old_value=old_product.price,
                    new_value=new_product.price,
                    platform=new_product.platform
                ))
            
            # Availability changes
            if old_product.availability != new_product.availability:
                changes.append(ChangeInfo(
                    change_type="availability_change",
                    product_id=product_id,
                    old_value=old_product.availability,
                    new_value=new_product.availability,
                    platform=new_product.platform
                ))
            
            # Rating changes (if significant)
            if (old_product.rating and new_product.rating and 
                abs(old_product.rating - new_product.rating) >= 0.1):
                changes.append(ChangeInfo(
                    change_type="rating_change",
                    product_id=product_id,
                    old_value=old_product.rating,
                    new_value=new_product.rating,
                    platform=new_product.platform
                ))
        
        # Count different types of changes
        price_changes = sum(1 for c in changes if c.change_type == "price_change")
        availability_changes = sum(1 for c in changes if c.change_type == "availability_change")
        
        return ComparisonResult(
            has_changes=len(changes) > 0,
            changes=changes,
            new_products=len(new_product_ids),
            removed_products=len(removed_product_ids),
            price_changes=price_changes,
            availability_changes=availability_changes,
            total_products_before=len(old_products),
            total_products_after=len(new_products),
            comparison_timestamp=datetime.now().isoformat()
        )
    
    def save_changes(self, comparison: ComparisonResult, keyword: str) -> str:
        """Save detected changes to a file"""
        filename = self.generate_timestamp_filename(f"{keyword}_changes")
        filepath = self.changes_dir / filename
        
        # Convert to serializable format
        changes_data = {
            "keyword": keyword,
            "comparison_summary": {
                "has_changes": comparison.has_changes,
                "new_products": comparison.new_products,
                "removed_products": comparison.removed_products,
                "price_changes": comparison.price_changes,
                "availability_changes": comparison.availability_changes,
                "total_products_before": comparison.total_products_before,
                "total_products_after": comparison.total_products_after,
                "comparison_timestamp": comparison.comparison_timestamp
            },
            "changes": [asdict(change) for change in comparison.changes]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(changes_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Changes saved to {filepath}")
        return str(filepath)
    
    def generate_summary_report(self, comparison: ComparisonResult, keyword: str) -> Dict:
        """Generate a human-readable summary report"""
        report = {
            "keyword": keyword,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_changes": len(comparison.changes),
                "has_significant_changes": comparison.has_changes,
                "products_before": comparison.total_products_before,
                "products_after": comparison.total_products_after,
                "net_product_change": comparison.total_products_after - comparison.total_products_before
            },
            "change_breakdown": {
                "new_products": comparison.new_products,
                "removed_products": comparison.removed_products,
                "price_changes": comparison.price_changes,
                "availability_changes": comparison.availability_changes,
                "rating_changes": sum(1 for c in comparison.changes if c.change_type == "rating_change")
            },
            "notable_changes": []
        }
        
        # Add notable price changes
        for change in comparison.changes:
            if change.change_type == "price_change" and change.old_value and change.new_value:
                price_diff = float(change.new_value) - float(change.old_value)
                percentage_change = (price_diff / float(change.old_value)) * 100
                
                if abs(percentage_change) >= 5:  # 5% or more change
                    report["notable_changes"].append({
                        "type": "significant_price_change",
                        "product_id": change.product_id,
                        "platform": change.platform,
                        "old_price": change.old_value,
                        "new_price": change.new_value,
                        "price_difference": round(price_diff, 2),
                        "percentage_change": round(percentage_change, 2)
                    })
        
        return report
    
    def save_summary_report(self, report: Dict, keyword: str) -> str:
        """Save the summary report"""
        filename = self.generate_timestamp_filename(f"{keyword}_summary")
        filepath = self.summaries_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Summary report saved to {filepath}")
        return str(filepath)
    
    def save_results_only(self, results: Dict, keyword: str) -> str:
        """Save scraping results with timestamp only (no change detection)"""
        filename = self.generate_timestamp_filename(keyword)
        filepath = self.results_dir / filename
        
        # Add metadata to results
        enhanced_results = {
            **results,
            "saved_at": datetime.now().isoformat(),
            "filename": filename
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(enhanced_results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to {filepath}")
        return str(filepath)
    
    def detect_changes_for_keyword(self, keyword: str) -> Dict:
        """
        Detect changes by comparing the two most recent scraping results for a keyword.
        This should be run separately after scraping sessions.
        """
        logger.info(f"Detecting changes for keyword: {keyword}")
        
        # Load the two most recent results
        latest_results = self.load_latest_results(keyword)
        previous_results = self.load_second_latest_results(keyword)
        
        response = {
            "keyword": keyword,
            "has_sufficient_data": False,
            "changes_detected": False,
            "changes_filepath": None,
            "summary_filepath": None,
            "comparison_summary": None,
            "error": None
        }
        
        if not latest_results:
            response["error"] = "No results found for this keyword"
            return response
            
        if not previous_results:
            response["error"] = "Need at least 2 scraping sessions to detect changes"
            return response
        
        response["has_sufficient_data"] = True
        
        try:
            # Compare results
            comparison = self.compare_results(previous_results, latest_results)
            
            if comparison.has_changes:
                # Save changes
                changes_filepath = self.save_changes(comparison, keyword)
                response["changes_filepath"] = changes_filepath
                response["changes_detected"] = True
                
                # Generate and save summary report
                summary_report = self.generate_summary_report(comparison, keyword)
                summary_filepath = self.save_summary_report(summary_report, keyword)
                response["summary_filepath"] = summary_filepath
                response["comparison_summary"] = summary_report
                
                logger.info(f"Changes detected: {len(comparison.changes)} total changes")
            else:
                logger.info("No changes detected between the two most recent results")
                
        except Exception as e:
            logger.error(f"Error during change detection: {e}")
            response["error"] = str(e)
        
        return response
        return response

    def process_scraping_results(self, results: Dict, keyword: str) -> Dict:
        """
        DEPRECATED: Use save_results_only() for saving and detect_changes_for_keyword() for analysis.
        This method is kept for backward compatibility but will be removed.
        """
        logger.warning("process_scraping_results is deprecated. Use save_results_only() and detect_changes_for_keyword() separately.")
        return {"results_saved": self.save_results_only(results, keyword)}


def create_change_detector(data_dir: str = "data") -> ChangeDetector:
    """Factory function to create a ChangeDetector instance"""
    return ChangeDetector(data_dir)
