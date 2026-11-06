# gmaps-mcp

Google Maps MCP server for AI agents and LLM applications.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Purpose

gmaps-mcp is an open-source Google Maps MCP server and command line interface built on the Model Context Protocol. It provides an AI agent maps tool that requires no API key, billing account, or browser automation setup.

AI assistants in Claude Desktop, Cursor, Cline, Windsurf, Zed, and OpenCode connect to this Model Context Protocol Google Maps server to search local businesses, inspect reviews and star ratings, find phone numbers and websites, and retrieve geographic coordinates. The tool runs locally through standard input/output (stdio) or across networks through Streamable HTTP.

## Architecture

The system has four core layers:

1. **Protocol layer.** Built with the official MCP Python SDK (`mcp.server.mcpserver.MCPServer`). Exposes tools and resources over stdio or Streamable HTTP transports. Server logging writes strictly to stderr so stdout remains clean JSON-RPC for MCP clients.
2. **Scraper engine.** Built on `aiohttp` and `phonenumbers`. The engine queries Google Maps endpoints directly with asynchronous HTTP requests, parses raw response payloads, extracts place records, and normalizes phone numbers into E.164 format. It runs without Playwright, Puppeteer, or browser binaries.
3. **Geospatial grid tiling.** When searching broad areas or entire cities, the grid crawler calculates the geographic bounding box and subdivides the region into smaller viewport tiles. This bypasses the standard 20-result pagination cap of Google Maps and collects hundreds of places per query.
4. **Storage and delivery layer.** When result sets exceed normal prompt budgets, the server stores full result objects in memory and returns an MCP resource URI (`gmaps://results/{resource_id}`). Clients fetch the complete payload through the MCP resource interface, preventing context window exhaustion.

## Setup

### Requirements

- Python 3.10 or higher
- `uv` package manager (recommended) or `pip`

### Install and run with uvx

Run the server directly without cloning:

```bash
uvx --from git+https://github.com/devsanthoshmk/gmaps-mcp.git gmaps-mcp serve
```

### Install from source

Clone the repository and install dependencies with `uv`:

```bash
git clone https://github.com/devsanthoshmk/gmaps-mcp.git
cd gmaps-mcp
uv sync
```

## Usage

### Run as an MCP server

Start the server using stdio transport (default):

```bash
uv run gmaps-mcp serve
```

Start the server using Streamable HTTP transport:

```bash
uv run gmaps-mcp serve --transport streamable-http --host 127.0.0.1 --port 8000
```

### Run via command line

#### Search places

Search for places and display a formatted table:

```bash
uv run gmaps-mcp search "dentists" "Chicago" --limit 10 --country us --format table
```

Search across an entire city using geospatial grid tiling:

```bash
uv run gmaps-mcp search "bakeries" "Paris" --country fr --grid --format table
```

Export search results to CSV or JSON:

```bash
uv run gmaps-mcp search "pharmacies" "Chennai" --grid --country in --output pharmacies.csv
uv run gmaps-mcp search "coffee shops" "Seattle" --country us --output coffee.json
```

#### Get place details

Look up details by Google Place ID:

```bash
uv run gmaps-mcp details "ChIJ7xiFY1VmUjoR2IuH0fYWMlk" --format table
```

Look up details by name and export to CSV:

```bash
uv run gmaps-mcp details "Eiffel Tower Paris" --country fr --output eiffel.csv
```

## Configuration

### Claude Desktop

To configure Claude Desktop MCP Maps integration, add gmaps-mcp to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "google-maps": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/devsanthoshmk/gmaps-mcp.git",
        "gmaps-mcp",
        "serve"
      ]
    }
  }
}
```

Config file paths by platform:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

### Cursor

Add to `.cursor/mcp.json` or your global Cursor MCP configuration:

```json
{
  "mcpServers": {
    "google-maps": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/devsanthoshmk/gmaps-mcp.git",
        "gmaps-mcp",
        "serve"
      ]
    }
  }
}
```

### Windsurf, Cline, and Zed

Add to your client MCP configuration:

```json
{
  "mcpServers": {
    "google-maps": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/devsanthoshmk/gmaps-mcp.git",
        "gmaps-mcp",
        "serve"
      ]
    }
  }
}
```

### Install with mcp-add

Add the server using the `mcp-add` utility:

```bash
npx mcp-add -n google-maps -t stdio -c "uvx --from git+https://github.com/devsanthoshmk/gmaps-mcp.git gmaps-mcp serve"
```

### Local development configuration

Point an MCP client to a local repository checkout:

```json
{
  "mcpServers": {
    "google-maps": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/gmaps-mcp",
        "gmaps-mcp",
        "serve"
      ]
    }
  }
}
```

## Available tools

The server registers two MCP tools:

### `search_google_maps`

Searches Google Maps for businesses, places, and points of interest.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `term` | string | required | Search query or business category such as "coffee shops" or "dentists" |
| `location` | string | required | City, neighborhood, or landmark such as "Paris", "Chicago", or "Chennai" |
| `limit` | integer | null | Maximum number of results to return |
| `grid` | boolean | false | Enable geospatial grid tiling for large area coverage |
| `country` | string | "in" | ISO 3166-1 alpha-2 country code such as "us", "fr", or "in" |
| `language` | string | "en" | Response language code |
| `result_delivery` | "inline" \| "resource" | "inline" | Delivery mode. Use "resource" to prevent large result sets from filling the context window |

### `get_place_details`

Fetches structured details for a specific place.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `place` | string | required | Google Place ID (e.g. "ChIJ...") or exact business name |
| `country` | string | "in" | ISO 3166-1 alpha-2 country code |
| `language` | string | "en" | Response language code |

## Output schema

Places return structured JSON matching this schema:

```json
{
  "place_id": "ChIJ7xiFY1VmUjoR2IuH0fYWMlk",
  "name": "New Chennai Pharmacy",
  "category": "Pharmacy",
  "address": "No. 33, Sarojini Street, T.Nagar, Chennai, Tamil Nadu 600017",
  "phone": "091500 97960",
  "international_phone": "+91 91500 97960",
  "website": "https://example.com",
  "domain": "example.com",
  "latitude": 13.0371485,
  "longitude": 80.2319365,
  "rating": 4.7,
  "review_count": 25,
  "google_maps_url": "https://www.google.com/maps/place/?q=place_id:ChIJ7xiFY1VmUjoR2IuH0fYWMlk"
}
```

## Development

Run the test suite:

```bash
uv run --extra dev pytest
```

## License

MIT license in [LICENSE](LICENSE).
