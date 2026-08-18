"""Google Maps Places Async Crawler.

Adapted and modularized from mapScraper (https://github.com/christivn/mapScraper).
Pinned Upstream Commit: 1b38cf3e153294e3dad2f6cb5862be0201a54065

This module runs natively in-process using asyncio and aiohttp, avoiding external
subprocesses. All logging outputs strictly to stderr to keep MCP stdio transport
unpolluted.
"""

import asyncio
import base64
import json
import logging
import math
import re
import struct
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

import aiohttp
import phonenumbers
from phonenumbers import PhoneNumberFormat

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


def _place_id_to_cid_hex(place_id: str) -> Optional[Tuple[str, str]]:
    """Decode a Google Place ID into its underlying (feature_id_hex, cid_hex) tuple."""
    try:
        clean = place_id.replace("place_id:", "").strip()
        b64 = clean.replace("-", "+").replace("_", "/")
        while len(b64) % 4 != 0:
            b64 += "="
        raw = base64.b64decode(b64)
        if len(raw) < 20:
            return None
        fid_bytes = raw[3:11]
        cid_bytes = raw[12:20]
        fid_int = struct.unpack("<Q", fid_bytes)[0]
        cid_int = struct.unpack("<Q", cid_bytes)[0]
        return f"0x{fid_int:016x}", f"0x{cid_int:016x}"
    except Exception as e:
        logger.debug("Failed decoding place_id %s: %s", place_id, e)
        return None


def _normalize_phone(
    phone_raw: Optional[str],
    phone_intl_raw: Optional[str],
    country_code: str = "IN",
) -> Tuple[Optional[str], Optional[str]]:
    """Normalize local and international phone numbers using the phonenumbers library.

    Returns:
        (normalized_local_phone, normalized_international_phone)
    """
    country_code = country_code.upper() if country_code else "IN"

    for raw in [phone_intl_raw, phone_raw]:
        if not raw or not isinstance(raw, str):
            continue
        cleaned = re.sub(r"[^\d+]", "", raw.strip())
        if not cleaned:
            continue
        try:
            parsed = phonenumbers.parse(raw, country_code)
            if phonenumbers.is_valid_number(parsed) or phonenumbers.is_possible_number(parsed):
                nat = phonenumbers.format_number(parsed, PhoneNumberFormat.NATIONAL)
                intl = phonenumbers.format_number(parsed, PhoneNumberFormat.INTERNATIONAL)
                return nat, intl
        except Exception:
            continue

    # Fallback to trimmed raw strings if parsing fails
    local_out = phone_raw.strip() if phone_raw and isinstance(phone_raw, str) else None
    intl_out = phone_intl_raw.strip() if phone_intl_raw and isinstance(phone_intl_raw, str) else None
    return local_out, intl_out


