"""MCP Tools definitions and handlers for Google Maps.

Provides rich, descriptive tool schemas and execution handlers optimized
for AI agents and LLM tool calling.
"""

import logging
from typing import Annotated, Optional

from pydantic import Field

from gmaps_mcp.schemas import (
    GetPlaceDetailsResult,
    Place,
    SearchGoogleMapsResult,
)
from gmaps_mcp.scraper import (
    get_place_details_async,
    search_google_maps_async,
)

logger = logging.getLogger("gmaps_mcp.tools")


async def search_google_maps(
    query: Annotated[
        str,
        Field(
            description=(
                "The search query for Google Maps. Can be a business category, specific place name, "
                "service, or landmark along with a location. Examples: "
                "'coffee shops in Koramangala Bangalore', "
                "'dentists near Connaught Place Delhi', "
                "'Italian restaurants in Bandra Mumbai', "
                "'hospitals in Hyderabad', "
                "'electricians near Indiranagar', "
                "'museums in London'."
            )
        ),
    ],
    limit: Annotated[
        int,
        Field(
            default=10,
            ge=1,
            le=50,
            description="Maximum number of place results to return (between 1 and 50, default is 10).",
        ),
    ] = 10,
    country: Annotated[
        str,
        Field(
            default="in",
            description=(
                "Two-letter ISO 3166-1 alpha-2 country code to localize search results and map boundaries. "
                "Default is 'in' (India). Other examples: 'us' (United States), 'gb' or 'uk' (United Kingdom), "
                "'ca' (Canada), 'au' (Australia), 'de' (Germany), 'fr' (France), 'sg' (Singapore), 'ae' (UAE)."
            ),
        ),
    ] = "in",
    language: Annotated[
        str,
        Field(
            default="en",
            description=(
                "Language code for the results (e.g. 'en' for English, 'hi' for Hindi, 'es' for Spanish, "
                "'fr' for French, 'de' for German, 'ja' for Japanese). Default is 'en'."
            ),
        ),
    ] = "en",
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
        "Tool call search_google_maps: query=%r, limit=%d, country=%r, language=%r",
        query,
        limit,
        country,
        language,
    )

    places = await search_google_maps_async(
        query=query,
        lang=language,
        country=country,
        limit=limit,
    )

    return SearchGoogleMapsResult(
        query=query,
        country=country,
        language=language,
        total_results=len(places),
        places=places,
    )


async def get_place_details(
    place: Annotated[
        str,
        Field(
            description=(
                "The place identifier to fetch details for. Can be either:\n"
                "1. A Google Place ID (e.g., 'ChIJ12k5kG_iDDkRwuzibQwYZ4M' or 'place_id:ChIJ...')\n"
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
    """Retrieve detailed information for a single specific Google Maps place or business.

    Looks up a place using its unique Google Place ID (ChIJ...) or specific landmark/business name.
    Returns complete structured details including address, phone number, website, rating,
    coordinates, and Google Maps URL.
    """
    logger.info(
        "Tool call get_place_details: place=%r, country=%r, language=%r",
        place,
        country,
        language,
    )

    result_place = await get_place_details_async(
        query_or_id=place,
        lang=language,
        country=country,
    )

    return GetPlaceDetailsResult(
        place=result_place,
        found=result_place is not None,
        query_or_id=place,
    )
