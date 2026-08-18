"""Unit tests for crawler extraction and parsing logic."""

import pytest
from gmaps_mcp.scraper.crawler import (
    _safe_get,
    _normalize_phone,
    _extract_place_from_raw,
    _extract_single_place_fallback,
    _extract_places_from_html,
    get_place_details_async,
)


def test_safe_get():
    data = {"a": [10, {"b": [100, 200, 300]}]}

    assert _safe_get(data, "a", 1, "b", 2) == 300
    assert _safe_get(data, "a", 1, "b", 5, default="missing") == "missing"
    assert _safe_get(data, "nonexistent", default=None) is None
    assert _safe_get(None, 0, default="def") == "def"


def test_normalize_phone():
    # India phone
    local, intl = _normalize_phone("089399 92112", "+91 89399 92112", country_code="IN")
    assert intl == "+91 89399 92112"

    # US phone
    local, intl = _normalize_phone("2067805777", None, country_code="US")
    assert local == "(206) 780-5777"
    assert intl == "+1 206-780-5777"

    # Invalid / empty phone
    local, intl = _normalize_phone(None, None, country_code="IN")
    assert local is None
    assert intl is None


def test_extract_place_from_raw():
    # Construct synthetic raw place array matching Google Maps internal structure
    raw_item = [None] * 200
    raw_item[11] = "Dyu Art Cafe"  # Title
    raw_item[78] = "ChIJBR3G8LJqkFQRWD2Wzn0qG3c"  # Place ID
    raw_item[13] = ["Coffee shop"]  # Category
    raw_item[39] = "Koramangala, Bangalore, Karnataka 560095"  # Address
    raw_item[4] = [None] * 8
    raw_item[4][7] = 4.6  # Stars
    raw_item[37] = [None, 3985]  # Review count
    raw_item[7] = ["https://example.com/cafe", "example.com"]  # URL and domain
    raw_item[9] = [None, None, 12.9373, 77.6176]  # Coordinates
    raw_item[178] = [["096113 19774", [["096113 19774", 1], ["+91 96113 19774", 2]], None, "+919611319774"]]  # Phone numbers

    place = _extract_place_from_raw(raw_item, "coffee in Bangalore", country="in")

    assert place is not None
    assert place.place_id == "ChIJBR3G8LJqkFQRWD2Wzn0qG3c"
    assert place.name == "Dyu Art Cafe"
    assert place.category == "Coffee shop"
    assert place.address == "Koramangala, Bangalore, Karnataka 560095"
    assert place.rating == 4.6
    assert place.review_count == 3985
    assert place.latitude == 12.9373
    assert place.longitude == 77.6176
    assert place.international_phone == "+91 96113 19774"
    assert place.website == "https://example.com/cafe"
    assert place.domain == "example.com"
    assert "place_id:ChIJBR3G8LJqkFQRWD2Wzn0qG3c" in place.google_maps_url


def test_extract_place_missing_place_id():
    raw_item = [None] * 200
    raw_item[11] = "Missing ID Cafe"
    # raw_item[78] is None

    place = _extract_place_from_raw(raw_item, "test", country="in")
    assert place is None


def test_extract_single_place_fallback():
    raw_item = [None] * 200
    raw_item[11] = "AIIMS New Delhi"
    raw_item[78] = "ChIJ12k5kG_iDDkRwuzibQwYZ4M"
    raw_item[39] = "Ansari Nagar East, New Delhi, Delhi 110029"

    # Simulate nested response structure data[0][1][0][14]
    mock_data = [[None, [[None] * 14 + [raw_item]]]]

    place = _extract_single_place_fallback(mock_data, "AIIMS New Delhi", country="in")
    assert place is not None
    assert place.name == "AIIMS New Delhi"
    assert place.place_id == "ChIJ12k5kG_iDDkRwuzibQwYZ4M"
    assert place.address == "Ansari Nagar East, New Delhi, Delhi 110029"


def test_extract_places_from_html():
    import json
    raw_item = [None] * 200
    raw_item[11] = "Marina Beach"
    raw_item[78] = "ChIJRTQj_11nUjoRzYQ6wX2sUvY"
    raw_item[39] = "Marina Beach, Chennai, Tamil Nadu 600005"
    raw_item[13] = ["Beach"]

    mock_state = [[[None, [[None] * 14 + [raw_item]]]]]
    json_str = json.dumps(mock_state)

    mock_html = (
        '<html><head><script nonce="test">'
        f'window.APP_INITIALIZATION_STATE={json_str};'
        'window.APP_FLAGS=[1,2,3];</script></head><body></body></html>'
    )

    places = _extract_places_from_html(mock_html, "Marina Beach", country="in")
    assert len(places) == 1
    assert places[0].name == "Marina Beach"
    assert places[0].place_id == "ChIJRTQj_11nUjoRzYQ6wX2sUvY"


