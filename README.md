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
uvx --from git+https://github.com/<your-username>/gmaps-mcp.git gmaps-mcp
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
        "git+https://github.com/<your-username>/gmaps-mcp.git",
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
        "/absolute/path/to/gmap-mcp",
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
        "git+https://github.com/<your-username>/gmaps-mcp.git",
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
        "git+https://github.com/<your-username>/gmaps-mcp.git",
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
| `limit` | `integer` | `10` | Maximum number of results to return (`1` to `50`). |
| `country` | `string` | `"in"` | Two-letter ISO country code for region localization (e.g. `"in"`, `"us"`, `"gb"`, `"de"`, `"fr"`, `"ae"`). |
| `language` | `string` | `"en"` | Language code for results (e.g. `"en"`, `"hi"`, `"es"`, `"fr"`). |

#### Output Structure
```json
{
  "query": "coffee in Koramangala Bangalore",
  "country": "in",
  "language": "en",
  "total_results": 2,
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
