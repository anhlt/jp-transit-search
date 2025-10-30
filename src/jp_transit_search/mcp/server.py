"""MCP Server for Japanese Transit Search.

This module implements a Model Context Protocol (MCP) server that exposes
Japanese transit route search and station management functionality.
"""

import asyncio
import json
import logging
from typing import Any

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.types import (
    TextContent,
    Tool,
)

from ..core.exceptions import (
    NetworkError,
    RouteNotFoundError,
    ScrapingError,
    ValidationError,
)
from ..core.scraper import YahooTransitScraper
from ..crawler.station_crawler import StationSearcher

logger = logging.getLogger(__name__)


class TransitMCPServer:
    """MCP Server for Japanese Transit Search functionality."""

    def __init__(self):
        """Initialize the Transit MCP Server."""
        self.server = Server("jp-transit-search")
        self.scraper = YahooTransitScraper()

        # Initialize station searcher with empty list initially
        self.station_searcher = StationSearcher([])

        # Load existing stations if available (read-only)
        self._load_stations()

        # Register handlers
        self._register_handlers()

    def _load_stations(self) -> None:
        """Load stations from CSV file (read-only)."""
        from pathlib import Path

        try:
            # Try to load from CSV file only (read-only mode)
            csv_file = Path("data/stations.csv")
            if csv_file.exists():
                logger.info(f"Loading stations from CSV file: {csv_file}")
                # Import StationCrawler only for loading CSV
                from ..crawler.station_crawler import StationCrawler

                temp_crawler = StationCrawler()
                stations = temp_crawler.load_from_csv(csv_file)
                self.station_searcher = StationSearcher(stations)
                logger.info(f"Loaded {len(stations)} stations from CSV")
                return

            # If no CSV file exists, start with empty list
            logger.warning(
                "No CSV file found at data/stations.csv. Starting with empty station list."
            )
            logger.info(
                "Use GitHub Action with '/update_station' comment to generate station data."
            )
            self.station_searcher = StationSearcher([])

        except Exception as e:
            logger.warning(
                f"Failed to load stations: {e}. Starting with empty station list."
            )
            self.station_searcher = StationSearcher([])

    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""

        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="search_route",
                    description="Search for transit routes between two Japanese stations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "from_station": {
                                "type": "string",
                                "description": "Departure station name (in Japanese or English)",
                            },
                            "to_station": {
                                "type": "string",
                                "description": "Destination station name (in Japanese or English)",
                            },
                        },
                        "required": ["from_station", "to_station"],
                    },
                ),
                Tool(
                    name="search_stations",
                    description="Search for Japanese train stations by name or keyword",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Station name or search keyword",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 100,
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="get_station_info",
                    description="Get detailed information about a specific Japanese train station",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "station_name": {
                                "type": "string",
                                "description": "Exact station name",
                            }
                        },
                        "required": ["station_name"],
                    },
                ),
                Tool(
                    name="list_station_database",
                    description="List all stations in the local database",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "prefecture": {
                                "type": "string",
                                "description": "Filter by prefecture (optional)",
                            },
                            "line": {
                                "type": "string",
                                "description": "Filter by railway line name (optional)",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 50,
                                "minimum": 1,
                                "maximum": 1000,
                            },
                        },
                    },
                ),
            ]

        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: dict[str, Any]
        ) -> list[TextContent]:
            """Handle tool calls."""
            try:
                if name == "search_route":
                    return await self._search_route(arguments)
                elif name == "search_stations":
                    return await self._search_stations(arguments)
                elif name == "get_station_info":
                    return await self._get_station_info(arguments)
                elif name == "list_station_database":
                    return await self._list_station_database(arguments)
                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]

            except Exception as e:
                logger.error(f"Error in tool {name}: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def _search_route(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Search for transit routes between stations."""
        from_station = arguments["from_station"]
        to_station = arguments["to_station"]

        try:
            route = self.scraper.search_route(from_station, to_station)

            # Format the route information
            route_info = {
                "from_station": route.from_station,
                "to_station": route.to_station,
                "duration": route.duration,
                "cost": route.cost,
                "transfer_count": route.transfer_count,
                "departure_time": route.departure_time.isoformat()
                if route.departure_time
                else None,
                "arrival_time": route.arrival_time.isoformat()
                if route.arrival_time
                else None,
                "transfers": [
                    {
                        "from_station": t.from_station,
                        "to_station": t.to_station,
                        "line_name": t.line_name,
                        "duration_minutes": t.duration_minutes,
                        "cost_yen": t.cost_yen,
                    }
                    for t in route.transfers
                ],
            }

            result_text = f"""
**Route from {route.from_station} to {route.to_station}**

• **Duration:** {route.duration}
• **Cost:** {route.cost}
• **Transfers:** {route.transfer_count}
• **Departure:** {route.departure_time or "N/A"}
• **Arrival:** {route.arrival_time or "N/A"}

**Route Details:**
"""

            for i, transfer in enumerate(route.transfers, 1):
                result_text += f"\n{i}. {transfer.from_station} → {transfer.to_station}"
                if transfer.line_name:
                    result_text += f" ({transfer.line_name})"
                result_text += (
                    f" - {transfer.duration_minutes}min - ¥{transfer.cost_yen}"
                )

            return [
                TextContent(type="text", text=result_text),
                TextContent(
                    type="text",
                    text=f"\nJSON Data:\n```json\n{json.dumps(route_info, indent=2, ensure_ascii=False)}\n```",
                ),
            ]

        except (ValidationError, RouteNotFoundError, ScrapingError, NetworkError) as e:
            return [TextContent(type="text", text=f"Route search failed: {str(e)}")]

    async def _search_stations(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Search for stations by name or keyword."""
        query = arguments["query"]
        limit = arguments.get("limit", 10)

        try:
            stations = self.station_searcher.search_stations(query, limit=limit)

            if not stations:
                return [
                    TextContent(
                        type="text", text=f"No stations found matching '{query}'"
                    )
                ]

            result_text = f"**Found {len(stations)} stations matching '{query}':**\n\n"

            for i, station in enumerate(stations, 1):
                result_text += f"{i}. **{station.name}**"
                if station.prefecture:
                    result_text += f" - {station.prefecture}"
                if station.city:
                    result_text += f", {station.city}"
                if station.railway_company:
                    result_text += f"\n   Company: {station.railway_company}"
                if station.line_name:
                    result_text += f"\n   Line: {station.line_name}"
                result_text += "\n\n"

            # Also return JSON data with enhanced fields
            stations_data = [
                {
                    "name": s.name,
                    "prefecture": s.prefecture,
                    "city": s.city,
                    "railway_company": s.railway_company,
                    "line_name": s.line_name,
                    "station_code": s.station_code,
                    "location": {"lat": s.latitude, "lng": s.longitude}
                    if s.latitude and s.longitude
                    else None,
                    "aliases": s.aliases,
                    "line_name_kana": s.line_name_kana,
                    "line_color": s.line_color,
                    "line_type": s.line_type,
                    "company_code": s.company_code,
                    "all_lines": s.all_lines,
                }
                for s in stations
            ]

            return [
                TextContent(type="text", text=result_text),
                TextContent(
                    type="text",
                    text=f"JSON Data:\n```json\n{json.dumps(stations_data, indent=2, ensure_ascii=False)}\n```",
                ),
            ]

        except Exception as e:
            return [TextContent(type="text", text=f"Station search failed: {str(e)}")]

    async def _get_station_info(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Get detailed information about a specific station."""
        station_name = arguments["station_name"]

        try:
            station = self.station_searcher.get_station_by_name(station_name)

            if not station:
                return [
                    TextContent(type="text", text=f"Station '{station_name}' not found")
                ]

            result_text = f"**{station.name}**\n\n"

            if station.prefecture:
                result_text += f"• **Prefecture:** {station.prefecture}\n"

            if station.city:
                result_text += f"• **City:** {station.city}\n"

            if station.railway_company:
                result_text += f"• **Company:** {station.railway_company}\n"

            if station.line_name:
                result_text += f"• **Line:** {station.line_name}\n"

            if station.station_code:
                result_text += f"• **Code:** {station.station_code}\n"

            if station.latitude and station.longitude:
                result_text += (
                    f"• **Location:** {station.latitude}, {station.longitude}\n"
                )

            station_data = {
                "name": station.name,
                "prefecture": station.prefecture,
                "city": station.city,
                "railway_company": station.railway_company,
                "line_name": station.line_name,
                "station_code": station.station_code,
                "location": {"lat": station.latitude, "lng": station.longitude}
                if station.latitude and station.longitude
                else None,
                "aliases": station.aliases,
                "line_name_kana": station.line_name_kana,
                "line_color": station.line_color,
                "line_type": station.line_type,
                "company_code": station.company_code,
                "all_lines": station.all_lines,
            }

            return [
                TextContent(type="text", text=result_text),
                TextContent(
                    type="text",
                    text=f"\nJSON Data:\n```json\n{json.dumps(station_data, indent=2, ensure_ascii=False)}\n```",
                ),
            ]

        except Exception as e:
            return [
                TextContent(type="text", text=f"Failed to get station info: {str(e)}")
            ]

    async def _list_station_database(
        self, arguments: dict[str, Any]
    ) -> list[TextContent]:
        """List stations from the local database."""
        prefecture = arguments.get("prefecture")
        line = arguments.get("line")
        limit = arguments.get("limit", 50)

        try:
            stations = self.station_searcher.list_stations(
                prefecture=prefecture, line=line, limit=limit
            )

            if not stations:
                filter_desc = ""
                if prefecture or line:
                    filters = []
                    if prefecture:
                        filters.append(f"prefecture: {prefecture}")
                    if line:
                        filters.append(f"line: {line}")
                    filter_desc = f" with filters ({', '.join(filters)})"

                return [
                    TextContent(type="text", text=f"No stations found{filter_desc}")
                ]

            result_text = f"**Station Database ({len(stations)} stations"
            if prefecture:
                result_text += f", prefecture: {prefecture}"
            if line:
                result_text += f", line: {line}"
            result_text += "):**\n\n"

            for i, station in enumerate(stations, 1):
                result_text += f"{i}. **{station.name}**"
                if station.prefecture:
                    result_text += f" - {station.prefecture}"
                if station.city:
                    result_text += f", {station.city}"
                if station.railway_company:
                    result_text += f"\n   Company: {station.railway_company}"
                if station.line_name:
                    result_text += f"\n   Line: {station.line_name}"
                result_text += "\n\n"

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            return [TextContent(type="text", text=f"Failed to list stations: {str(e)}")]


async def main() -> None:
    """Main entry point for the MCP server."""
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Japanese Transit Search MCP Server")

    # Create the server
    server_instance = TransitMCPServer()

    # Run the server with stdio transport using the correct MCP approach
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        logger.info("MCP Server running with stdio transport")
        await server_instance.server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="jp-transit-search",
                server_version="1.0.0",
                capabilities=server_instance.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main_sync() -> None:
    """Synchronous wrapper for the async main function - used as entry point."""
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
