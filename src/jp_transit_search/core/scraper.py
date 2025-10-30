"""Yahoo Transit scraper implementation based on the Qiita article approach."""

import re
from datetime import datetime, time

import requests
from bs4 import BeautifulSoup, Tag
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
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
                "Sec-Ch-Ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Linux"',
            }
        )

    def search_route(
        self,
        from_station: str,
        to_station: str,
        search_datetime: datetime | None = None,
        search_type: str = "earliest",
        save_html_path: str | None = None,
    ) -> list[Route]:
        """Search for routes between stations.

        Args:
            from_station: Departure station name
            to_station: Destination station name
            search_datetime: Optional datetime for departure time
            search_type: Search type: "earliest", "cheapest", "easiest"
            save_html_path: Optional path to save raw HTML for debugging

        Returns:
            List of Route objects with complete route information

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

        request = RouteSearchRequest(
            from_station=from_station,
            to_station=to_station,
            search_datetime=search_datetime,
            search_type=search_type,
        )
        html_content = self._fetch_route_page(request)

        # Save HTML for debugging if requested
        if save_html_path:
            with open(save_html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

        return self._parse_route_page(html_content, request)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_error_callback=lambda retry_state: retry_state.outcome.result()
        if retry_state.outcome is not None
        and hasattr(retry_state.outcome, "exception")
        and isinstance(retry_state.outcome.exception(), RouteNotFoundError)
        else None,
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
                raise RouteNotFoundError(
                    f"No route found from {request.from_station} to {request.to_station}"
                )

            return response.text

        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Failed to fetch route data: {str(e)}") from e

    def _parse_route_page(
        self, html_content: str, request: RouteSearchRequest
    ) -> list[Route]:
        """Parse the Yahoo Transit HTML page for multiple routes.

        Args:
            html_content: HTML content from Yahoo Transit
            request: Original search request

        Returns:
            List of parsed Route objects

        Raises:
            ScrapingError: If parsing fails
        """
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            routes: list[Route] = []

            # Find all route sections - try multiple approaches
            route_sections: list[Tag] = []

            # Approach 1: Look for divs with routeXX IDs
            route_divs = soup.find_all("div", id=re.compile(r"route\d+"))
            if route_divs:
                route_sections.extend(route_divs)

            # Approach 2: Look for routeSummary elements and find their parent containers
            if not route_sections:
                route_summaries = soup.find_all("div", class_="routeSummary")
                for summary in route_summaries:
                    # Find the parent container that contains both summary and detail
                    parent = summary.find_parent(
                        "div", class_=re.compile(r"elmRouteDetail|route")
                    )
                    if parent and parent not in route_sections:
                        route_sections.append(parent)
                    elif not parent and summary not in route_sections:
                        # Fallback: use the summary's parent as the route section
                        if summary.parent:
                            route_sections.append(summary.parent)

            # Approach 3: If no route sections found, try to parse the entire page as one route
            if not route_sections:
                # Check if we have at least routeSummary and routeDetail
                route_summary = soup.find("div", class_="routeSummary")
                route_detail = soup.find("div", class_="routeDetail")
                if route_summary and route_detail:
                    # Create a virtual route section containing both
                    virtual_section = soup.new_tag("div")
                    virtual_section.append(route_summary)
                    virtual_section.append(route_detail)
                    route_sections.append(virtual_section)

            if not route_sections:
                raise ScrapingError("Could not find any route sections")

            # Parse each route
            for route_section in route_sections:
                try:
                    route = self._parse_single_route(route_section, request)
                    if route:
                        routes.append(route)
                except Exception:
                    # Log individual route parsing errors but continue
                    continue

            if not routes:
                raise ScrapingError("Could not parse any routes from the page")

            return routes

        except Exception as e:
            if isinstance(e, (ScrapingError, RouteNotFoundError)):
                raise
            raise ScrapingError(f"Failed to parse route data: {str(e)}") from e

    def _extract_duration(self, route_summary: Tag) -> str:
        """Extract duration from route summary."""
        time_element = route_summary.find("li", class_="time")
        if not time_element:
            raise ScrapingError("Could not find duration information")
        return time_element.get_text().strip()

    def _extract_transfer_count(self, route_summary: Tag) -> int:
        """Extract transfer count from route summary."""
        transfer_element = route_summary.find("li", class_="transfer")
        if not transfer_element:
            return 0

        transfer_text = transfer_element.get_text().strip()
        # Extract number from text like "乗換：2回"
        match = re.search(r"(\d+)", transfer_text)
        return int(match.group(1)) if match else 0

    def _extract_cost(self, route_summary: Tag) -> str:
        """Extract cost from route summary."""
        fare_element = route_summary.find("li", class_="fare")
        if not fare_element:
            raise ScrapingError("Could not find fare information")
        return fare_element.get_text().strip()

    def _extract_departure_time(self, route_summary: Tag) -> time | None:
        """Extract departure time from route summary."""
        time_element = route_summary.find("li", class_="time")
        if not time_element:
            return None

        time_text = time_element.get_text().strip()
        # Extract departure time from patterns like "05:09発→06:17着"
        match = re.search(r"(\d{1,2}):(\d{2})発", time_text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            return time(hour, minute)
        return None

    def _extract_arrival_time(self, route_summary: Tag) -> time | None:
        """Extract arrival time from route summary."""
        time_element = route_summary.find("li", class_="time")
        if not time_element:
            return None

        time_text = time_element.get_text().strip()
        # Extract arrival time from patterns like "05:09発→06:17着"
        match = re.search(r"(\d{1,2}):(\d{2})着", time_text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            return time(hour, minute)
        return None

    def _parse_single_route(
        self, route_section: Tag, request: RouteSearchRequest
    ) -> Route | None:
        """Parse a single route from a route section.

        Args:
            route_section: BeautifulSoup element containing route information
            request: Original search request

        Returns:
            Parsed Route object
        """
        try:
            # Find route summary within this route section
            route_summary = route_section.find("div", class_="routeSummary")
            if not route_summary:
                return None

            # Extract basic route info
            duration = self._extract_duration(route_summary)
            transfer_count = self._extract_transfer_count(route_summary)
            cost = self._extract_cost(route_summary)
            departure_time = self._extract_departure_time(route_summary)
            arrival_time = self._extract_arrival_time(route_summary)

            # Extract detailed transfer information from this route's detail section
            route_detail = route_section.find("div", class_="routeDetail")
            transfers = []
            if route_detail:
                transfers = self._extract_transfers_from_section(route_detail)

            return Route(
                from_station=request.from_station,
                to_station=request.to_station,
                duration=duration,
                cost=cost,
                transfer_count=transfer_count,
                transfers=transfers,
                departure_time=departure_time,
                arrival_time=arrival_time,
                search_date=None,
            )

        except Exception:
            return None

    def _extract_transfers_from_section(
        self, route_detail: Tag | None
    ) -> list[Transfer]:
        """Extract detailed transfer information including stations, times, and platforms."""
        transfers: list[Transfer] = []

        # route_detail is already passed in, no need to find it again
        if not route_detail:
            return transfers

        # Extract all stations with their times and details
        stations = []
        station_elements = route_detail.find_all("div", class_="station")
        for station in station_elements:
            # Get station name from dt element
            station_name = station.find("dt")
            if station_name:
                station_name = station_name.get_text().strip()
            else:
                station_name = station.get_text().strip()

            # Extract departure/arrival times from time list
            time_list = station.find("ul", class_="time")
            times = []
            if time_list:
                time_elements = time_list.find_all("li")
                times = [t.get_text().strip() for t in time_elements]

            stations.append({"name": station_name, "times": times})

        # Extract all fare sections (segments between stations)
        fare_sections = route_detail.find_all("div", class_="fareSection")

        for i, section in enumerate(fare_sections):
            if i >= len(stations) - 1:
                break

            # Extract line information and platform details
            transport_info = section.find("li", class_="transport")
            line_name = "Unknown"
            departure_platform = None
            arrival_platform = None

            if transport_info:
                # Get the transport div
                line_div = transport_info.find("div")
                if line_div:
                    # Extract line name from the direct text content
                    # The structure is: [icon] LineName [destination] [platform]
                    full_text = line_div.get_text().strip()

                    # Clean up the text by removing icon and platform info
                    # Remove [line] and [発]...番線 patterns
                    clean_text = re.sub(r"\[.*?\]", "", full_text)
                    clean_text = re.sub(
                        r"\[発\].*?番線.*?→.*?\[着\].*?番線", "", clean_text
                    )
                    clean_text = re.sub(r"\s+", " ", clean_text).strip()

                    # Extract line name - look for patterns ending with "線"
                    line_match = re.search(r"([^\s]+線)", clean_text)
                    if line_match:
                        line_name = line_match.group(1).strip()
                    else:
                        # Alternative: extract from spans
                        destination_span = line_div.find("span", class_="destination")
                        if destination_span:
                            destination_text = destination_span.get_text().strip()
                            # Remove destination from clean text to get line name
                            line_name = clean_text.replace(destination_text, "").strip()
                        else:
                            line_name = clean_text

                # Extract platform information
                platform_span = transport_info.find("span", class_="platform")
                if platform_span:
                    platform_text = platform_span.get_text().strip()
                    # Parse platform format: "[発] 4番線 → [着] 1番線"
                    platform_parts = platform_text.split("→")
                    if len(platform_parts) >= 2:
                        # Extract departure platform
                        dep_match = re.search(r"(\d+)番線", platform_parts[0])
                        if dep_match:
                            departure_platform = f"{dep_match.group(1)}番線"

                        # Extract arrival platform
                        arr_match = re.search(r"(\d+)番線", platform_parts[1])
                        if arr_match:
                            arrival_platform = f"{arr_match.group(1)}番線"

            # Extract duration from stop information
            duration_minutes = 0
            stop_info = section.find("li", class_="stop")
            if stop_info:
                stop_text = stop_info.get_text().strip()
                match = re.search(r"(\d+)駅", stop_text)
                if match:
                    # More accurate estimate: 2.5 minutes per station for local trains
                    duration_minutes = int(int(match.group(1)) * 2.5)

            # Extract fare
            cost_yen = 0
            fare_element = section.find("p", class_="fare")
            if fare_element:
                fare_text = fare_element.get_text().strip()
                match = re.search(r"(\d+)", fare_text)
                if match:
                    cost_yen = int(match.group(1))

            # Extract departure and arrival times
            departure_time = None
            arrival_time = None

            # Get departure time from current station
            if i < len(stations) and stations[i]["times"]:
                dep_times = stations[i]["times"]
                # For intermediate stations, use the second time if available (departure time)
                if i > 0 and len(dep_times) > 1:
                    departure_time = re.sub(r"[^\d:]", "", dep_times[1])
                else:
                    # For first station or single time, use first time
                    for time_str in dep_times:
                        if "発" in time_str:
                            departure_time = re.sub(r"[^\d:]", "", time_str)
                            break
                    if not departure_time:
                        departure_time = re.sub(r"[^\d:]", "", dep_times[0])

            # Get arrival time at next station
            if i + 1 < len(stations) and stations[i + 1]["times"]:
                next_times = stations[i + 1]["times"]

                # Arrival time is the first time or marked with 着
                for time_str in next_times:
                    if "着" in time_str:
                        arrival_time = re.sub(r"[^\d:]", "", time_str)
                        break
                if not arrival_time and next_times:
                    arrival_time = re.sub(r"[^\d:]", "", next_times[0])

            # Create transfer with detailed information
            transfer = Transfer(
                from_station=stations[i]["name"],
                to_station=stations[i + 1]["name"],
                line_name=line_name,
                duration_minutes=int(duration_minutes),
                cost_yen=cost_yen,
                departure_time=departure_time,
                arrival_time=arrival_time,
                departure_platform=departure_platform,
                arrival_platform=arrival_platform,
            )
            transfers.append(transfer)

        return transfers
