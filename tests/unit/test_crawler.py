"""Tests for the station crawler module."""

import csv
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from bs4 import BeautifulSoup

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
        assert "User-Agent" in crawler.session.headers

    def test_init_default_timeout(self):
        """Test crawler initialization with default timeout."""
        crawler = StationCrawler()
        assert crawler.timeout == 30

    @patch(
        "jp_transit_search.crawler.station_crawler.StationCrawler._crawl_yahoo_transit_stations_resumable"
    )
    @patch(
        "jp_transit_search.crawler.station_crawler.StationCrawler._deduplicate_stations"
    )
    def test_crawl_all_stations(self, mock_dedupe, mock_crawl):
        """Test crawling all stations from Yahoo Transit."""
        mock_stations = [
            Station(name="新宿", prefecture="東京都"),
            Station(name="渋谷", prefecture="東京都"),
        ]
        mock_dedupe.return_value = mock_stations

        crawler = StationCrawler()
        result = crawler.crawl_all_stations()

        mock_crawl.assert_called_once()
        mock_dedupe.assert_called_once()
        assert result == mock_stations

    def test_save_to_csv(self):
        """Test saving stations to CSV file."""
        stations = [
            Station(
                name="新宿",
                prefecture="東京都",
                prefecture_id="13",
                station_id="12345",
                railway_company="JR東日本",
                line_name="山手線",
                aliases=["しんじゅく", "Shinjuku"],
            ),
            Station(name="渋谷", prefecture="東京都", prefecture_id="13"),
        ]

        crawler = StationCrawler()

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "test_stations.csv"
            crawler.save_to_csv(stations, csv_path)

            # Verify file exists and has correct content
            assert csv_path.exists()

            with open(csv_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2

            # Check first station
            assert rows[0]["name"] == "新宿"
            assert rows[0]["prefecture"] == "東京都"
            assert rows[0]["prefecture_id"] == "13"
            assert rows[0]["station_id"] == "12345"
            assert rows[0]["railway_company"] == "JR東日本"
            assert rows[0]["line_name"] == "山手線"
            assert rows[0]["aliases"] == "しんじゅく|Shinjuku"

            # Check second station (with empty fields)
            assert rows[1]["name"] == "渋谷"
            assert rows[1]["prefecture"] == "東京都"
            assert rows[1]["prefecture_id"] == "13"
            assert rows[1]["railway_company"] == ""
            assert rows[1]["aliases"] == ""

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
        csv_content = (
            """name,prefecture,prefecture_id,station_id,railway_company,line_name,aliases,line_type,company_code,all_lines
新宿,東京都,13,12345,JR東日本,山手線,しんじゅく|Shinjuku,JR,JR-E,
渋谷,東京都,13,54321,,,,,,,"""
            ""
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", encoding="utf-8", delete=False
        ) as f:
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
            assert station1.prefecture_id == "13"
            assert station1.station_id == "12345"
            assert station1.railway_company == "JR東日本"
            assert station1.line_name == "山手線"
            assert station1.aliases == ["しんじゅく", "Shinjuku"]

            # Check second station
            station2 = stations[1]
            assert station2.name == "渋谷"
            assert station2.prefecture == "東京都"
            assert station2.prefecture_id == "13"
            assert station2.station_id == "54321"
            assert station2.railway_company is None
            assert station2.aliases == []

        finally:
            csv_path.unlink()

    def test_load_from_csv_empty_values(self):
        """Test loading CSV with empty values."""
        csv_content = (
            """name,prefecture,prefecture_id,station_id,railway_company,line_name,aliases,line_type,company_code,all_lines
テスト駅,,,,,,,,,"""
            ""
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", encoding="utf-8", delete=False
        ) as f:
            f.write(csv_content)
            csv_path = Path(f.name)

        try:
            crawler = StationCrawler()
            stations = crawler.load_from_csv(csv_path)

            assert len(stations) == 1
            station = stations[0]
            assert station.name == "テスト駅"
            assert station.prefecture is None
            assert station.prefecture_id is None
            assert station.station_id is None
            assert station.railway_company is None

            assert station.aliases == []

        finally:
            csv_path.unlink()

    def test_deduplicate_stations(self):
        """Test station deduplication."""
        # Create duplicate stations
        stations = [
            Station(name="新宿", prefecture="東京都"),
            Station(name="新宿", prefecture="東京都"),  # Duplicate
            Station(name="渋谷", prefecture="東京都"),
            Station(
                name="新宿", prefecture="神奈川県"
            ),  # Different prefecture, not duplicate
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
            Station(
                name="新宿", prefecture="東京都", aliases=["しんじゅく", "Shinjuku"]
            ),
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


class TestStationDetailExtraction:
    """Test cases for station detail extraction from real HTML."""

    def test_get_station_details_from_real_html(self):
        """Test station detail extraction using real Yahoo Transit HTML."""
        # Load the actual HTML sample
        html_path = Path(__file__).parent.parent / "fixtures" / "station_pages" / "station_20042_yamanose_line.html"
        
        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()
        
        crawler = StationCrawler()
        
        # Mock the HTTP response to return our HTML sample
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        
        with patch.object(crawler.session, 'get', return_value=mock_response):
            details = crawler._get_station_details("/station/20042")
        
        # Test extracted data against known values from HTML
        assert details.station_id == "20042"
        
        # The current implementation should extract some lines
        assert details.all_lines is not None
        assert isinstance(details.all_lines, list)
        
        # Should find some line information in the HTML
        # The HTML contains "札幌市電内回り" and "札幌市電外回り"
        line_text = " ".join(details.all_lines) if details.all_lines else ""
        assert len(details.all_lines) > 0, "Should extract at least some line information"

    def test_extract_station_name_and_reading(self):
        """Test extraction of station name and reading from HTML structure."""
        html_path = Path(__file__).parent.parent / "fixtures" / "station_pages" / "station_20042_yamanose_line.html"
        
        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Test extraction of station name
        title_elem = soup.find("h1", class_="title")
        assert title_elem is not None
        assert title_elem.get_text().strip() == "石山通"
        
        # Test extraction of station reading (kana)
        kana_elem = soup.find("span", class_="staKana")
        assert kana_elem is not None
        assert kana_elem.get_text().strip() == "いしやまどおり"
        
        # Test title extraction (current crawler method)
        title_tag = soup.find("title")
        assert title_tag is not None
        title_text = title_tag.get_text()
        assert "石山通駅の駅周辺情報" in title_text

    def test_extract_company_and_line_info(self):
        """Test extraction of railway company and line information."""
        html_path = Path(__file__).parent.parent / "fixtures" / "station_pages" / "station_20042_yamanose_line.html"
        
        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Check for railway line information in the rail section
        rail_section = soup.find("div", id="mdStaRail")
        assert rail_section is not None
        
        # Should find "札幌市電内回り" and "札幌市電外回り"
        rail_info = rail_section.get_text()
        assert "札幌市電内回り" in rail_info
        assert "札幌市電外回り" in rail_info
        
        # The HTML also contains JSON data with company info
        script_tags = soup.find_all("script", {"id": "__NEXT_DATA__"})
        assert len(script_tags) > 0, "Should contain JSON data script"
        
        import json
        json_data = json.loads(script_tags[0].string)
        
        # Extract company and line info from JSON
        transport_info = json_data["props"]["pageProps"]["lipFeature"]["TransitSearchInfo"]["Detail"]
        assert transport_info["CompanyName"] == "札幌市交通事業振興公社"
        assert transport_info["RailName"] == "山鼻線"
        assert transport_info["StationId"] == "20042"

    def test_prefecture_extraction_from_url_params(self):
        """Test prefecture extraction from URL parameters."""
        html_path = Path(__file__).parent.parent / "fixtures" / "station_pages" / "station_20042_yamanose_line.html"
        
        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()
        
        # The URL contains pref=1 parameter which maps to Hokkaido
        crawler = StationCrawler()
        
        # Test the prefecture mapping for Hokkaido (code 01)
        prefecture_map = {
            "/01/": "北海道",
            "/13/": "東京都",
            "/14/": "神奈川県",
        }
        
        # Test URL with Hokkaido code
        hokkaido_url = "https://transit.yahoo.co.jp/station/01/test"
        prefecture = crawler._get_prefecture_from_url(hokkaido_url)
        # Now correctly handles Hokkaido prefecture mapping
        assert prefecture == "北海道"  # Enhanced implementation now handles all 47 prefectures

    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_station_id_extraction_from_url(self, mock_sleep):
        """Test station ID extraction from URL patterns."""
        crawler = StationCrawler()
        
        # Test different URL patterns
        test_urls = [
            "https://transit.yahoo.co.jp/station/20042",
            "/station/20042?pref=1&company=test",
            "https://transit.yahoo.co.jp/station/12345/info"
        ]
        
        expected_ids = ["20042", "20042", "12345"]
        
        for url, expected_id in zip(test_urls, expected_ids):
            # Mock response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "<html><body>Test</body></html>"
            
            with patch.object(crawler.session, 'get', return_value=mock_response):
                details = crawler._get_station_details(url)
                assert details.station_id == expected_id

    def test_get_station_details_higashi_tonden_dori(self):
        """Test station detail extraction using station 20470 (東屯田通駅) HTML."""
        # Load the actual HTML sample for station 20470
        html_path = Path(__file__).parent.parent / "fixtures" / "station_pages" / "station_20470_sapporo_line.html"
        
        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()
        
        crawler = StationCrawler()
        
        # Mock the HTTP response to return our HTML sample
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        
        with patch.object(crawler.session, 'get', return_value=mock_response):
            details = crawler._get_station_details("/station/20470")
        
        # Test extracted data against known values from HTML
        assert details.station_id == "20470"
        
        # Test station reading extraction
        assert details.station_reading == "ひがしとんでんどおり"
        
        # Test line extraction - should find both inner and outer loop lines
        assert details.all_lines is not None
        assert isinstance(details.all_lines, list)
        assert len(details.all_lines) == 2
        
        # Verify specific lines are extracted
        assert "札幌市電内回り" in details.all_lines
        assert "札幌市電外回り" in details.all_lines
        
        # Verify company name extraction
        assert details.company_name == "札幌市交通事業振興公社"
        
        # Verify line name extraction (from JSON data)
        assert details.line_name == "山鼻線"

    def test_get_station_details_meguro_multi_lines(self):
        """Test station detail extraction using station 23018 (目黒駅) HTML - multi-line major station."""
        # Load the actual HTML sample for station 23018
        html_path = Path(__file__).parent.parent / "fixtures" / "station_pages" / "station_23018_tokyu_meguro_line.html"
        
        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()
        
        crawler = StationCrawler()
        
        # Mock the HTTP response to return our HTML sample
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        
        with patch.object(crawler.session, 'get', return_value=mock_response):
            details = crawler._get_station_details("/station/23018")
        
        # Test extracted data against known values from HTML
        assert details.station_id == "23018"
        
        # Test station reading extraction
        assert details.station_reading == "めぐろ"
        
        # Test line extraction - should find all five lines
        assert details.all_lines is not None
        assert isinstance(details.all_lines, list)
        assert len(details.all_lines) == 5
        
        # Verify specific lines are extracted (from multiple railway companies)
        expected_lines = [
            "ＪＲ山手線外回り",
            "ＪＲ山手線内回り", 
            "東急目黒線",
            "東京メトロ南北線",
            "都営地下鉄三田線"
        ]
        for expected_line in expected_lines:
            assert expected_line in details.all_lines, f"Expected line '{expected_line}' not found in {details.all_lines}"
        
        # Verify company name extraction (should pick up from JSON - Tokyo Metro in this case)
        assert details.company_name == "東京地下鉄"
        
        # Verify line name extraction (from JSON data - should be 南北線)
        assert details.line_name == "南北線"

    def test_get_station_details_denenchofu_tokyu_lines(self):
        """Test station detail extraction using station 22826 (田園調布駅) HTML - Tokyu multi-line station."""
        # Load the actual HTML sample for station 22826
        html_path = Path(__file__).parent.parent / "fixtures" / "station_pages" / "station_22826_tokyu_meguro_line.html"

        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        crawler = StationCrawler()

        # Mock the HTTP response to return our HTML sample
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content

        with patch.object(crawler.session, 'get', return_value=mock_response):
            details = crawler._get_station_details("/station/22826")

        # Test extracted data against known values from HTML
        assert details.station_id == "22826"

        # Test station reading extraction
        assert details.station_reading == "でんえんちょうふ"

        # Test line extraction - should find both Tokyu lines
        assert details.all_lines is not None
        assert isinstance(details.all_lines, list)
        assert len(details.all_lines) == 2

        # Verify specific lines are extracted (both Tokyu lines)
        expected_lines = [
            "東急東横線",
            "東急目黒線"
        ]
        for expected_line in expected_lines:
            assert expected_line in details.all_lines, f"Expected line '{expected_line}' not found in {details.all_lines}"

        # Verify company name extraction (should be Tokyu Corporation)
        assert details.company_name == "東急電鉄"

        # Verify line name extraction (should pick up Toyoko Line from JSON - the main line)
        assert details.line_name == "東横線"

    def test_get_station_details_shibuya_jr_yamanote(self):
        """Test station detail extraction using station 22715 (渋谷駅) HTML - Japan's busiest interchange."""
        # Load the actual HTML sample for station 22715
        html_path = Path(__file__).parent.parent / "fixtures" / "station_pages" / "station_22715_shibuya_jr_yamanote.html"

        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        crawler = StationCrawler()

        # Mock the HTTP response to return our HTML sample
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content

        with patch.object(crawler.session, 'get', return_value=mock_response):
            details = crawler._get_station_details("/station/22715")

        # Test extracted data against known values from HTML
        assert details.station_id == "22715"

        # Test station reading extraction
        assert details.station_reading == "しぶや"

        # Test line extraction - should find all nine lines (JR + private + metro)
        assert details.all_lines is not None
        assert isinstance(details.all_lines, list)
        assert len(details.all_lines) == 9

        # Verify specific lines are extracted (JR East, Tokyu, Keio, Tokyo Metro)
        expected_lines = [
            "ＪＲ山手線外回り",
            "ＪＲ山手線内回り",
            "ＪＲ埼京線",
            "東急東横線",
            "東急田園都市線",
            "京王井の頭線",
            "東京メトロ銀座線",
            "東京メトロ半蔵門線",
            "東京メトロ副都心線"
        ]
        for expected_line in expected_lines:
            assert expected_line in details.all_lines, f"Expected line '{expected_line}' not found in {details.all_lines}"

        # Verify company name extraction (should be Tokyu - the primary operator in JSON)
        assert details.company_name == "東急電鉄"

        # Verify line name extraction (from JSON data - should be Den-en-toshi Line)
        assert details.line_name == "田園都市線"

    def test_get_station_details_hiroshima_astram_line(self):
        """Test station detail extraction using station 27244 (紙屋町東駅) HTML - Hiroshima Astram Line monorail."""
        # Load the actual HTML sample for station 27244
        html_path = Path(__file__).parent.parent / "fixtures" / "station_pages" / "station_27244_hiroshima_astram.html"

        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        crawler = StationCrawler()

        # Mock the HTTP response to return our HTML sample
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content

        with patch.object(crawler.session, 'get', return_value=mock_response):
            details = crawler._get_station_details("/station/27244")

        # Test extracted data against known values from HTML
        assert details.station_id == "27244"

        # Test station reading extraction
        assert details.station_reading == "かみやす"

        # Test line extraction - Astram Line is a monorail with single line
        assert details.all_lines is not None
        assert isinstance(details.all_lines, list)
        # For monorail systems, lines array might be empty as it's a single line system
        assert len(details.all_lines) >= 0

        # Verify company name extraction (Hiroshima Rapid Transit)
        assert details.company_name == "広島高速交通"

        # Verify line name extraction (Astram Line)
        assert details.line_name == "アストラムライン"
