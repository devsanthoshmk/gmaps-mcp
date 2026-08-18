"""Unit tests for MCP server tool registration, resource handling, and execution."""

import json
import pytest
from mcp.server.mcpserver.exceptions import ResourceNotFoundError, ResourceError
from gmaps_mcp.server import server
from gmaps_mcp.schemas import Place, SearchGoogleMapsResult
from gmaps_mcp.storage import ResultStore, result_store


@pytest.mark.asyncio
async def test_server_tool_registration():
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]

    assert "search_google_maps" in tool_names
    assert "get_place_details" in tool_names

    # Check search_google_maps tool schema
    search_tool = next(t for t in tools if t.name == "search_google_maps")
    assert search_tool.description is not None
    assert "Search Google Maps" in search_tool.description
    properties = search_tool.input_schema.get("properties", {})
    assert "term" in properties
    assert "location" in properties
    assert "limit" in properties
    assert "country" in properties
    assert "language" in properties
    assert "result_delivery" in properties
    required = search_tool.input_schema.get("required", [])
    assert "term" in required
    assert "location" in required


@pytest.mark.asyncio
async def test_server_resource_template_registration():
    templates = await server.list_resource_templates()
    template_uris = [t.uri_template for t in templates]

    assert "gmaps://results/{resource_id}" in template_uris


@pytest.mark.asyncio
async def test_server_call_search_tool_with_limit(monkeypatch):
    sample_place = Place(
        place_id="ChIJ_TEST",
        name="Test Brew",
        category="Cafe",
        address="123 Road, City",
        phone="1234567890",
        rating=4.5,
        review_count=100,
    )

    recorded_kwargs = {}

    async def mock_search_places(term=None, location=None, lang="en", country="in", limit=None, **kwargs):
        recorded_kwargs["term"] = term
        recorded_kwargs["location"] = location
        recorded_kwargs["lang"] = lang
        recorded_kwargs["country"] = country
        recorded_kwargs["limit"] = limit
        return [sample_place]

    monkeypatch.setattr("gmaps_mcp.tools.search_google_maps_async", mock_search_places)

    result = await server.call_tool(
        "search_google_maps",
        {"term": "coffee", "location": "Bangalore", "limit": 5, "country": "in", "result_delivery": "inline"}
    )

    assert not result.is_error
    assert result.structured_content is not None
    assert result.structured_content["total_results"] == 1
    assert result.structured_content["delivery_mode"] == "inline"
    assert result.structured_content["places"][0]["name"] == "Test Brew"
    assert recorded_kwargs["term"] == "coffee"
    assert recorded_kwargs["location"] == "Bangalore"
    assert recorded_kwargs["limit"] == 5


@pytest.mark.asyncio
async def test_server_call_search_tool_without_limit(monkeypatch):
    sample_place = Place(
        place_id="ChIJ_TEST_2",
        name="All Results Cafe",
        category="Cafe",
        address="456 Road, City",
        phone="9876543210",
        rating=4.8,
        review_count=200,
    )

    recorded_kwargs = {}

    async def mock_search_places(term=None, location=None, lang="en", country="in", limit=None, **kwargs):
        recorded_kwargs["term"] = term
        recorded_kwargs["location"] = location
        recorded_kwargs["lang"] = lang
        recorded_kwargs["country"] = country
        recorded_kwargs["limit"] = limit
        return [sample_place]

    monkeypatch.setattr("gmaps_mcp.tools.search_google_maps_async", mock_search_places)

    # Calling without specifying limit
    result = await server.call_tool(
        "search_google_maps",
        {"term": "coffee", "location": "Bangalore", "country": "in"}
    )

    assert not result.is_error
    assert result.structured_content is not None
    assert result.structured_content["total_results"] == 1
    assert result.structured_content["delivery_mode"] == "inline"
    assert result.structured_content["places"][0]["name"] == "All Results Cafe"
    assert recorded_kwargs["limit"] is None


