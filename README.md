# 🗺️ Google Maps MCP Server & CLI (`gmaps-mcp`)

[![MCP Version](https://img.shields.io/badge/MCP-2.0-blue.svg)](https://modelcontextprotocol.io/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A self-contained, high-throughput **Google Maps Model Context Protocol (MCP)** server and command-line tool. It equips AI agents (Claude Desktop, Cursor, Antigravity, Cline, Windsurf, Zed) and terminal users with structured live search results, full place profiles, normalized contact information, reviews, and coordinates worldwide—**without requiring an API key, headless browser, or external dependencies**.

---

## ⚡ Key Capabilities

- **No API Key Required**: Integrated live crawler runs natively in-process with `asyncio` and `aiohttp`.
- **Deep Sliding-Window Pagination**: Uses internal Protobuf offset indexing (`!7i{size}!8i{start}`) to retrieve up to thousands of results per query without artificial caps.
- **Dynamic Geospatial Grid Tiling**: Automatically detects Google's bounding box coordinates (`data[1][0]`) and tiles the region into a geodesic sub-viewport matrix to scrape thousands of places across entire metropolitan areas with zero hardcoded locality names.
- **Direct Place ID & Name Resolution**: Decodes Google Place IDs (`ChIJ...`) into 64-bit feature IDs and cell IDs (`0x{fid}:0x{cid}`) to query Google Maps' native entity endpoint (`preview/place`).
- **Standardized Phone Normalization**: Automatically normalizes all local and international phone numbers into E.164 (`+91 44 ...`, `+1 312 ...`) and National formats using Google's `phonenumbers` library.
- **MCP Resource Delivery (`result_delivery: resource`)**: Stores large result sets in an in-memory MCP Resource (`gmaps://results/{id}`) with dynamic listing, eliminating LLM context window bloat.
- **Dual-Purpose CLI & Server**: Run as a standard MCP server (`gmaps-mcp serve`) or as a rich standalone CLI (`gmaps-mcp search`, `gmaps-mcp details`) with formatted tables, JSON, and CSV file exports.

---

## 🚀 Quickstart

Run directly using [`uvx`](https://docs.astral.sh/uv/):

```bash
# Run MCP server over stdio
uvx --from git+https://github.com/devsanthoshmk/gmaps-mcp.git gmaps-mcp serve

# Run a live CLI search from anywhere
uvx --from git+https://github.com/devsanthoshmk/gmaps-mcp.git gmaps-mcp search "bakeries in Paris" --country fr --limit 10
```

Or install locally:

```bash
git clone https://github.com/devsanthoshmk/gmaps-mcp.git
cd gmaps-mcp
uv pip install -e .
```

---

## 💻 CLI Usage Guide

The `gmaps-mcp` CLI exposes the exact same scraping engine and tools as the MCP server:

### 1. Search Places (Table, JSON, or CSV)

```bash
# Formatted table output
gmaps-mcp search "dentists in Chicago" --limit 10 --country us --format table

# Deep dynamic geospatial grid search across Paris (zero hardcoded names)
gmaps-mcp search "bakeries in Paris" --country fr --grid --format table

# Direct export to CSV file
gmaps-mcp search "pharmacies in Chennai" --grid --country in --output pharmacies.csv

# JSON output
gmaps-mcp search "coffee in Tokyo" --limit 5 --country jp --format json
```

### 2. Lookup Place Details (Place ID or Name)

```bash
# Lookup by raw Google Place ID
gmaps-mcp details "ChIJ7xiFY1VmUjoR2IuH0fYWMlk" --format table

# Lookup by business or landmark name
gmaps-mcp details "Eiffel Tower Paris" --country fr --format table
```

### 3. Start MCP Server

```bash
# stdio transport (default)
gmaps-mcp serve --transport stdio

# Streamable HTTP transport (remote agent deployments)
gmaps-mcp serve --transport streamable-http --host 0.0.0.0 --port 8000
```

---

## 🛠️ MCP Client Configuration

### 1. Claude Desktop

Add this to your `claude_desktop_config.json`:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

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

*For local repository development:*
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

---

### 2. Cursor IDE / Antigravity / Windsurf

Add to `.cursor/mcp.json` or `.mcp.json` in your workspace:

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

---

## 🧩 MCP Tools Reference

### `search_google_maps`

Searches Google Maps for businesses, services, and locations.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `string` | *required* | The search query (e.g. `"cafes in Brooklyn"`, `"dentists in Chicago"`). |
| `limit` | `integer` | `null` | Maximum results to return. If omitted, returns as many as available. |
| `grid` | `boolean` | `false` | Enables dynamic geospatial bounding box grid tiling for massive results. |
| `country` | `string` | `"in"` | Two-letter ISO country code for localized relevance (e.g. `"us"`, `"fr"`, `"jp"`). |
| `language` | `string` | `"en"` | Response language code (`"en"`, `"fr"`, `"es"`, `"hi"`, etc.). |
| `result_delivery` | `"inline" \| "resource"` | `"inline"` | `"inline"` returns places directly; `"resource"` returns an MCP resource URI link. |

---

### `get_place_details`

Fetches complete structured details for a specific place.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `place` | `string` | *required* | A Google Place ID (`"ChIJ..."`) or exact business/landmark name. |
| `country` | `string` | `"in"` | Two-letter ISO country code. |
| `language` | `string` | `"en"` | Response language code. |

---

## 📦 Output Data Schema

Each place in the results contains the following structured fields:

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

---

## 🧪 Testing

Run the test suite using `uv`:

```bash
uv run --with pytest --with pytest-asyncio pytest
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
