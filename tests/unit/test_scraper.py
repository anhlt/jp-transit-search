"""Unit tests for Yahoo Transit scraper."""

import pytest
import responses
from bs4 import BeautifulSoup

from jp_transit_search.core.scraper import YahooTransitScraper
from jp_transit_search.core.exceptions import ValidationError, RouteNotFoundError, ScrapingError


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
        
        with pytest.raises(ValidationError, match="Departure station name cannot be empty"):
            scraper.search_route("", "豊洲")
        
        with pytest.raises(ValidationError, match="Destination station name cannot be empty"):
            scraper.search_route("横浜", "")
        
        with pytest.raises(ValidationError, match="Departure station name cannot be empty"):
            scraper.search_route("   ", "豊洲")
    
    @responses.activate
    def test_route_not_found_error(self):
        """Test route not found error."""
        responses.add(
            responses.GET,
            "https://transit.yahoo.co.jp/search/print",
            body="経路が見つかりませんでした",
            status=200
        )
        
        scraper = YahooTransitScraper()
        with pytest.raises(RouteNotFoundError):
            scraper.search_route("InvalidStation", "AnotherInvalidStation")
    
    @responses.activate 
    def test_successful_route_parsing(self, sample_yahoo_response):
        """Test successful route parsing."""
        responses.add(
            responses.GET,
            "https://transit.yahoo.co.jp/search/print",
            body=sample_yahoo_response,
            status=200
        )
        
        scraper = YahooTransitScraper()
        route = scraper.search_route("横浜", "豊洲")
        
        assert route.from_station == "横浜"
        assert route.to_station == "豊洲"
        assert route.duration == "49分(乗車33分)"
        assert route.cost == "IC優先：628円"
        assert route.transfer_count == 2
        assert len(route.transfers) == 3  # Three segments
    
    def test_extract_duration(self):
        """Test duration extraction."""
        scraper = YahooTransitScraper()
        html = '<div class="routeSummary"><li class="time">49分(乗車33分)</li></div>'
        soup = BeautifulSoup(html, 'html.parser')
        route_summary = soup.find("div", class_="routeSummary")
        
        duration = scraper._extract_duration(route_summary)
        assert duration == "49分(乗車33分)"
    
    def test_extract_transfer_count(self):
        """Test transfer count extraction."""
        scraper = YahooTransitScraper()
        html = '<div class="routeSummary"><li class="transfer">乗換：2回</li></div>'
        soup = BeautifulSoup(html, 'html.parser')
        route_summary = soup.find("div", class_="routeSummary")
        
        count = scraper._extract_transfer_count(route_summary)
        assert count == 2
    
    def test_extract_cost(self):
        """Test cost extraction."""
        scraper = YahooTransitScraper()
        html = '<div class="routeSummary"><li class="fare">IC優先：628円</li></div>'
        soup = BeautifulSoup(html, 'html.parser')
        route_summary = soup.find("div", class_="routeSummary")
        
        cost = scraper._extract_cost(route_summary)
        assert cost == "IC優先：628円"
    
    def test_missing_route_summary_error(self):
        """Test error when route summary is missing."""
        scraper = YahooTransitScraper()
        html = '<div>No route summary here</div>'
        
        with pytest.raises(ScrapingError, match="Could not find route summary section"):
            scraper._parse_route_page(html, type('MockRequest', (), {
                'from_station': '横浜', 
                'to_station': '豊洲'
            })())
    
    def test_extract_duration_missing(self):
        """Test duration extraction when element is missing."""
        scraper = YahooTransitScraper()
        html = '<div class="routeSummary">No time element</div>'
        soup = BeautifulSoup(html, 'html.parser')
        route_summary = soup.find("div", class_="routeSummary")
        
        with pytest.raises(ScrapingError, match="Could not find duration information"):
            scraper._extract_duration(route_summary)
    
    def test_extract_transfer_count_missing(self):
        """Test transfer count extraction when element is missing."""
        scraper = YahooTransitScraper()
        html = '<div class="routeSummary">No transfer element</div>'
        soup = BeautifulSoup(html, 'html.parser')
        route_summary = soup.find("div", class_="routeSummary")
        
        count = scraper._extract_transfer_count(route_summary)
        assert count == 0
    
    def test_extract_transfer_count_no_number(self):
        """Test transfer count extraction when no number found."""
        scraper = YahooTransitScraper()
        html = '<div class="routeSummary"><li class="transfer">乗換なし</li></div>'
        soup = BeautifulSoup(html, 'html.parser')
        route_summary = soup.find("div", class_="routeSummary")
        
        count = scraper._extract_transfer_count(route_summary)
        assert count == 0
    
    def test_extract_cost_missing(self):
        """Test cost extraction when element is missing."""
        scraper = YahooTransitScraper()
        html = '<div class="routeSummary">No fare element</div>'
        soup = BeautifulSoup(html, 'html.parser')
        route_summary = soup.find("div", class_="routeSummary")
        
        with pytest.raises(ScrapingError, match="Could not find fare information"):
            scraper._extract_cost(route_summary)
    
    def test_extract_transfers_no_route_detail(self):
        """Test transfer extraction when route detail is missing."""
        scraper = YahooTransitScraper()
        html = '<div>No route detail here</div>'
        soup = BeautifulSoup(html, 'html.parser')
        
        transfers = scraper._extract_transfers(soup)
        assert transfers == []
    
    def test_extract_transfers_empty_data(self):
        """Test transfer extraction with empty route detail."""
        scraper = YahooTransitScraper()
        html = '<div class="routeDetail"></div>'
        soup = BeautifulSoup(html, 'html.parser')
        
        transfers = scraper._extract_transfers(soup)
        assert transfers == []
    
    @responses.activate    
    def test_network_error(self):
        """Test network error handling."""
        responses.add(
            responses.GET,
            "https://transit.yahoo.co.jp/search/print",
            body="",
            status=500
        )
        
        scraper = YahooTransitScraper()
        with pytest.raises(Exception):  # Should raise NetworkError or requests exception
            scraper.search_route("横浜", "豊洲")
    
    def test_parse_route_page_general_exception(self):
        """Test general exception handling in parse_route_page."""
        scraper = YahooTransitScraper()
        # Invalid HTML that will cause parsing issues
        html = None
        
        with pytest.raises(ScrapingError, match="Failed to parse route data"):
            scraper._parse_route_page(html, type('MockRequest', (), {
                'from_station': '横浜', 
                'to_station': '豊洲'
            })())