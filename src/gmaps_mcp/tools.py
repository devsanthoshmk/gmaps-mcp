"""Google Maps MCP Tool implementations.

Provides the core async tool handlers invoked by the FastMCP server.
All business logic is isolated here for clean separation of concerns and testability.
"""

import logging
from typing import Annotated, Optional

from pydantic import Field

from gmaps_mcp.schemas import (
    GetPlaceDetailsResult,
    ResultDelivery,
    SearchGoogleMapsResult,
)
from gmaps_mcp.scraper import get_place_details_async, search_google_maps_async
from gmaps_mcp.storage import result_store

logger = logging.getLogger("gmaps_mcp.tools")


async def search_google_maps(
    query: Annotated[
        str,
        Field(
            description=(
                "Search query for places, businesses, or points of interest.\n"
                "Examples: 'dentists in Chicago', 'restaurants in Tokyo', 'hospitals near me',\n"
                "'pharmacies in Chennai', 'hotels in Paris', 'coffee shops in Brooklyn'."
            )
        ),
    ],
    limit: Annotated[
        Optional[int],
        Field(
            default=None,
            description=(
                "Maximum number of place results to return. If omitted or null, returns as many results as possible "
                "from Google Maps without artificial limits."
            ),
        ),
    ] = None,
    grid: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "When True, enables dynamic geospatial viewport grid tiling across the auto-detected city/region bounding box, "
                "yielding massive multi-zone coverage worldwide."
            ),
        ),
    ] = False,
    country: Annotated[
        str,
        Field(
            default="in",
            description=(
                "Two-letter ISO 3166-1 alpha-2 country code for region localization (e.g., 'us', 'in', 'uk', 'fr', 'de').\n"
                "Used to bias search results geographically."
            ),
        ),
    ] = "in",
    language: Annotated[
        str,
        Field(
            default="en",
            description=(
                "Language code for the response (e.g., 'en' for English, 'hi' for Hindi, 'fr' for French, 'ja' for Japanese).\n"
                "Controls the language of place names, categories, and addresses."
            ),
        ),
    ] = "en",
    result_delivery: Annotated[
        ResultDelivery,
        Field(
            default="inline",
            description=(
                "How the search results should be returned:\n"
                "- 'inline': Returns the full list of Place objects directly in the tool response.\n"
                "- 'resource': Stores the complete results server-side and returns only an MCP resource link "
                "(e.g. 'gmaps://results/{resource_id}'), preventing LLM context window bloat for large result sets."
            ),
        ),
    ] = "inline",
) -> SearchGoogleMapsResult:
    """Search Google Maps for local businesses, places, points of interest, and services.

    Returns structured place data including business name, Google Place ID, category,
    formatted street address, local and international phone numbers, official website URL,
    exact geographic coordinates (latitude and longitude), star rating, total review count,
    and a direct Google Maps URL.

    Use this tool whenever the user needs:
    - Recommendations for places (restaurants, cafes, hotels, shops, tourist spots)
    - Contact details for local services (plumbers, clinics, lawyers, mechanics)
    - Geo-coordinates (lat/long) or addresses of locations
    - Ratings and review volume comparisons for businesses in any city or area.
    """
    logger.info(
        "Tool call search_google_maps: query=%r, limit=%r, grid=%r, country=%r, language=%r, result_delivery=%r",
        query,
        limit,
        grid,
        country,
        language,
        result_delivery,
    )

    places = await search_google_maps_async(
        query=query,
        lang=language,
        country=country,
        limit=limit,
        grid=grid,
    )

    if result_delivery == "resource":
        full_result = SearchGoogleMapsResult(
            query=query,
            country=country,
            language=language,
            total_results=len(places),
            delivery_mode="inline",
            places=places,
        )
        resource_id = result_store.store(full_result)
        resource_link = f"gmaps://results/{resource_id}"
        sample_preview = [
            f"{i + 1}. {p.name} ({p.category or 'Place'}) - Rating: {p.rating or 'N/A'}"
            for i, p in enumerate(places[:3])
        ]

        return SearchGoogleMapsResult(
            query=query,
            country=country,
            language=language,
            total_results=len(places),
            delivery_mode="resource",
            resource_link=resource_link,
            resource_id=resource_id,
            summary=(
                f"Successfully retrieved {len(places)} places. Results are stored in MCP resource '{resource_link}' "
                f"to conserve context. Retrieve full place data using the MCP Resource API."
            ),
            sample_places=sample_preview,
            places=[],
        )

    return SearchGoogleMapsResult(
        query=query,
        country=country,
        language=language,
        total_results=len(places),
        delivery_mode="inline",
        places=places,
    )


async def get_place_details(
    place: Annotated[
        str,
        Field(
            description=(
                "The place identifier to fetch details for. Can be either:\n"
                "1. A Google Place ID (e.g., 'ChIJ12k5kG_iDDkRwuzibQwYZ4M' or 'place_id:ChIJ12k5kG_iDDkRwuzibQwYZ4M')\n"
                "2. An exact place / business name and location (e.g., 'AIIMS New Delhi' or 'Taj Mahal Palace Mumbai')."
            )
        ),
    ],
    country: Annotated[
        str,
        Field(
            default="in",
            description="Two-letter ISO country code for region localization (default: 'in').",
        ),
    ] = "in",
    language: Annotated[
        str,
        Field(
            default="en",
            description="Language code for the response (default: 'en').",
        ),
    ] = "en",
) -> GetPlaceDetailsResult:
    """Retrieve detailed information about a specific Google Maps place or business.

    Accepts either a Google Place ID or an exact place name.
    Returns complete structured place data including name, address, phone number,
    website, coordinates, star rating, and review count.
    """
    logger.info(
        "Tool call get_place_details: place=%r, country=%r, language=%r",
        place,
        country,
        language,
    )

    result = await get_place_details_async(
        query_or_id=place,
        lang=language,
        country=country,
    )

    if result is None:
        logger.warning("Place not found for query_or_id=%r", place)
        return GetPlaceDetailsResult(
            place=None,
            found=False,
            query_or_id=place,
        )

    return GetPlaceDetailsResult(
        place=result,
        found=True,
        query_or_id=place,
    )