def _extract_place_from_raw(result: list, query: str, country: str = "in") -> Optional[Place]:
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
        if len(result) > 0 and isinstance(result[0], str) and result[0].startswith("ChIJ"):
            place_id = result[0]
        elif query.startswith("ChIJ") or "place_id:ChIJ" in query:
            place_id = query.replace("place_id:", "").strip()
        else:
            return None

    name = _safe_get(result, 11, default="")
    if not name:
        name = _safe_get(result, 14, default="")
    if not name:
        return None

    category = _safe_get(result, 13, 0, default=None)
    if not category:
        category = _safe_get(result, 13, default=None)
        if isinstance(category, list) and category:
            category = category[0]

    address = _safe_get(result, 39, default=None)
    if not address:
        address = _safe_get(result, 18, default=None)
    if not address:
        addr_list = _safe_get(result, 2, default=None)
        if isinstance(addr_list, list):
            address = ", ".join(str(a) for a in addr_list if isinstance(a, str) and not a.startswith("http"))
        elif isinstance(addr_list, str) and not addr_list.startswith("http"):
            address = addr_list

    # Collect all phone number candidates from offset 178 and alternatives
    phone_candidates: List[str] = []
    raw_178 = _safe_get(result, 178)
    if raw_178 and isinstance(raw_178, list):
        def _collect_phones(obj: Any):
            if isinstance(obj, str) and obj.strip():
                if sum(c.isdigit() for c in obj) >= 6:
                    phone_candidates.append(obj.strip())
            elif isinstance(obj, list):
                for item in obj:
                    _collect_phones(item)
        _collect_phones(raw_178)

    if not phone_candidates:
        for offset in (115, 100, 30, 201):
            val = _safe_get(result, offset)
            if isinstance(val, str) and sum(c.isdigit() for c in val) >= 6:
                phone_candidates.append(val.strip())

    phone_local_raw = phone_candidates[0] if phone_candidates else None
    phone_intl_raw = next((p for p in phone_candidates if p.startswith("+")), None)

    phone, international_phone = _normalize_phone(phone_local_raw, phone_intl_raw, country_code=country)

    # Website extraction
    website = _safe_get(result, 7, 0, default=None)
    domain = _safe_get(result, 7, 1, default=None)
    if not website or not isinstance(website, str) or not website.startswith("http"):
        for offset in (7, 8, 10, 115):
            val = _safe_get(result, offset)
            if isinstance(val, str) and val.startswith("http"):
                website = val
                break
            elif isinstance(val, list) and val and isinstance(val[0], str) and val[0].startswith("http"):
                website = val[0]
                break

    if website and not domain:
        domain_match = re.search(r'https?://([^/]+)', website)
        if domain_match:
            domain = domain_match.group(1).replace("www.", "")

    # Coordinates
    lat_val = _safe_get(result, 9, 2)
    lng_val = _safe_get(result, 9, 3)
    latitude = float(lat_val) if isinstance(lat_val, (int, float)) else None
    longitude = float(lng_val) if isinstance(lng_val, (int, float)) else None

    # Rating and reviews
    rating_val = _safe_get(result, 4, 7)
    rating = float(rating_val) if isinstance(rating_val, (int, float)) else None

    review_count_val = _safe_get(result, 37, 1)
    if review_count_val is None:
        review_count_val = _safe_get(result, 4, 8)
    review_count = int(review_count_val) if isinstance(review_count_val, (int, float)) else None

    google_maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"

    return Place(
        place_id=place_id,
        name=str(name).strip(),
        category=str(category).strip() if category else None,
        address=str(address).strip() if address else None,
        phone=phone,
        international_phone=international_phone,
        website=str(website).strip() if website else None,
        domain=str(domain).strip() if domain else None,
        latitude=latitude,
        longitude=longitude,
        rating=rating,
        review_count=review_count,
        google_maps_url=google_maps_url,
    )


def _extract_all_places_from_data(data: Any, query: str, country: str = "in") -> List[Place]:
    """Robustly extract all Place objects from any response data structure."""
    places: List[Place] = []
    seen = set()

    # 1. Standard multi-result list is in data[64]
    results_array = _safe_get(data, 64)
    if results_array and isinstance(results_array, list):
        for entry in results_array:
            if entry and isinstance(entry, list) and len(entry) > 1:
                result_item = entry[1]
                if result_item and isinstance(result_item, list):
                    place = _extract_place_from_raw(result_item, query, country=country)
                    if place and place.place_id not in seen:
                        seen.add(place.place_id)
                        places.append(place)

    # 2. Check preview place data at data[6]
    preview_place = _safe_get(data, 6)
    if preview_place and isinstance(preview_place, list) and len(preview_place) > 11 and preview_place[11]:
        place = _extract_place_from_raw(preview_place, query, country=country)
        if place and place.place_id not in seen:
            seen.add(place.place_id)
            places.append(place)

    # 3. Check data[0][1] (alternative structure)
    if not places:
        alt_array = _safe_get(data, 0, 1)
        if alt_array and isinstance(alt_array, list):
            for entry in alt_array:
                if entry and isinstance(entry, list) and len(entry) > 14:
                    item = entry[14]
                    if item and isinstance(item, list):
                        place = _extract_place_from_raw(item, query, country=country)
                        if place and place.place_id not in seen:
                            seen.add(place.place_id)
                            places.append(place)

    # 4. Recursive fallback to find any valid place arrays
    if not places:
        def _scan(obj: Any, depth: int = 0):
            if depth > 10 or len(places) > 100:
                return
            if isinstance(obj, list):
                if len(obj) > 11 and isinstance(obj[11], str) and obj[11]:
                    has_id = (len(obj) > 78 and isinstance(obj[78], str) and obj[78].startswith("ChIJ")) or (len(obj) > 10 and isinstance(obj[10], str) and obj[10].startswith("0x"))
                    if has_id:
                        place = _extract_place_from_raw(obj, query, country=country)
                        if place and place.place_id not in seen:
                            seen.add(place.place_id)
                            places.append(place)
                        return
                for child in obj:
                    _scan(child, depth + 1)
            elif isinstance(obj, dict):
                for v in obj.values():
                    _scan(v, depth + 1)

        _scan(data)

    return places


