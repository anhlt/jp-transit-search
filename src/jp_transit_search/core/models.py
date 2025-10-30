"""Data models for Japanese transit search."""

from datetime import datetime, time

from pydantic import BaseModel, Field


class Station(BaseModel):
    """Represents a train station."""

    name: str = Field(..., description="Station name in Japanese")
    prefecture: str | None = Field(None, description="Prefecture name")
    prefecture_id: str | None = Field(
        None, description="JIS X 0401 prefecture code (01-47)"
    )
    # city field removed - not available from Yahoo Transit data source
    station_id: str | None = Field(
        None, description="Yahoo Transit station ID (extractable from URLs)"
    )
    railway_company: str | None = Field(None, description="Railway company")
    line_name: str | None = Field(None, description="Railway line name")
    # latitude, longitude, line_name_kana, line_color, station_code removed - no data available
    aliases: list[str] | None = Field(
        default_factory=list, description="Alternative names"
    )

    # Additional line information
    line_type: str | None = Field(
        None, description="Line type (JR, Metro, Private, etc.)"
    )
    company_code: str | None = Field(None, description="Railway company code")
    all_lines: list[str] | None = Field(
        default_factory=list, description="All lines serving this station"
    )

    def __str__(self) -> str:
        return self.name


class Transfer(BaseModel):
    """Represents a single transfer/segment of a route."""

    from_station: str = Field(..., description="Departure station name")
    to_station: str = Field(..., description="Arrival station name")
    line_name: str = Field(..., description="Railway line name")
    duration_minutes: int = Field(..., description="Travel time in minutes")
    cost_yen: int = Field(..., description="Cost in Japanese yen")
    departure_time: str | None = Field(
        None, description="Departure time as string (HH:MM)"
    )
    arrival_time: str | None = Field(None, description="Arrival time as string (HH:MM)")
    departure_platform: str | None = Field(
        None, description="Departure platform number"
    )
    arrival_platform: str | None = Field(None, description="Arrival platform number")

    def __str__(self) -> str:
        return f"{self.from_station} → {self.to_station} ({self.line_name})"


class Route(BaseModel):
    """Represents a complete route between stations."""

    from_station: str = Field(..., description="Starting station")
    to_station: str = Field(..., description="Destination station")
    duration: str = Field(..., description="Total duration (e.g., '49分')")
    cost: str = Field(..., description="Total cost (e.g., '628円')")
    transfer_count: int = Field(..., description="Number of transfers")
    transfers: list[Transfer] = Field(
        default_factory=list, description="List of transfer segments"
    )
    departure_time: time | None = Field(None, description="Overall departure time")
    arrival_time: time | None = Field(None, description="Overall arrival time")
    search_date: datetime | None = Field(
        None, description="When this route was searched"
    )

    def __str__(self) -> str:
        return f"{self.from_station} → {self.to_station} ({self.duration}, {self.cost})"

    def summary(self) -> str:
        """Get route summary."""
        transfer_text = (
            "乗換なし" if self.transfer_count == 0 else f"乗換{self.transfer_count}回"
        )
        return f"{self.from_station} → {self.to_station}\n所要時間: {self.duration}\n料金: {self.cost}\n{transfer_text}"


class RouteSearchRequest(BaseModel):
    """Request model for route search."""

    from_station: str = Field(..., description="Departure station name")
    to_station: str = Field(..., description="Destination station name")
    search_datetime: datetime | None = Field(None, description="Search date and time")
    search_type: str = Field(
        "earliest", description="Search type: earliest, cheapest, least_transfers"
    )

    def to_yahoo_url(self) -> str:
        """Convert to Yahoo Transit search URL."""
        base_url = "https://transit.yahoo.co.jp/search/result"

        # Build base parameters
        params = f"?from={self.from_station}&to={self.to_station}&type=1&ticket=ic&expkind=2&userpass=1&ws=3&s=0&al=1&shin=1&ex=1&hb=1&lb=1&sr=1"

        # Add date/time parameters if search_datetime is provided
        if self.search_datetime:
            year = self.search_datetime.year
            month = self.search_datetime.month
            day = self.search_datetime.day
            hour = self.search_datetime.hour
            minute = self.search_datetime.minute

            # Yahoo uses m1 and m2 for minutes (tens and ones place)
            m1 = minute // 10
            m2 = minute % 10

            params += f"&y={year}&m={month}&d={day}&hh={hour}&m1={m1}&m2={m2}"

        return base_url + params
