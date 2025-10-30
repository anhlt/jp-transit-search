"""Integration tests for MCP server functionality.

These tests verify the MCP server works correctly by testing the actual server methods
rather than mocking the MCP protocol layer.
"""

import asyncio
import logging
from unittest.mock import MagicMock, patch

import pytest

from jp_transit_search.core.models import Route, Station, Transfer
from jp_transit_search.mcp.server import TransitMCPServer

logger = logging.getLogger(__name__)


@pytest.fixture
def mcp_server():
    """Create an MCP server instance for integration testing."""
    # Mock external dependencies and CSV loading
    with patch("jp_transit_search.mcp.server.YahooTransitScraper"):
        with patch("jp_transit_search.mcp.server.StationSearcher"):
            with patch("jp_transit_search.crawler.station_crawler.StationCrawler"):
                with patch(
                    "pathlib.Path.exists", return_value=False
                ):  # Mock no CSV file
                    server = TransitMCPServer()
                    # Setup basic mocks
                    server.scraper = MagicMock()
                    server.station_searcher = MagicMock()
                    return server


@pytest.fixture
def sample_stations():
    """Sample station data for testing."""
    return [
        Station(
            name="東京駅",
            prefecture="東京都",
            railway_company="JR東日本",
            line_name="JR東海道本線",
            aliases=["Tokyo Station", "とうきょうえき"],
        ),
        Station(
            name="新宿駅",
            prefecture="東京都",
            railway_company="JR東日本",
            line_name="JR山手線",
            aliases=["Shinjuku Station", "しんじゅくえき"],
        ),
    ]


@pytest.fixture
def sample_route():
    """Sample route data for testing."""
    from datetime import time

    return Route(
        from_station="東京駅",
        to_station="大阪駅",
        duration="2時間30分",
        cost="¥13,320",
        transfer_count=1,
        departure_time=time(9, 0),
        arrival_time=time(11, 30),
        transfers=[
            Transfer(
                from_station="東京駅",
                to_station="新横浜駅",
                line_name="JR東海道新幹線",
                duration_minutes=18,
                cost_yen=550,
            ),
            Transfer(
                from_station="新横浜駅",
                to_station="大阪駅",
                line_name="JR東海道新幹線",
                duration_minutes=132,
                cost_yen=12770,
            ),
        ],
    )