def _extract_single_place_fallback(data: Any, query: str, country: str = "in") -> Optional[Place]:
    """Fallback search for a single Place object when Google returns direct place view."""
    candidate = _safe_get(data, 0, 1, 0, 14)
    if candidate and isinstance(candidate, list) and _safe_get(candidate, 78):
        return _extract_place_from_raw(candidate, query, country=country)

    places = _extract_all_places_from_data(data, query, country=country)
    if places:
        return places[0]
    return None


def _extract_places_from_html(html: str, query: str, country: str = "in") -> List[Place]:
    """Extract Place objects directly from Google Maps HTML scripts and APP_INITIALIZATION_STATE."""
    places: List[Place] = []
    seen = set()

    for match in re.finditer(r'window\.APP_INITIALIZATION_STATE\s*=\s*(\[[\s\S]*?\]);\s*window\.', html):
        try:
            data = json.loads(match.group(1))
            extracted = _extract_all_places_from_data(data, query, country=country)
            for p in extracted:
                if p.place_id not in seen:
                    seen.add(p.place_id)
                    places.append(p)
        except Exception as e:
            logger.debug("Failed parsing APP_INITIALIZATION_STATE: %s", e)

    if not places:
        for script_match in re.finditer(r'<script[^>]*>([\s\S]*?)</script>', html):
            content = script_match.group(1)
            if "ChIJ" in content:
                for arr_match in re.finditer(r'(\[\[[\s\S]*?\]\])', content):
                    try:
                        arr_data = json.loads(arr_match.group(1))
                        extracted = _extract_all_places_from_data(arr_data, query, country=country)
                        for p in extracted:
                            if p.place_id not in seen:
                                seen.add(p.place_id)
                                places.append(p)
                    except Exception:
                        continue
            if places:
                break

    return places


def _extract_search_term(query: str) -> Tuple[str, Optional[str]]:
    """Extract (base_search_term, location_hint) from natural language query.

    Examples:
        "gift shop in chennai" -> ("gift shop", "chennai")
        "dentists in chicago" -> ("dentists", "chicago")
        "coffee near eiffel tower" -> ("coffee", "eiffel tower")
        "pharmacies at t nagar" -> ("pharmacies", "t nagar")
        "restaurants" -> ("restaurants", None)
    """
    pattern = r'^(.*?)\s+(?:in|near|around|at|within)\s+(.+)$'
    match = re.match(pattern, query.strip(), flags=re.IGNORECASE)
    if match:
        term = match.group(1).strip()
        loc = match.group(2).strip()
        if term and loc:
            return term, loc
    return query.strip(), None


def _build_viewport_tile_url(
    base_search_url: str,
    base_decoded_pb: str,
    term: str,
    lat: float,
    lng: float,
    span_meters: float,
    start: int = 0,
    page_idx: int = 1,
) -> str:
    """Inject sub-viewport geographic constraints and pagination into a valid session search URL."""
    vp_clause = f"!4m8!1m3!1d{span_meters:.1f}!2d{lng:.7f}!3d{lat:.7f}!3m2!1i1024!2i768!4f13.1"
    tile_pb = re.sub(r'^!1s[^!]+', f"!1s{quote(term)}{vp_clause}", base_decoded_pb)

    if start > 0:
        if "!8i" in tile_pb:
            tile_pb = re.sub(r'(!8i)\d+', f'!8i{start}', tile_pb)
        elif "!7i" in tile_pb:
            tile_pb = re.sub(r'(!7i\d+)', rf'\1!8i{start}', tile_pb)
        else:
            tile_pb = f"{tile_pb}!8i{start}"

    tile_url = re.sub(r'pb=[^&]+', f"pb={quote(tile_pb)}", base_search_url)
    tile_url = re.sub(r'q=[^&]+', f"q={quote(term)}", tile_url)
    if start > 0:
        tile_url = f"{tile_url}&start={start}&ech={page_idx}"
    return tile_url


def _generate_geo_grid(
    center_lat: float,
    center_lng: float,
    span_meters: float,
    grid_size: int,
) -> List[Tuple[float, float, float]]:
    """Dynamically divides any location on Earth into an NxN sub-viewport coordinate matrix without gaps."""
    if grid_size <= 0:
        return []

    lat_deg_span = span_meters / 111000.0
    lng_deg_span = span_meters / (111000.0 * max(0.01, math.cos(math.radians(center_lat))))

    cell_lat_deg = lat_deg_span / grid_size
    cell_lng_deg = lng_deg_span / grid_size
    cell_span = span_meters / grid_size

    half_grid = (grid_size - 1) / 2.0

    grid = []
    for r in range(grid_size):
        for c in range(grid_size):
            lat = center_lat + (r - half_grid) * cell_lat_deg
            lng = center_lng + (c - half_grid) * cell_lng_deg
            grid.append((lat, lng, cell_span))
    return grid


