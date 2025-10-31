"""Unit tests for CLI formatters."""

import json
from io import StringIO
from unittest.mock import patch

from rich.console import Console

from jp_transit_search.cli.formatters import (
    format_route_detailed,
    format_route_json,
    format_route_table,
    format_station_table,
)
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
                    cost_yen=290,
                ),
                Transfer(
                    from_station="新橋",
                    to_station="豊洲",
                    line_name="ゆりかもめ",
                    duration_minutes=8,
                    cost_yen=200,
                ),
            ],
        )

        # Create route without transfers
        self.route_no_transfers = Route(
            from_station="東京",
            to_station="新宿",
            duration="15分",
            cost="160円",
            transfer_count=0,
            transfers=[],
        )

    def test_format_route_table_basic(self):
        """Test basic table formatting."""
        console = Console(file=StringIO())
        with patch('jp_transit_search.cli.formatters.console', console):
            format_route_table(self.sample_route, verbose=False)
            output = console.file.getvalue()

        assert "横浜 → 豊洲" in output
        assert "49分(乗車33分)" in output
        assert "IC優先：628円" in output
        assert "2" in output  # transfer count

    def test_format_route_table_verbose(self):
        """Test verbose table formatting."""
        console = Console(file=StringIO())
        with patch('jp_transit_search.cli.formatters.console', console):
            format_route_table(self.sample_route, verbose=True)
            output = console.file.getvalue()

        assert "横浜 → 豊洲" in output
        assert "Transfer Details" in output
        assert "東海道本線" in output
        assert "ゆりかもめ" in output
        assert "25分" in output
        assert "290円" in output

    def test_format_route_table_no_transfers(self):
        """Test table formatting with no transfers."""
        console = Console(file=StringIO())
        with patch('jp_transit_search.cli.formatters.console', console):
            format_route_table(self.route_no_transfers, verbose=False)
            output = console.file.getvalue()

        assert "東京 → 新宿" in output
        assert "15分" in output
        assert "160円" in output
        assert "0" in output  # transfer count

    def test_format_route_table_no_transfers_verbose(self):
        """Test verbose table formatting with no transfers."""
        console = Console(file=StringIO())
        with patch('jp_transit_search.cli.formatters.console', console):
            format_route_table(self.route_no_transfers, verbose=True)
            output = console.file.getvalue()

        assert "東京 → 新宿" in output
        assert "No transfer details available" in output

    def test_format_route_detailed(self):
        """Test detailed route formatting."""
        console = Console(file=StringIO())
        with patch('jp_transit_search.cli.formatters.console', console):
            format_route_detailed(self.sample_route)
            output = console.file.getvalue()

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
        console = Console(file=StringIO())
        with patch('jp_transit_search.cli.formatters.console', console):
            format_route_detailed(self.route_no_transfers)
            output = console.file.getvalue()

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

        # Parse JSON to verify structure - returns a list
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 1

        route = data[0]
        assert route["from_station"] == "横浜"
        assert route["to_station"] == "豊洲"
        assert route["duration"] == "49分(乗車33分)"
        assert route["cost"] == "IC優先：628円"
        assert route["transfer_count"] == 2
        assert len(route["transfers"]) == 2

        # Check first transfer
        transfer1 = route["transfers"][0]
        assert transfer1["from_station"] == "横浜"
        assert transfer1["to_station"] == "新橋"
        assert transfer1["line_name"] == "東海道本線"
        assert transfer1["duration_minutes"] == 25
        assert transfer1["cost_yen"] == 290

        # Check second transfer
        transfer2 = route["transfers"][1]
        assert transfer2["from_station"] == "新橋"
        assert transfer2["to_station"] == "豊洲"
        assert transfer2["line_name"] == "ゆりかもめ"
        assert transfer2["duration_minutes"] == 8
        assert transfer2["cost_yen"] == 200

    def test_format_route_json_no_transfers(self):
        """Test JSON formatting with no transfers."""
        output = format_route_json(self.route_no_transfers)

        # Parse JSON to verify structure - returns a list
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 1

        route = data[0]
        assert route["from_station"] == "東京"
        assert route["to_station"] == "新宿"
        assert route["duration"] == "15分"
        assert route["cost"] == "160円"
        assert route["transfer_count"] == 0
        assert len(route["transfers"]) == 0

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
        assert isinstance(data, list)
        assert len(data) == 1

    def test_format_station_table_basic(self):
        """Test basic station table formatting."""
        console = Console(file=StringIO())
        with patch('jp_transit_search.cli.formatters.console', console):
            format_station_table([], verbose=False)
            output = console.file.getvalue()

        assert "Stations" in output
        assert "Name" in output
        assert "Prefecture" in output

    def test_format_station_table_verbose(self):
        """Test verbose station table formatting."""
        console = Console(file=StringIO())
        with patch('jp_transit_search.cli.formatters.console', console):
            format_station_table([], verbose=True)
            output = console.file.getvalue()

        assert "Stations" in output
        assert "Name" in output
        assert "Prefecture" in output
        # Verbose mode should add more columns
        assert "Company" in output or "Line" in output

    def test_format_route_detailed_with_intermediate_stations(self):
        """Test detailed formatting with intermediate stations and enhanced features."""
        from jp_transit_search.core.models import IntermediateStation

        # Create route with enhanced transfer data
        route_with_intermediates = Route(
            from_station="大船",
            to_station="羽田空港",
            duration="58分",
            cost="715円",
            transfer_count=1,
            transfers=[
                Transfer(
                    from_station="大船",
                    to_station="横浜",
                    line_name="ＪＲ東海道本線",
                    duration_minutes=16,
                    cost_yen=318,
                    departure_time="16:36",
                    arrival_time="16:52",
                    departure_platform="1・2番線",
                    arrival_platform="7番線",
                    riding_position="[15両] 前 中",
                    intermediate_stations=[
                        IntermediateStation(name="戸塚", arrival_time="16:42")
                    ]
                ),
                Transfer(
                    from_station="横浜",
                    to_station="羽田空港第１・第２ターミナル(京急)",
                    line_name="京急本線",
                    duration_minutes=29,
                    cost_yen=397,
                    departure_time="16:58",
                    arrival_time="17:27",
                    departure_platform="2番線",
                    arrival_platform="2番線",
                    intermediate_stations=[
                        IntermediateStation(name="京急東神奈川", arrival_time="17:00"),
                        IntermediateStation(name="京急川崎", arrival_time="17:09"),
                        IntermediateStation(name="羽田空港第３ターミナル(京急)", arrival_time="17:25")
                    ]
                )
            ]
        )

        console = Console(file=StringIO())
        with patch('jp_transit_search.cli.formatters.console', console):
            format_route_detailed(route_with_intermediates)
            output = console.file.getvalue()

        # Test route summary
        assert "大船" in output
        assert "羽田空港" in output
        assert "58分" in output
        assert "715円" in output

        # Test platform information
        assert "Platform: From: 1・2番線 | To: 7番線" in output
        assert "Platform: From: 2番線 | To: 2番線" in output

        # Test riding position
        assert "Riding Position: [15両] 前 中" in output

        # Test intermediate stations
        assert "Intermediate Stations:" in output
        assert "• 戸塚 (16:42)" in output
        assert "• 京急東神奈川 (17:00)" in output
        assert "• 京急川崎 (17:09)" in output
        assert "• 羽田空港第３ターミナル(京急) (17:25)" in output

    def test_format_route_json_with_intermediate_stations(self):
        """Test JSON formatting includes intermediate stations and enhanced features."""
        from jp_transit_search.core.models import IntermediateStation

        route_with_intermediates = Route(
            from_station="大船",
            to_station="横浜",
            duration="16分",
            cost="318円",
            transfer_count=0,
            transfers=[
                Transfer(
                    from_station="大船",
                    to_station="横浜",
                    line_name="ＪＲ東海道本線",
                    duration_minutes=16,
                    cost_yen=318,
                    departure_time="16:36",
                    arrival_time="16:52",
                    departure_platform="1・2番線",
                    arrival_platform="7番線",
                    riding_position="[15両] 前 中",
                    intermediate_stations=[
                        IntermediateStation(name="戸塚", arrival_time="16:42"),
                        IntermediateStation(name="藤沢", arrival_time="16:48")
                    ]
                )
            ]
        )

        output = format_route_json(route_with_intermediates)
        data = json.loads(output)

        # Verify structure
        assert len(data) == 1
        assert len(data[0]["transfers"]) == 1

        transfer = data[0]["transfers"][0]

        # Test platform information in JSON
        assert transfer["departure_platform"] == "1・2番線"
        assert transfer["arrival_platform"] == "7番線"

        # Test riding position in JSON
        assert transfer["riding_position"] == "[15両] 前 中"

        # Test intermediate stations in JSON
        assert "intermediate_stations" in transfer
        assert len(transfer["intermediate_stations"]) == 2

        # Test first intermediate station
        station1 = transfer["intermediate_stations"][0]
        assert station1["name"] == "戸塚"
        assert station1["arrival_time"] == "16:42"

        # Test second intermediate station
        station2 = transfer["intermediate_stations"][1]
        assert station2["name"] == "藤沢"
        assert station2["arrival_time"] == "16:48"
