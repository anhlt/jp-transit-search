"""Unit tests for Yahoo Transit scraper."""

import re

import pytest
import requests
import responses
from bs4 import BeautifulSoup

from jp_transit_search.core.exceptions import (
    RouteNotFoundError,
    ScrapingError,
    ValidationError,
)
from jp_transit_search.core.scraper import YahooTransitScraper


class TestYahooTransitScraper:
    """Test Yahoo Transit scraper."""

    def test_scraper_initialization(self):
        """Test scraper initialization."""
        scraper = YahooTransitScraper()
        assert scraper.timeout == 30

        scraper_custom = YahooTransitScraper(timeout=60)
        assert scraper_custom.timeout == 60

    def test_validation_error_empty_stations(self):
        """Test validation errors for empty station names."""
        scraper = YahooTransitScraper()

        with pytest.raises(
            ValidationError, match="Departure station name cannot be empty"
        ):
            scraper.search_route("", "豊洲")

        with pytest.raises(
            ValidationError, match="Destination station name cannot be empty"
        ):
            scraper.search_route("横浜", "")

        with pytest.raises(
            ValidationError, match="Departure station name cannot be empty"
        ):
            scraper.search_route("   ", "豊洲")

    @responses.activate
    def test_route_not_found_error(self):
        """Test route not found error."""
        responses.add(
            responses.GET,
            "https://transit.yahoo.co.jp/search/result",
            body="経路が見つかりませんでした",
            status=200,
        )

        scraper = YahooTransitScraper()
        with pytest.raises(RouteNotFoundError):
            scraper.search_route("InvalidStation", "AnotherInvalidStation")

    @responses.activate
    def test_successful_route_parsing(self, sample_yahoo_response):
        """Test successful route parsing."""
        responses.add(
            responses.GET,
            "https://transit.yahoo.co.jp/search/result",
            body=sample_yahoo_response,
            status=200,
        )

        scraper = YahooTransitScraper()
        routes = scraper.search_route("横浜", "豊洲")

        assert isinstance(routes, list)
        assert len(routes) > 0
        route = routes[0]  # Get first route
        assert route.from_station == "横浜"
        assert route.to_station == "豊洲"
        assert route.duration == "49分(乗車33分)"
        assert route.cost == "IC優先：628円"
        assert route.transfer_count == 2
        assert len(route.transfers) == 3  # Should extract 3 transfers from fixture

    def test_extract_duration(self):
        """Test duration extraction."""
        scraper = YahooTransitScraper()
        html = '<div class="routeSummary"><li class="time">49分(乗車33分)</li></div>'
        soup = BeautifulSoup(html, "html.parser")
        route_summary = soup.find("div", class_="routeSummary")

        duration = scraper._extract_duration(route_summary)
        assert duration == "49分(乗車33分)"

    def test_extract_transfer_count(self):
        """Test transfer count extraction."""
        scraper = YahooTransitScraper()
        html = '<div class="routeSummary"><li class="transfer">乗換：2回</li></div>'
        soup = BeautifulSoup(html, "html.parser")
        route_summary = soup.find("div", class_="routeSummary")

        count = scraper._extract_transfer_count(route_summary)
        assert count == 2

    def test_extract_cost(self):
        """Test cost extraction."""
        scraper = YahooTransitScraper()
        html = '<div class="routeSummary"><li class="fare">IC優先：628円</li></div>'
        soup = BeautifulSoup(html, "html.parser")
        route_summary = soup.find("div", class_="routeSummary")

        cost = scraper._extract_cost(route_summary)
        assert cost == "IC優先：628円"

    def test_missing_route_summary_error(self):
        """Test error when route summary is missing."""
        scraper = YahooTransitScraper()
        html = "<div>No route summary here</div>"

        with pytest.raises(ScrapingError, match="Could not find any route sections"):
            scraper._parse_route_page(
                html,
                type(
                    "MockRequest", (), {"from_station": "横浜", "to_station": "豊洲"}
                )(),
            )

    def test_extract_duration_missing(self):
        """Test duration extraction when element is missing."""
        scraper = YahooTransitScraper()
        html = '<div class="routeSummary">No time element</div>'
        soup = BeautifulSoup(html, "html.parser")
        route_summary = soup.find("div", class_="routeSummary")

        with pytest.raises(ScrapingError, match="Could not find duration information"):
            scraper._extract_duration(route_summary)

    def test_extract_transfer_count_missing(self):
        """Test transfer count extraction when element is missing."""
        scraper = YahooTransitScraper()
        html = '<div class="routeSummary">No transfer element</div>'
        soup = BeautifulSoup(html, "html.parser")
        route_summary = soup.find("div", class_="routeSummary")

        count = scraper._extract_transfer_count(route_summary)
        assert count == 0

    def test_extract_transfer_count_no_number(self):
        """Test transfer count extraction when no number found."""
        scraper = YahooTransitScraper()
        html = '<div class="routeSummary"><li class="transfer">乗換なし</li></div>'
        soup = BeautifulSoup(html, "html.parser")
        route_summary = soup.find("div", class_="routeSummary")

        count = scraper._extract_transfer_count(route_summary)
        assert count == 0

    def test_extract_cost_missing(self):
        """Test cost extraction when element is missing."""
        scraper = YahooTransitScraper()
        html = '<div class="routeSummary">No fare element</div>'
        soup = BeautifulSoup(html, "html.parser")
        route_summary = soup.find("div", class_="routeSummary")

        with pytest.raises(ScrapingError, match="Could not find fare information"):
            scraper._extract_cost(route_summary)

    def test_extract_transfers_no_route_detail(self):
        """Test transfer extraction when route detail is missing."""
        scraper = YahooTransitScraper()
        html = "<div>No route detail here</div>"
        soup = BeautifulSoup(html, "html.parser")

        transfers = scraper._extract_transfers_from_section(soup)
        assert transfers == []

    def test_extract_transfers_empty_data(self):
        """Test transfer extraction with empty route detail."""
        scraper = YahooTransitScraper()
        html = '<div class="routeDetail"></div>'
        soup = BeautifulSoup(html, "html.parser")

        transfers = scraper._extract_transfers_from_section(soup)
        assert transfers == []

    @responses.activate
    def test_network_error(self):
        """Test network error handling."""
        responses.add(
            responses.GET,
            re.compile(r"https://transit\.yahoo\.co\.jp/search/result.*"),
            body=requests.RequestException("Network error"),
        )

        scraper = YahooTransitScraper()
        with pytest.raises(ScrapingError):
            scraper.search_route("横浜", "豊洲")

    def test_parse_route_page_general_exception(self):
        """Test general exception handling in parse_route_page."""
        scraper = YahooTransitScraper()
        # Invalid HTML that will cause parsing issues
        html = None

        with pytest.raises(ScrapingError, match="Failed to parse route data"):
            scraper._parse_route_page(
                html,
                type(
                    "MockRequest", (), {"from_station": "横浜", "to_station": "豊洲"}
                )(),
            )

    def test_parse_route_page_ofuna_shibuya_multi_routes(self):
        """Test route parsing for 大船→渋谷 with 3 routes fixture."""
        from pathlib import Path

        # Load the actual HTML sample for 大船→渋谷 search results
        html_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "search_results"
            / "search_大船渋谷.html"
        )

        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        scraper = YahooTransitScraper()

        # Create mock request object
        mock_request = type(
            "MockRequest", (), {"from_station": "大船", "to_station": "渋谷"}
        )()

        # Parse the route page
        routes = scraper._parse_route_page(html_content, mock_request)

        # Should extract exactly 3 routes
        assert len(routes) == 3

        # Verify route data matches fixture content
        route1, route2, route3 = routes

        from datetime import time

        # Route 1: 05:09→06:17 (1h8m, 2 transfers, 627円)
        assert route1.departure_time == time(5, 9)
        assert route1.arrival_time == time(6, 17)
        assert route1.duration == "05:09発→06:17着1時間8分（乗車52分）"
        assert route1.transfer_count == 2
        assert route1.cost == "IC優先：627円"

        # Route 2: 05:04→06:17 (1h13m, 2 transfers, 627円)
        assert route2.departure_time == time(5, 4)
        assert route2.arrival_time == time(6, 17)
        assert route2.duration == "05:04発→06:17着1時間13分（乗車54分）"
        assert route2.transfer_count == 2
        assert route2.cost == "IC優先：627円"

        # Route 3: 05:09→06:18 (1h9m, 1 transfer, 627円)
        assert route3.departure_time == time(5, 9)
        assert route3.arrival_time == time(6, 18)
        assert route3.duration == "05:09発→06:18着1時間9分（乗車58分）"
        assert route3.transfer_count == 1
        assert route3.cost == "IC優先：627円"

    def test_parse_route_page_ofuna_shinjuku_with_time(self):
        """Test route parsing for 大船→新宿 with specific start time."""
        from datetime import datetime
        from pathlib import Path

        # Load the actual HTML sample for 大船→新宿 search results
        html_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "search_results"
            / "search_大船新宿.html"
        )

        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        scraper = YahooTransitScraper()

        # Create mock request object with specific time
        mock_request = type(
            "MockRequest",
            (),
            {
                "from_station": "大船",
                "to_station": "新宿",
                "search_datetime": datetime(2025, 10, 31, 16, 31),
                "search_type": "earliest",
            },
        )()

        # Parse the route page
        routes = scraper._parse_route_page(html_content, mock_request)

        # Should extract exactly 3 routes
        assert len(routes) == 3

        # Verify route data matches fixture content
        route1, route2, route3 = routes

        from datetime import time

        # Route 1: 16:34→17:22 (48m, 0 transfers, 945円)
        assert route1.departure_time == time(16, 34)
        assert route1.arrival_time == time(17, 22)
        assert route1.duration == "16:34発→17:22着48分（乗車48分）"
        assert route1.transfer_count == 0
        assert route1.cost == "IC優先：945円"

        # Route 2: 16:47→17:39 (52m, 0 transfers, 945円)
        assert route2.departure_time == time(16, 47)
        assert route2.arrival_time == time(17, 39)
        assert route2.duration == "16:47発→17:39着52分（乗車52分）"
        assert route2.transfer_count == 0
        assert route2.cost == "IC優先：945円"

        # Route 3: 16:51→17:46 (55m, 2 transfers, 945円)
        assert route3.departure_time == time(16, 51)
        assert route3.arrival_time == time(17, 46)
        assert route3.duration == "16:51発→17:46着55分（乗車50分）"
        assert route3.transfer_count == 2
        assert route3.cost == "IC優先：945円"

    def test_search_route_with_datetime(self):
        """Test search_route method with datetime parameter."""
        from datetime import datetime

        from jp_transit_search.core.models import RouteSearchRequest

        # Test URL generation with datetime
        search_dt = datetime(2025, 10, 31, 16, 31)
        request = RouteSearchRequest(
            from_station="大船",
            to_station="新宿",
            search_datetime=search_dt,
            search_type="earliest",
        )

        url = request.to_yahoo_url()
        expected_params = [
            "from=大船",
            "to=新宿",
            "y=2025",
            "m=10",
            "d=31",
            "hh=16",
            "m1=3",
            "m2=1",
        ]

        for param in expected_params:
            assert param in url

    def test_search_route_different_search_types(self):
        """Test search_route with different search types."""
        from datetime import datetime

        from jp_transit_search.core.models import RouteSearchRequest

        # Test different search types
        search_dt = datetime(2025, 10, 31, 16, 31)

        # Test earliest
        request1 = RouteSearchRequest(
            from_station="大船",
            to_station="新宿",
            search_datetime=search_dt,
            search_type="earliest",
        )
        assert "s=0" in request1.to_yahoo_url()

        # Test cheapest
        request2 = RouteSearchRequest(
            from_station="大船",
            to_station="新宿",
            search_datetime=search_dt,
            search_type="cheapest",
        )
        assert "s=1" in request2.to_yahoo_url()

        # Test easiest
        request3 = RouteSearchRequest(
            from_station="大船",
            to_station="新宿",
            search_datetime=search_dt,
            search_type="easiest",
        )
        assert "s=2" in request3.to_yahoo_url()

    def test_parse_route_page_ofuna_haneda_with_time(self):
        """Test parsing 大船→羽田空港 route with specific departure time."""
        from datetime import datetime, time

        with open(
            "tests/fixtures/search_results/search_大船羽田空港.html", encoding="utf-8"
        ) as f:
            html_content = f.read()

        scraper = YahooTransitScraper()

        # Create mock request object with specific time
        mock_request = type(
            "MockRequest",
            (),
            {
                "from_station": "大船",
                "to_station": "羽田空港(東京)",
                "search_datetime": datetime(2025, 10, 31, 16, 31),
                "search_type": "earliest",
            },
        )()

        # Parse the route page
        routes = scraper._parse_route_page(html_content, mock_request)

        # Should extract exactly 3 routes
        assert len(routes) == 3

        # Verify route data matches expected values
        route1, route2, route3 = routes

        # Route 1: 16:36→17:34 58分 715円 乗換：1回
        assert route1.departure_time == time(16, 36)
        assert route1.arrival_time == time(17, 34)
        assert route1.duration == "16:36発→17:34着58分（乗車45分）"
        assert route1.transfer_count == 1
        assert route1.cost == "IC優先：715円"

        # Route 2: 16:34→17:34 1時間0分 715円 乗換：1回
        assert route2.departure_time == time(16, 34)
        assert route2.arrival_time == time(17, 34)
        assert route2.duration == "16:34発→17:34着1時間0分（乗車43分）"
        assert route2.transfer_count == 1
        assert route2.cost == "IC優先：715円"

        # Route 3: 16:37→17:37 1時間0分 968円 乗換：1回
        assert route3.departure_time == time(16, 37)
        assert route3.arrival_time == time(17, 37)
        assert route3.duration == "16:37発→17:37着1時間0分（乗車41分）"
        assert route3.transfer_count == 1
        assert route3.cost == "IC優先：968円"

        # Test detailed transfer information for route 1
        assert len(route1.transfers) == 2

        # Transfer 1: 大船 -> 横浜 (JR東海道本線)
        transfer1 = route1.transfers[0]
        assert transfer1.from_station == "大船"
        assert transfer1.to_station == "横浜"
        assert transfer1.line_name == "ＪＲ東海道本線"
        assert transfer1.departure_time == "16:36"
        assert transfer1.arrival_time == "16:52"
        assert transfer1.departure_platform == "1・2番線"
        assert transfer1.arrival_platform == "7番線"
        assert transfer1.riding_position == "[15両] 前 中"
        assert len(transfer1.intermediate_stations) == 1
        assert transfer1.intermediate_stations[0].name == "戸塚"
        assert transfer1.intermediate_stations[0].arrival_time == "16:42"

        # Transfer 2: 横浜 -> 羽田空港第１・第２ターミナル(京急) (京急本線)
        transfer2 = route1.transfers[1]
        assert transfer2.from_station == "横浜"
        assert transfer2.to_station == "羽田空港第１・第２ターミナル(京急)"
        assert transfer2.line_name == "京急本線"
        assert transfer2.departure_time == "16:58"
        assert transfer2.arrival_time == "17:27"
        assert transfer2.departure_platform == "2番線"
        assert transfer2.arrival_platform == "2番線"
        assert transfer2.riding_position is None
        assert len(transfer2.intermediate_stations) == 10
        # Test a few key intermediate stations
        assert transfer2.intermediate_stations[0].name == "京急東神奈川"
        assert transfer2.intermediate_stations[0].arrival_time == "17:00"
        assert transfer2.intermediate_stations[3].name == "京急川崎"
        assert transfer2.intermediate_stations[3].arrival_time == "17:09"
        assert transfer2.intermediate_stations[9].name == "羽田空港第３ターミナル(京急)"
        assert transfer2.intermediate_stations[9].arrival_time == "17:25"
