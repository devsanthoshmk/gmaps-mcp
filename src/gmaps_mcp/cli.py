"""Unified Command Line Interface for Google Maps MCP.

Provides CLI commands for:
- Running the MCP Server (stdio or streamable-http)
- Direct searching with table, JSON, and CSV export
- Direct Place ID / name details lookup
- Stored MCP resource inspection
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
from typing import Optional

from gmaps_mcp.schemas import Place
from gmaps_mcp.server import server
from gmaps_mcp.storage import result_store
from gmaps_mcp.tools import get_place_details, search_google_maps

logger = logging.getLogger("gmaps_mcp.cli")


def _format_table(places: list[Place]) -> str:
    """Format a list of Place models as a readable text table."""
    if not places:
        return "No places found."

    lines = []
    header = f"{'#':<4} {'Name':<32} {'Category':<18} {'Phone':<18} {'Rating':<8} {'Reviews':<8} {'Address'}"
    separator = "-" * len(header)
    lines.append(header)
    lines.append(separator)

    for idx, p in enumerate(places, start=1):
        name = (p.name[:29] + "...") if len(p.name) > 32 else p.name
        cat = ((p.category or "")[:15] + "...") if p.category and len(p.category) > 18 else (p.category or "-")
        phone = p.phone or p.international_phone or "-"
        rating = f"{p.rating:.1f}" if p.rating is not None else "-"
        reviews = str(p.review_count) if p.review_count is not None else "-"
        addr = (p.address[:45] + "...") if p.address and len(p.address) > 48 else (p.address or "-")
        lines.append(f"{idx:<4} {name:<32} {cat:<18} {phone:<18} {rating:<8} {reviews:<8} {addr}")

    return "\n".join(lines)


def _export_csv(places: list[Place], filepath: str) -> None:
    """Export a list of Place models to a CSV file."""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    fieldnames = [
        "place_id", "name", "category", "address", "phone",
        "international_phone", "website", "domain", "rating",
        "review_count", "latitude", "longitude", "google_maps_url"
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in places:
            writer.writerow(p.model_dump())


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the Google Maps MCP Server."""
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    logger.info("Starting gmaps-mcp server (transport=%s)...", args.transport)

    if args.transport == "streamable-http":
        logger.info("Serving Streamable HTTP on http://%s:%d/mcp", args.host, args.port)
        server.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        server.run(transport="stdio")


async def _run_search(args: argparse.Namespace) -> None:
    """Execute search command."""
    res = await search_google_maps(
        query=args.query,
        limit=args.limit,
        grid=args.grid,
        country=args.country,
        language=args.lang,
        result_delivery=args.delivery,
    )

    if args.output:
        if args.output.endswith(".json"):
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(res.model_dump_json(indent=2))
            print(f"Exported {res.total_results} results to JSON: {args.output}")
        else:
            _export_csv(res.places, args.output)
            print(f"Exported {len(res.places)} places to CSV: {args.output}")
        return

    if args.format == "json":
        print(res.model_dump_json(indent=2))
    elif args.format == "csv":
        fieldnames = [
            "place_id", "name", "category", "address", "phone",
            "international_phone", "website", "domain", "rating",
            "review_count", "latitude", "longitude", "google_maps_url"
        ]
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        for p in res.places:
            writer.writerow(p.model_dump())
    else:
        # Table format
        if res.delivery_mode == "resource":
            print(f"Results delivered as MCP Resource: {res.resource_link}")
            print(f"Summary: {res.summary}")
            if res.sample_places:
                print("\nSample Places:")
                for sp in res.sample_places:
                    print(f"  - {sp}")
        else:
            print(f"\nSearch: {res.query!r} | Country: {res.country.upper()} | Found: {res.total_results} place(s)\n")
            print(_format_table(res.places))


