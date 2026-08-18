# 🗺️ Google Maps MCP Server (`gmaps-mcp`)

[![MCP Version](https://img.shields.io/badge/MCP-2.0-blue.svg)](https://modelcontextprotocol.io/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A self-contained, lightweight **Google Maps Model Context Protocol (MCP)** server built with the official MCP Python SDK. It provides AI agents (such as Claude Desktop, Cursor, Cline, and Antigravity) with structured search results, place details, ratings, contact info, coordinates, and Google Maps URLs.

---

## ⚡ Key Features

- **One-Command Installation**: Runs anywhere instantly via `uvx` without manual environment setup.
- **100% Self-Contained**: Scraper engine is integrated natively in-process via `asyncio` and `aiohttp`—no external subprocesses, headless browsers, or API keys required.
- **Rich Structured Place Data**: Returns Place IDs, business names, categories, addresses, local & international phone numbers, website URLs, coordinates (`lat`/`long`), star ratings, review counts, and direct Google Maps links.
- **Stdio & Streamable HTTP**: Native `stdio` support for desktop AI clients and `streamable-http` for remote/containerized deployments.
- **Clean JSON-RPC**: All internal logging is piped strictly to `stderr`, keeping the stdio protocol stream 100% compliant.

---

## 🚀 Quickstart

Run directly using [`uvx`](https://docs.astral.sh/uv/):

```bash
# Run directly from GitHub repository
uvx --from git+https://github.com/devsanthoshmk/gmaps-mcp.git gmaps-mcp
```

Or from a local clone:

```bash
uv run gmaps-mcp
```

---

## 🛠️ MCP Client Configuration

### 1. Claude Desktop

Add this to your `claude_desktop_config.json` (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "google-maps": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/devsanthoshmk/gmaps-mcp.git",
        "gmaps-mcp"
      ]
    }
  }
}
```

*If running from a local folder:*
```json
{
  "mcpServers": {
    "google-maps": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/gmaps-mcp",
        "gmaps-mcp"
      ]
    }
  }
}
```

---

### 2. Cursor IDE

In Cursor, open **Settings → Features → MCP** (or edit `.cursor/mcp.json` in your project):

```json
{
  "mcpServers": {
    "google-maps": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/devsanthoshmk/gmaps-mcp.git",
        "gmaps-mcp"
      ]
    }
  }
}
```

---

### 3. Cline (VS Code Extension)

In Cline Settings (`cline_mcp_settings.json`):

```json
{
  "mcpServers": {
    "google-maps": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/devsanthoshmk/gmaps-mcp.git",
        "gmaps-mcp"
      ]
    }
  }
}
```

---

### 4. Google Antigravity / AGY CLI

#### Project-Scoped Plugin (`.agents/plugins/gmaps-mcp/mcp_config.json`)
Antigravity automatically discovers and activates MCP servers placed in project plugins. Create `.agents/plugins/gmaps-mcp/plugin.json`:
```json
{
  "name": "gmaps-mcp",
  "description": "Google Maps MCP server"
}
```

And `.agents/plugins/gmaps-mcp/mcp_config.json`:
```json
{
  "mcpServers": {
    "google-maps": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/gmaps-mcp",
        "gmaps-mcp"
      ]
    }
  }
}
```

#### Global Configuration (`~/.gemini/antigravity/mcp_config.json` or `~/.gemini/config/mcp_config.json`)
```json
{
  "mcpServers": {
    "google-maps": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/devsanthoshmk/gmaps-mcp.git",
        "gmaps-mcp"
      ]
    }
  }
}
```

---

## 🧰 Available Tools

### 1. `search_google_maps`
Search Google Maps for businesses, attractions, services, and landmarks.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `string` | *(required)* | Search term (e.g. `"coffee in Koramangala Bangalore"`, `"dentists near Connaught Place Delhi"`, `"Italian restaurants in New York"`). |
| `limit` | `integer` | `None` *(optional)* | Maximum number of results to return. If omitted or `null`, fetches as many results as possible across all pages. |
| `result_delivery` | `string` | `"inline"` | Delivery mode: `"inline"` returns all places directly in the tool response (default), `"resource"` stores the complete results server-side in an MCP resource and returns a `resource_link` URI to eliminate LLM context bloat. |
| `country` | `string` | `"in"` | Two-letter ISO country code for region localization (e.g. `"in"`, `"us"`, `"gb"`, `"de"`, `"fr"`, `"ae"`). |
| `language` | `string` | `"en"` | Language code for results (e.g. `"en"`, `"hi"`, `"es"`, `"fr"`). |

#### Output Structure (Inline Delivery)
```json
{
  "query": "coffee in Koramangala Bangalore",
  "country": "in",
  "language": "en",
  "total_results": 2,
  "delivery_mode": "inline",
  "places": [
    {
      "place_id": "ChIJ80IECk8UrjsRqCffDjE09lw",
      "name": "Dyu Art Cafe",
      "category": "Art cafe",
      "address": "KHB MIG Colony, 1st Cross Rd, Koramangala 8th Block, Bengaluru, Karnataka 560095",
      "phone": "096113 19774",
      "international_phone": "+91 96113 19774",
      "website": "http://www.dyuartcafe.com/",
      "domain": "dyuartcafe.com",
      "latitude": 12.9373076,
      "longitude": 77.6176544,
      "rating": 4.4,
      "review_count": 21440,
      "google_maps_url": "https://www.google.com/maps/place/?q=place_id:ChIJ80IECk8UrjsRqCffDjE09lw"
    }
  ]
}
```

#### Output Structure (Resource Delivery)
When `result_delivery="resource"`, results are stored in an MCP resource and the tool response returns a lightweight link:
```json
{
  "query": "dentists in Delhi",
  "country": "in",
  "language": "en",
  "total_results": 50,
  "delivery_mode": "resource",
  "resource_link": "gmaps://results/search_a1b2c3d4e5f6",
  "resource_id": "search_a1b2c3d4e5f6",
  "summary": "Successfully retrieved 50 places. Results are stored in MCP resource 'gmaps://results/search_a1b2c3d4e5f6' to conserve context. Retrieve full place data using the MCP Resource API.",
  "places": []
}
```

#### Reading Stored Results via MCP Resource API
AI agents and clients can retrieve the complete structured JSON at any time via the MCP `resources/read` endpoint using the `resource_link` (e.g. `gmaps://results/{resource_id}`). The server stores results in memory without exposing local filesystem paths, ensuring identical behavior across `stdio`, `sse`, and `streamable-http` transports.

