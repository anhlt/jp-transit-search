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
                            "search_type": {
                                "type": "string",
                                "description": "Route search preference: 'earliest' (fastest), 'cheapest' (lowest cost), or 'easiest' (fewest transfers)",
                                "enum": ["earliest", "cheapest", "easiest"],
                                "default": "earliest",
                            },
                        },
                        "required": ["from_station", "to_station"],
                    },
                ),
                Tool(
                    name="search_stations",
                    description="Search for Japanese train stations by name or keyword with fuzzy matching",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Station name or search keyword (supports romaji, kanji, hiragana, katakana)",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 100,
                            },
                            "fuzzy_threshold": {
                                "type": "integer",
                                "description": "Minimum fuzzy match score (0-100). Lower = more lenient matching",
                                "default": 70,
                                "minimum": 0,
                                "maximum": 100,
                            },
                            "exact": {
                                "type": "boolean",
                                "description": "If true, perform exact matching only (disables fuzzy search)",
                                "default": False,
                            },
                            "show_scores": {
                                "type": "boolean",
                                "description": "If true, include matching scores in results",
                                "default": False,
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
        search_type = arguments.get("search_type", "earliest")

        # Validate station names and warn about potential ambiguity
        validation_warnings = []
        if self._is_romaji_name(from_station):
            validation_warnings.append(
                f"Warning: '{from_station}' appears to be a romaji name. For better accuracy, consider using the Japanese name."
            )
        if self._is_romaji_name(to_station):
            validation_warnings.append(
                f"Warning: '{to_station}' appears to be a romaji name. For better accuracy, consider using the Japanese name."
            )

        try:
            routes = self.scraper.search_route(
                from_station, to_station, search_type=search_type
            )

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
            result_text = ""

            # Add validation warnings if any
            if validation_warnings:
                result_text += "⚠️  **Validation Warnings:**\n"
                for warning in validation_warnings:
                    result_text += f"   • {warning}\n"
                result_text += "\n"

            search_type_display = {
                "earliest": "fastest",
                "cheapest": "cheapest",
                "easiest": "easiest (fewest transfers)",
            }.get(search_type, search_type)

            result_text += f"**Found {len(routes_list)} routes from {from_station} to {to_station}** ({search_type_display} preference):**\n\n"

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
                        result_text += (
                            f" - {transfer.duration_minutes}min - ¥{transfer.cost_yen}"
                        )

                        # Add platform information if available
                        if transfer.departure_platform or transfer.arrival_platform:
                            platform_info = []
                            if transfer.departure_platform:
                                platform_info.append(
                                    f"From: {transfer.departure_platform}"
                                )
                            if transfer.arrival_platform:
                                platform_info.append(f"To: {transfer.arrival_platform}")
                            result_text += f" | Platform: {' | '.join(platform_info)}"

                        # Add riding position if available
                        if transfer.riding_position:
                            result_text += f" | Position: {transfer.riding_position}"

                        result_text += "\n"

                        # Add intermediate stations if available
                        if transfer.intermediate_stations:
                            result_text += "        Intermediate stations: "
                            station_names = [
                                f"{station.name} ({station.arrival_time})"
                                for station in transfer.intermediate_stations
                            ]
                            result_text += " → ".join(station_names) + "\n"
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

    def _is_romaji_name(self, name: str) -> bool:
        """Check if a station name appears to be in romaji (ASCII characters only)."""
        return name.isascii() and name.isalpha()

    async def _search_stations(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Search for stations by name or keyword with enhanced fuzzy matching."""
        query = arguments["query"]
        limit = arguments.get("limit", 10)
        fuzzy_threshold = arguments.get("fuzzy_threshold", 70)
        exact = arguments.get("exact", False)
        show_scores = arguments.get("show_scores", False)

        try:
            if show_scores:
                # Use fuzzy_search method that returns scores
                station_scores = self.station_searcher.fuzzy_search(
                    query, limit=limit, threshold=fuzzy_threshold
                )
                stations = [station for station, _score in station_scores]
                scores = [score for _station, score in station_scores]
            else:
                # Use regular search methods
                if exact:
                    stations = self.station_searcher.search_by_name(query, exact=True)[
                        :limit
                    ]
                else:
                    stations = self.station_searcher.search_stations(
                        query, limit=limit, fuzzy_threshold=fuzzy_threshold
                    )
                scores = None

            if not stations:
                search_type = (
                    "exact" if exact else f"fuzzy (threshold: {fuzzy_threshold})"
                )
                return [
                    TextContent(
                        type="text",
                        text=f"No stations found matching '{query}' with {search_type} search",
                    )
                ]

            # Build result text
            search_type = "exact" if exact else f"fuzzy (threshold: {fuzzy_threshold})"
            result_text = f"**Found {len(stations)} stations matching '{query}' ({search_type} search):**\n\n"

            for i, station in enumerate(stations, 1):
                result_text += f"{i}. **{station.name}**"
                if show_scores and scores:
                    result_text += f" (Score: {scores[i - 1]}%)"
                if station.station_id:
                    result_text += f" (Code: {station.station_id})"
                if station.prefecture:
                    result_text += f" - {station.prefecture}"
                if station.line_name:
                    result_text += f"\n   Line: {station.line_name}"
                if station.name_romaji:
                    result_text += f"\n   Romaji: {station.name_romaji}"
                result_text += "\n\n"

            # Also return JSON data with enhanced fields
            stations_data = []
            for i, s in enumerate(stations):
                station_data = {
                    "name": s.name,
                    "name_hiragana": s.name_hiragana,
                    "name_katakana": s.name_katakana,
                    "name_romaji": s.name_romaji,
                    "prefecture": s.prefecture,
                    "prefecture_id": s.prefecture_id,
                    "station_id": s.station_id,
                    "railway_company": s.railway_company,
                    "line_name": s.line_name,
                    "aliases": s.aliases,
                    "all_lines": s.all_lines,
                }
                if show_scores and scores:
                    station_data["search_score"] = scores[i]  # type: ignore[assignment]
                stations_data.append(station_data)

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

            if station.station_id:
                result_text += f"• **Station Code:** {station.station_id}\n"

            if station.prefecture:
                result_text += f"• **Prefecture:** {station.prefecture}\n"

            if station.line_name:
                result_text += f"• **Line:** {station.line_name}\n"

            if station.railway_company:
                result_text += f"• **Company:** {station.railway_company}\n"

            if station.name_hiragana:
                result_text += f"• **Hiragana:** {station.name_hiragana}\n"

            if station.name_katakana:
                result_text += f"• **Katakana:** {station.name_katakana}\n"

            if station.name_romaji:
                result_text += f"• **Romaji:** {station.name_romaji}\n"

            if station.all_lines:
                result_text += f"• **All Lines:** {', '.join(station.all_lines)}\n"

            station_data = {
                "name": station.name,
                "name_hiragana": station.name_hiragana,
                "name_katakana": station.name_katakana,
                "name_romaji": station.name_romaji,
                "prefecture": station.prefecture,
                "prefecture_id": station.prefecture_id,
                "station_id": station.station_id,
                "railway_company": station.railway_company,
                "line_name": station.line_name,
                "aliases": station.aliases,
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
                if station.station_id:
                    result_text += f" (Code: {station.station_id})"
                if station.prefecture:
                    result_text += f" - {station.prefecture}"
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
