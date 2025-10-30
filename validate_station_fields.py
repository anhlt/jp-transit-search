#!/usr/bin/env python3
"""
Station Model Field Validation Script

This script validates all fields in the Station dataclass model to ensure
comprehensive parser validation and data integrity.

Usage:
    python validate_station_fields.py
    python validate_station_fields.py --data data/stations.csv
    python validate_station_fields.py --detailed
"""

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

from src.jp_transit_search.core.models import Station
from src.jp_transit_search.crawler.station_crawler import StationCrawler


class StationFieldValidator:
    """Validates all fields in Station model for data integrity."""

    def __init__(self):
        self.console = Console()

    def validate_stations_csv(self, csv_path: Path, detailed: bool = False) -> None:
        """Validate all Station fields from CSV data.
        
        Args:
            csv_path: Path to stations CSV file
            detailed: Show detailed field analysis
        """
        if not csv_path.exists():
            self.console.print(f"[red]CSV file not found:[/red] {csv_path}")
            return

        # Load stations
        try:
            crawler = StationCrawler()
            stations = crawler.load_from_csv(csv_path)
        except Exception as e:
            self.console.print(f"[red]Failed to load stations:[/red] {e}")
            return

        if not stations:
            self.console.print("[yellow]No stations loaded[/yellow]")
            return

        self.console.print(f"[green]Loaded {len(stations)} stations for validation[/green]\n")

        # Validate each field
        self._validate_field_completeness(stations, detailed)
        self._validate_field_types(stations)
        self._validate_field_values(stations, detailed)
        self._validate_data_consistency(stations)

        # Summary
        self._print_validation_summary(stations)

    def _validate_field_completeness(self, stations: List[Station], detailed: bool) -> None:
        """Check completeness of all Station fields."""
        self.console.print("[bold blue]📊 Field Completeness Analysis[/bold blue]")
        
        # Count non-null values for each field
        field_stats = {}
        total_stations = len(stations)
        
        # Get all Station model fields
        station_fields = Station.model_fields
        
        for field_name in station_fields:
            non_null_count = sum(1 for s in stations if getattr(s, field_name) is not None and getattr(s, field_name) != "")
            if field_name in ['aliases', 'all_lines']:  # List fields
                non_null_count = sum(1 for s in stations if getattr(s, field_name) and len(getattr(s, field_name)) > 0)
            
            percentage = (non_null_count / total_stations) * 100
            field_stats[field_name] = {
                'count': non_null_count,
                'percentage': percentage,
                'description': station_fields[field_name].description or "No description"
            }

        # Create completeness table
        table = Table(title="Field Completeness Statistics")
        table.add_column("Field Name", style="cyan", no_wrap=True)
        table.add_column("Description", style="green")
        table.add_column("Non-Empty", justify="right", style="yellow")
        table.add_column("Percentage", justify="right", style="magenta")
        table.add_column("Status", justify="center")

        for field_name, stats in sorted(field_stats.items()):
            # Status emoji based on completeness
            if stats['percentage'] >= 90:
                status = "✅"
            elif stats['percentage'] >= 50:
                status = "⚠️"  
            else:
                status = "❌"

            table.add_row(
                field_name,
                stats['description'][:50] + ("..." if len(stats['description']) > 50 else ""),
                f"{stats['count']:,}",
                f"{stats['percentage']:.1f}%",
                status
            )

        self.console.print(table)
        self.console.print()

        if detailed:
            self._show_field_samples(stations)

    def _show_field_samples(self, stations: List[Station]) -> None:
        """Show sample values for each field."""
        self.console.print("[bold blue]📋 Field Sample Values[/bold blue]")
        
        station_fields = Station.model_fields
        
        for field_name in station_fields:
            # Get non-empty sample values
            samples = []
            for station in stations[:50]:  # Check first 50 stations
                value = getattr(station, field_name)
                if value is not None and value != "" and (not isinstance(value, list) or len(value) > 0):
                    if isinstance(value, list):
                        samples.append(str(value[:3]))  # Show first 3 items for lists
                    else:
                        samples.append(str(value))
                    
                    if len(samples) >= 5:  # Show up to 5 samples
                        break
            
            if samples:
                sample_text = " | ".join(samples)
                self.console.print(f"[cyan]{field_name}:[/cyan] {sample_text}")
            else:
                self.console.print(f"[cyan]{field_name}:[/cyan] [red]No valid samples found[/red]")
        
        self.console.print()

    def _validate_field_types(self, stations: List[Station]) -> None:
        """Validate field types match the model definition."""
        self.console.print("[bold blue]🔍 Field Type Validation[/bold blue]")
        
        type_errors = defaultdict(list)
        
        for i, station in enumerate(stations[:100]):  # Check first 100 stations
            # Check float fields
            for field_name in ['latitude', 'longitude']:
                value = getattr(station, field_name)
                if value is not None and not isinstance(value, (int, float)):
                    type_errors[field_name].append(f"Station {i}: {value} (type: {type(value).__name__})")
            
            # Check list fields
            for field_name in ['aliases', 'all_lines']:
                value = getattr(station, field_name)
                if value is not None and not isinstance(value, list):
                    type_errors[field_name].append(f"Station {i}: {value} (type: {type(value).__name__})")
        
        if type_errors:
            for field_name, errors in type_errors.items():
                self.console.print(f"[red]❌ {field_name} type errors:[/red]")
                for error in errors[:5]:  # Show first 5 errors
                    self.console.print(f"  • {error}")
        else:
            self.console.print("[green]✅ All field types are valid[/green]")
        
        self.console.print()

    def _validate_field_values(self, stations: List[Station], detailed: bool) -> None:
        """Validate field values for reasonable ranges and formats."""
        self.console.print("[bold blue]✅ Field Value Validation[/bold blue]")
        
        validation_results = []
        
        # Validate prefecture_id (should be 01-47)
        invalid_prefecture_ids = []
        valid_prefecture_ids = set(f"{i:02d}" for i in range(1, 48))
        
        for station in stations:
            if station.prefecture_id and station.prefecture_id not in valid_prefecture_ids:
                invalid_prefecture_ids.append(f"{station.name}: {station.prefecture_id}")
        
        if invalid_prefecture_ids:
            validation_results.append(("prefecture_id", "❌", f"{len(invalid_prefecture_ids)} invalid IDs"))
            if detailed:
                for error in invalid_prefecture_ids[:5]:
                    self.console.print(f"  • [red]{error}[/red]")
        else:
            validation_results.append(("prefecture_id", "✅", "All valid JIS codes"))
        
        # Validate coordinates (Japan bounds: lat 24-46, lon 123-146)
        invalid_coords = []
        for station in stations:
            if station.latitude is not None:
                if not (24 <= station.latitude <= 46):
                    invalid_coords.append(f"{station.name}: lat={station.latitude}")
            if station.longitude is not None:
                if not (123 <= station.longitude <= 146):
                    invalid_coords.append(f"{station.name}: lon={station.longitude}")
        
        if invalid_coords:
            validation_results.append(("coordinates", "❌", f"{len(invalid_coords)} out of bounds"))
            if detailed:
                for error in invalid_coords[:5]:
                    self.console.print(f"  • [red]{error}[/red]")
        else:
            validation_results.append(("coordinates", "✅", "All within Japan bounds"))
        
        # Validate line_color (should be hex format)
        invalid_colors = []
        for station in stations:
            if station.line_color and not (station.line_color.startswith('#') and len(station.line_color) == 7):
                invalid_colors.append(f"{station.name}: {station.line_color}")
        
        if invalid_colors:
            validation_results.append(("line_color", "❌", f"{len(invalid_colors)} invalid hex colors"))
            if detailed:
                for error in invalid_colors[:5]:
                    self.console.print(f"  • [red]{error}[/red]")
        else:
            validation_results.append(("line_color", "✅", "Valid hex format"))
        
        # Create validation table
        table = Table(title="Field Value Validation Results")
        table.add_column("Field", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Result", style="white")
        
        for field, status, result in validation_results:
            table.add_row(field, status, result)
        
        self.console.print(table)
        self.console.print()

    def _validate_data_consistency(self, stations: List[Station]) -> None:
        """Check for data consistency across stations."""
        self.console.print("[bold blue]🔗 Data Consistency Validation[/bold blue]")
        
        # Check prefecture name vs prefecture_id consistency
        prefecture_mapping = {}
        inconsistencies = []
        
        for station in stations:
            if station.prefecture and station.prefecture_id:
                if station.prefecture in prefecture_mapping:
                    if prefecture_mapping[station.prefecture] != station.prefecture_id:
                        inconsistencies.append(
                            f"{station.name}: {station.prefecture} maps to both "
                            f"{prefecture_mapping[station.prefecture]} and {station.prefecture_id}"
                        )
                else:
                    prefecture_mapping[station.prefecture] = station.prefecture_id
        
        if inconsistencies:
            self.console.print(f"[red]❌ Prefecture mapping inconsistencies: {len(inconsistencies)}[/red]")
            for error in inconsistencies[:5]:
                self.console.print(f"  • {error}")
        else:
            self.console.print("[green]✅ Prefecture mappings are consistent[/green]")
        
        # Check for duplicate stations (same name + prefecture)
        station_key_counts = Counter()
        for station in stations:
            key = (station.name, station.prefecture)
            station_key_counts[key] += 1
        
        duplicates = {k: v for k, v in station_key_counts.items() if v > 1}
        if duplicates:
            self.console.print(f"[yellow]⚠️  Potential duplicates: {len(duplicates)} station name/prefecture pairs[/yellow]")
            for (name, pref), count in list(duplicates.items())[:5]:
                self.console.print(f"  • {name} ({pref}): {count} entries")
        else:
            self.console.print("[green]✅ No duplicate station entries found[/green]")
        
        self.console.print()

    def _print_validation_summary(self, stations: List[Station]) -> None:
        """Print overall validation summary."""
        total_stations = len(stations)
        station_fields = Station.model_fields
        total_fields = len(station_fields)
        
        # Calculate overall completeness
        total_filled_fields = 0
        total_possible_fields = total_stations * total_fields
        
        for field_name in station_fields:
            for station in stations:
                value = getattr(station, field_name)
                if value is not None and value != "":
                    if isinstance(value, list):
                        if len(value) > 0:
                            total_filled_fields += 1
                    else:
                        total_filled_fields += 1
        
        overall_completeness = (total_filled_fields / total_possible_fields) * 100
        
        # Summary panel
        summary_text = f"""
[bold]Station Data Validation Summary[/bold]

📊 Dataset Overview:
  • Total Stations: {total_stations:,}
  • Total Fields per Station: {total_fields}
  • Overall Data Completeness: {overall_completeness:.1f}%

🔍 Field Categories:
  • Core Fields: name, prefecture, prefecture_id, station_id
  • Location Fields: latitude, longitude
  • Railway Fields: railway_company, line_name, station_code
  • Extended Fields: aliases, line_name_kana, line_color, line_type, company_code, all_lines

✅ Validation Complete - Ready for parser testing!
        """
        
        panel = Panel(summary_text, title="🎯 Validation Summary", border_style="green")
        self.console.print(panel)


def main():
    """Main entry point for station field validation."""
    parser = argparse.ArgumentParser(
        description="Validate all Station model fields for data integrity"
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/stations.csv"),
        help="Path to stations CSV file (default: data/stations.csv)"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed field analysis and sample values"
    )
    
    args = parser.parse_args()
    
    # Initialize validator
    validator = StationFieldValidator()
    
    # Run validation
    validator.validate_stations_csv(args.data, args.detailed)


if __name__ == "__main__":
    main()