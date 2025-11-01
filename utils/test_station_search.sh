#!/bin/bash

# Simple MCP Station Search Test
# This script provides an easy way to test individual station searches

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Simple MCP Station Search Test ===${NC}"
echo

# Check if query is provided
if [ $# -eq 0 ]; then
    echo -e "${YELLOW}Usage: $0 <station_query> [limit] [fuzzy_threshold] [exact] [show_scores]${NC}"
    echo
    echo "Examples:"
    echo "  $0 shibuya"
    echo "  $0 tokyo 5"
    echo "  $0 shibya 10 50"
    echo "  $0 渋谷 5 70 true"
    echo "  $0 shinjuku 3 70 false true"
    exit 1
fi

query="$1"
limit="${2:-10}"
fuzzy_threshold="${3:-70}"
exact="${4:-false}"
show_scores="${5:-false}"

echo -e "${GREEN}Searching for stations matching: '$query'${NC}"
echo "Parameters: limit=$limit, fuzzy_threshold=$fuzzy_threshold, exact=$exact, show_scores=$show_scores"
echo

# Create the MCP requests (each must be on a single line)
init_request='{"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}'

search_request="{\"jsonrpc\": \"2.0\", \"id\": \"search_$(date +%s)\", \"method\": \"tools/call\", \"params\": {\"name\": \"search_stations\", \"arguments\": {\"query\": \"$query\", \"limit\": $limit, \"fuzzy_threshold\": $fuzzy_threshold, \"exact\": $exact, \"show_scores\": $show_scores}}}"

# Send requests and get response
echo -e "$init_request\n$search_request" | timeout 15s uv run jp-transit-mcp | grep -E "^\{.*\}$" | tail -1 | jq -r '.result.content[0].text'