"""Tests for station CLI commands."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from jp_transit_search.cli.station_commands import stations
from jp_transit_search.core.models import Station


class TestStationCLICommands:
    """Test cases for station CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def sample_csv_file(self):
        """Create a temporary CSV file with sample station data."""
        csv_content = """name,prefecture,prefecture_id,station_id,railway_company,line_name,aliases,line_type,company_code,all_lines
新宿,東京都,13,station_shinjuku,JR東日本,山手線,しんじゅく|Shinjuku,JR,JR-E,
渋谷,東京都,13,station_shibuya,JR東日本,山手線,しぶや|Shibuya,JR,JR-E,
横浜,神奈川県,14,station_yokohama,JR東日本,東海道線,よこはま|Yokohama,JR,JR-E,"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", encoding="utf-8", delete=False
        ) as f:
            f.write(csv_content)
            return Path(f.name)

    def test_crawl_command_help(self, runner):
        """Test stations crawl command help."""
        result = runner.invoke(stations, ["crawl", "--help"])
        assert result.exit_code == 0
        assert (
            "Crawl station data from Yahoo Transit with resumable functionality"
            in result.output
        )

    @patch("jp_transit_search.cli.station_commands.StationCrawler")
    def test_crawl_command_success(self, mock_crawler_class, runner):
        """Test successful station crawling."""
        # Mock the crawler
        mock_crawler = Mock()
        mock_stations = [
            Station(name="新宿", prefecture="東京都"),
            Station(name="渋谷", prefecture="東京都"),
        ]
        mock_crawler.crawl_all_stations.return_value = mock_stations
        mock_crawler_class.return_value = mock_crawler

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "stations.csv"
            result = runner.invoke(stations, ["crawl", "--output", str(output_path)])

            assert result.exit_code == 0
            assert "✓ Successfully crawled" in result.output
            mock_crawler.crawl_all_stations.assert_called_once()
            # CSV writing now happens incrementally within crawl_all_stations call

    @patch("jp_transit_search.cli.station_commands.StationCrawler")
    def test_crawl_command_error(self, mock_crawler_class, runner):
        """Test station crawling with error."""
        mock_crawler = Mock()
        mock_crawler.crawl_all_stations.side_effect = Exception("Network error")
        mock_crawler_class.return_value = mock_crawler

        result = runner.invoke(stations, ["crawl"])
        assert result.exit_code == 0
        assert "Error crawling stations" in result.output

    def test_search_command_help(self, runner):
        """Test stations search command help."""
        result = runner.invoke(stations, ["search", "--help"])
        assert result.exit_code == 0
        assert "Search for stations by name" in result.output

    def test_search_command_no_data_file(self, runner):
        """Test search command when data file doesn't exist."""
        result = runner.invoke(
            stations, ["search", "新宿", "--data", "nonexistent.csv"]
        )
        assert result.exit_code == 0
        assert "Station data file not found" in result.output

    def test_search_command_success(self, runner, sample_csv_file):
        """Test successful station search."""
        result = runner.invoke(
            stations, ["search", "新宿", "--data", str(sample_csv_file)]
        )

        assert result.exit_code == 0
        assert "新宿" in result.output
        # Clean up
        sample_csv_file.unlink()

    def test_search_command_with_prefecture(self, runner, sample_csv_file):
        """Test station search with prefecture filter."""
        result = runner.invoke(
            stations,
            ["search", "宿", "--prefecture", "東京都", "--data", str(sample_csv_file)],
        )

        assert result.exit_code == 0
        assert "新宿" in result.output
        # Clean up
        sample_csv_file.unlink()

    def test_search_command_exact_match(self, runner, sample_csv_file):
        """Test station search with exact match."""
        result = runner.invoke(
            stations, ["search", "新宿", "--exact", "--data", str(sample_csv_file)]
        )

        assert result.exit_code == 0
        assert "新宿" in result.output
        # Clean up
        sample_csv_file.unlink()

    def test_search_command_no_results(self, runner, sample_csv_file):
        """Test station search with no results."""
        result = runner.invoke(
            stations, ["search", "存在しない駅", "--data", str(sample_csv_file)]
        )

        assert result.exit_code == 0
        assert "No stations found matching" in result.output
        # Clean up
        sample_csv_file.unlink()

    def test_search_command_error(self, runner, sample_csv_file):
        """Test station search with error."""
        # Create malformed CSV file to trigger parsing error
        with open(sample_csv_file, "w") as f:
            f.write("name\ntest,extra,column,data")  # Mismatched columns

        result = runner.invoke(
            stations, ["search", "新宿", "--data", str(sample_csv_file)]
        )
        assert result.exit_code == 0
        assert "Error searching stations" in result.output
        # Clean up
        sample_csv_file.unlink()

    def test_list_command_help(self, runner):
        """Test stations list command help."""
        result = runner.invoke(stations, ["list", "--help"])
        assert result.exit_code == 0
        assert "List stations" in result.output

    def test_list_command_no_data_file(self, runner):
        """Test list command when data file doesn't exist."""
        result = runner.invoke(stations, ["list", "--data", "nonexistent.csv"])
        assert result.exit_code == 0
        assert "Station data file not found" in result.output

    def test_list_command_table_format(self, runner, sample_csv_file):
        """Test station list in table format."""
        result = runner.invoke(
            stations, ["list", "--data", str(sample_csv_file), "--format", "table"]
        )

        assert result.exit_code == 0
        assert "新宿" in result.output
        assert "渋谷" in result.output
        # Clean up
        sample_csv_file.unlink()

    def test_list_command_json_format(self, runner, sample_csv_file):
        """Test station list in JSON format."""
        result = runner.invoke(
            stations, ["list", "--data", str(sample_csv_file), "--format", "json"]
        )

        assert result.exit_code == 0
        assert '"name": "新宿"' in result.output
        # Clean up
        sample_csv_file.unlink()

    def test_list_command_csv_format(self, runner, sample_csv_file):
        """Test station list in CSV format."""
        result = runner.invoke(
            stations, ["list", "--data", str(sample_csv_file), "--format", "csv"]
        )

        assert result.exit_code == 0
        assert "name,prefecture,prefecture_id" in result.output
        assert "新宿,東京都,13" in result.output
        # Clean up
        sample_csv_file.unlink()

    def test_list_command_with_prefecture(self, runner, sample_csv_file):
        """Test station list with prefecture filter."""
        result = runner.invoke(
            stations, ["list", "--prefecture", "東京都", "--data", str(sample_csv_file)]
        )

        assert result.exit_code == 0
        assert "新宿" in result.output
        assert "渋谷" in result.output
        assert "横浜" not in result.output  # Should be filtered out
        # Clean up
        sample_csv_file.unlink()

    def test_list_command_with_limit(self, runner, sample_csv_file):
        """Test station list with limit."""
        result = runner.invoke(
            stations, ["list", "--limit", "1", "--data", str(sample_csv_file)]
        )

        assert result.exit_code == 0
        # Should only show one station
        lines = [
            line
            for line in result.output.split("\n")
            if "│" in line and "新宿" in line or "渋谷" in line or "横浜" in line
        ]
        assert len(lines) == 1
        # Clean up
        sample_csv_file.unlink()

    def test_list_command_no_stations(self, runner):
        """Test station list with empty data."""
        # Create empty CSV file
        csv_content = "name,prefecture,prefecture_id,station_id,railway_company,line_name,aliases,line_type,company_code,all_lines\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", encoding="utf-8", delete=False
        ) as f:
            f.write(csv_content)
            csv_path = Path(f.name)

        try:
            result = runner.invoke(stations, ["list", "--data", str(csv_path)])
            assert result.exit_code == 0
            assert "No stations found" in result.output
        finally:
            csv_path.unlink()

    def test_info_command_help(self, runner):
        """Test stations info command help."""
        result = runner.invoke(stations, ["info", "--help"])
        assert result.exit_code == 0
        assert "Show station database information" in result.output

    def test_info_command_no_data_file(self, runner):
        """Test info command when data file doesn't exist."""
        result = runner.invoke(stations, ["info", "--data", "nonexistent.csv"])
        assert result.exit_code == 0
        assert "Station data file not found" in result.output

    def test_info_command_success(self, runner, sample_csv_file):
        """Test successful station info display."""
        result = runner.invoke(stations, ["info", "--data", str(sample_csv_file)])

        assert result.exit_code == 0
        assert "Station Database Information" in result.output
        assert "Total stations: 3" in result.output
        assert "Prefectures: 2" in result.output
        assert "東京都" in result.output
        assert "神奈川県" in result.output
        # Clean up
        sample_csv_file.unlink()

    def test_info_command_error(self, runner, sample_csv_file):
        """Test station info with error."""
        # Create malformed CSV file to trigger parsing error
        with open(sample_csv_file, "w") as f:
            f.write("name\ntest,extra,column,data")  # Mismatched columns

        result = runner.invoke(stations, ["info", "--data", str(sample_csv_file)])
        assert result.exit_code == 0
        assert "Error reading station info" in result.output
        # Clean up
        sample_csv_file.unlink()

    def test_stations_group_help(self, runner):
        """Test stations group help."""
        result = runner.invoke(stations, ["--help"])
        assert result.exit_code == 0
        assert "Station management commands" in result.output
        assert "crawl" in result.output
        assert "search" in result.output
        assert "list" in result.output
        assert "info" in result.output
