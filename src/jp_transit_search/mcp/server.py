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
from ..core.models import Route
from ..core.scraper import YahooTransitScraper
from ..crawler.station_crawler import StationSearcher

logger = logging.getLogger(__name__)


class TransitMCPServer:
    """MCP Server for Japanese Transit Search functionality."""

    def __init__(self) -> None:
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
            routes = self.scraper.search_route(from_station, to_station)

            # Allow scraper to return either a single Route or a list of Route
            if isinstance(routes, Route):
                pass  # Will be normalized to list below
            elif isinstance(routes, (list, tuple)):
                if not routes:
                    return [TextContent(type="text", text="No routes found")]
            else:
                # Unknown return type from scraper
                return [
                    TextContent(
                        type="text",
                        text=(
                            "Route search returned an unexpected type. "
                            "Expected Route or list[Route]."
                        ),
                    )
                ]

            # Normalize to a list of routes for unified handling
            if isinstance(routes, Route):
                routes_list = [routes]
            else:
                routes_list = list(routes)

            if not routes_list:
                return [TextContent(type="text", text="No routes found")]

            # Build a human-readable summary for all found routes
            result_text = f"**Found {len(routes_list)} routes from {from_station} to {to_station}:**\n\n"

            for idx, r in enumerate(routes_list, 1):
                result_text += (
                    f"{idx}. **Route {idx}: {r.from_station} → {r.to_station}**\n"
                )
                result_text += f"   • Duration: {r.duration}\n"
                result_text += f"   • Cost: {r.cost}\n"
                result_text += f"   • Transfers: {r.transfer_count}\n"
                result_text += f"   • Departure: {r.departure_time or 'N/A'}\n"
                result_text += f"   • Arrival: {r.arrival_time or 'N/A'}\n"

                # Add per-route transfer details
                if r.transfers:
                    result_text += "   Route Details:\n"
                    for t_i, transfer in enumerate(r.transfers, 1):
                        result_text += f"     {t_i}. {transfer.from_station} → {transfer.to_station}"
                        if transfer.line_name:
                            result_text += f" ({transfer.line_name})"
                        result_text += f" - {transfer.duration_minutes}min - ¥{transfer.cost_yen}\n"
                result_text += "\n"

            # JSON representation as a list
            routes_data = [r.model_dump(mode="json") for r in routes_list]

            return [
                TextContent(type="text", text=result_text),
                TextContent(
                    type="text",
                    text=f"JSON Data:\n```json\n{json.dumps(routes_data, indent=2, ensure_ascii=False)}\n```",
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
                    "prefecture_id": s.prefecture_id,
                    "station_id": s.station_id,
                    "railway_company": s.railway_company,
                    "line_name": s.line_name,
                    "aliases": s.aliases,
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

            if station.railway_company:
                result_text += f"• **Company:** {station.railway_company}\n"

            if station.line_name:
                result_text += f"• **Line:** {station.line_name}\n"

            if station.line_type:
                result_text += f"• **Line Type:** {station.line_type}\n"

            if station.company_code:
                result_text += f"• **Company Code:** {station.company_code}\n"

            if station.all_lines:
                result_text += f"• **All Lines:** {', '.join(station.all_lines)}\n"

            station_data = {
                "name": station.name,
                "prefecture": station.prefecture,
                "prefecture_id": station.prefecture_id,
                "station_id": station.station_id,
                "railway_company": station.railway_company,
                "line_name": station.line_name,
                "aliases": station.aliases,
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
