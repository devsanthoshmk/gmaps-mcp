"""Google Maps MCP Server entry point and CLI runner.

Uses the official MCP Python SDK (MCPServer) with stdio and Streamable HTTP support.
"""

import argparse
import logging
import sys
from typing import Annotated, Literal, Optional

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError
from pydantic import Field

from gmaps_mcp.schemas import (
    GetPlaceDetailsResult,
    ResultDelivery,
    SearchGoogleMapsResult,
)
from gmaps_mcp.storage import result_store
from gmaps_mcp.tools import (
    get_place_details,
    search_google_maps,
)

# Initialize MCP Server instance
server = MCPServer(
    name="gmaps-mcp",
    version="0.1.0",
    instructions=(
        "Google Maps MCP server providing live search, place details, ratings, addresses, "
        "phone numbers, and geo-coordinates for places and businesses worldwide."
    ),
)


# Register tools on the MCPServer instance
@server.tool(
    name="search_google_maps",
    description=(
        "Search Google Maps for local businesses, places, points of interest, and services within a specified location. "
        "Returns structured place data including business name, Google Place ID, category, "
        "formatted street address, phone numbers, website URL, geo-coordinates (latitude/longitude), "
        "star rating, total review count, and direct Google Maps URL."
    ),
)
async def search_google_maps_tool(
    term: Annotated[
        str,
        Field(
            description=(
                "The search term, business category, service, or place name (e.g. "
                "'coffee shops', 'dentists', 'Italian restaurants', 'hospitals', 'electricians', 'museums')."
            )
        ),
    ],
    location: Annotated[
        str,
        Field(
            description=(
                "The target location, city, neighborhood, or landmark to search within (e.g. "
                "'Koramangala Bangalore', 'Connaught Place Delhi', 'Bandra Mumbai', 'Hyderabad', 'London', 'Chicago')."
            )
        ),
    ],
    limit: Annotated[
        Optional[int],
        Field(
            default=None,
            ge=1,
            description=(
                "Optional maximum number of place results to return. "
                "Recommendation: It is generally NOT recommended to use limit frequently; use only when strictly necessary. "
                "Google Maps delivers results in full batch pages/tiles and results are simply trimmed to the limit afterwards, "
                "so setting a limit does not save server or network resources. Leave omitted/null for complete results."
            ),
        ),
    ] = None,
    country: Annotated[
        str,
        Field(
            default="in",
            description=(
                "Two-letter ISO 3166-1 alpha-2 country code to localize search results and map boundaries. "
                "Default is 'in' (India). Other examples: 'us' (United States), 'gb' (United Kingdom), "
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
    result_delivery: Annotated[
        Literal["inline", "resource"],
        Field(
            default="inline",
            description=(
                "Delivery method for search results:\n"
                "- 'inline': Return all structured place results directly inside the tool response (default).\n"
                "- 'resource': Store full results server-side in an MCP resource and return an MCP resource_link URI "
                "(e.g. 'gmaps://results/{resource_id}'), preventing LLM context window bloat for large result sets."
            ),
        ),
    ] = "inline",
) -> SearchGoogleMapsResult:
    return await search_google_maps(
        term=term,
        location=location,
        limit=limit,
        country=country,
        language=language,
        result_delivery=result_delivery,
    )


# Register MCP Resources for stored search results
@server.resource(
    "gmaps://results/{resource_id}",
    name="stored_search_results",
    title="Stored Google Maps Search Results",
    description="Retrieve complete stored Google Maps search results JSON by resource ID.",
    mime_type="application/json",
)
def get_stored_search_results(resource_id: str) -> str:
    """Retrieve complete stored search results by resource ID."""
    result = result_store.get(resource_id)
    if result is None:
        raise ResourceNotFoundError(f"No stored Google Maps results found for resource ID: {resource_id}")
    return result.model_dump_json(indent=2)


def _register_stored_resource(entry) -> None:
    """Register stored search result dynamically into the server's concrete resources list."""
    from mcp.server.mcpserver.resources.types import FunctionResource

    uri = f"gmaps://results/{entry.resource_id}"
    resource = FunctionResource.from_function(
        fn=lambda rid=entry.resource_id: result_store.get_json(rid),
        uri=uri,
        name=f"search_{entry.resource_id}",
        title=f"Google Maps: {entry.result.query} ({entry.result.total_results} places)",
        description=(
            f"Stored search results for '{entry.result.query}' in {entry.result.country.upper()} "
            f"({entry.result.total_results} results found)"
        ),
        mime_type="application/json",
    )
    server.add_resource(resource)


def _unregister_stored_resource(resource_id: str) -> None:
    """Remove expired/deleted stored search result from concrete resources."""
    uri = f"gmaps://results/{resource_id}"
    if hasattr(server, "_resource_manager") and hasattr(server._resource_manager, "_resources"):
        server._resource_manager._resources.pop(uri, None)


result_store.add_store_callback(_register_stored_resource)
result_store.add_delete_callback(_unregister_stored_resource)


@server.tool(
    name="get_place_details",
    description=(
        "Retrieve detailed information for a single specific Google Maps place or business. "
        "Looks up a place using its unique Google Place ID (e.g., 'ChIJ...' or 'place_id:ChIJ...') "
        "or specific landmark/business name. Returns complete structured details including address, "
        "phone number, website, rating, coordinates, and Google Maps URL."
    ),
)
async def get_place_details_tool(
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
    return await get_place_details(
        place=place,
        country=country,
        language=language,
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="gmaps-mcp",
        description="Google Maps MCP Server — Live place search & details for AI agents",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind for streamable-http transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind for streamable-http transport (default: 8000)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity (default: INFO)",
    )
    return parser.parse_args()


def main() -> None:
    """Main CLI entrypoint for gmaps-mcp."""
    args = parse_args()

    # Configure logging strictly to stderr to prevent stdio stream corruption
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    logger = logging.getLogger("gmaps_mcp")
    logger.info("Starting gmaps-mcp server (transport=%s)...", args.transport)

    if args.transport == "streamable-http":
        logger.info("Serving Streamable HTTP on http://%s:%d/mcp", args.host, args.port)
        server.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        # Default to stdio transport
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
