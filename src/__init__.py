"""
Japanese Marketplace Scraper - Bright Data Edition

A comprehensive web scraper for Japanese e-commerce platforms using Bright Data.
"""

from .models import Product, SearchResult, Platform
from .utils import setup_logging, load_config

__version__ = "0.1.0"
__all__ = ["Product", "SearchResult", "Platform", "setup_logging", "load_config"]
