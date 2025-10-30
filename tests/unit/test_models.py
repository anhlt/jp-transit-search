"""Unit tests for data models."""

import pytest
from datetime import datetime, time

from jp_transit_search.core.models import Route, Station, Transfer, RouteSearchRequest


class TestStation:
    """Test Station model."""
    
    def test_station_creation(self):
        """Test basic station creation."""
        station = Station(name="横浜")
        assert station.name == "横浜"
        assert station.prefecture is None
        assert station.aliases == []
    
    def test_station_with_full_data(self):
        """Test station with all fields."""
        station = Station(
            name="横浜",
            prefecture="神奈川県",
            city="横浜市",
            railway_company="JR東日本",
            line_name="東海道本線",
            station_code="JT05",
            latitude=35.4658,
            longitude=139.6220,
            aliases=["ヨコハマ", "yokohama"]
        )
        
        assert station.name == "横浜"
        assert station.prefecture == "神奈川県"
        assert len(station.aliases) == 2
        assert str(station) == "横浜"


class TestTransfer:
    """Test Transfer model."""
    
    def test_transfer_creation(self):
        """Test basic transfer creation."""
        transfer = Transfer(
            from_station="横浜",
            to_station="品川",
            line_name="京急本線",
            duration_minutes=16,
            cost_yen=303
        )
        
        assert transfer.from_station == "横浜"
        assert transfer.to_station == "品川"
        assert transfer.duration_minutes == 16
        assert transfer.cost_yen == 303
        assert str(transfer) == "横浜 → 品川 (京急本線)"


class TestRoute:
    """Test Route model."""
    
    def test_route_creation(self):
        """Test basic route creation."""
        route = Route(
            from_station="横浜",
            to_station="豊洲",
            duration="49分",
            cost="628円",
            transfer_count=2
        )
        
        assert route.from_station == "横浜"
        assert route.to_station == "豊洲"
        assert route.transfer_count == 2
        assert str(route) == "横浜 → 豊洲 (49分, 628円)"
    
    def test_route_with_transfers(self):
        """Test route with transfer details."""
        transfers = [
            Transfer(
                from_station="横浜",
                to_station="品川", 
                line_name="京急本線",
                duration_minutes=16,
                cost_yen=303
            ),
            Transfer(
                from_station="品川",
                to_station="豊洲",
                line_name="JR山手線",
                duration_minutes=10,
                cost_yen=157
            )
        ]
        
        route = Route(
            from_station="横浜",
            to_station="豊洲",
            duration="49分",
            cost="628円",
            transfer_count=2,
            transfers=transfers
        )
        
        assert len(route.transfers) == 2
        assert route.transfers[0].from_station == "横浜"
        assert route.transfers[1].to_station == "豊洲"
    
    def test_route_summary(self):
        """Test route summary generation."""
        route = Route(
            from_station="横浜",
            to_station="豊洲",
            duration="49分",
            cost="628円",
            transfer_count=2
        )
        
        summary = route.summary()
        assert "横浜 → 豊洲" in summary
        assert "49分" in summary
        assert "628円" in summary
        assert "乗換2回" in summary


class TestRouteSearchRequest:
    """Test RouteSearchRequest model."""
    
    def test_request_creation(self):
        """Test basic request creation."""
        request = RouteSearchRequest(
            from_station="横浜",
            to_station="豊洲"
        )
        
        assert request.from_station == "横浜"
        assert request.to_station == "豊洲"
        assert request.search_type == "earliest"
    
    def test_to_yahoo_url(self):
        """Test URL generation."""
        request = RouteSearchRequest(
            from_station="横浜",  
            to_station="豊洲"
        )
        
        url = request.to_yahoo_url()
        assert "transit.yahoo.co.jp" in url
        assert "from=横浜" in url
        assert "to=豊洲" in url
    
    def test_request_with_datetime_time_extraction(self):
        """Test request with datetime can extract time."""
        test_datetime = datetime(2024, 1, 15, 9, 30)
        request = RouteSearchRequest(
            from_station="横浜",
            to_station="豊洲",
            search_datetime=test_datetime
        )
        
        # We can extract time from datetime if needed
        if request.search_datetime:
            extracted_time = request.search_datetime.time()
            assert extracted_time == time(9, 30)
    
    def test_request_search_types(self):
        """Test different search types."""
        # Test latest arrival
        request = RouteSearchRequest(
            from_station="横浜",
            to_station="豊洲",
            search_type="latest"
        )
        assert request.search_type == "latest"
        
        # Test cheapest route
        request = RouteSearchRequest(
            from_station="横浜",
            to_station="豊洲",
            search_type="cheapest"
        )
        assert request.search_type == "cheapest"
    
    def test_route_zero_transfers(self):
        """Test route summary with zero transfers."""
        route = Route(
            from_station="東京",
            to_station="新宿",
            duration="15分",
            cost="160円",
            transfer_count=0
        )
        
        summary = route.summary()
        assert "東京 → 新宿" in summary
        assert "15分" in summary
        assert "160円" in summary
        assert "乗換なし" in summary or "乗換0回" in summary
    
    def test_station_empty_name_allowed(self):
        """Test station allows empty name (Pydantic default behavior)."""
        # Pydantic doesn't validate empty strings by default
        station = Station(name="")
        assert station.name == ""
    
    def test_transfer_negative_values_allowed(self):
        """Test transfer allows negative values (Pydantic default behavior)."""
        # Pydantic doesn't validate negative numbers by default
        transfer = Transfer(
            from_station="横浜",
            to_station="品川",
            line_name="京急本線",
            duration_minutes=-10,
            cost_yen=-303
        )
        assert transfer.duration_minutes == -10
        assert transfer.cost_yen == -303
    
    def test_route_search_request_with_datetime(self):
        """Test request with specific datetime."""
        test_datetime = datetime(2024, 1, 15, 9, 30)
        request = RouteSearchRequest(
            from_station="横浜",
            to_station="豊洲",
            search_datetime=test_datetime
        )
        
        assert request.search_datetime == test_datetime
    
    def test_route_with_times(self):
        """Test route with departure and arrival times."""
        departure = time(9, 30)
        arrival = time(10, 15)
        
        route = Route(
            from_station="横浜",
            to_station="豊洲",
            duration="45分",
            cost="620円",
            transfer_count=1,
            departure_time=departure,
            arrival_time=arrival
        )
        
        assert route.departure_time == departure
        assert route.arrival_time == arrival
    
    def test_transfer_with_times(self):
        """Test transfer with departure and arrival times."""
        departure = time(9, 30)
        arrival = time(9, 45)
        
        transfer = Transfer(
            from_station="横浜",
            to_station="品川",
            line_name="京急本線",
            duration_minutes=15,
            cost_yen=300,
            departure_time=departure,
            arrival_time=arrival
        )
        
        assert transfer.departure_time == departure
        assert transfer.arrival_time == arrival