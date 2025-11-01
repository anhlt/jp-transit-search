#!/bin/bash

# Test script for MCP route search functionality
# This script tests the search_route tool via stdio communication

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== MCP Route Search Test Script ===${NC}"
echo

# Function to send MCP request and get response
send_mcp_request() {
    local tool_name="$1"
    local arguments="$2"
    local call_id="call_$(date +%s)"
    
    # Create initialization request (single line)
    local init_request='{"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}'
    
    # Create the MCP tool call request (single line)
    local request="{\"jsonrpc\": \"2.0\", \"id\": \"$call_id\", \"method\": \"tools/call\", \"params\": {\"name\": \"$tool_name\", \"arguments\": $arguments}}"
    
    echo -e "${YELLOW}Sending request for $tool_name:${NC}"
    echo "$request" | jq .
    echo
    
    # Send both initialization and tool call requests to MCP server
    echo -e "$init_request\n$request" | timeout 15s uv run jp-transit-mcp | grep -E "^\{.*\}$" | tail -1 | jq .
}

# Test 1: Basic route search - popular Tokyo route
echo -e "${GREEN}Test 1: Route search from Shibuya to Shinjuku${NC}"
send_mcp_request "search_route" '{"from_station": "shibuya", "to_station": "shinjuku"}'
echo -e "\n${BLUE}--- End Test 1 ---${NC}\n"

# Test 2: Route search with Japanese station names
echo -e "${GREEN}Test 2: Route search using Japanese station names${NC}"
send_mcp_request "search_route" '{"from_station": "渋谷", "to_station": "新宿"}'
echo -e "\n${BLUE}--- End Test 2 ---${NC}\n"

# Test 3: Longer distance route
echo -e "${GREEN}Test 3: Longer route from Tokyo to Yokohama${NC}"
send_mcp_request "search_route" '{"from_station": "tokyo", "to_station": "yokohama"}'
echo -e "\n${BLUE}--- End Test 3 ---${NC}\n"

# Test 4: Route with mixed Japanese/English input
echo -e "${GREEN}Test 4: Mixed language input (English to Japanese)${NC}"
send_mcp_request "search_route" '{"from_station": "shibuya", "to_station": "品川"}'
echo -e "\n${BLUE}--- End Test 4 ---${NC}\n"

# Test 5: Airport route (practical use case)
echo -e "${GREEN}Test 5: Route to Haneda Airport${NC}"
send_mcp_request "search_route" '{"from_station": "shimbashi", "to_station": "haneda airport"}'
echo -e "\n${BLUE}--- End Test 5 ---${NC}\n"

# Test 6: Route with hiragana input
echo -e "${GREEN}Test 6: Hiragana station names${NC}"
send_mcp_request "search_route" '{"from_station": "しんじゅく", "to_station": "しぶや"}'
echo -e "\n${BLUE}--- End Test 6 ---${NC}\n"

# Test 7: Inter-city route (if supported)
echo -e "${GREEN}Test 7: Route from Tokyo to Osaka (if supported)${NC}"
send_mcp_request "search_route" '{"from_station": "tokyo", "to_station": "osaka"}'
echo -e "\n${BLUE}--- End Test 7 ---${NC}\n"

# Test 8: Invalid/non-existent route
echo -e "${GREEN}Test 8: Invalid station names (should handle gracefully)${NC}"
send_mcp_request "search_route" '{"from_station": "nonexistent1", "to_station": "nonexistent2"}'
echo -e "\n${BLUE}--- End Test 8 ---${NC}\n"

# Test 9: Same station (edge case)
echo -e "${GREEN}Test 9: Same departure and destination station${NC}"
send_mcp_request "search_route" '{"from_station": "shibuya", "to_station": "shibuya"}'
echo -e "\n${BLUE}--- End Test 9 ---${NC}\n"

echo -e "${BLUE}=== All Route Search Tests Complete ===${NC}"