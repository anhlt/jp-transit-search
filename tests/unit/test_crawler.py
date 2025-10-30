"""Tests for the station crawler module."""

import csv
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests
from bs4 import BeautifulSoup

from jp_transit_search.core.exceptions import NetworkError, ScrapingError
from jp_transit_search.core.models import Station
from jp_transit_search.crawler.station_crawler import StationCrawler, StationSearcher


class TestStationCrawler:
    """Test cases for StationCrawler class."""

    def test_init(self):
        """Test crawler initialization."""
        crawler = StationCrawler(timeout=60)
        assert crawler.timeout == 60
        assert crawler.session is not None
        assert crawler.stations == []
        assert 'User-Agent' in crawler.session.headers

    def test_init_default_timeout(self):
        """Test crawler initialization with default timeout."""
        crawler = StationCrawler()
        assert crawler.timeout == 30

    @patch('jp_transit_search.crawler.station_crawler.StationCrawler._crawl_wikipedia_stations')
    @patch('jp_transit_search.crawler.station_crawler.StationCrawler._crawl_ekitan_stations')
    @patch('jp_transit_search.crawler.station_crawler.StationCrawler._deduplicate_stations')
    def test_crawl_all_stations(self, mock_dedupe, mock_ekitan, mock_wiki):
        """Test crawling all stations from multiple sources."""
        mock_stations = [
            Station(name="新宿", prefecture="東京都"),
            Station(name="渋谷", prefecture="東京都")
        ]
        mock_dedupe.return_value = mock_stations

        crawler = StationCrawler()
        result = crawler.crawl_all_stations()

        mock_wiki.assert_called_once()
        mock_ekitan.assert_called_once()
        mock_dedupe.assert_called_once()
        assert result == mock_stations

    def test_save_to_csv(self):
        """Test saving stations to CSV file."""
        stations = [
            Station(
                name="新宿",
                prefecture="東京都",
                city="新宿区",
                railway_company="JR東日本",
                line_name="山手線",
                station_code="JY17",
                latitude=35.689487,
                longitude=139.700531,
                aliases=["しんじゅく", "Shinjuku"]
            ),
            Station(
                name="渋谷",
                prefecture="東京都",
                city="渋谷区"
            )
        ]

        crawler = StationCrawler()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "test_stations.csv"
            crawler.save_to_csv(stations, csv_path)
            
            # Verify file exists and has correct content
            assert csv_path.exists()
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                
            assert len(rows) == 2
            
            # Check first station
            assert rows[0]['name'] == "新宿"
            assert rows[0]['prefecture'] == "東京都"
            assert rows[0]['city'] == "新宿区"
            assert rows[0]['railway_company'] == "JR東日本"
            assert rows[0]['line_name'] == "山手線"
            assert rows[0]['station_code'] == "JY17"
            assert rows[0]['latitude'] == "35.689487"
            assert rows[0]['longitude'] == "139.700531"
            assert rows[0]['aliases'] == "しんじゅく|Shinjuku"
            
            # Check second station (with empty fields)
            assert rows[1]['name'] == "渋谷"
            assert rows[1]['prefecture'] == "東京都"
            assert rows[1]['city'] == "渋谷区"
            assert rows[1]['railway_company'] == ""
            assert rows[1]['aliases'] == ""

    def test_save_to_csv_creates_parent_directory(self):
        """Test that save_to_csv creates parent directories."""
        stations = [Station(name="テスト", prefecture="東京都")]
        crawler = StationCrawler()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "subdir" / "test_stations.csv"
            crawler.save_to_csv(stations, csv_path)
            
            assert csv_path.exists()
            assert csv_path.parent.exists()

    def test_load_from_csv(self):
        """Test loading stations from CSV file."""
        # Create test CSV data
        csv_content = """name,prefecture,city,railway_company,line_name,station_code,latitude,longitude,aliases
新宿,東京都,新宿区,JR東日本,山手線,JY17,35.689487,139.700531,しんじゅく|Shinjuku
渋谷,東京都,渋谷区,,,,,,"""""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', encoding='utf-8', delete=False) as f:
            f.write(csv_content)
            csv_path = Path(f.name)
        
        try:
            crawler = StationCrawler()
            stations = crawler.load_from_csv(csv_path)
            
            assert len(stations) == 2
            
            # Check first station
            station1 = stations[0]
            assert station1.name == "新宿"
            assert station1.prefecture == "東京都"
            assert station1.city == "新宿区"
            assert station1.railway_company == "JR東日本"
            assert station1.line_name == "山手線"
            assert station1.station_code == "JY17"
            assert station1.latitude == 35.689487
            assert station1.longitude == 139.700531
            assert station1.aliases == ["しんじゅく", "Shinjuku"]
            
            # Check second station
            station2 = stations[1]
            assert station2.name == "渋谷"
            assert station2.prefecture == "東京都"
            assert station2.city == "渋谷区"
            assert station2.railway_company is None
            assert station2.aliases == []
            
        finally:
            csv_path.unlink()

    def test_load_from_csv_empty_values(self):
        """Test loading CSV with empty values."""
        csv_content = """name,prefecture,city,railway_company,line_name,station_code,latitude,longitude,aliases
テスト駅,,,,,,,,"""""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', encoding='utf-8', delete=False) as f:
            f.write(csv_content)
            csv_path = Path(f.name)
        
        try:
            crawler = StationCrawler()
            stations = crawler.load_from_csv(csv_path)
            
            assert len(stations) == 1
            station = stations[0]
            assert station.name == "テスト駅"
            assert station.prefecture is None
            assert station.city is None
            assert station.railway_company is None
            assert station.latitude is None
            assert station.longitude is None
            assert station.aliases == []
            
        finally:
            csv_path.unlink()

    @patch('jp_transit_search.crawler.station_crawler.StationCrawler._parse_wikipedia_station_page')
    def test_crawl_wikipedia_stations(self, mock_parse):
        """Test crawling Wikipedia stations."""
        crawler = StationCrawler()
        crawler._crawl_wikipedia_stations()
        
        # Should call parse for each prefecture
        assert mock_parse.call_count == 4
        expected_prefectures = ['東京都', '神奈川県', '千葉県', '埼玉県']
        called_prefectures = [call[0][1] for call in mock_parse.call_args_list]
        assert all(pref in called_prefectures for pref in expected_prefectures)

    @patch('jp_transit_search.crawler.station_crawler.StationCrawler._parse_wikipedia_station_page')
    def test_crawl_wikipedia_stations_handles_errors(self, mock_parse):
        """Test that Wikipedia crawling handles parsing errors."""
        mock_parse.side_effect = Exception("Parse error")
        
        crawler = StationCrawler()
        # Should not raise an exception despite parse errors
        crawler._crawl_wikipedia_stations()
        
        assert mock_parse.call_count == 4

    @patch('requests.Session.get')
    def test_parse_wikipedia_station_page(self, mock_get):
        """Test parsing a Wikipedia station page."""
        # Mock HTML response with station table
        html_content = """
        <html>
            <body>
                <table class="wikitable">
                    <tr><th>駅名</th><th>路線</th></tr>
                    <tr><td>新宿駅</td><td>JR山手線</td></tr>
                    <tr><td>渋谷駅</td><td>JR山手線</td></tr>
                </table>
            </body>
        </html>
        """
        
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        crawler = StationCrawler()
        crawler._parse_wikipedia_station_page("http://example.com", "東京都")
        
        # Should have parsed 2 stations
        assert len(crawler.stations) == 2
        assert crawler.stations[0].name == "新宿駅"
        assert crawler.stations[0].prefecture == "東京都"
        assert crawler.stations[0].railway_company == "JR山手線"

    @patch('requests.Session.get')
    def test_parse_wikipedia_station_page_network_error(self, mock_get):
        """Test network error handling in Wikipedia parsing."""
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        
        crawler = StationCrawler()
        with pytest.raises(NetworkError):
            crawler._parse_wikipedia_station_page("http://example.com", "東京都")

    @patch('requests.Session.get')
    def test_parse_wikipedia_station_page_scraping_error(self, mock_get):
        """Test scraping error handling in Wikipedia parsing."""
        mock_response = Mock()
        mock_response.text = "invalid html"
        mock_response.raise_for_status.side_effect = Exception("Parse error")
        mock_get.return_value = mock_response
        
        crawler = StationCrawler()
        with pytest.raises(ScrapingError):
            crawler._parse_wikipedia_station_page("http://example.com", "東京都")

    def test_crawl_ekitan_stations(self):
        """Test crawling Ekitan stations (sample implementation)."""
        crawler = StationCrawler()
        initial_count = len(crawler.stations)
        
        crawler._crawl_ekitan_stations()
        
        # Should add sample stations
        assert len(crawler.stations) > initial_count
        assert any(s.name == "新宿" for s in crawler.stations)
        assert any(s.name == "渋谷" for s in crawler.stations)

    def test_deduplicate_stations(self):
        """Test station deduplication."""
        # Create duplicate stations
        stations = [
            Station(name="新宿", prefecture="東京都"),
            Station(name="新宿", prefecture="東京都"),  # Duplicate
            Station(name="渋谷", prefecture="東京都"),
            Station(name="新宿", prefecture="神奈川県"),  # Different prefecture, not duplicate
        ]
        
        crawler = StationCrawler()
        crawler.stations = stations
        
        unique_stations = crawler._deduplicate_stations()
        
        assert len(unique_stations) == 3
        names_prefs = [(s.name, s.prefecture) for s in unique_stations]
        assert ("新宿", "東京都") in names_prefs
        assert ("渋谷", "東京都") in names_prefs
        assert ("新宿", "神奈川県") in names_prefs


