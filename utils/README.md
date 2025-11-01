# MCP Testing Utils

This directory contains bash scripts to test the MCP (Model Context Protocol) server functionality for the Japanese Transit Search system.

## Available Scripts

### 1. Simple Testing Scripts (Recommended)

#### `test_station_search.sh` - Simple Station Search Test
Test station search functionality with customizable parameters.

**Usage:**
```bash
./utils/test_station_search.sh <station_query> [limit] [fuzzy_threshold] [exact] [show_scores]
```

**Examples:**
```bash
# Basic search for Shibuya
./utils/test_station_search.sh shibuya

# Search with limit of 5 results
./utils/test_station_search.sh tokyo 5

# Fuzzy search with lower threshold (more lenient)
./utils/test_station_search.sh shibya 10 50

# Exact search (no fuzzy matching)
./utils/test_station_search.sh 渋谷 5 70 true

# Show fuzzy matching scores
./utils/test_station_search.sh shinjuku 3 70 false true
```

#### `test_route_search.sh` - Simple Route Search Test
Test route search functionality between two stations.

**Usage:**
```bash
./utils/test_route_search.sh <from_station> <to_station>
```

**Examples:**
```bash
# Basic route search
./utils/test_route_search.sh shibuya shinjuku

# Japanese station names
./utils/test_route_search.sh 渋谷 新宿

# Longer distance route
./utils/test_route_search.sh tokyo yokohama

# Airport route
./utils/test_route_search.sh "haneda airport" shibuya
```

### 2. Comprehensive Testing Scripts

#### `test_mcp_station_search.sh` - Complete Station Search Test Suite
Runs multiple predefined test cases for station search functionality.

**Usage:**
```bash
./utils/test_mcp_station_search.sh
```

**Test Cases:**
- Basic station search
- Search with limit
- Fuzzy search with threshold
- Exact search
- Search with scores displayed
- Japanese hiragana search
- Kanji search
- No results test

#### `test_mcp_route_search.sh` - Complete Route Search Test Suite
Runs multiple predefined test cases for route search functionality.

**Usage:**
```bash
./utils/test_mcp_route_search.sh
```

**Test Cases:**
- Popular Tokyo routes
- Japanese station names
- Longer distance routes
- Mixed language input
- Airport routes
- Edge cases (same station, invalid stations)

## Prerequisites

1. **jq** - JSON processor for formatting output
   ```bash
   # Install on Ubuntu/Debian
   sudo apt install jq
   
   # Install on macOS
   brew install jq
   ```

2. **UV** - Python package manager (should already be installed)
3. **Timeout command** - For preventing hanging requests (usually pre-installed)

## How MCP Testing Works

The MCP server communicates via stdio (standard input/output) using JSON-RPC 2.0 protocol. The test scripts:

1. **Initialize** the MCP server with protocol handshake
2. **Send tool calls** with appropriate parameters
3. **Parse responses** and display results

## Available MCP Tools

### 1. `search_stations`
Search for Japanese train stations with fuzzy matching support.

**Parameters:**
- `query` (required): Station name or search keyword
- `limit` (optional): Maximum results (default: 10, max: 100)
- `fuzzy_threshold` (optional): Minimum match score 0-100 (default: 70)
- `exact` (optional): Exact matching only (default: false)
- `show_scores` (optional): Include matching scores (default: false)

### 2. `search_route`
Search for transit routes between two Japanese stations.

**Parameters:**
- `from_station` (required): Departure station name
- `to_station` (required): Destination station name

### 3. `get_station_info`
Get detailed information about a specific station.

**Parameters:**
- `station_name` (required): Exact station name

### 4. `list_station_database`
List all stations in the local database.

**Parameters:**
- `prefecture` (optional): Filter by prefecture
- `line` (optional): Filter by railway line
- `limit` (optional): Maximum results (default: 50, max: 1000)

## Troubleshooting

### Script Permissions
If you get permission denied errors:
```bash
chmod +x utils/*.sh
```

### Timeout Issues
If requests hang, the scripts use `timeout` to prevent blocking. You can adjust timeout values in the scripts if needed.

### JSON Parsing Errors
Make sure `jq` is installed for proper JSON formatting and parsing.

### Server Startup Issues
The MCP server needs to load station data on startup, which may take a few seconds. The timeout values in the scripts account for this.

## Example Output

### Station Search Output:
```
**Found 2 stations matching 'shibuya' (fuzzy (threshold: 70) search):**

1. **渋谷** (Code: 22715) - 東京都
   Line: 山手線
   Romaji: shibuya

2. **高座渋谷** (Code: 23155) - 神奈川県
   Line: 江ノ島線
   Romaji: kouzashibuya
```

### Route Search Output:
```
**Found 3 routes from shibuya to shinjuku:**

1. **Route 1: shibuya → shinjuku**
   • Duration: 17:32発→18:25着53分（乗車46分）
   • Cost: IC優先：1,163円（乗車券513円　特別料金650円）
   • Transfers: 1
   • Departure: 17:32:00
   • Arrival: 18:25:00
```

## Support

For issues with the MCP server itself, check the main project documentation and test suite in the `tests/` directory.