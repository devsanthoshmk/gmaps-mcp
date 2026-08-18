# 🗺️ gmaps-mcp

A Google Maps scraper server and CLI for AI agents and terminal use. **No API key required.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://python.org) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ⚡ Key Features

- **No API key** — scrapes Google Maps directly via `aiohttp`
- **Search** businesses by query with pagination and geo-grid tiling
- **Place details** — full profile by Place ID or name (phone, address, rating, coordinates)
- **Grid mode** — tiles an entire city/region into sub-viewports to collect thousands of results
- **MCP + CLI** — same engine, two interfaces

---

## 🚀 Quickstart

### Add to AI Agents (Claude Desktop, Cursor, Windsurf, Cline, Zed, etc.)

```bash
npx mcp-add -n google-maps -t stdio -c "uvx --from git+https://github.com/devsanthoshmk/gmaps-mcp.git gmaps-mcp serve"
```

### Or Run via CLI

```bash
# Direct run without cloning
uvx --from git+https://github.com/devsanthoshmk/gmaps-mcp.git gmaps-mcp search "bakeries" "Paris" --country fr --limit 10

# Or clone and run locally
git clone https://github.com/devsanthoshmk/gmaps-mcp.git
cd gmaps-mcp
uv run gmaps-mcp search "bakeries" "Paris" --country fr --limit 10
```

---

## 💻 CLI

### Search

```bash
uv run gmaps-mcp search "dentists" "Chicago" --limit 10 --country us --format table
uv run gmaps-mcp search "bakeries" "Paris" --country fr --grid --format table
uv run gmaps-mcp search "pharmacies" "Chennai" --grid --country in --output pharmacies.csv
```

### Place Details

```bash
uv run gmaps-mcp details "ChIJ7xiFY1VmUjoR2IuH0fYWMlk" --format table
uv run gmaps-mcp details "Eiffel Tower Paris" --country fr --output eiffel.csv
```

### Start MCP Server

```bash
uv run gmaps-mcp serve                                                         # stdio (default)
uv run gmaps-mcp serve --transport streamable-http --host 0.0.0.0 --port 8000  # HTTP
```

---

## 🔌 MCP Client Config (Manual)

```json
{
  "mcpServers": {
    "google-maps": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/devsanthoshmk/gmaps-mcp.git", "gmaps-mcp", "serve"]
    }
  }
}
```

*Local dev:*
```json
{
  "mcpServers": {
    "google-maps": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/gmaps-mcp", "gmaps-mcp", "serve"]
    }
  }
}
```

---

## 🧩 MCP Tools

### `search_google_maps`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `term` | string | *required* | Search term / business category (e.g. `"coffee shops"`, `"dentists"`) |
| `location` | string | *required* | Target location / city (e.g. `"Paris"`, `"Chicago"`, `"Chennai"`) |
| `limit` | integer | null | Max results |
| `grid` | boolean | false | Enable geo-grid tiling for large area coverage |
| `country` | string | `"in"` | ISO country code (`"us"`, `"fr"`, `"jp"`) |
| `language` | string | `"en"` | Response language |
| `result_delivery` | `"inline"` \| `"resource"` | `"inline"` | `"resource"` avoids context bloat for large result sets |

### `get_place_details`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `place` | string | *required* | Place ID (`"ChIJ..."`) or business name |
| `country` | string | `"in"` | ISO country code |
| `language` | string | `"en"` | Response language |

---

## 📦 Output Schema

```json
{
  "place_id": "ChIJ7xiFY1VmUjoR2IuH0fYWMlk",
  "name": "New Chennai Pharmacy",
  "category": "Pharmacy",
  "address": "No. 33, Sarojini Street, T.Nagar, Chennai, Tamil Nadu 600017",
  "phone": "091500 97960",
  "international_phone": "+91 91500 97960",
  "website": "https://example.com",
  "latitude": 13.0371485,
  "longitude": 80.2319365,
  "rating": 4.7,
  "review_count": 25,
  "google_maps_url": "https://www.google.com/maps/place/?q=place_id:ChIJ7xiFY1VmUjoR2IuH0fYWMlk"
}
```

---

## 📄 License

MIT — see [LICENSE](LICENSE).
