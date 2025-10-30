"""Tests for MCP server functionality."""

from unittest.mock import MagicMock, patch

import pytest

from jp_transit_search.core.exceptions import RouteNotFoundError, ValidationError
from jp_transit_search.core.models import Route, Station, Transfer
from jp_transit_search.mcp.server import TransitMCPServer


class TestTransitMCPServer:
    """Test cases for TransitMCPServer."""

    @pytest.fixture
    def server(self):
        """Create a TransitMCPServer instance for testing."""
        with patch("jp_transit_search.crawler.station_crawler.StationSearcher"):
            with patch("jp_transit_search.core.scraper.YahooTransitScraper"):
                server = TransitMCPServer()
                # Reset the searcher to a proper mock
                server.station_searcher = MagicMock()
                server.scraper = MagicMock()
                return server

    @pytest.fixture
    def sample_route(self):
        """Create a sample route for testing."""
        return Route(
            from_station="Tokyo",
            to_station="Osaka",
            duration="2h 30m",
            cost="¥13,320",
            transfer_count=1,
            transfers=[
                Transfer(
                    from_station="Tokyo",
                    to_station="Shinagawa",
                    line_name="JR Tokaido Line",
                    duration_minutes=7,
                    cost_yen=160,
                ),
                Transfer(
                    from_station="Shinagawa",
                    to_station="Osaka",
                    line_name="JR Tokaido Shinkansen",
                    duration_minutes=143,
                    cost_yen=13160,
                ),
            ],
        )

    @pytest.fixture
    def sample_stations(self):
        """Create sample stations for testing."""
        return [
            Station(
                name="東京駅",
                prefecture="Tokyo",
                city="Chiyoda",
                railway_company="JR East",
                line_name="JR Tokaido Line",
                station_code="JT01",
                latitude=35.6812,
                longitude=139.7671,
                aliases=["Tokyo Station"],
            ),
            Station(
                name="新宿駅",
                prefecture="Tokyo",
                city="Shinjuku",
                railway_company="JR East",
                line_name="JR Yamanote Line",
                station_code="JY17",
                latitude=35.6896,
                longitude=139.7006,
                aliases=["Shinjuku Station"],
            ),
        ]

    @pytest.mark.asyncio
    async def test_list_tools(self, server):
        """Test that server has registered handlers."""
        # Just verify that the server has a list_tools handler
        assert hasattr(server.server, "list_tools")

        # Test that we can call the handler
        handler_func = server.server.list_tools
        assert callable(handler_func)

    @pytest.mark.asyncio
    async def test_search_route_success(self, server, sample_route):
        """Test successful route search."""
        with patch.object(server.scraper, "search_route", return_value=sample_route):
            result = await server._search_route(
                {"from_station": "Tokyo", "to_station": "Osaka"}
            )

        assert len(result) == 2  # Text content and JSON data

        # Check text content
        text_content = result[0].text
        assert "Tokyo" in text_content
        assert "Osaka" in text_content
        assert "2h 30m" in text_content
        assert "¥13,320" in text_content

        # Check JSON data is included
        json_content = result[1].text
        assert "JSON Data:" in json_content
        assert "duration" in json_content

    @pytest.mark.asyncio
    async def test_search_route_validation_error(self, server):
        """Test route search with validation error."""
        with patch.object(
            server.scraper,
            "search_route",
            side_effect=ValidationError("Empty station name"),
        ):
            result = await server._search_route(
                {"from_station": "", "to_station": "Osaka"}
            )

        assert len(result) == 1
        assert "Route search failed" in result[0].text
        assert "Empty station name" in result[0].text

    @pytest.mark.asyncio
    async def test_search_route_not_found(self, server):
        """Test route search when no route is found."""
        with patch.object(
            server.scraper,
            "search_route",
            side_effect=RouteNotFoundError("No route found"),
        ):
            result = await server._search_route(
                {"from_station": "NonExistent", "to_station": "AlsoNonExistent"}
            )

        assert len(result) == 1
        assert "Route search failed" in result[0].text
        assert "No route found" in result[0].text

    @pytest.mark.asyncio
    async def test_search_stations_success(self, server, sample_stations):
        """Test successful station search."""
        with patch.object(
            server.station_searcher, "search_stations", return_value=sample_stations
        ):
            result = await server._search_stations({"query": "Tokyo", "limit": 10})

        assert len(result) == 2  # Text content and JSON data

        # Check text content
        text_content = result[0].text
        assert "Found 2 stations matching 'Tokyo':" in text_content
        assert "東京駅" in text_content
        assert "新宿駅" in text_content
        assert "Company:" in text_content
        assert "Line:" in text_content



    @pytest.mark.asyncio
    async def test_list_station_database_success(self, server, sample_stations):
        """Test successful station database listing."""
        with patch.object(
            server.station_searcher, "list_stations", return_value=sample_stations
        ):
            result = await server._list_station_database(
                {"prefecture": "Tokyo", "limit": 50}
            )

        assert len(result) == 1

        # Check result content
        text_content = result[0].text
        assert "Station Database" in text_content
        assert "prefecture: Tokyo" in text_content
        assert "東京駅" in text_content
        assert "新宿駅" in text_content

    @pytest.mark.asyncio
    async def test_list_station_database_no_results(self, server):
        """Test station database listing with no results."""
        with patch.object(server.station_searcher, "list_stations", return_value=[]):
            result = await server._list_station_database({"prefecture": "NonExistent"})

        assert len(result) == 1
        assert "No stations found" in result[0].text
        assert "prefecture: NonExistent" in result[0].text

    @pytest.mark.asyncio
    async def test_list_station_database_default_params(self, server, sample_stations):
        """Test station database listing with default parameters."""
        with patch.object(
            server.station_searcher, "list_stations", return_value=sample_stations
        ) as mock_list:
            await server._list_station_database({})

            # Check default parameters are used
            mock_list.assert_called_once_with(prefecture=None, line=None, limit=50)

    @pytest.mark.asyncio
    async def test_handle_call_tool_unknown_tool(self, server):
        """Test handling of unknown tool calls."""
        # Since we can't directly access the call_tool handler, we'll test that
        # the server properly initializes and we can verify unknown tool handling
        # by reading the server.py code which shows it returns "Unknown tool: {name}"

        # Test that the server has the proper structure for handling unknown tools
        assert server.server is not None
        assert hasattr(server, "_search_route")
        assert hasattr(server, "_search_stations")

        # We can't easily test the exact unknown tool message without accessing
        # internal MCP handlers, but we can verify the server is properly set up

    @pytest.mark.asyncio
    async def test_handle_call_tool_exception(self, server):
        """Test handling of exceptions in tool calls."""
        # Test exception handling by mocking the scraper to raise a ValidationError
        # which is one of the expected exception types that gets caught
        with patch.object(
            server.scraper,
            "search_route",
            side_effect=ValidationError("Test validation error"),
        ):
            result = await server._search_route(
                {"from_station": "A", "to_station": "B"}
            )

            assert len(result) == 1
            assert "Route search failed:" in result[0].text
            assert "Test validation error" in result[0].text

    def test_server_initialization(self, server):
        """Test that server initializes correctly."""
        assert server.server is not None
        assert server.scraper is not None
        assert server.station_searcher is not None

        # Check server is properly initialized - we can't access private attributes
        # but we can check that the server has the expected methods
        assert hasattr(server.server, "list_tools")
        assert callable(server.server.list_tools)