class TestStationSearcher:
    """Test cases for StationSearcher class."""

    @pytest.fixture
    def sample_stations(self):
        """Create sample stations for testing."""
        return [
            Station(name="新宿", prefecture="東京都", aliases=["しんじゅく", "Shinjuku"]),
            Station(name="新宿三丁目", prefecture="東京都"),
            Station(name="渋谷", prefecture="東京都"),
            Station(name="横浜", prefecture="神奈川県"),
            Station(name="新横浜", prefecture="神奈川県"),
        ]

    def test_init(self, sample_stations):
        """Test searcher initialization."""
        searcher = StationSearcher(sample_stations)
        assert searcher.stations == sample_stations
        assert len(searcher.name_index) > 0
        assert len(searcher.prefecture_index) > 0

    def test_build_search_index(self, sample_stations):
        """Test building search index."""
        searcher = StationSearcher(sample_stations)
        
        # Check name index
        assert "新宿" in searcher.name_index
        assert len(searcher.name_index["新宿"]) == 1
        assert searcher.name_index["新宿"][0].name == "新宿"
        
        # Check prefecture index
        assert "東京都" in searcher.prefecture_index
        assert len(searcher.prefecture_index["東京都"]) == 3
        assert "神奈川県" in searcher.prefecture_index
        assert len(searcher.prefecture_index["神奈川県"]) == 2

    def test_search_by_name_exact(self, sample_stations):
        """Test exact name search."""
        searcher = StationSearcher(sample_stations)
        
        results = searcher.search_by_name("新宿", exact=True)
        assert len(results) == 1
        assert results[0].name == "新宿"
        
        # Non-existent station
        results = searcher.search_by_name("存在しない駅", exact=True)
        assert len(results) == 0

    def test_search_by_name_fuzzy(self, sample_stations):
        """Test fuzzy name search."""
        searcher = StationSearcher(sample_stations)
        
        # Partial match
        results = searcher.search_by_name("新宿")
        assert len(results) == 2  # "新宿" and "新宿三丁目"
        names = [s.name for s in results]
        assert "新宿" in names
        assert "新宿三丁目" in names
        
        # Search by alias
        results = searcher.search_by_name("Shinjuku")
        assert len(results) == 1
        assert results[0].name == "新宿"

    def test_search_by_name_case_insensitive(self, sample_stations):
        """Test case-insensitive search."""
        searcher = StationSearcher(sample_stations)
        
        results = searcher.search_by_name("shinjuku")
        assert len(results) == 1
        assert results[0].name == "新宿"

    def test_search_by_prefecture(self, sample_stations):
        """Test prefecture search."""
        searcher = StationSearcher(sample_stations)
        
        # Tokyo stations
        results = searcher.search_by_prefecture("東京都")
        assert len(results) == 3
        names = [s.name for s in results]
        assert "新宿" in names
        assert "新宿三丁目" in names
        assert "渋谷" in names
        
        # Kanagawa stations
        results = searcher.search_by_prefecture("神奈川県")
        assert len(results) == 2
        names = [s.name for s in results]
        assert "横浜" in names
        assert "新横浜" in names
        
        # Non-existent prefecture
        results = searcher.search_by_prefecture("存在しない県")
        assert len(results) == 0

    def test_get_all_prefectures(self, sample_stations):
        """Test getting all prefectures."""
        searcher = StationSearcher(sample_stations)
        
        prefectures = searcher.get_all_prefectures()
        assert len(prefectures) == 2
        assert "東京都" in prefectures
        assert "神奈川県" in prefectures
        assert prefectures == sorted(prefectures)  # Should be sorted

    def test_get_all_prefectures_excludes_none(self):
        """Test that get_all_prefectures excludes None values."""
        stations = [
            Station(name="駅1", prefecture="東京都"),
            Station(name="駅2", prefecture=None),
            Station(name="駅3", prefecture="神奈川県"),
        ]
        
        searcher = StationSearcher(stations)
        prefectures = searcher.get_all_prefectures()
        
        assert len(prefectures) == 2
        assert "東京都" in prefectures
        assert "神奈川県" in prefectures
        assert None not in prefectures

    def test_search_empty_stations(self):
        """Test searcher with empty station list."""
        searcher = StationSearcher([])
        
        assert searcher.search_by_name("新宿") == []
        assert searcher.search_by_prefecture("東京都") == []
        assert searcher.get_all_prefectures() == []

    def test_search_station_without_aliases(self):
        """Test searching stations without aliases."""
        stations = [Station(name="テスト駅", prefecture="東京都", aliases=None)]
        searcher = StationSearcher(stations)
        
        results = searcher.search_by_name("テスト")
        assert len(results) == 1
        assert results[0].name == "テスト駅"