---

### 2. `get_place_details`
Retrieve detailed information for a single specific place or business by its Place ID or name.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `place` | `string` | *(required)* | Google Place ID (e.g. `"ChIJ12k5kG_iDDkRwuzibQwYZ4M"`) or exact business/landmark name (e.g. `"AIIMS New Delhi"`). |
| `country` | `string` | `"in"` | Two-letter ISO country code (default: `"in"`). |
| `language` | `string` | `"en"` | Language code for response (default: `"en"`). |

---

## 🌐 Remote Deployment (Streamable HTTP)

The server supports modern **Streamable HTTP** transport for deployment behind reverse proxies or cloud hosting:

```bash
# Start Streamable HTTP server on port 8000
uv run gmaps-mcp --transport streamable-http --host 0.0.0.0 --port 8000
```

The MCP endpoint will be available at:
`http://<host>:8000/mcp`

---

## 🧪 Development & Testing

Run unit and integration tests using `uv`:

```bash
# Run pytest test suite
uv run --with pytest --with pytest-asyncio pytest tests/ -v

# Run the server locally with debug logs
uv run gmaps-mcp --log-level DEBUG
```

---

## 📦 Project Structure

```
gmap-mcp/
├── pyproject.toml              # Packaging & dependencies (PEP 517/621)
├── README.md                   # Setup guide and MCP client docs
├── src/
│   └── gmaps_mcp/
│       ├── __init__.py         # Package entry
│       ├── schemas.py          # Pydantic data models (Place, Search, Details)
│       ├── server.py           # MCPServer instance & CLI runner
│       ├── tools.py            # MCP Tool definitions & detailed descriptions
│       └── scraper/
│           ├── __init__.py     # Scraper API
│           └── crawler.py      # Async Google Maps parser & extraction engine
└── tests/
    ├── test_schemas.py         # Schema tests
    ├── test_crawler.py         # Parser unit tests
    └── test_server.py          # MCP Server registration & tool calling tests
```

---

## 📜 Attribution & License

- Scraper core adapted and modularized from [christivn/mapScraper](https://github.com/christivn/mapScraper) (commit `1b38cf3e153294e3dad2f6cb5862be0201a54065`).
- Licensed under the **MIT License**.
