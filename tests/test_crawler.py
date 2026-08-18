"""Unit tests for crawler extraction and parsing logic."""

from gmaps_mcp.scraper.crawler import (
    _safe_get,
    _extract_place_from_raw,
    _extract_single_place_fallback,
)


def test_safe_get():
    data = {"a": [10, {"b": [100, 200, 300]}]}

    assert _safe_get(data, "a", 1, "b", 2) == 300
    assert _safe_get(data, "a", 1, "b", 5, default="missing") == "missing"
    assert _safe_get(data, "nonexistent", default=None) is None
    assert _safe_get(None, 0, default="def") == "def"


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

    place = _extract_place_from_raw(raw_item, "coffee in Bangalore")

    assert place is not None
    assert place.place_id == "ChIJBR3G8LJqkFQRWD2Wzn0qG3c"
    assert place.name == "Dyu Art Cafe"
    assert place.category == "Coffee shop"
    assert place.address == "Koramangala, Bangalore, Karnataka 560095"
    assert place.rating == 4.6
    assert place.review_count == 3985
    assert place.latitude == 12.9373
    assert place.longitude == 77.6176
    assert place.phone == "096113 19774"
    assert place.international_phone == "+91 96113 19774"
    assert place.website == "https://example.com/cafe"
    assert place.domain == "example.com"
    assert "place_id:ChIJBR3G8LJqkFQRWD2Wzn0qG3c" in place.google_maps_url


def test_extract_place_missing_place_id():
    raw_item = [None] * 200
    raw_item[11] = "Missing ID Cafe"
    # raw_item[78] is None

    place = _extract_place_from_raw(raw_item, "test")
    assert place is None


def test_extract_single_place_fallback():
    raw_item = [None] * 200
    raw_item[11] = "AIIMS New Delhi"
    raw_item[78] = "ChIJ12k5kG_iDDkRwuzibQwYZ4M"
    raw_item[39] = "Ansari Nagar East, New Delhi, Delhi 110029"

    # Simulate nested response structure data[0][1][0][14]
    mock_data = [[None, [[None] * 14 + [raw_item]]]]

    place = _extract_single_place_fallback(mock_data, "AIIMS New Delhi")
    assert place is not None
    assert place.name == "AIIMS New Delhi"
    assert place.place_id == "ChIJ12k5kG_iDDkRwuzibQwYZ4M"
    assert place.address == "Ansari Nagar East, New Delhi, Delhi 110029"
