"""Unit tests for CLI components."""

import json
from unittest.mock import Mock, patch

from click.testing import CliRunner

from jp_transit_search.cli.main import cli
from jp_transit_search.core.exceptions import (
    RouteNotFoundError,
    ScrapingError,
    ValidationError,
)
from jp_transit_search.core.models import Route, Transfer


class TestCLI:
    """Test CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

        # Create sample route data
        self.sample_route = Route(
            from_station="横浜",
            to_station="豊洲",
            duration="49分(乗車33分)",
            cost="IC優先：628円",
            transfer_count=2,
            transfers=[
                Transfer(
                    from_station="横浜",
                    to_station="新橋",
                    line_name="東海道本線",
                    duration_minutes=25,
                    cost_yen=290,
                ),
                Transfer(
                    from_station="新橋",
                    to_station="豊洲",
                    line_name="ゆりかもめ",
                    duration_minutes=8,
                    cost_yen=200,
                ),
            ],
        )

    def test_cli_version(self):
        """Test CLI version option."""
        result = self.runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_cli_help(self):
        """Test CLI help."""
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Japanese Transit Search" in result.output

    @patch("jp_transit_search.cli.main.YahooTransitScraper")
    def test_search_command_success_table_format(self, mock_scraper_class):
        """Test successful search with table format."""
        # Setup mock
        mock_scraper = Mock()
        mock_scraper.search_route.return_value = [self.sample_route]
        mock_scraper_class.return_value = mock_scraper

        result = self.runner.invoke(cli, ["search", "横浜", "豊洲"])

        assert result.exit_code == 0
        assert "横浜" in result.output
        assert "豊洲" in result.output
        assert "49分(乗車33分)" in result.output
        mock_scraper.search_route.assert_called_once_with(
            from_station="横浜",
            to_station="豊洲",
            search_datetime=None,
            search_type="earliest",
            save_html_path=None
        )

    @patch("jp_transit_search.cli.main.YahooTransitScraper")
    def test_search_command_success_json_format(self, mock_scraper_class):
        """Test successful search with JSON format."""
        # Setup mock
        mock_scraper = Mock()
        mock_scraper.search_route.return_value = [self.sample_route]
        mock_scraper_class.return_value = mock_scraper

        result = self.runner.invoke(cli, ["search", "横浜", "豊洲", "--format", "json"])

        assert result.exit_code == 0
        # Parse JSON to verify it's valid
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) == 1
        route = output_data[0]
        assert route["from_station"] == "横浜"
        assert route["to_station"] == "豊洲"
        assert route["transfer_count"] == 2
        assert len(route["transfers"]) == 2

    @patch("jp_transit_search.cli.main.YahooTransitScraper")
    def test_search_command_success_detailed_format(self, mock_scraper_class):
        """Test successful search with detailed format."""
        # Setup mock
        mock_scraper = Mock()
        mock_scraper.search_route.return_value = [self.sample_route]
        mock_scraper_class.return_value = mock_scraper

        result = self.runner.invoke(
            cli, ["search", "横浜", "豊洲", "--format", "detailed"]
        )

        assert result.exit_code == 0
        assert "Route Summary" in result.output
        assert "Transfer Details" in result.output
        assert "東海道本線" in result.output

    @patch("jp_transit_search.cli.main.YahooTransitScraper")
    def test_search_command_with_verbose(self, mock_scraper_class):
        """Test search command with verbose flag."""
        # Setup mock
        mock_scraper = Mock()
        mock_scraper.search_route.return_value = [self.sample_route]
        mock_scraper_class.return_value = mock_scraper

        result = self.runner.invoke(cli, ["search", "横浜", "豊洲", "--verbose"])

        assert result.exit_code == 0
        assert "Transfer Details" in result.output

    @patch("jp_transit_search.cli.main.YahooTransitScraper")
    def test_search_command_with_timeout(self, mock_scraper_class):
        """Test search command with custom timeout."""
        # Setup mock
        mock_scraper = Mock()
        mock_scraper.search_route.return_value = [self.sample_route]
        mock_scraper_class.return_value = mock_scraper

        result = self.runner.invoke(cli, ["search", "横浜", "豊洲", "--timeout", "60"])

        assert result.exit_code == 0
        mock_scraper_class.assert_called_once_with(timeout=60)
        mock_scraper.search_route.assert_called_once_with(
            from_station="横浜",
            to_station="豊洲",
            search_datetime=None,
            search_type="earliest",
            save_html_path=None
        )

    @patch("jp_transit_search.cli.main.YahooTransitScraper")
    def test_search_command_validation_error(self, mock_scraper_class):
        """Test search command with validation error."""
        # Setup mock
        mock_scraper = Mock()
        mock_scraper.search_route.side_effect = ValidationError("Invalid station")
        mock_scraper_class.return_value = mock_scraper

        result = self.runner.invoke(cli, ["search", "", "豊洲"], catch_exceptions=False)

        assert result.exit_code == 1
        # Error should be in stderr output, which in CLI testing shows up differently
        # We'll just check that the command exits with error code 1

    @patch("jp_transit_search.cli.main.YahooTransitScraper")
    def test_search_command_route_not_found_error(self, mock_scraper_class):
        """Test search command with route not found error."""
        # Setup mock
        mock_scraper = Mock()
        mock_scraper.search_route.side_effect = RouteNotFoundError("No route found")
        mock_scraper_class.return_value = mock_scraper

        result = self.runner.invoke(
            cli, ["search", "Invalid", "Station"], catch_exceptions=False
        )

        assert result.exit_code == 1
        # Error should be in stderr output, check exit code

    @patch("jp_transit_search.cli.main.YahooTransitScraper")
    def test_search_command_scraping_error(self, mock_scraper_class):
        """Test search command with scraping error."""
        # Setup mock
        mock_scraper = Mock()
        mock_scraper.search_route.side_effect = ScrapingError("Parsing failed")
        mock_scraper_class.return_value = mock_scraper

        result = self.runner.invoke(
            cli, ["search", "横浜", "豊洲"], catch_exceptions=False
        )

        assert result.exit_code == 1
        # Error should be in stderr output, check exit code

    @patch("jp_transit_search.cli.main.YahooTransitScraper")
    def test_search_command_unexpected_error(self, mock_scraper_class):
        """Test search command with unexpected error."""
        # Setup mock
        mock_scraper = Mock()
        mock_scraper.search_route.side_effect = Exception("Unexpected error")
        mock_scraper_class.return_value = mock_scraper

        result = self.runner.invoke(
            cli, ["search", "横浜", "豊洲"], catch_exceptions=False
        )

        assert result.exit_code == 1
        # Error should be in stderr output, check exit code

    @patch("jp_transit_search.cli.main.YahooTransitScraper")
    def test_search_command_unexpected_error_verbose(self, mock_scraper_class):
        """Test search command with unexpected error and verbose flag."""
        # Setup mock
        mock_scraper = Mock()
        mock_scraper.search_route.side_effect = Exception("Unexpected error")
        mock_scraper_class.return_value = mock_scraper

        result = self.runner.invoke(
            cli, ["search", "横浜", "豊洲", "--verbose"], catch_exceptions=False
        )

        assert result.exit_code == 1
        # Error should be in stderr output, check exit code

    @patch("pathlib.Path.exists", return_value=False)
    def test_stations_search_command_no_data(self, mock_exists):
        """Test stations search command with no data file."""
        result = self.runner.invoke(cli, ["stations", "search", "新宿"])

        # Should fail gracefully when no data file exists
        assert result.exit_code == 0
        assert "Station data file not found" in result.output

    @patch("pathlib.Path.exists", return_value=False)
    def test_stations_search_command_with_prefecture_no_data(self, mock_exists):
        """Test stations search command with prefecture filter but no data."""
        result = self.runner.invoke(
            cli, ["stations", "search", "駅", "--prefecture", "東京都"]
        )

        assert result.exit_code == 0
        assert "Station data file not found" in result.output

    @patch("pathlib.Path.exists", return_value=False)
    def test_stations_list_command_no_data(self, mock_exists):
        """Test stations list command with no data file."""
        result = self.runner.invoke(cli, ["stations", "list"])

        # Should fail gracefully when no data file exists
        assert result.exit_code == 0
        assert "Station data file not found" in result.output

    @patch("pathlib.Path.exists", return_value=False)
    def test_stations_list_command_with_prefecture_no_data(self, mock_exists):
        """Test stations list command with prefecture filter but no data."""
        result = self.runner.invoke(cli, ["stations", "list", "--prefecture", "東京都"])

        assert result.exit_code == 0
        assert "Station data file not found" in result.output

    def test_config_show_command(self):
        """Test config show command."""
        result = self.runner.invoke(cli, ["config", "show"])

        assert result.exit_code == 0
        assert "Current Configuration" in result.output
        assert "Default timeout: 30 seconds" in result.output
        assert "Default format: table" in result.output

    def test_config_set_command(self):
        """Test config set command (not implemented)."""
        result = self.runner.invoke(cli, ["config", "set", "timeout", "60"])

        assert result.exit_code == 0
        assert "Configuration setting not implemented yet" in result.output
        assert "Would set timeout = 60" in result.output