async def _run_details(args: argparse.Namespace) -> None:
    """Execute details lookup command."""
    res = await get_place_details(
        place=args.place,
        country=args.country,
        language=args.lang,
    )

    if args.output:
        if args.output.endswith(".json"):
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(res.model_dump_json(indent=2))
            print(f"Exported place details to JSON: {args.output}")
        else:
            places = [res.place] if res.found and res.place else []
            _export_csv(places, args.output)
            print(f"Exported place details to CSV: {args.output}")
        return

    if args.format == "json":
        print(res.model_dump_json(indent=2))
    elif args.format == "csv":
        fieldnames = [
            "place_id", "name", "category", "address", "phone",
            "international_phone", "website", "domain", "rating",
            "review_count", "latitude", "longitude", "google_maps_url"
        ]
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        if res.found and res.place:
            writer.writerow(res.place.model_dump())
    else:
        if not res.found or not res.place:
            print(f"Place not found for: {args.place!r}")
            return
        p = res.place
        print(f"\nPlace Details: {p.name}")
        print("=" * (15 + len(p.name)))
        print(f"Place ID:             {p.place_id}")
        print(f"Category:             {p.category or '-'}")
        print(f"Address:              {p.address or '-'}")
        print(f"Phone (National):     {p.phone or '-'}")
        print(f"Phone (Intl):         {p.international_phone or '-'}")
        print(f"Website:              {p.website or '-'}")
        print(f"Domain:               {p.domain or '-'}")
        print(f"Rating:               {p.rating if p.rating is not None else '-'} ({p.review_count or 0} reviews)")
        print(f"Coordinates:          {p.latitude}, {p.longitude}")
        print(f"Google Maps URL:      {p.google_maps_url or '-'}\n")


def build_parser() -> argparse.ArgumentParser:
    """Build unified argument parser for CLI and server."""
    parser = argparse.ArgumentParser(
        prog="gmaps-mcp",
        description="Google Maps MCP Server & CLI Tool — Live place search, details, and exports",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Serve subcommand
    serve_parser = subparsers.add_parser("serve", help="Run the MCP Server (default)")
    serve_parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport protocol (default: stdio)",
    )
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP transport")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port for HTTP transport")
    serve_parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity (default: INFO)",
    )

    # Search subcommand
    search_parser = subparsers.add_parser("search", help="Search Google Maps places")
    search_parser.add_argument("query", help="Search query (e.g. 'bakeries in Paris', 'dentists in Chicago')")
    search_parser.add_argument("--limit", type=int, default=None, help="Maximum number of places (default: unlimited)")
    search_parser.add_argument(
        "--grid",
        action="store_true",
        help="Enable dynamic geospatial grid tiling for massive citywide results coverage",
    )
    search_parser.add_argument("--country", default="in", help="ISO country code (default: in)")
    search_parser.add_argument("--lang", default="en", help="Language code (default: en)")
    search_parser.add_argument(
        "--delivery",
        choices=["inline", "resource"],
        default="inline",
        help="Result delivery mode (default: inline)",
    )
    search_parser.add_argument(
        "--format",
        choices=["table", "json", "csv"],
        default="table",
        help="Output display format (default: table)",
    )
    search_parser.add_argument("--output", default=None, help="Save results directly to CSV or JSON file")

    # Details subcommand
    details_parser = subparsers.add_parser("details", help="Lookup place details by Place ID or name")
    details_parser.add_argument("place", help="Google Place ID ('ChIJ...') or exact place name")
    details_parser.add_argument("--country", default="in", help="ISO country code (default: in)")
    details_parser.add_argument("--lang", default="en", help="Language code (default: en)")
    details_parser.add_argument(
        "--format",
        choices=["table", "json", "csv"],
        default="table",
        help="Output display format (default: table)",
    )
    details_parser.add_argument("--output", default=None, help="Save details directly to CSV or JSON file")

    # Top-level fallback flags (if user runs `gmaps-mcp --transport stdio` without typing `serve`)
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport protocol when running server (default: stdio)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP transport")
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP transport")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity (default: INFO)",
    )

    return parser


async def async_main(args: argparse.Namespace) -> None:
    """Async entrypoint dispatcher."""
    if args.command == "search":
        await _run_search(args)
    elif args.command == "details":
        await _run_details(args)
    else:
        if getattr(args, "transport", "stdio") == "streamable-http":
            await server.run_streamable_http_async(host=args.host, port=args.port)
        else:
            await server.run_stdio_async()


def main() -> None:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "search":
        asyncio.run(_run_search(args))
    elif args.command == "details":
        asyncio.run(_run_details(args))
    else:
        cmd_serve(args)


if __name__ == "__main__":
    main()