@pytest.mark.asyncio
async def test_server_call_search_tool_with_resource_delivery(monkeypatch):
    sample_places = [
        Place(
            place_id=f"ChIJ_TEST_{i}",
            name=f"Place {i}",
            category="Restaurant",
            address=f"{i} Street",
            phone="1234567890",
            rating=4.5,
            review_count=50,
        )
        for i in range(10)
    ]

    async def mock_search_places(term=None, location=None, lang="en", country="in", limit=None, **kwargs):
        return sample_places

    monkeypatch.setattr("gmaps_mcp.tools.search_google_maps_async", mock_search_places)

    # Execute search with result_delivery="resource"
    result = await server.call_tool(
        "search_google_maps",
        {"term": "restaurants", "location": "Mumbai", "result_delivery": "resource"}
    )

    assert not result.is_error
    structured = result.structured_content
    assert structured is not None
    assert structured["delivery_mode"] == "resource"
    assert structured["total_results"] == 10
    assert structured["places"] == []  # Should be empty to prevent context bloat
    assert structured["resource_link"] is not None
    assert structured["resource_link"].startswith("gmaps://results/")
    assert structured["resource_id"] is not None

    resource_link = structured["resource_link"]
    resource_id = structured["resource_id"]

    # Now read the stored resource via the MCP Resource API
    resource_contents = await server.read_resource(resource_link)
    assert len(resource_contents) == 1
    first_content = list(resource_contents)[0]
    assert first_content.mime_type == "application/json"

    # Verify that the content parses to valid JSON with all 10 places
    data = json.loads(first_content.content)
    assert data["query"] == "restaurants in Mumbai"
    assert data["total_results"] == 10
    assert len(data["places"]) == 10
    assert data["places"][0]["name"] == "Place 0"
    assert data["places"][9]["name"] == "Place 9"

    # Verify that list_resources now includes this stored resource!
    resources_list = await server.list_resources()
    resource_uris = [str(r.uri) for r in resources_list]
    assert resource_link in resource_uris


@pytest.mark.asyncio
async def test_server_read_nonexistent_resource():
    with pytest.raises((ResourceNotFoundError, ResourceError, ValueError)):
        await server.read_resource("gmaps://results/non_existent_id_12345")


@pytest.mark.asyncio
async def test_server_call_get_place_details(monkeypatch):
    sample_place = Place(
        place_id="ChIJ_DETAILS",
        name="Taj Mahal Palace",
        address="Apollo Bandar, Colaba, Mumbai",
        rating=4.8,
        review_count=35000,
    )

    async def mock_get_place(*args, **kwargs):
        return sample_place

    monkeypatch.setattr("gmaps_mcp.tools.get_place_details_async", mock_get_place)

    result = await server.call_tool(
        "get_place_details",
        {"place": "Taj Mahal Palace Mumbai", "country": "in"}
    )

    assert not result.is_error
    assert result.structured_content is not None
    assert result.structured_content["found"] is True
    assert result.structured_content["place"]["name"] == "Taj Mahal Palace"


def test_result_store_operations():
    store = ResultStore(max_capacity=3, default_ttl_seconds=3600.0)

    res1 = SearchGoogleMapsResult(
        query="q1", country="in", language="en", total_results=1, places=[]
    )
    res2 = SearchGoogleMapsResult(
        query="q2", country="in", language="en", total_results=2, places=[]
    )
    res3 = SearchGoogleMapsResult(
        query="q3", country="in", language="en", total_results=3, places=[]
    )
    res4 = SearchGoogleMapsResult(
        query="q4", country="in", language="en", total_results=4, places=[]
    )

    id1 = store.store(res1, resource_id="id1")
    id2 = store.store(res2, resource_id="id2")
    id3 = store.store(res3, resource_id="id3")

    assert store.exists("id1")
    assert store.get("id1").query == "q1"

    # Adding a 4th entry exceeds max_capacity 3 -> oldest (id2 since id1 was just accessed) gets evicted or id1 if unaccessed
    store.store(res4, resource_id="id4")
    assert store.exists("id4")
    assert store.exists("id1")  # was accessed via get so it moved to end
    assert not store.exists("id2")  # was evicted as oldest

    # Delete
    assert store.delete("id4") is True
    assert store.exists("id4") is False

    # Clear
    store.clear()
    assert store.exists("id1") is False


def test_result_store_expiration():
    store = ResultStore(max_capacity=10, default_ttl_seconds=0.01)
    res = SearchGoogleMapsResult(
        query="test", country="in", language="en", total_results=0, places=[]
    )
    rid = store.store(res, ttl_seconds=-1.0)  # already expired
    assert store.get(rid) is None
    assert store.exists(rid) is False
