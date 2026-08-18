"""Unit tests for MCP server tool registration and execution."""

import pytest
from gmaps_mcp.server import server
from gmaps_mcp.schemas import Place


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
    assert "query" in properties
    assert "limit" in properties
    assert "country" in properties
    assert "language" in properties


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

    async def mock_search_places(query, lang, country, limit):
        recorded_kwargs["query"] = query
        recorded_kwargs["lang"] = lang
        recorded_kwargs["country"] = country
        recorded_kwargs["limit"] = limit
        return [sample_place]

    monkeypatch.setattr("gmaps_mcp.tools.search_google_maps_async", mock_search_places)

    result = await server.call_tool(
        "search_google_maps",
        {"query": "coffee in Bangalore", "limit": 5, "country": "in"}
    )

    assert not result.is_error
    assert result.structured_content is not None
    assert result.structured_content["total_results"] == 1
    assert result.structured_content["places"][0]["name"] == "Test Brew"
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

    async def mock_search_places(query, lang, country, limit):
        recorded_kwargs["query"] = query
        recorded_kwargs["lang"] = lang
        recorded_kwargs["country"] = country
        recorded_kwargs["limit"] = limit
        return [sample_place]

    monkeypatch.setattr("gmaps_mcp.tools.search_google_maps_async", mock_search_places)

    # Calling without specifying limit
    result = await server.call_tool(
        "search_google_maps",
        {"query": "coffee in Bangalore", "country": "in"}
    )

    assert not result.is_error
    assert result.structured_content is not None
    assert result.structured_content["total_results"] == 1
    assert result.structured_content["places"][0]["name"] == "All Results Cafe"
    assert recorded_kwargs["limit"] is None


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
