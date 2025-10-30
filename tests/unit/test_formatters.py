"""Unit tests for CLI formatters."""

import json

from jp_transit_search.cli.formatters import format_route_detailed, format_route_json, format_route_table, format_station_table
from jp_transit_search.core.models import Route, Transfer


class TestFormatters:
    """Test CLI formatters."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create sample route data
        self.sample_route = Route(
            from_station="横浜",
            to_station="豊洲",
            duration="49分(乗車33分)",
            cost="IC優先：628円",
            transfer_count=2,
            transfers=[
                Transfer(
                    from_station="横浜",
                    to_station="新橋",
                    line_name="東海道本線",
                    duration_minutes=25,
                    cost_yen=290
                ),
                Transfer(
                    from_station="新橋",
                    to_station="豊洲",
                    line_name="ゆりかもめ",
                    duration_minutes=8,
                    cost_yen=200
                )
            ]
        )
        
        # Create route without transfers
        self.route_no_transfers = Route(
            from_station="東京",
            to_station="新宿",
            duration="15分",
            cost="160円",
            transfer_count=0,
            transfers=[]
        )
    
    def test_format_route_table_basic(self):
        """Test basic table formatting."""
        output = format_route_table(self.sample_route, verbose=False)
        
        assert "横浜 → 豊洲" in output
        assert "49分(乗車33分)" in output
        assert "IC優先：628円" in output
        assert "2" in output  # transfer count
    
    def test_format_route_table_verbose(self):
        """Test verbose table formatting."""
        output = format_route_table(self.sample_route, verbose=True)
        
        assert "横浜 → 豊洲" in output
        assert "Transfer Details" in output
        assert "東海道本線" in output
        assert "ゆりかもめ" in output
        assert "25分" in output
        assert "290円" in output
    
    def test_format_route_table_no_transfers(self):
        """Test table formatting with no transfers."""
        output = format_route_table(self.route_no_transfers, verbose=False)
        
        assert "東京 → 新宿" in output
        assert "15分" in output
        assert "160円" in output
        assert "0" in output  # transfer count
    
    def test_format_route_table_no_transfers_verbose(self):
        """Test verbose table formatting with no transfers."""
        output = format_route_table(self.route_no_transfers, verbose=True)
        
        assert "東京 → 新宿" in output
        assert "No transfer details available" in output
    
    def test_format_route_detailed(self):
        """Test detailed route formatting."""
        output = format_route_detailed(self.sample_route)
        
        assert "Route Summary" in output
        assert "From: 横浜" in output
        assert "To: 豊洲" in output
        assert "Duration: 49分(乗車33分)" in output
        assert "Cost: IC優先：628円" in output
        assert "Transfers: 2" in output
        assert "Transfer Details:" in output
        assert "Segment 1" in output
        assert "Segment 2" in output
        assert "東海道本線" in output
        assert "ゆりかもめ" in output
    
    def test_format_route_detailed_no_transfers(self):
        """Test detailed formatting with no transfers."""
        output = format_route_detailed(self.route_no_transfers)
        
        assert "Route Summary" in output
        assert "From: 東京" in output
        assert "To: 新宿" in output
        assert "Duration: 15分" in output
        assert "Cost: 160円" in output
        assert "Transfers: 0" in output
        # Should not have transfer details section
        assert "Transfer Details:" not in output
    
    def test_format_route_json(self):
        """Test JSON route formatting."""
        output = format_route_json(self.sample_route)
        
        # Parse JSON to verify structure
        data = json.loads(output)
        
        assert data["from_station"] == "横浜"
        assert data["to_station"] == "豊洲"
        assert data["duration"] == "49分(乗車33分)"
        assert data["cost"] == "IC優先：628円"
        assert data["transfer_count"] == 2
        assert len(data["transfers"]) == 2
        
        # Check first transfer
        transfer1 = data["transfers"][0]
        assert transfer1["from_station"] == "横浜"
        assert transfer1["to_station"] == "新橋"
        assert transfer1["line_name"] == "東海道本線"
        assert transfer1["duration_minutes"] == 25
        assert transfer1["cost_yen"] == 290
        
        # Check second transfer
        transfer2 = data["transfers"][1]
        assert transfer2["from_station"] == "新橋"
        assert transfer2["to_station"] == "豊洲"
        assert transfer2["line_name"] == "ゆりかもめ"
        assert transfer2["duration_minutes"] == 8
        assert transfer2["cost_yen"] == 200
    
    def test_format_route_json_no_transfers(self):
        """Test JSON formatting with no transfers."""
        output = format_route_json(self.route_no_transfers)
        
        # Parse JSON to verify structure
        data = json.loads(output)
        
        assert data["from_station"] == "東京"
        assert data["to_station"] == "新宿"
        assert data["duration"] == "15分"
        assert data["cost"] == "160円"
        assert data["transfer_count"] == 0
        assert len(data["transfers"]) == 0
    
    def test_format_route_json_unicode_handling(self):
        """Test JSON formatting handles Unicode correctly."""
        output = format_route_json(self.sample_route)
        
        # Should contain Japanese characters properly encoded
        assert "横浜" in output
        assert "豊洲" in output
        assert "東海道本線" in output
        assert "ゆりかもめ" in output
        
        # Should be valid JSON
        data = json.loads(output)
        assert isinstance(data, dict)
    
    def test_format_station_table_basic(self):
        """Test basic station table formatting."""
        # This is a placeholder function in the current implementation
        output = format_station_table([], verbose=False)
        
        assert "Stations" in output
        assert "Name" in output
        assert "Prefecture" in output
    
    def test_format_station_table_verbose(self):
        """Test verbose station table formatting."""
        # This is a placeholder function in the current implementation
        output = format_station_table([], verbose=True)
        
        assert "Stations" in output
        assert "Name" in output
        assert "Prefecture" in output
        # Verbose mode should add more columns
        assert "City" in output or "Company" in output or "Line" in output