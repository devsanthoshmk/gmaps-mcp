"""Google Maps Places Async Crawler.

Adapted and modularized from mapScraper (https://github.com/christivn/mapScraper).
Pinned Upstream Commit: 1b38cf3e153294e3dad2f6cb5862be0201a54065

This module runs natively in-process using asyncio and aiohttp, avoiding external
subprocesses. All logging outputs strictly to stderr to keep MCP stdio transport
unpolluted.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import aiohttp

from gmaps_mcp.schemas import Place

logger = logging.getLogger("gmaps_mcp.scraper")

# Realistic browser headers to avoid consent walls and bot detection
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def _safe_get(obj: Any, *indices: Any, default: Any = None) -> Any:
    """Safely navigate nested lists and dicts, returning default on index/key error."""
    try:
        current = obj
        for idx in indices:
            current = current[idx]
        return current
    except (IndexError, TypeError, KeyError):
        return default


def _extract_place_from_raw(result: list, query: str) -> Optional[Place]:
    """Extract a Place model from a single raw result entry list.

    Google Maps tbm=map internal JSON offsets:
      [4][7]          float  – average star rating
      [7][0]          str    – website URL
      [7][1]          str    – website domain
      [9][2], [9][3]  float  – latitude, longitude
      [11]            str    – place name / title
      [13][0]         str    – primary category
      [37][1]         int    – review count
      [39]            str    – full formatted address
      [78]            str    – ChIJ place ID
      [178][0][1][0][0] str  – local phone (e.g. "(716) 847-0070")
      [178][0][1][1][0] str  – international phone (e.g. "+1 716-847-0070")
    """
    if not isinstance(result, list):
        return None

    place_id = _safe_get(result, 78)
    if not place_id or not isinstance(place_id, str):
        logger.debug("Skipping entry with no valid place ID for query %r", query)
        return None

    name = _safe_get(result, 11, default="")
    if not name:
        return None

    category = _safe_get(result, 13, 0, default=None)
    address = _safe_get(result, 39, default=None)
    
    # Phone numbers
    phone_local = _safe_get(result, 178, 0, 0)
    if not phone_local or not isinstance(phone_local, str):
        phone_local = _safe_get(result, 178, 0, 1, 0, 0)
    
    phone_intl = _safe_get(result, 178, 0, 1, 1, 0)
    if not phone_intl or not isinstance(phone_intl, str):
        phone_intl = _safe_get(result, 178, 0, 3)
    
    # Website
    website = _safe_get(result, 7, 0, default=None)
    domain = _safe_get(result, 7, 1, default=None)
    
    # Coordinates
    lat_val = _safe_get(result, 9, 2)
    lng_val = _safe_get(result, 9, 3)
    latitude = float(lat_val) if isinstance(lat_val, (int, float)) else None
    longitude = float(lng_val) if isinstance(lng_val, (int, float)) else None

    # Rating and reviews
    rating_val = _safe_get(result, 4, 7)
    rating = float(rating_val) if isinstance(rating_val, (int, float)) else None

    review_count_val = _safe_get(result, 37, 1)
    review_count = int(review_count_val) if isinstance(review_count_val, (int, float)) else None

    google_maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"

    return Place(
        place_id=place_id,
        name=str(name).strip(),
        category=str(category).strip() if category else None,
        address=str(address).strip() if address else None,
        phone=str(phone_local).strip() if phone_local else None,
        international_phone=str(phone_intl).strip() if phone_intl else None,
        website=str(website).strip() if website else None,
        domain=str(domain).strip() if domain else None,
        latitude=latitude,
        longitude=longitude,
        rating=rating,
        review_count=review_count,
        google_maps_url=google_maps_url,
    )


def _extract_single_place_fallback(data: Any, query: str) -> Optional[Place]:
    """Fallback search for a single Place object when Google returns direct place view."""
    # Often located at data[0][1][0][14]
    candidate = _safe_get(data, 0, 1, 0, 14)
    if candidate and isinstance(candidate, list) and _safe_get(candidate, 78):
        return _extract_place_from_raw(candidate, query)

    # Recursive check for any nested list with a valid ChIJ place ID
    def _find_place_list(obj: Any, depth: int = 0) -> Optional[list]:
        if depth > 6:
            return None
        if isinstance(obj, list):
            if len(obj) > 78 and isinstance(obj[78], str) and obj[78].startswith("ChIJ") and len(obj) > 11 and obj[11]:
                return obj
            for item in obj:
                found = _find_place_list(item, depth + 1)
                if found:
                    return found
        return None

    raw_list = _find_place_list(data)
    if raw_list:
        return _extract_place_from_raw(raw_list, query)

    return None


async def _get_search_url(
    session: aiohttp.ClientSession,
    query: str,
    lang: str,
    country: str,
    timeout: int = 20
) -> Optional[str]:
    """Step 1: Resolve the canonical Google Maps search URL from the SPA link tag."""
    encoded_query = quote(query)
    maps_url = f"https://www.google.com/maps/search/{encoded_query}?hl={lang}&gl={country}"

    try:
        async with session.get(
            maps_url,
            headers=DEFAULT_HEADERS,
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            if resp.status != 200:
                logger.error("[%s] Maps page returned HTTP %d", query, resp.status)
                return None
            html = await resp.text()
    except Exception as e:
        logger.error("[%s] Failed to fetch Maps page: %s", query, e)
        return None

    pb_match = re.search(r'href="(/search\?tbm=map[^"]+)"', html)
    if not pb_match:
        logger.warning(
            "[%s] Could not find pb= search URL in Maps page. Response might be a consent page.",
            query
        )
        return None

    search_path = pb_match.group(1).replace("&amp;", "&")
    search_url = "https://www.google.com" + search_path
    logger.debug("[%s] Resolved Search URL: %s...", query, search_url[:100])
    return search_url


async def _fetch_results_page(
    session: aiohttp.ClientSession,
    search_url: str,
    query: str,
    start: int = 0,
    timeout: int = 20
) -> List[Place]:
    """Step 2: Fetch and parse one page of tbm=map results."""
    url = search_url if start == 0 else f"{search_url}&start={start}"

    try:
        async with session.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            if resp.status != 200:
                logger.error("[%s] API returned HTTP %d (start=%d)", query, resp.status, start)
                return []
            raw = await resp.text()
    except Exception as e:
        logger.error("[%s] Network error fetching page (start=%d): %s", query, start, e)
        return []

    # Strip Google's XSSI prefix )]}'
    if raw.startswith(")]}'"):
        raw = raw[4:].strip()
    else:
        logger.debug("[%s] Missing )]}' prefix at start=%d", query, start)
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("[%s] JSON decode error at start=%d: %s", query, start, e)
        return []

    # Standard multi-result list is in data[64]
    results_array = _safe_get(data, 64)
    places: List[Place] = []

    if results_array and isinstance(results_array, list):
        for entry in results_array:
            if entry and isinstance(entry, list) and len(entry) > 1:
                result_item = entry[1]
                if result_item and isinstance(result_item, list):
                    place = _extract_place_from_raw(result_item, query)
                    if place:
                        places.append(place)

    # If no results in data[64] on start=0, attempt single-place fallback
    if not places and start == 0:
        single_place = _extract_single_place_fallback(data, query)
        if single_place:
            places.append(single_place)

    logger.debug("[%s] Extracted %d places (start=%d)", query, len(places), start)
    return places


async def search_google_maps_async(
    query: str,
    lang: str = "en",
    country: str = "in",
    limit: int = 10,
    timeout: int = 20,
) -> List[Place]:
    """Execute asynchronous Google Maps search with pagination and deduplication.

    Args:
        query: Search term (e.g., 'coffee in Koramangala Bangalore').
        lang: Language code for Google Maps (e.g., 'en', 'hi', 'es').
        country: ISO country code for Google Maps (e.g., 'in', 'us', 'uk').
        limit: Maximum number of place results to return (1-50).
        timeout: Request timeout in seconds.

    Returns:
        List of Place models.
    """
    places: List[Place] = []
    seen_ids: set[str] = set()

    connector = aiohttp.TCPConnector(ssl=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        search_url = await _get_search_url(session, query, lang, country, timeout=timeout)
        if not search_url:
            logger.warning("[%s] Could not obtain search URL, aborting search.", query)
            return []

        page_size = 20
        start = 0
        max_pages = max(1, (limit + page_size - 1) // page_size)

        for _ in range(max_pages):
            page_places = await _fetch_results_page(
                session, search_url, query, start=start, timeout=timeout
            )

            if not page_places:
                break

            for place in page_places:
                if place.place_id not in seen_ids:
                    seen_ids.add(place.place_id)
                    places.append(place)
                    if len(places) >= limit:
                        break

            if len(places) >= limit:
                break

            start += page_size

    logger.info("[%s] Search finished. Found %d place(s).", query, len(places))
    return places[:limit]


async def get_place_details_async(
    query_or_id: str,
    lang: str = "en",
    country: str = "in",
    timeout: int = 20,
) -> Optional[Place]:
    """Retrieve place details by place ID or exact place name.

    Args:
        query_or_id: Google Place ID (e.g. 'ChIJ...') or place name.
        lang: Language code.
        country: Country code.
        timeout: Request timeout in seconds.

    Returns:
        Place model if found, None otherwise.
    """
    search_query = query_or_id
    if query_or_id.startswith("ChIJ") and not query_or_id.startswith("place_id:"):
        search_query = f"place_id:{query_or_id}"

    results = await search_google_maps_async(
        query=search_query,
        lang=lang,
        country=country,
        limit=1,
        timeout=timeout,
    )

    if results:
        return results[0]
    return None
