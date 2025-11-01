#!/bin/bash

# Test script for MCP station search functionality
# This script tests the search_stations tool via stdio communication

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== MCP Station Search Test Script ===${NC}"
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

# Test 1: Basic station search
echo -e "${GREEN}Test 1: Basic station search for 'shibuya'${NC}"
send_mcp_request "search_stations" '{"query": "shibuya"}'
echo -e "\n${BLUE}--- End Test 1 ---${NC}\n"

# Test 2: Station search with limit
echo -e "${GREEN}Test 2: Station search with limit (3 results)${NC}"
send_mcp_request "search_stations" '{"query": "tokyo", "limit": 3}'
echo -e "\n${BLUE}--- End Test 2 ---${NC}\n"

# Test 3: Fuzzy search with threshold
echo -e "${GREEN}Test 3: Fuzzy search with lower threshold${NC}"
send_mcp_request "search_stations" '{"query": "shibya", "fuzzy_threshold": 50}'
echo -e "\n${BLUE}--- End Test 3 ---${NC}\n"

# Test 4: Exact search
echo -e "${GREEN}Test 4: Exact search (no fuzzy matching)${NC}"
send_mcp_request "search_stations" '{"query": "渋谷", "exact": true}'
echo -e "\n${BLUE}--- End Test 4 ---${NC}\n"

# Test 5: Search with scores displayed
echo -e "${GREEN}Test 5: Search with fuzzy scores displayed${NC}"
send_mcp_request "search_stations" '{"query": "shinjuku", "show_scores": true, "limit": 5}'
echo -e "\n${BLUE}--- End Test 5 ---${NC}\n"

# Test 6: Japanese search (hiragana)
echo -e "${GREEN}Test 6: Japanese hiragana search${NC}"
send_mcp_request "search_stations" '{"query": "しんじゅく"}'
echo -e "\n${BLUE}--- End Test 6 ---${NC}\n"

# Test 7: Kanji search
echo -e "${GREEN}Test 7: Kanji search${NC}"
send_mcp_request "search_stations" '{"query": "新宿"}'
echo -e "\n${BLUE}--- End Test 7 ---${NC}\n"

# Test 8: No results test
echo -e "${GREEN}Test 8: Search that should return no results${NC}"
send_mcp_request "search_stations" '{"query": "nonexistentstation123", "exact": true}'
echo -e "\n${BLUE}--- End Test 8 ---${NC}\n"

echo -e "${BLUE}=== All Station Search Tests Complete ===${NC}"