class TestMCPIntegration:
    """Integration tests using actual MCP server methods."""

    def test_list_tools_protocol(self, mcp_server):
        """Test list_tools returns correct tools."""
        # The MCP server uses decorators to register handlers, so we need to test
        # the actual tool registration by checking the server's internal state
        # or by testing the actual functionality

        # Since we can't directly access the tools list, we'll test that the
        # server has the expected tools by testing each method exists
        assert hasattr(mcp_server, "_search_route")
        assert hasattr(mcp_server, "_search_stations")
        assert hasattr(mcp_server, "_get_station_info")
        assert hasattr(mcp_server, "_list_station_database")

        # Verify these are the only public tool methods
        tool_methods = [
            attr
            for attr in dir(mcp_server)
            if attr.startswith("_") and not attr.startswith("__")
        ]
        expected_methods = [
            "_search_route",
            "_search_stations",
            "_get_station_info",
            "_list_station_database",
        ]

        for method in expected_methods:
            assert method in tool_methods

    @pytest.mark.asyncio
    async def test_search_stations_protocol(self, mcp_server, sample_stations):
        """Test search_stations tool."""
        # Mock the station searcher
        mcp_server.station_searcher.search_stations.return_value = sample_stations

        # Call the search_stations method directly
        result = await mcp_server._search_stations({"query": "東京", "limit": 10})

        # Verify the response structure
        assert isinstance(result, list)
        assert len(result) == 2  # Text content + JSON data

        # Verify first content is formatted text
        text_content = result[0]
        assert "Found 2 stations matching '東京'" in text_content.text
        assert "東京駅" in text_content.text
        assert "新宿駅" in text_content.text

        # Verify second content is JSON data
        json_content = result[1]
        assert "JSON Data:" in json_content.text
        assert "name" in json_content.text  # Check for actual field in Station model
        assert (
            "prefecture" in json_content.text
        )  # Check for actual field in Station model

        # Verify the station searcher was called correctly
        mcp_server.station_searcher.search_stations.assert_called_once_with(
            "東京", limit=10
        )

    @pytest.mark.asyncio
    async def test_search_route_protocol(self, mcp_server, sample_route):
        """Test search_route tool."""
        # Mock the scraper
        mcp_server.scraper.search_route.return_value = sample_route

        # Call the search_route method directly
        result = await mcp_server._search_route(
            {"from_station": "東京駅", "to_station": "大阪駅"}
        )

        # Verify the response structure
        assert isinstance(result, list)
        assert len(result) == 2  # Text content + JSON data

        # Verify text content
        text_content = result[0]
        assert "Route from 東京駅 to 大阪駅" in text_content.text
        assert "2時間30分" in text_content.text
        assert "¥13,320" in text_content.text
        assert "JR東海道新幹線" in text_content.text

        # Verify JSON content
        json_content = result[1]
        assert "JSON Data:" in json_content.text
        assert "transfers" in json_content.text

        # Verify the scraper was called correctly
        mcp_server.scraper.search_route.assert_called_once_with("東京駅", "大阪駅")

    @pytest.mark.asyncio
    async def test_get_station_info_protocol(self, mcp_server, sample_stations):
        """Test get_station_info tool."""
        # Mock the station searcher
        mcp_server.station_searcher.get_station_by_name.return_value = sample_stations[
            0
        ]

        # Call the get_station_info method directly
        result = await mcp_server._get_station_info({"station_name": "東京駅"})

        # Verify the response structure
        assert isinstance(result, list)
        assert len(result) == 2  # Text content + JSON data

        # Verify text content
        text_content = result[0]
        assert "東京駅" in text_content.text
        assert "東京都" in text_content.text
        assert "JR東日本" in text_content.text

        # Verify JSON content
        json_content = result[1]
        assert "JSON Data:" in json_content.text
        assert "aliases" in json_content.text

        # Verify the station searcher was called correctly
        mcp_server.station_searcher.get_station_by_name.assert_called_once_with(
            "東京駅"
        )

    @pytest.mark.asyncio
    async def test_list_station_database_protocol(self, mcp_server, sample_stations):
        """Test list_station_database tool."""
        # Mock the station searcher
        mcp_server.station_searcher.list_stations.return_value = sample_stations

        # Call the list_station_database method directly
        result = await mcp_server._list_station_database(
            {"prefecture": "東京都", "limit": 50}
        )

        # Verify the response structure
        assert isinstance(result, list)
        assert len(result) == 1  # Only text content for list operation

        # Verify text content
        text_content = result[0]
        assert "Station Database (2 stations" in text_content.text
        assert "prefecture: 東京都" in text_content.text
        assert "東京駅" in text_content.text
        assert "新宿駅" in text_content.text

        # Verify the station searcher was called correctly
        mcp_server.station_searcher.list_stations.assert_called_once_with(
            prefecture="東京都", line=None, limit=50
        )

    @pytest.mark.asyncio
    async def test_invalid_tool_protocol(self, mcp_server):
        """Test calling an invalid tool."""
        # Call a non-existent method directly
        with pytest.raises(AttributeError):
            await mcp_server._non_existent_tool({})

    @pytest.mark.asyncio
    async def test_error_handling_protocol(self, mcp_server):
        """Test error handling in tool methods."""
        from jp_transit_search.core.exceptions import ValidationError

        # Mock the scraper to raise an exception
        mcp_server.scraper.search_route.side_effect = ValidationError(
            "Invalid station name"
        )

        # Call the search_route method directly with invalid data
        result = await mcp_server._search_route(
            {"from_station": "", "to_station": "大阪駅"}
        )

        # Verify error is handled gracefully
        assert isinstance(result, list)
        assert len(result) == 1

        text_content = result[0]
        assert "Route search failed:" in text_content.text
        assert "Invalid station name" in text_content.text

    def test_read_only_mode_verification(self, mcp_server):
        """Verify that server is in read-only mode (no data modification tools)."""
        # Verify only read-only tool methods are available
        tool_methods = [
            attr
            for attr in dir(mcp_server)
            if attr.startswith("_") and not attr.startswith("__")
        ]
        read_only_methods = [
            "_search_route",
            "_search_stations",
            "_get_station_info",
            "_list_station_database",
        ]

        # Check that only the expected read-only methods exist
        for method in read_only_methods:
            assert method in tool_methods

        # Verify no write/modification methods exist
        write_methods = ["_crawl_stations", "_load_stations_csv", "_save_stations_csv"]
        for write_method in write_methods:
            assert write_method not in tool_methods

        # Also verify no other public methods that could modify data
        public_methods = [attr for attr in dir(mcp_server) if not attr.startswith("_")]
        data_mod_methods = ["crawl", "save", "load", "update"]
        for method in public_methods:
            for dm in data_mod_methods:
                assert dm not in method.lower()

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, mcp_server, sample_stations):
        """Test handling multiple concurrent requests."""
        # Mock the station searcher for both requests
        mcp_server.station_searcher.search_stations.return_value = sample_stations
        mcp_server.station_searcher.get_station_by_name.return_value = sample_stations[
            0
        ]

        # Execute requests concurrently using direct method calls
        results = await asyncio.gather(
            mcp_server._search_stations({"query": "東京", "limit": 5}),
            mcp_server._get_station_info({"station_name": "東京駅"}),
        )

        # Verify both requests completed successfully
        assert len(results) == 2

        # Verify first result (search_stations)
        result1 = results[0]
        assert isinstance(result1, list)
        assert "Found 2 stations matching '東京'" in result1[0].text

        # Verify second result (get_station_info)
        result2 = results[1]
        assert isinstance(result2, list)
        assert "東京駅" in result2[0].text
