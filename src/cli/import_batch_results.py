#!/usr/bin/env python3
"""
Import batch processing results into the canonical product system.
Processes JSON files from data/batch/results/ and updates the canonical product database.
"""

import json
import sys
from pathlib import Path
from loguru import logger
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from canonical_products_simple import SimpleCanonicalProducts


def format_product_for_canonical(product_data: dict) -> dict:
    """Format a product from batch results for the canonical system."""
    try:
        return {
            'title': product_data.get('title', ''),
            'platform': product_data.get('platform', ''),  # Add platform field
            'price': product_data.get('price', 0.0),
            'currency': product_data.get('currency', 'USD'),
            'url': product_data.get('url', ''),
            'availability': product_data.get('availability', 'unknown'),
            'site': product_data.get('site', ''),
            'category': product_data.get('category', ''),
            'brand': product_data.get('brand', ''),
            'model': product_data.get('model', ''),
            'description': product_data.get('description', ''),
            'image_urls': product_data.get('image_urls', []),
            'scraped_at': product_data.get('scraped_at', datetime.now().isoformat()),
            'metadata': product_data.get('metadata', {})
        }
    except Exception as e:
        logger.error(f"Error formatting product: {e}")
        return None


def import_batch_results(data_dir: str = "data"):
    """Import all batch results into canonical product system."""
    logger.info("Starting batch results import...")
    
    # Initialize canonical product manager
    canonical_manager = SimpleCanonicalProducts(data_dir)
    
    # Find all batch result files
    batch_results_dir = Path(data_dir) / "batch" / "results"
    if not batch_results_dir.exists():
        logger.warning(f"Batch results directory not found: {batch_results_dir}")
        return
    
    json_files = list(batch_results_dir.glob("*.json"))
    if not json_files:
        logger.warning(f"No JSON files found in {batch_results_dir}")
        return
    
    logger.info(f"Found {len(json_files)} batch result files to process")
    
    total_products = 0
    processed_files = 0
    
    # Process each batch result file
    for json_file in json_files:
        try:
            logger.info(f"Processing: {json_file.name}")
            
            with open(json_file, 'r', encoding='utf-8') as f:
                batch_data = json.load(f)
            
            # Extract products from batch data
            if batch_data.get('products'):
                products = batch_data['products']
                
                # Format products for canonical system
                formatted_products = []
                for product in products:
                    formatted = format_product_for_canonical(product)
                    if formatted:
                        formatted_products.append(formatted)
                
                if formatted_products:
                    # Use correct method signature
                    added_count = canonical_manager.add_discovered_products(
                        products_data=formatted_products,
                        discovery_session_id=json_file.stem
                    )
                    total_products += added_count
                    logger.info(f"Added {added_count} products from {json_file.name}")
                else:
                    logger.warning(f"No valid products found in {json_file.name}")
            else:
                logger.warning(f"No products found in {json_file.name}")
            
            processed_files += 1
            
        except Exception as e:
            logger.error(f"Error processing {json_file.name}: {e}")
            continue
    
    # Get final stats
    total_canonical = len(canonical_manager.products)
    price_changes = len(canonical_manager.price_history)
    
    logger.info("✅ Import completed!")
    logger.info(f"📁 Processed files: {processed_files}/{len(json_files)}")
    logger.info(f"🆕 Products imported: {total_products}")
    logger.info(f"📊 Total canonical products: {total_canonical}")
    logger.info(f"💰 Price changes detected: {price_changes}")
    
    print(f"\n✅ Successfully imported {total_products} products from {processed_files} files")
    print(f"📊 Total canonical products: {total_canonical}")
    print(f"💰 Price changes: {price_changes}")


if __name__ == "__main__":
    import_batch_results()
