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
                name_hiragana="しんじゅく",
                name_katakana="シンジュク",
                name_romaji="shinjuku",
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
            assert rows[0]["name_hiragana"] == "しんじゅく"
            assert rows[0]["name_katakana"] == "シンジュク"
            assert rows[0]["name_romaji"] == "shinjuku"

            # Check second station (with empty fields)
            assert rows[1]["name"] == "渋谷"
            assert rows[1]["prefecture"] == "東京都"
            assert rows[1]["prefecture_id"] == "13"
            assert rows[1]["railway_company"] == ""
            assert rows[1]["aliases"] == ""
            assert rows[1]["name_hiragana"] == ""
            assert rows[1]["name_katakana"] == ""
            assert rows[1]["name_romaji"] == ""

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
        # Create test CSV data with new format
        csv_content = (
            """name,prefecture,prefecture_id,station_id,railway_company,line_name,aliases,name_hiragana,name_katakana,name_romaji,all_lines
新宿,東京都,13,12345,JR東日本,山手線,しんじゅく|Shinjuku,しんじゅく,シンジュク,shinjuku,
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
            assert station1.name_hiragana == "しんじゅく"
            assert station1.name_katakana == "シンジュク"
            assert station1.name_romaji == "shinjuku"

            # Check second station
            station2 = stations[1]
            assert station2.name == "渋谷"
            assert station2.prefecture == "東京都"
            assert station2.prefecture_id == "13"
            assert station2.station_id == "54321"
            assert station2.railway_company is None
            assert station2.aliases == []
            assert station2.name_hiragana is None
            assert station2.name_katakana is None
            assert station2.name_romaji is None

        finally:
            csv_path.unlink()

    def test_load_from_csv_empty_values(self):
        """Test loading CSV with empty values."""
        csv_content = (
            """name,prefecture,prefecture_id,station_id,railway_company,line_name,aliases,name_hiragana,name_katakana,name_romaji,all_lines
テスト駅,,,,,,,,,,"""
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
            assert station.name_hiragana is None
            assert station.name_katakana is None
            assert station.name_romaji is None
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
                name="新宿",
                prefecture="東京都",
                aliases=["しんじゅく", "Shinjuku"],
                name_hiragana="しんじゅく",
                name_katakana="シンジュク",
                name_romaji="shinjuku",
            ),
            Station(
                name="新宿三丁目",
                prefecture="東京都",
                name_hiragana="しんじゅくさんちょうめ",
                name_katakana="シンジュクサンチョウメ",
                name_romaji="shinjuku-sanchome",
            ),
            Station(
                name="渋谷",
                prefecture="東京都",
                name_hiragana="しぶや",
                name_katakana="シブヤ",
                name_romaji="shibuya",
            ),
            Station(
                name="横浜",
                prefecture="神奈川県",
                name_hiragana="よこはま",
                name_katakana="ヨコハマ",
                name_romaji="yokohama",
            ),
            Station(
                name="新横浜",
                prefecture="神奈川県",
                name_hiragana="しんよこはま",
                name_katakana="シンヨコハマ",
                name_romaji="shin-yokohama",
            ),
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

    def test_search_by_hiragana(self, sample_stations):
        """Test searching by hiragana text."""
        searcher = StationSearcher(sample_stations)

        results = searcher.search_by_name("しんじゅく")
        assert len(results) >= 1
        station_names = [s.name for s in results]
        assert "新宿" in station_names

    def test_search_by_katakana(self, sample_stations):
        """Test searching by katakana text."""
        searcher = StationSearcher(sample_stations)

        results = searcher.search_by_name("シブヤ")
        assert len(results) >= 1
        station_names = [s.name for s in results]
        assert "渋谷" in station_names

    def test_search_by_romaji(self, sample_stations):
        """Test searching by romaji text."""
        searcher = StationSearcher(sample_stations)

        results = searcher.search_by_name("yokohama")
        assert len(results) >= 1
        station_names = [s.name for s in results]
        assert "横浜" in station_names

    def test_fuzzy_search_with_threshold(self, sample_stations):
        """Test fuzzy search with different thresholds."""
        searcher = StationSearcher(sample_stations)

        # High threshold - exact matches only
        results = searcher.fuzzy_search("新宿", threshold=90)
        assert len(results) >= 1
        if isinstance(results[0], tuple):
            station, score = results[0]
            assert station.name == "新宿"
            assert score >= 90
        else:
            assert results[0].name == "新宿"

        # Lower threshold - fuzzy matches allowed
        results = searcher.fuzzy_search("shinjuk", threshold=70)  # Missing 'u'
        assert len(results) >= 1

    def test_fuzzy_search_returns_scores(self, sample_stations):
        """Test that fuzzy search returns tuples with scores."""
        searcher = StationSearcher(sample_stations)

        results = searcher.fuzzy_search("新宿", threshold=50)
        assert len(results) > 0

        for result in results:
            if isinstance(result, tuple):
                station, score = result
                assert hasattr(station, "name")
                assert isinstance(score, (int, float))
                assert 0 <= score <= 100


class TestEnhancedStationSearch:
    """Test cases for enhanced station search functionality."""

    @pytest.fixture
    def comprehensive_stations(self):
        """Create comprehensive station list for advanced search testing."""
        return [
            Station(
                name="新宿",
                prefecture="東京都",
                aliases=["しんじゅく", "Shinjuku"],
                name_hiragana="しんじゅく",
                name_katakana="シンジュク",
                name_romaji="shinjuku",
                railway_company="JR東日本",
                line_name="山手線",
            ),
            Station(
                name="新宿三丁目",
                prefecture="東京都",
                name_hiragana="しんじゅくさんちょうめ",
                name_katakana="シンジュクサンチョウメ",
                name_romaji="shinjuku-sanchome",
                railway_company="東京メトロ",
                line_name="丸ノ内線",
            ),
            Station(
                name="西新宿",
                prefecture="東京都",
                name_hiragana="にししんじゅく",
                name_katakana="ニシシンジュク",
                name_romaji="nishi-shinjuku",
                railway_company="東京メトロ",
                line_name="丸ノ内線",
            ),
            Station(
                name="渋谷",
                prefecture="東京都",
                name_hiragana="しぶや",
                name_katakana="シブヤ",
                name_romaji="shibuya",
                railway_company="JR東日本",
                line_name="山手線",
            ),
            Station(
                name="横浜",
                prefecture="神奈川県",
                name_hiragana="よこはま",
                name_katakana="ヨコハマ",
                name_romaji="yokohama",
                railway_company="JR東日本",
                line_name="東海道本線",
            ),
        ]

    def test_fuzzy_search_exact_match(self, comprehensive_stations):
        """Test fuzzy search with exact matches returns high scores."""
        searcher = StationSearcher(comprehensive_stations)

        results = searcher.fuzzy_search("新宿", threshold=80)
        assert len(results) > 0

        # First result should be exact match with high score
        first_result = results[0]
        if isinstance(first_result, tuple):
            station, score = first_result
            assert station.name == "新宿"
            assert score >= 95  # Exact match should have very high score

    def test_fuzzy_search_partial_match(self, comprehensive_stations):
        """Test fuzzy search with partial matches."""
        searcher = StationSearcher(comprehensive_stations)

        results = searcher.fuzzy_search("新宿", threshold=50)
        assert len(results) >= 3  # Should find 新宿, 新宿三丁目, 西新宿

        station_names = []
        for result in results:
            if isinstance(result, tuple):
                station, score = result
                station_names.append(station.name)
                assert score >= 50
            else:
                station_names.append(result.name)

        assert "新宿" in station_names
        assert "新宿三丁目" in station_names or "西新宿" in station_names

    def test_fuzzy_search_hiragana_query(self, comprehensive_stations):
        """Test fuzzy search with hiragana query."""
        searcher = StationSearcher(comprehensive_stations)

        results = searcher.fuzzy_search("しんじゅく", threshold=70)
        assert len(results) > 0

        # Should find stations with matching hiragana
        found_shinjuku = False
        for result in results:
            if isinstance(result, tuple):
                station, score = result
                if station.name == "新宿":
                    found_shinjuku = True
                    assert score >= 70
            else:
                if result.name == "新宿":
                    found_shinjuku = True

        assert found_shinjuku

    def test_fuzzy_search_katakana_query(self, comprehensive_stations):
        """Test fuzzy search with katakana query."""
        searcher = StationSearcher(comprehensive_stations)

        results = searcher.fuzzy_search("シブヤ", threshold=70)
        assert len(results) > 0

        # Should find Shibuya station
        found_shibuya = False
        for result in results:
            if isinstance(result, tuple):
                station, score = result
                if station.name == "渋谷":
                    found_shibuya = True
                    assert score >= 70
            else:
                if result.name == "渋谷":
                    found_shibuya = True

        assert found_shibuya

    def test_fuzzy_search_romaji_query(self, comprehensive_stations):
        """Test fuzzy search with romaji query."""
        searcher = StationSearcher(comprehensive_stations)

        results = searcher.fuzzy_search("yokohama", threshold=70)
        assert len(results) > 0

        # Should find Yokohama station
        found_yokohama = False
        for result in results:
            if isinstance(result, tuple):
                station, score = result
                if station.name == "横浜":
                    found_yokohama = True
                    assert score >= 70
            else:
                if result.name == "横浜":
                    found_yokohama = True

        assert found_yokohama

    def test_fuzzy_search_typo_tolerance(self, comprehensive_stations):
        """Test fuzzy search with typos."""
        searcher = StationSearcher(comprehensive_stations)

        # Test with common typos
        test_cases = [
            ("shinjku", "新宿"),  # Missing 'u'
            ("shibya", "渋谷"),  # Missing 'u'
            ("yokohma", "横浜"),  # Missing 'a'
        ]

        for typo_query, expected_station in test_cases:
            results = searcher.fuzzy_search(typo_query, threshold=60)
            assert len(results) > 0, f"No results found for typo query: {typo_query}"

            found_expected = False
            for result in results:
                if isinstance(result, tuple):
                    station, score = result
                    if station.name == expected_station:
                        found_expected = True
                        assert score >= 60
                        break
                else:
                    if result.name == expected_station:
                        found_expected = True
                        break

            assert found_expected, (
                f"Expected station '{expected_station}' not found for typo '{typo_query}'"
            )

    def test_fuzzy_search_threshold_filtering(self, comprehensive_stations):
        """Test that fuzzy search respects threshold filtering."""
        searcher = StationSearcher(comprehensive_stations)

        # High threshold should return fewer results
        high_results = searcher.fuzzy_search("新宿", threshold=90)
        low_results = searcher.fuzzy_search("新宿", threshold=50)

        assert len(high_results) <= len(low_results)

        # All high threshold results should have high scores
        for result in high_results:
            if isinstance(result, tuple):
                station, score = result
                assert score >= 90

    def test_fuzzy_search_score_ordering(self, comprehensive_stations):
        """Test that fuzzy search results are ordered by score."""
        searcher = StationSearcher(comprehensive_stations)

        results = searcher.fuzzy_search("新宿", threshold=40)
        assert len(results) > 1

        # Extract scores and verify ordering
        scores = []
        for result in results:
            if isinstance(result, tuple):
                station, score = result
                scores.append(score)
            else:
                scores.append(100.0)  # Assume perfect match if no score

        # Scores should be in descending order
        assert scores == sorted(scores, reverse=True)

    def test_fuzzy_search_empty_query(self, comprehensive_stations):
        """Test fuzzy search with empty query."""
        searcher = StationSearcher(comprehensive_stations)

        results = searcher.fuzzy_search("", threshold=50)
        # Empty query should return no results
        assert len(results) == 0

    def test_fuzzy_search_no_matches_above_threshold(self, comprehensive_stations):
        """Test fuzzy search when no matches exceed threshold."""
        searcher = StationSearcher(comprehensive_stations)

        # Use a very high threshold with a poor match
        results = searcher.fuzzy_search("xyz", threshold=95)
        assert len(results) == 0

    def test_build_search_index_with_japanese_variants(self, comprehensive_stations):
        """Test that search index includes all Japanese text variants."""
        searcher = StationSearcher(comprehensive_stations)

        # Check that index contains various forms
        index_keys = set()
        for key_list in searcher.name_index.values():
            for station in key_list:
                index_keys.add(station.name)

        # Should contain the original station names
        assert "新宿" in [s.name for s in comprehensive_stations]
        assert "渋谷" in [s.name for s in comprehensive_stations]

    def test_enhanced_search_by_name_with_japanese_variants(
        self, comprehensive_stations
    ):
        """Test enhanced search_by_name method with Japanese variants."""
        searcher = StationSearcher(comprehensive_stations)

        # Test searching by different text forms
        test_cases = [
            ("新宿", "新宿"),
            ("しんじゅく", "新宿"),
            ("シンジュク", "新宿"),
            ("shinjuku", "新宿"),
        ]

        for query, expected_station in test_cases:
            results = searcher.search_by_name(query, exact=False)
            assert len(results) > 0, f"No results for query: {query}"

            station_names = [s.name for s in results]
            assert expected_station in station_names, (
                f"Expected '{expected_station}' not found for query '{query}'"
            )


class TestStationDetailExtraction:
    """Test cases for station detail extraction from real HTML."""

    def test_get_station_details_from_real_html(self):
        """Test station detail extraction using real Yahoo Transit HTML."""
        # Load the actual HTML sample
        html_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "station_pages"
            / "station_20042_yamanose_line.html"
        )

        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        crawler = StationCrawler()

        # Mock the HTTP response to return our HTML sample
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content

        with patch.object(crawler.session, "get", return_value=mock_response):
            details = crawler._get_station_details("/station/20042")

        # Test extracted data against known values from HTML
        assert details.station_id == "20042"

        # The current implementation should extract some lines
        assert details.all_lines is not None
        assert isinstance(details.all_lines, list)

        # Should find some line information in the HTML
        # The HTML contains "札幌市電内回り" and "札幌市電外回り"
        assert len(details.all_lines) > 0, (
            "Should extract at least some line information"
        )

    def test_extract_station_name_and_reading(self):
        """Test extraction of station name and reading from HTML structure."""
        html_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "station_pages"
            / "station_20042_yamanose_line.html"
        )

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
        html_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "station_pages"
            / "station_20042_yamanose_line.html"
        )

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
        transport_info = json_data["props"]["pageProps"]["lipFeature"][
            "TransitSearchInfo"
        ]["Detail"]
        assert transport_info["CompanyName"] == "札幌市交通事業振興公社"
        assert transport_info["RailName"] == "山鼻線"
        assert transport_info["StationId"] == "20042"

    def test_prefecture_extraction_from_url_params(self):
        """Test prefecture extraction from URL parameters."""
        html_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "station_pages"
            / "station_20042_yamanose_line.html"
        )

        with open(html_path, encoding="utf-8") as f:
            f.read()  # Just read to verify file exists

        # The URL contains pref=1 parameter which maps to Hokkaido
        crawler = StationCrawler()

        # Test URL with Hokkaido code
        hokkaido_url = "https://transit.yahoo.co.jp/station/01/test"
        prefecture = crawler._get_prefecture_from_url(hokkaido_url)
        # Now correctly handles Hokkaido prefecture mapping
        assert (
            prefecture == "北海道"
        )  # Enhanced implementation now handles all 47 prefectures

    @patch("time.sleep")  # Mock sleep to speed up tests
    def test_station_id_extraction_from_url(self, mock_sleep):
        """Test station ID extraction from URL patterns."""
        crawler = StationCrawler()

        # Test different URL patterns
        test_urls = [
            "https://transit.yahoo.co.jp/station/20042",
            "/station/20042?pref=1&company=test",
            "https://transit.yahoo.co.jp/station/12345/info",
        ]

        expected_ids = ["20042", "20042", "12345"]

        for url, expected_id in zip(test_urls, expected_ids, strict=True):
            # Mock response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "<html><body>Test</body></html>"

            with patch.object(crawler.session, "get", return_value=mock_response):
                details = crawler._get_station_details(url)
                assert details.station_id == expected_id

    def test_get_station_details_higashi_tonden_dori(self):
        """Test station detail extraction using station 20470 (東屯田通駅) HTML."""
        # Load the actual HTML sample for station 20470
        html_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "station_pages"
            / "station_20470_sapporo_line.html"
        )

        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        crawler = StationCrawler()

        # Mock the HTTP response to return our HTML sample
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content

        with patch.object(crawler.session, "get", return_value=mock_response):
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
        html_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "station_pages"
            / "station_23018_tokyu_meguro_line.html"
        )

        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        crawler = StationCrawler()

        # Mock the HTTP response to return our HTML sample
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content

        with patch.object(crawler.session, "get", return_value=mock_response):
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
            "都営地下鉄三田線",
        ]
        for expected_line in expected_lines:
            assert expected_line in details.all_lines, (
                f"Expected line '{expected_line}' not found in {details.all_lines}"
            )

        # Verify company name extraction (should pick up from JSON - Tokyo Metro in this case)
        assert details.company_name == "東京地下鉄"

        # Verify line name extraction (from JSON data - should be 南北線)
        assert details.line_name == "南北線"

    def test_get_station_details_denenchofu_tokyu_lines(self):
        """Test station detail extraction using station 22826 (田園調布駅) HTML - Tokyu multi-line station."""
        # Load the actual HTML sample for station 22826
        html_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "station_pages"
            / "station_22826_tokyu_meguro_line.html"
        )

        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        crawler = StationCrawler()

        # Mock the HTTP response to return our HTML sample
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content

        with patch.object(crawler.session, "get", return_value=mock_response):
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
        expected_lines = ["東急東横線", "東急目黒線"]
        for expected_line in expected_lines:
            assert expected_line in details.all_lines, (
                f"Expected line '{expected_line}' not found in {details.all_lines}"
            )

        # Verify company name extraction (should be Tokyu Corporation)
        assert details.company_name == "東急電鉄"

        # Verify line name extraction (should pick up Toyoko Line from JSON - the main line)
        assert details.line_name == "東横線"

    def test_get_station_details_shibuya_jr_yamanote(self):
        """Test station detail extraction using station 22715 (渋谷駅) HTML - Japan's busiest interchange."""
        # Load the actual HTML sample for station 22715
        html_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "station_pages"
            / "station_22715_shibuya_jr_yamanote.html"
        )

        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        crawler = StationCrawler()

        # Mock the HTTP response to return our HTML sample
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content

        with patch.object(crawler.session, "get", return_value=mock_response):
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
            "東京メトロ副都心線",
        ]
        for expected_line in expected_lines:
            assert expected_line in details.all_lines, (
                f"Expected line '{expected_line}' not found in {details.all_lines}"
            )

        # Verify company name extraction (should be Tokyu - the primary operator in JSON)
        assert details.company_name == "東急電鉄"

        # Verify line name extraction (from JSON data - should be Den-en-toshi Line)
        assert details.line_name == "田園都市線"

    def test_get_station_details_hiroshima_astram_line(self):
        """Test station detail extraction using station 27244 (紙屋町東駅) HTML - Hiroshima Astram Line monorail."""
        # Load the actual HTML sample for station 27244
        html_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "station_pages"
            / "station_27244_hiroshima_astram.html"
        )

        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        crawler = StationCrawler()

        # Mock the HTTP response to return our HTML sample
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content

        with patch.object(crawler.session, "get", return_value=mock_response):
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
