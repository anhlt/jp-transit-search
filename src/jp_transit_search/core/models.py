"""Data models for Japanese transit search."""

from datetime import datetime, time
from typing import List, Optional

from pydantic import BaseModel, Field


class Station(BaseModel):
    """Represents a train station."""
    
    name: str = Field(..., description="Station name in Japanese")
    prefecture: Optional[str] = Field(None, description="Prefecture name")
    city: Optional[str] = Field(None, description="City name")
    railway_company: Optional[str] = Field(None, description="Railway company")
    line_name: Optional[str] = Field(None, description="Railway line name")
    station_code: Optional[str] = Field(None, description="Station code")
    latitude: Optional[float] = Field(None, description="Latitude")
    longitude: Optional[float] = Field(None, description="Longitude")
    aliases: Optional[List[str]] = Field(default_factory=list, description="Alternative names")
    
    # Additional line information
    line_name_kana: Optional[str] = Field(None, description="Line name in kana")
    line_color: Optional[str] = Field(None, description="Line color code (hex)")
    line_type: Optional[str] = Field(None, description="Line type (JR, Metro, Private, etc.)")
    company_code: Optional[str] = Field(None, description="Railway company code")
    all_lines: Optional[List[str]] = Field(default_factory=list, description="All lines serving this station")

    def __str__(self) -> str:
        return self.name


class Transfer(BaseModel):
    """Represents a single transfer/segment of a route."""
    
    from_station: str = Field(..., description="Departure station name")
    to_station: str = Field(..., description="Arrival station name")
    line_name: str = Field(..., description="Railway line name")
    duration_minutes: int = Field(..., description="Travel time in minutes")
    cost_yen: int = Field(..., description="Cost in Japanese yen")
    departure_time: Optional[time] = Field(None, description="Departure time")
    arrival_time: Optional[time] = Field(None, description="Arrival time")
    
    def __str__(self) -> str:
        return f"{self.from_station} → {self.to_station} ({self.line_name})"


class Route(BaseModel):
    """Represents a complete route between stations."""
    
    from_station: str = Field(..., description="Starting station")
    to_station: str = Field(..., description="Destination station")
    duration: str = Field(..., description="Total duration (e.g., '49分')")
    cost: str = Field(..., description="Total cost (e.g., '628円')")
    transfer_count: int = Field(..., description="Number of transfers")
    transfers: List[Transfer] = Field(default_factory=list, description="List of transfer segments")
    departure_time: Optional[time] = Field(None, description="Overall departure time")
    arrival_time: Optional[time] = Field(None, description="Overall arrival time")
    search_date: Optional[datetime] = Field(None, description="When this route was searched")
    
    def __str__(self) -> str:
        return f"{self.from_station} → {self.to_station} ({self.duration}, {self.cost})"
    
    def summary(self) -> str:
        """Get route summary."""
        transfer_text = "乗換なし" if self.transfer_count == 0 else f"乗換{self.transfer_count}回"
        return f"{self.from_station} → {self.to_station}\n所要時間: {self.duration}\n料金: {self.cost}\n{transfer_text}"


class RouteSearchRequest(BaseModel):
    """Request model for route search."""
    
    from_station: str = Field(..., description="Departure station name")
    to_station: str = Field(..., description="Destination station name")
    search_datetime: Optional[datetime] = Field(None, description="Search date and time")
    search_type: str = Field("earliest", description="Search type: earliest, cheapest, least_transfers")
    
    def to_yahoo_url(self) -> str:
        """Convert to Yahoo Transit search URL."""
        base_url = "https://transit.yahoo.co.jp/search/print"
        params = f"?from={self.from_station}&flatlon=&to={self.to_station}"
        return base_url + params