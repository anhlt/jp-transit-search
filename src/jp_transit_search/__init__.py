"""Japanese Transit Search Package

A Python package for searching transit times between Japanese stations
with CLI and MCP client capabilities.
"""

__version__ = "0.1.0"
__author__ = "anhlt"
__email__ = "tuananh.kirimaru@gmail.com"

from .core.models import Route, Station, Transfer
from .core.scraper import YahooTransitScraper

__all__ = ["Route", "Station", "Transfer", "YahooTransitScraper"]
