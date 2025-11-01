"""Yahoo Transit scraper implementation based on the Qiita article approach."""

import re
from datetime import datetime, time

import requests
from bs4 import BeautifulSoup, Tag
from tenacity import retry, stop_after_attempt, wait_exponential

from .exceptions import NetworkError, RouteNotFoundError, ScrapingError, ValidationError
from .models import IntermediateStation, Route, RouteSearchRequest, Transfer


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
        stations: list[dict[str, str | list[str]]] = []
        station_elements = route_detail.find_all("div", class_="station")
        for station in station_elements:
            # Get station name from dt element
            station_name_element = station.find("dt")
            if station_name_element:
                station_name = station_name_element.get_text().strip()
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

        # Track current station index for transfers
        current_station_idx = 0

        for section in fare_sections:
            # Find all access divs within this fare section
            access_divs = section.find_all("div", class_="access")

            # Extract fare information for this section (shared across all transfers in this section)
            cost_yen = 0
            fare_element = section.find("p", class_="fare")
            if fare_element:
                fare_text = fare_element.get_text().strip()
                match = re.search(r"(\d+)", fare_text)
                if match:
                    cost_yen = int(match.group(1))

            # Process each access div as a separate transfer
            for access_div in access_divs:
                if current_station_idx >= len(stations) - 1:
                    break

                # Extract transport information from this access div
                transport_info = access_div.find("li", class_="transport")
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
                            destination_span = line_div.find(
                                "span", class_="destination"
                            )
                            if destination_span:
                                destination_text = destination_span.get_text().strip()
                                # Remove destination from clean text to get line name
                                line_name = clean_text.replace(
                                    destination_text, ""
                                ).strip()
                            else:
                                line_name = clean_text

                # Extract platform information from the access div (outside transport_info)
                platform_li = access_div.find("li", class_="platform")
                if platform_li:
                    platform_text = platform_li.get_text().strip()
                    # Parse platform format: "[発] 2番線 → [着] 5番線" or "[発] 2番線 → [着] 情報なし"
                    platform_parts = platform_text.split("→")
                    if len(platform_parts) >= 2:
                        # Extract departure platform - find all span.num elements
                        dep_nums = platform_li.find_all("span", class_="num")

                        # Handle departure platform (first part before →)
                        if len(dep_nums) >= 1:
                            dep_platform_text = dep_nums[0].get_text().strip()
                            departure_platform = f"{dep_platform_text}番線"

                        # Handle arrival platform (second part after →)
                        if len(dep_nums) >= 2:
                            arr_platform_text = dep_nums[1].get_text().strip()
                            arrival_platform = f"{arr_platform_text}番線"
                        elif "情報なし" not in platform_parts[1]:
                            # Fallback: try to extract from text after →
                            arr_part = platform_parts[1].strip()
                            # Look for patterns like "6番線", "情報なし", "７番線" etc.
                            arr_match = re.search(r"([０-９\d・・]+)番線", arr_part)
                            if arr_match:
                                arrival_platform = f"{arr_match.group(1)}番線"
                            else:
                                # Extract text between "[着]" and any whitespace/punctuation
                                arr_match = re.search(r"\[着\]\s*([^→\s]+)", arr_part)
                                if arr_match:
                                    arrival_platform = arr_match.group(1)

                # Extract riding position information
                riding_position = None
                riding_pos_li = access_div.find("li", class_="ridingPos")
                if riding_pos_li:
                    riding_pos_text = riding_pos_li.get_text().strip()
                    # Remove "乗車位置：" prefix if present
                    if riding_pos_text.startswith("乗車位置："):
                        riding_position = riding_pos_text[
                            5:
                        ]  # Remove "乗車位置：" prefix
                    elif riding_pos_text:
                        riding_position = riding_pos_text

                # Extract duration and intermediate stations from stop information
                duration_minutes = 0
                intermediate_stations = []
                stop_info = access_div.find("li", class_="stop")
                if stop_info:
                    stop_text = stop_info.get_text().strip()
                    match = re.search(r"(\d+)駅", stop_text)
                    if match:
                        # More accurate estimate: 2.5 minutes per station for local trains
                        duration_minutes = int(int(match.group(1)) * 2.5)

                    # Parse intermediate stations from structured HTML first, fall back to regex
                    stop_ul = stop_info.find("ul")
                    if stop_ul:
                        # Use structured HTML parsing (preferred method)
                        station_items = stop_ul.find_all("li")
                        for item in station_items:
                            dt_time = item.find("dt")
                            dd_station = item.find("dd")
                            if dt_time and dd_station:
                                time_text = dt_time.get_text().strip()
                                station_text = dd_station.get_text().strip()
                                # Clean station name by removing extra whitespace and icon spans
                                clean_station_name = re.sub(
                                    r"\s+", "", station_text.strip()
                                )
                                if clean_station_name and time_text:
                                    intermediate_stations.append(
                                        IntermediateStation(
                                            name=clean_station_name,
                                            arrival_time=time_text,
                                        )
                                    )
                    else:
                        # Fallback to regex parsing for compatibility with older HTML formats
                        station_pattern = r"(\d{2}:\d{2})([^0-9]+?)(?=\d{2}:\d{2}|$)"
                        station_matches = re.findall(station_pattern, stop_text)

                        for time_str, station_name in station_matches:
                            # Clean up station name by removing extra whitespace
                            clean_station_name = re.sub(
                                r"\s+", "", station_name.strip()
                            )
                            if clean_station_name:
                                intermediate_stations.append(
                                    IntermediateStation(
                                        name=clean_station_name, arrival_time=time_str
                                    )
                                )

                # Extract departure and arrival times
                departure_time = None
                arrival_time = None

                # Get departure time from current station
                if (
                    current_station_idx < len(stations)
                    and stations[current_station_idx]["times"]
                ):
                    dep_times = stations[current_station_idx]["times"]
                    if isinstance(dep_times, list):
                        # For intermediate stations, use the second time if available (departure time)
                        if current_station_idx > 0 and len(dep_times) > 1:
                            departure_time = re.sub(r"[^\d:]", "", dep_times[1])
                        else:
                            # For first station or single time, use first time
                            for time_str in dep_times:
                                if "発" in time_str:
                                    departure_time = re.sub(r"[^\d:]", "", time_str)
                                    break
                            if not departure_time and dep_times:
                                departure_time = re.sub(r"[^\d:]", "", dep_times[0])

                # Get arrival time at next station
                if (
                    current_station_idx + 1 < len(stations)
                    and stations[current_station_idx + 1]["times"]
                ):
                    next_times = stations[current_station_idx + 1]["times"]
                    if isinstance(next_times, list):
                        # Arrival time is the first time or marked with 着
                        for time_str in next_times:
                            if "着" in time_str:
                                arrival_time = re.sub(r"[^\d:]", "", time_str)
                                break
                        if not arrival_time and next_times:
                            arrival_time = re.sub(r"[^\d:]", "", next_times[0])

                # Create transfer with detailed information
                from_station_name = stations[current_station_idx]["name"]
                to_station_name = stations[current_station_idx + 1]["name"]
                if isinstance(from_station_name, str) and isinstance(
                    to_station_name, str
                ):
                    transfer = Transfer(
                        from_station=from_station_name,
                        to_station=to_station_name,
                        line_name=line_name,
                        duration_minutes=int(duration_minutes),
                        cost_yen=cost_yen,
                        departure_time=departure_time,
                        arrival_time=arrival_time,
                        departure_platform=departure_platform,
                        arrival_platform=arrival_platform,
                        riding_position=riding_position,
                        intermediate_stations=intermediate_stations,
                    )
                    transfers.append(transfer)

                # Move to next station for the next transfer
                current_station_idx += 1

        return transfers
