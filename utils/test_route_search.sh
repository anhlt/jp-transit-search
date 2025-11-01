#!/bin/bash

# Simple MCP Route Search Test
# This script provides an easy way to test individual route searches

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Simple MCP Route Search Test ===${NC}"
echo

# Check if both stations are provided
if [ $# -lt 2 ]; then
    echo -e "${YELLOW}Usage: $0 <from_station> <to_station> [search_type]${NC}"
    echo
    echo "Parameters:"
    echo "  from_station   - Departure station name"
    echo "  to_station     - Destination station name"
    echo "  search_type    - Optional: 'earliest' (default), 'cheapest', or 'easiest'"
    echo
    echo "Examples:"
    echo "  $0 shibuya shinjuku"
    echo "  $0 渋谷 新宿 cheapest"
    echo "  $0 tokyo yokohama easiest"
    echo "  $0 'haneda airport' shibuya earliest"
    exit 1
fi

from_station="$1"
to_station="$2"
search_type="${3:-earliest}"

echo -e "${GREEN}Searching route from '$from_station' to '$to_station' (${search_type})${NC}"
echo

# Create the MCP requests (each must be on a single line)
init_request='{"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}'

route_request="{\"jsonrpc\": \"2.0\", \"id\": \"route_$(date +%s)\", \"method\": \"tools/call\", \"params\": {\"name\": \"search_route\", \"arguments\": {\"from_station\": \"$from_station\", \"to_station\": \"$to_station\", \"search_type\": \"$search_type\"}}}"

# Send requests and get response
echo -e "$init_request\n$route_request" | timeout 30s uv run jp-transit-mcp | grep -E "^\{.*\}$" | tail -1 | jq -r '.result.content[0].text'