async def _get_search_url(
    session: aiohttp.ClientSession,
    query: str,
    lang: str,
    country: str,
    timeout: int = 20
) -> Tuple[Optional[str], List[Place], Optional[Tuple[float, float, float]]]:
    """Step 1: Resolve the canonical Google Maps search URL and detect geospatial viewport bounding box.

    Returns:
        (search_url, html_fallback_places, viewport_bounds_tuple_or_none)
    """
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
                return None, [], None
            html = await resp.text()
    except Exception as e:
        logger.error("[%s] Failed to fetch Maps page: %s", query, e)
        return None, [], None

    pb_match = re.search(r'href="(/search\?tbm=map[^"]+)"', html)
    if not pb_match:
        pb_match = re.search(r'(/search\?tbm=map[^"\'\s>]+)', html)

    search_url = None
    if pb_match:
        search_path = pb_match.group(1).replace("&amp;", "&")
        search_url = "https://www.google.com" + search_path
        logger.debug("[%s] Resolved Search URL: %s...", query, search_url[:100])

    fallback_places = _extract_places_from_html(html, query, country=country) if not search_url else []
    return search_url, fallback_places, None


async def _fetch_results_page(
    session: aiohttp.ClientSession,
    search_url: str,
    query: str,
    start: int = 0,
    country: str = "in",
    timeout: int = 20
) -> Tuple[List[Place], Optional[Tuple[float, float, float]]]:
    """Step 2: Fetch and parse one page of tbm=map results with proper protobuf offset adjustment.

    Returns:
        (places, detected_viewport_bounds)
    """
    if start == 0:
        url = search_url
        logger.info("[%s] Fetching initial results page (start=0)", query)
    else:
        # Google Maps protobuf pagination uses !7i{page_size}!8i{start}
        url = search_url
        if "!8i" in url:
            url = re.sub(r'(!8i)\d+', f'!8i{start}', url)
            method = "!8i (raw protobuf start offset)"
        elif "%218i" in url:
            url = re.sub(r'(%218i)\d+', f'%218i{start}', url)
            method = "%218i (encoded protobuf start offset)"
        elif "!7i" in url:
            url = re.sub(r'(!7i\d+)', rf'\1!8i{start}', url)
            method = "!7i (injected !8i after page size)"
        elif "%217i" in url:
            url = re.sub(r'(%217i\d+)', rf'\1%218i{start}', url)
            method = "%217i (injected %218i after encoded page size)"
        else:
            url = f"{url}&start={start}"
            method = "fallback &start= query param"

        page_num = (start // 20) + 1
        url = f"{url}&start={start}&ech={page_num}"
        logger.info(
            "[%s] Fetching pagination results (page=%d, start=%d, method=%s)",
            query,
            page_num,
            start,
            method,
        )

    try:
        async with session.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            if resp.status != 200:
                logger.error("[%s] API returned HTTP %d (start=%d)", query, resp.status, start)
                return [], None
            raw = await resp.text()
    except Exception as e:
        logger.error("[%s] Network error fetching page (start=%d): %s", query, start, e)
        return [], None

    # Strip Google's XSSI prefix )]}'
    if raw.startswith(")]}'"):
        raw = raw[4:].strip()
    else:
        if "APP_INITIALIZATION_STATE" in raw or "<html" in raw.lower():
            return _extract_places_from_html(raw, query, country=country), None
        logger.debug("[%s] Missing )]}' prefix at start=%d", query, start)
        return [], None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("[%s] JSON decode error at start=%d: %s", query, start, e)
        return [], None

    bounds = None
    if len(data) > 1 and data[1] and isinstance(data[1], list) and len(data[1]) > 0:
        b_item = data[1][0]
        if isinstance(b_item, list) and len(b_item) >= 3:
            span_m, lng, lat = b_item[0], b_item[1], b_item[2]
            if isinstance(span_m, (int, float)) and isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                bounds = (float(lat), float(lng), float(span_m))

    places = _extract_all_places_from_data(data, query, country=country)
    logger.debug("[%s] Extracted %d places (start=%d)", query, len(places), start)
    return places, bounds


async def search_google_maps_async(
    query: str,
    lang: str = "en",
    country: str = "in",
    limit: Optional[int] = None,
    grid: bool = False,
    grid_size: Optional[int] = None,
    concurrency: int = 8,
    timeout: int = 20,
    target_tile_meters: float = 5000.0,
    max_grid_size: int = 10,
) -> List[Place]:
    """Execute asynchronous Google Maps search with deep pagination and coverage-first adaptive grid expansion.

    Args:
        query: Search term (e.g., 'gift shop in chennai', 'dentists in chicago', 'coffee in Paris').
        lang: Language code for Google Maps (e.g., 'en', 'hi', 'fr', 'ja').
        country: ISO country code for Google Maps (e.g., 'in', 'us', 'fr', 'de').
        limit: Optional maximum number of place results to return. If None, fetches as many results as possible.
        grid: Whether to dynamically tile and search the detected geographic bounding box for massive result coverage.
        grid_size: Optional manual override for coordinate grid dimension (e.g. 4 = 4x4 = 16 sub-viewports). If None, calculated adaptively.
        concurrency: Semaphore concurrency limit when querying grid tiles.
        timeout: Request timeout in seconds.
        target_tile_meters: Target width/height in meters for each sub-viewport tile (default: 5000.0 = ~5 km).
        max_grid_size: Maximum grid dimension cap to limit excessive tiling (default: 10 = max 100 tiles).

    Returns:
        List of Place models.
    """
    places: List[Place] = []
    seen_ids: set[str] = set()

    connector = aiohttp.TCPConnector(ssl=True, limit=concurrency * 2)
    async with aiohttp.ClientSession(connector=connector) as session:
        search_url, html_places, _ = await _get_search_url(session, query, lang, country, timeout=timeout)
        if not search_url:
            if html_places:
                for p in html_places:
                    if p.place_id not in seen_ids:
                        seen_ids.add(p.place_id)
                        places.append(p)
                return places[:limit] if limit and limit > 0 else places

            logger.warning("[%s] Could not obtain search URL, aborting search.", query)
            return []

        # Extract base decoded protobuf template from search_url
        pb_match = re.search(r'pb=([^&]+)', search_url)
        decoded_pb = unquote(pb_match.group(1)) if pb_match else ""

        # 1. Primary sliding-window crawl on initial viewport
        page_size = 20
        start = 0
        max_pages = max(1, (limit + page_size - 1) // page_size) if limit and limit > 0 else 15

        detected_bounds = None
        consecutive_stagnant = 0
        while True:
            page_places, bounds = await _fetch_results_page(
                session, search_url, query, start=start, country=country, timeout=timeout
            )
            if bounds and not detected_bounds:
                detected_bounds = bounds

            if not page_places:
                consecutive_stagnant += 1
                if consecutive_stagnant >= 2:
                    break
                start += page_size
                continue

            new_added = 0
            for place in page_places:
                if place.place_id not in seen_ids:
                    seen_ids.add(place.place_id)
                    places.append(place)
                    new_added += 1
                    if limit and limit > 0 and len(places) >= limit:
                        break

            if new_added == 0:
                consecutive_stagnant += 1
                if consecutive_stagnant >= 2:
                    break
            else:
                consecutive_stagnant = 0

            if limit and limit > 0 and len(places) >= limit:
                break

            start += page_size

        # 2. Dynamic Geospatial Sub-Viewport Grid Expansion
        # Automatically expands if grid=True OR limit is None (unlimited) OR requested limit exceeds primary crawl count
        should_grid_expand = (grid or limit is None or (limit and len(places) < limit)) and detected_bounds and decoded_pb
        if should_grid_expand and detected_bounds:
            center_lat, center_lng, span_m = detected_bounds
            effective_grid_size = grid_size if grid_size is not None else min(
                math.ceil(span_m / target_tile_meters),
                max_grid_size,
            )
            effective_span = min(span_m, 80000.0) if span_m > 80000.0 else span_m
            tile_span_km = (effective_span / effective_grid_size) / 1000.0 if effective_grid_size > 0 else 0.0
            logger.info(
                "[%s] span=%.1fkm target=%.1fkm grid=%dx%d tiles=%d tile_span=%.1fkm",
                query,
                span_m / 1000,
                target_tile_meters / 1000,
                effective_grid_size,
                effective_grid_size,
                effective_grid_size * effective_grid_size,
                tile_span_km,
            )
            if effective_grid_size > 1:
                base_term, _ = _extract_search_term(query)
                grid_tiles = _generate_geo_grid(center_lat, center_lng, effective_span, grid_size=effective_grid_size)
                logger.info(
                    "[%s] Auto-detected bounding box center=(%.4f, %.4f), span=%.0fm. Crawling %d sub-viewport grid tiles...",
                    query,
                    center_lat,
                    center_lng,
                    span_m,
                    len(grid_tiles),
                )
                sem = asyncio.Semaphore(concurrency)

                async def _scrape_tile(tile_idx: int, lat: float, lng: float, cell_span: float) -> List[Place]:
                    tile_places: List[Place] = []
                    async with sem:
                        logger.warning(
                            "[%s] TILE %d START lat=%.6f lng=%.6f span=%.1fm",
                            query,
                            tile_idx,
                            lat,
                            lng,
                            cell_span,
                        )
                        # Crawl up to 5 pages per sub-viewport tile
                        for p_idx in range(5):
                            t_start = p_idx * 20
                            tile_url = _build_viewport_tile_url(
                                base_search_url=search_url,
                                base_decoded_pb=decoded_pb,
                                term=base_term,
                                lat=lat,
                                lng=lng,
                                span_meters=cell_span,
                                start=t_start,
                                page_idx=p_idx + 1,
                            )
                            tp, _ = await _fetch_results_page(
                                session, tile_url, base_term, start=t_start, country=country, timeout=timeout
                            )
                            if not tp:
                                break
                            tile_places.extend(tp)
                            if len(tp) < 20:
                                break
                        logger.warning(
                            "[%s] TILE %d DONE: %d places",
                            query,
                            tile_idx,
                            len(tile_places),
                        )
                    return tile_places

                tile_tasks = [_scrape_tile(idx, lat, lng, cell_span) for idx, (lat, lng, cell_span) in enumerate(grid_tiles)]
                tile_results = await asyncio.gather(*tile_tasks)

                for batch in tile_results:
                    for p in batch:
                        if p.place_id not in seen_ids:
                            seen_ids.add(p.place_id)
                            places.append(p)
                            if limit and limit > 0 and len(places) >= limit:
                                break
                    if limit and limit > 0 and len(places) >= limit:
                        break

    logger.info("[%s] Search finished. Found %d unique place(s).", query, len(places))
    return places[:limit] if limit and limit > 0 else places



async def get_place_details_async(
    query_or_id: str,
    lang: str = "en",
    country: str = "in",
    timeout: int = 20,
) -> Optional[Place]:
    """Retrieve place details by place ID or exact place name.

    Handles:
    - Raw Google Place IDs (e.g. 'ChIJRTQj...')
    - Prefixed Google Place IDs (e.g. 'place_id:ChIJRTQj...')
    - Place/business names (e.g. 'Marina Beach Chennai')
    """
    clean_id = query_or_id.replace("place_id:", "").strip()
    is_place_id = clean_id.startswith("ChIJ")

    connector = aiohttp.TCPConnector(ssl=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        # 1. Direct Place ID resolution via Google Maps Preview API
        if is_place_id:
            hex_pair = _place_id_to_cid_hex(clean_id)
            if hex_pair:
                fid_hex, cid_hex = hex_pair
                preview_url = (
                    f"https://www.google.com/maps/preview/place?authuser=0&hl={lang}&gl={country}"
                    f"&pb=%211m14%211s{fid_hex}%3A{cid_hex}%213m12%211m3%211d31107.0%212d80.0%213d13.0"
                    f"%212m3%211f0.0%212f0.0%213f0.0%213m2%211i1024%212i768%214f13.1%217e81"
                )
                try:
                    async with session.get(
                        preview_url,
                        headers=DEFAULT_HEADERS,
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as resp:
                        if resp.status == 200:
                            raw = await resp.text()
                            if raw.startswith(")]}'"):
                                raw = raw[4:].strip()
                            data = json.loads(raw)
                            places = _extract_all_places_from_data(data, clean_id, country=country)
                            if places:
                                return places[0]
                except Exception as e:
                    logger.debug("Preview API resolution failed for %s: %s", clean_id, e)

        # 2. Text Search / Fallback search
        search_queries = [query_or_id] if not is_place_id else [clean_id, f"place_id:{clean_id}"]
        for sq in search_queries:
            results = await search_google_maps_async(
                query=sq,
                lang=lang,
                country=country,
                limit=1,
                timeout=timeout,
            )
            if results:
                return results[0]

    return None
