"""Unit tests for gmaps_mcp schemas."""

from gmaps_mcp.schemas import Place, SearchGoogleMapsResult, GetPlaceDetailsResult


def test_place_schema_valid():
    place = Place(
        place_id="ChIJ12345",
        name="Art Cafe",
        category="Coffee shop",
        address="123 Main St, Bangalore, India",
        phone="080 1234 5678",
        international_phone="+91 80 1234 5678",
        website="https://artcafe.example.com",
        domain="artcafe.example.com",
        latitude=12.9716,
        longitude=77.5946,
        rating=4.7,
        review_count=1200,
        google_maps_url="https://www.google.com/maps/place/?q=place_id:ChIJ12345",
    )

    assert place.place_id == "ChIJ12345"
    assert place.name == "Art Cafe"
    assert place.rating == 4.7
    assert place.latitude == 12.9716
    assert place.longitude == 77.5946


def test_place_schema_optional_fields():
    place = Place(
        place_id="ChIJ99999",
        name="Simple Shop",
    )

    assert place.place_id == "ChIJ99999"
    assert place.name == "Simple Shop"
    assert place.category is None
    assert place.phone is None
    assert place.rating is None
    assert place.review_count is None


def test_search_result_schema():
    place = Place(place_id="ChIJ1", name="Cafe 1")
    result = SearchGoogleMapsResult(
        query="cafe in bangalore",
        country="in",
        language="en",
        total_results=1,
        places=[place],
    )

    assert result.total_results == 1
    assert len(result.places) == 1
    assert result.places[0].name == "Cafe 1"


def test_get_place_details_result_schema():
    place = Place(place_id="ChIJ1", name="Cafe 1")
    result = GetPlaceDetailsResult(
        place=place,
        found=True,
        query_or_id="ChIJ1",
    )

    assert result.found is True
    assert result.place is not None
    assert result.place.place_id == "ChIJ1"
