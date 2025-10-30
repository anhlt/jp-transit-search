"""Yahoo Transit scraper implementation based on the Qiita article approach."""

import re
from typing import List, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from .exceptions import NetworkError, RouteNotFoundError, ScrapingError, ValidationError
from .models import Route, RouteSearchRequest, Transfer


class YahooTransitScraper:
    """Scraper for Yahoo Transit route information."""
    
    def __init__(self, timeout: int = 30):
        """Initialize the scraper.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def search_route(self, from_station: str, to_station: str) -> Route:
        """Search for route between stations.
        
        Args:
            from_station: Departure station name
            to_station: Destination station name
            
        Returns:
            Route object with complete route information
            
        Raises:
            ValidationError: If station names are invalid
            RouteNotFoundError: If no route is found
            ScrapingError: If parsing fails
            NetworkError: If network request fails
        """
        # Validate input
        if not from_station or not from_station.strip():
            raise ValidationError("Departure station name cannot be empty")
        if not to_station or not to_station.strip():
            raise ValidationError("Destination station name cannot be empty")
        
        request = RouteSearchRequest(from_station=from_station, to_station=to_station)
        html_content = self._fetch_route_page(request)
        return self._parse_route_page(html_content, request)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_error_callback=lambda retry_state: retry_state.outcome.result() if hasattr(retry_state.outcome, 'exception') and isinstance(retry_state.outcome.exception(), RouteNotFoundError) else None
    )
    def _fetch_route_page(self, request: RouteSearchRequest) -> str:
        """Fetch the Yahoo Transit print page.
        
        Args:
            request: Route search request
            
        Returns:
            HTML content as string
            
        Raises:
            NetworkError: If request fails
        """
        try:
            url = request.to_yahoo_url()
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Check if we got a valid response
            if "経路が見つかりませんでした" in response.text:
                raise RouteNotFoundError(f"No route found from {request.from_station} to {request.to_station}")
            
            return response.text
            
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Failed to fetch route data: {str(e)}")
    
    def _parse_route_page(self, html_content: str, request: RouteSearchRequest) -> Route:
        """Parse the Yahoo Transit HTML page.
        
        Args:
            html_content: HTML content from Yahoo Transit
            request: Original search request
            
        Returns:
            Parsed Route object
            
        Raises:
            ScrapingError: If parsing fails
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Get route summary information
            route_summary = soup.find("div", class_="routeSummary")
            if not route_summary:
                raise ScrapingError("Could not find route summary section")
            
            # Extract basic route info
            duration = self._extract_duration(route_summary)
            transfer_count = self._extract_transfer_count(route_summary)  
            cost = self._extract_cost(route_summary)
            
            # Extract detailed transfer information
            transfers = self._extract_transfers(soup)
            
            return Route(
                from_station=request.from_station,
                to_station=request.to_station,
                duration=duration,
                cost=cost,
                transfer_count=transfer_count,
                transfers=transfers
            )
            
        except Exception as e:
            if isinstance(e, (ScrapingError, RouteNotFoundError)):
                raise
            raise ScrapingError(f"Failed to parse route data: {str(e)}")
    
    def _extract_duration(self, route_summary) -> str:
        """Extract duration from route summary."""
        time_element = route_summary.find("li", class_="time")
        if not time_element:
            raise ScrapingError("Could not find duration information")
        return time_element.get_text().strip()
    
    def _extract_transfer_count(self, route_summary) -> int:
        """Extract transfer count from route summary."""
        transfer_element = route_summary.find("li", class_="transfer")
        if not transfer_element:
            return 0
        
        transfer_text = transfer_element.get_text().strip()
        # Extract number from text like "乗換：2回"
        match = re.search(r'(\d+)', transfer_text)
        return int(match.group(1)) if match else 0
    
    def _extract_cost(self, route_summary) -> str:
        """Extract cost from route summary."""
        fare_element = route_summary.find("li", class_="fare")
        if not fare_element:
            raise ScrapingError("Could not find fare information")
        return fare_element.get_text().strip()
    
    def _extract_transfers(self, soup) -> List[Transfer]:
        """Extract detailed transfer information."""
        transfers = []
        
        # Get route detail section
        route_detail = soup.find("div", class_="routeDetail")
        if not route_detail:
            return transfers
        
        # Extract stations
        stations = []
        stations_tmp = route_detail.find_all("div", class_="station")
        for station in stations_tmp:
            stations.append(station.get_text().strip())
        
        # Extract lines
        lines = []
        lines_tmp = route_detail.find_all("li", class_="transport")
        for line in lines_tmp:
            line_element = line.find("div")
            if line_element:
                lines.append(line_element.get_text().strip())
        
        # Extract durations
        durations = []
        durations_tmp = route_detail.find_all("li", class_="estimatedTime")
        for duration in durations_tmp:
            duration_text = duration.get_text().strip()
            # Extract minutes from text like "16分"
            match = re.search(r'(\d+)', duration_text)
            if match:
                durations.append(int(match.group(1)))
            else:
                durations.append(0)
        
        # Extract fares
        fares = []
        fares_tmp = route_detail.find_all("p", class_="fare")
        for fare in fares_tmp:
            fare_text = fare.get_text().strip()
            # Extract yen amount from text like "303円"
            match = re.search(r'(\d+)', fare_text)
            if match:
                fares.append(int(match.group(1)))
            else:
                fares.append(0)
        
        # Create Transfer objects
        min_length = min(len(stations)-1, len(lines), len(durations), len(fares))
        for i in range(min_length):
            if i < len(stations) - 1:
                transfer = Transfer(
                    from_station=stations[i],
                    to_station=stations[i + 1],
                    line_name=lines[i] if i < len(lines) else "Unknown",
                    duration_minutes=durations[i] if i < len(durations) else 0,
                    cost_yen=fares[i] if i < len(fares) else 0
                )
                transfers.append(transfer)
        
        return transfers