@pytest.mark.asyncio
async def test_get_place_details_async_place_id(monkeypatch):
    sample_place = _extract_place_from_raw(
        [None] * 11 + ["Marina Beach", None, ["Beach"]] + [None] * 64 + ["ChIJRTQj_11nUjoRzYQ6wX2sUvY"],
        "Marina Beach",
        country="in",
    )

    async def mock_search_maps(query, **kwargs):
        if "ChIJRTQj_11nUjoRzYQ6wX2sUvY" in query:
            return [sample_place]
        return []

    monkeypatch.setattr("gmaps_mcp.scraper.crawler.search_google_maps_async", mock_search_maps)

    # 1. Test with raw ChIJ ID
    res1 = await get_place_details_async("ChIJRTQj_11nUjoRzYQ6wX2sUvY")
    assert res1 is not None
    assert res1.name == "Marina Beach"

    # 2. Test with place_id: prefix
    res2 = await get_place_details_async("place_id:ChIJRTQj_11nUjoRzYQ6wX2sUvY")
    assert res2 is not None
    assert res2.name == "Marina Beach"


def test_extract_search_term():
    from gmaps_mcp.scraper.crawler import _extract_search_term

    term, loc = _extract_search_term("gift shop in chennai")
    assert term == "gift shop"
    assert loc == "chennai"

    term, loc = _extract_search_term("dentists in chicago")
    assert term == "dentists"
    assert loc == "chicago"

    term, loc = _extract_search_term("coffee near eiffel tower")
    assert term == "coffee"
    assert loc == "eiffel tower"

    term, loc = _extract_search_term("pharmacies at t nagar")
    assert term == "pharmacies"
    assert loc == "t nagar"

    term, loc = _extract_search_term("supermarket")
    assert term == "supermarket"
    assert loc is None


def test_generate_geo_grid():
    from gmaps_mcp.scraper.crawler import _generate_geo_grid
    import math

    center_lat = 13.0827
    center_lng = 80.2707
    span = 40000.0
    grid_size = 4

    grid = _generate_geo_grid(center_lat, center_lng, span, grid_size=grid_size)
    assert len(grid) == 16
    for lat, lng, cell_span in grid:
        assert isinstance(lat, float)
        assert isinstance(lng, float)
        assert cell_span == 10000.0

    # Verify gapless symmetric coverage
    lat_deg_span = span / 111000.0
    lng_deg_span = span / (111000.0 * math.cos(math.radians(center_lat)))
    cell_lat_deg = lat_deg_span / grid_size
    cell_lng_deg = lng_deg_span / grid_size

    lats = sorted(list(set(round(g[0], 6) for g in grid)))
    lngs = sorted(list(set(round(g[1], 6) for g in grid)))
    assert len(lats) == 4
    assert len(lngs) == 4

    # Distance between adjacent tile centers should exactly equal cell degree span
    for i in range(len(lats) - 1):
        assert math.isclose(lats[i + 1] - lats[i], cell_lat_deg, rel_tol=1e-5)
    for i in range(len(lngs) - 1):
        assert math.isclose(lngs[i + 1] - lngs[i], cell_lng_deg, rel_tol=1e-5)

    # Edge bounds: min_lat - cell/2 to max_lat + cell/2 should equal full lat_deg_span
    min_lat_bound = lats[0] - cell_lat_deg / 2.0
    max_lat_bound = lats[-1] + cell_lat_deg / 2.0
    assert math.isclose(max_lat_bound - min_lat_bound, lat_deg_span, rel_tol=1e-5)


def test_coverage_first_grid_size_calculation():
    import math

    target_tile_meters = 5000.0
    max_grid_size = 10

    test_cases = [
        (3000.0, 1),    # 3 km  -> ceil(3/5) = 1 (no expansion)
        (5000.0, 1),    # 5 km  -> ceil(5/5) = 1 (no expansion)
        (6000.0, 2),    # 6 km  -> ceil(6/5) = 2 (2x2 = 4 tiles)
        (10000.0, 2),   # 10 km -> ceil(10/5) = 2 (2x2 = 4 tiles)
        (20000.0, 4),   # 20 km -> ceil(20/5) = 4 (4x4 = 16 tiles)
        (40000.0, 8),   # 40 km -> ceil(40/5) = 8 (8x8 = 64 tiles)
        (80000.0, 10),  # 80 km -> ceil(80/5) = 16 -> clamped to 10 (10x10 = 100 tiles)
    ]

    for span_m, expected_grid_size in test_cases:
        calculated = min(math.ceil(span_m / target_tile_meters), max_grid_size)
        assert calculated == expected_grid_size


