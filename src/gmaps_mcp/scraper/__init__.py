"""Scraper module package for gmaps_mcp.

Exposes native async search and details functions for Google Maps.
"""

from gmaps_mcp.scraper.crawler import (
    search_google_maps_async,
    get_place_details_async,
)

__all__ = [
    "search_google_maps_async",
    "get_place_details_async",
]
