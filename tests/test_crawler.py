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