def test_build_viewport_tile_url():
    from gmaps_mcp.scraper.crawler import _build_viewport_tile_url
    from urllib.parse import unquote

    base_url = "https://www.google.com/search?tbm=map&q=gift+shop+in+chennai&pb=%211sgift+shop+in+chennai%217i20%2110b1"
    base_pb = "!1sgift+shop+in+chennai!7i20!10b1"

    tile_url = _build_viewport_tile_url(
        base_search_url=base_url,
        base_decoded_pb=base_pb,
        term="gift shop",
        lat=13.085,
        lng=80.210,
        span_meters=15000.0,
        start=20,
        page_idx=2,
    )

    assert "q=gift%20shop" in tile_url or "q=gift+shop" in tile_url
    assert "start=20" in tile_url
    assert "ech=2" in tile_url
    assert "!3d13.085" in unquote(tile_url)
    assert "!2d80.21" in unquote(tile_url)


@pytest.mark.asyncio
async def test_search_google_maps_async_adaptive_grid_small_area(monkeypatch):
    from gmaps_mcp.scraper.crawler import search_google_maps_async, Place

    # Mock _get_search_url to return a valid search URL and bounds (span = 4000m <= 5000m target)
    async def mock_get_search_url(session, query, lang, country, timeout=20):
        return "https://www.google.com/search?tbm=map&pb=!1stest", [], (13.0827, 80.2707, 4000.0)

    fetched_urls = []

    async def mock_fetch_results_page(session, search_url, query, start=0, country="in", timeout=20):
        fetched_urls.append(search_url)
        # return 1 place on initial page, then None
        if start == 0:
            return [
                Place(place_id="p1", name="Place 1", category="Shop", address="Address 1")
            ], (13.0827, 80.2707, 4000.0)
        return [], None

    monkeypatch.setattr("gmaps_mcp.scraper.crawler._get_search_url", mock_get_search_url)
    monkeypatch.setattr("gmaps_mcp.scraper.crawler._fetch_results_page", mock_fetch_results_page)

    places = await search_google_maps_async("gift shop in small area", grid=True, target_tile_meters=5000.0)
    assert len(places) == 1
    # For a 4km area with 5km target tile, grid_size = ceil(4/5) = 1 <= 1, so no sub-viewport tile searches should be triggered
    # Only pagination on base url
    assert not any("!4m8" in u for u in fetched_urls)


@pytest.mark.asyncio
async def test_search_google_maps_async_adaptive_grid_large_area(monkeypatch):
    from urllib.parse import unquote
    from gmaps_mcp.scraper.crawler import search_google_maps_async, Place

    # Mock _get_search_url with span = 10000m (> 5000m target -> 2x2 = 4 tiles)
    async def mock_get_search_url(session, query, lang, country, timeout=20):
        return "https://www.google.com/search?tbm=map&pb=!1stest", [], (13.0827, 80.2707, 10000.0)

    fetched_urls = []

    async def mock_fetch_results_page(session, search_url, query, start=0, country="in", timeout=20):
        fetched_urls.append(search_url)
        if "!4m8" in unquote(search_url):
            # Sub-viewport tile
            tile_id = f"place_from_tile_{len(fetched_urls)}"
            return [Place(place_id=tile_id, name=f"Name {tile_id}", category="Shop", address="Addr")], None
        if start == 0:
            return [Place(place_id="p_initial", name="Initial Place", category="Shop", address="Addr")], (13.0827, 80.2707, 10000.0)
        return [], None

    monkeypatch.setattr("gmaps_mcp.scraper.crawler._get_search_url", mock_get_search_url)
    monkeypatch.setattr("gmaps_mcp.scraper.crawler._fetch_results_page", mock_fetch_results_page)

    places = await search_google_maps_async("gift shop in big city", grid=True, target_tile_meters=5000.0)
    # ceil(10000 / 5000) = 2 -> 2x2 = 4 tiles
    tile_urls = [u for u in fetched_urls if "!4m8" in unquote(u)]
    assert len(tile_urls) == 4
    # Check that places from initial search and all 4 tiles were collected
    assert len(places) == 5



