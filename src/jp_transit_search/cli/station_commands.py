"""CLI commands for station management."""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..crawler import StationCrawler, StationSearcher

console = Console()


@click.group()
def stations():
    """Station management commands."""
    pass


@stations.command("crawl")
@click.option("--output", "-o", type=click.Path(), default="data/stations.csv", 
              help="Output CSV file path")
@click.option("--timeout", "-t", default=30, help="Request timeout in seconds")
def crawl_stations(output: str, timeout: int):
    """Crawl station data from various sources and save to CSV.
    
    Examples:
        jp-transit stations crawl
        jp-transit stations crawl --output my_stations.csv
    """
    output_path = Path(output)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Crawling station data...", total=None)
        
        try:
            crawler = StationCrawler(timeout=timeout)
            stations = crawler.crawl_all_stations()
            
            progress.update(task, description="Saving to CSV...")
            crawler.save_to_csv(stations, output_path)
            
            progress.update(task, description="Complete!", completed=True)
            
        except Exception as e:
            console.print(f"[red]Error crawling stations:[/red] {e}")
            return
    
    console.print(f"[green]Successfully crawled {len(stations)} stations to {output_path}[/green]")


@stations.command("search")
@click.argument("query")
@click.option("--prefecture", "-p", help="Filter by prefecture")
@click.option("--limit", "-l", default=10, help="Maximum number of results")
@click.option("--data", "-d", type=click.Path(), default="data/stations.csv",
              help="Station data CSV file")
@click.option("--exact", is_flag=True, help="Exact match only")
def search_stations(query: str, prefecture: Optional[str], limit: int, data: str, exact: bool):
    """Search for stations by name.
    
    Examples:
        jp-transit stations search "新宿"
        jp-transit stations search "駅" --prefecture "東京都" --limit 5
        jp-transit stations search "東京" --exact
    """
    data_path = Path(data)
    
    if not data_path.exists():
        console.print(f"[red]Station data file not found:[/red] {data_path}")
        console.print("Run 'jp-transit stations crawl' first to create the database")
        return
    
    try:
        crawler = StationCrawler()
        stations = crawler.load_from_csv(data_path)
        searcher = StationSearcher(stations)
        
        # Search for stations
        if prefecture:
            results = [s for s in searcher.search_by_prefecture(prefecture) 
                      if query.lower() in s.name.lower()]
        else:
            results = searcher.search_by_name(query, exact=exact)
        
        # Limit results
        results = results[:limit]
        
        if not results:
            console.print(f"[yellow]No stations found matching '{query}'[/yellow]")
            return
        
        # Display results
        table = Table(title=f"Station Search Results: '{query}'", show_header=True, header_style="bold magenta")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Prefecture", style="green")
        table.add_column("City", style="yellow")
        table.add_column("Railway Company", style="blue")
        
        for station in results:
            table.add_row(
                station.name,
                station.prefecture or "",
                station.city or "",
                station.railway_company or ""
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error searching stations:[/red] {e}")


@stations.command("list")
@click.option("--prefecture", "-p", help="Filter by prefecture")
@click.option("--limit", "-l", default=20, help="Maximum number of results")
@click.option("--data", "-d", type=click.Path(), default="data/stations.csv",
              help="Station data CSV file")
@click.option("--format", "-f", "output_format",
              type=click.Choice(["table", "json", "csv"]),
              default="table",
              help="Output format")
def list_stations(prefecture: Optional[str], limit: int, data: str, output_format: str):
    """List stations.
    
    Examples:
        jp-transit stations list
        jp-transit stations list --prefecture "東京都"
        jp-transit stations list --format csv
    """
    data_path = Path(data)
    
    if not data_path.exists():
        console.print(f"[red]Station data file not found:[/red] {data_path}")
        console.print("Run 'jp-transit stations crawl' first to create the database")
        return
    
    try:
        crawler = StationCrawler()
        stations = crawler.load_from_csv(data_path)
        searcher = StationSearcher(stations)
        
        # Filter by prefecture if specified
        if prefecture:
            filtered_stations = searcher.search_by_prefecture(prefecture)
        else:
            filtered_stations = stations
        
        # Limit results
        filtered_stations = filtered_stations[:limit]
        
        if not filtered_stations:
            console.print("[yellow]No stations found[/yellow]")
            return
        
        # Output in requested format
        if output_format == "json":
            import json
            station_data = [
                {
                    "name": s.name,
                    "prefecture": s.prefecture,
                    "city": s.city,
                    "railway_company": s.railway_company,
                    "line_name": s.line_name,
                    "station_code": s.station_code,
                    "latitude": s.latitude,
                    "longitude": s.longitude,
                    "aliases": s.aliases
                }
                for s in filtered_stations
            ]
            console.print(json.dumps(station_data, ensure_ascii=False, indent=2))
            
        elif output_format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            fieldnames = ['name', 'prefecture', 'city', 'railway_company', 'line_name', 
                         'station_code', 'latitude', 'longitude', 'aliases']
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for station in filtered_stations:
                writer.writerow({
                    'name': station.name,
                    'prefecture': station.prefecture or '',
                    'city': station.city or '',
                    'railway_company': station.railway_company or '',
                    'line_name': station.line_name or '',
                    'station_code': station.station_code or '',
                    'latitude': station.latitude or '',
                    'longitude': station.longitude or '',
                    'aliases': '|'.join(station.aliases) if station.aliases else ''
                })
            
            console.print(output.getvalue())
            
        else:  # table format
            table = Table(title=f"Stations ({len(filtered_stations)})", show_header=True, header_style="bold magenta")
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Prefecture", style="green")
            table.add_column("City", style="yellow")
            table.add_column("Railway Company", style="blue")
            
            for station in filtered_stations:
                table.add_row(
                    station.name,
                    station.prefecture or "",
                    station.city or "",
                    station.railway_company or ""
                )
            
            console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing stations:[/red] {e}")


@stations.command("info")
@click.option("--data", "-d", type=click.Path(), default="data/stations.csv",
              help="Station data CSV file")
def station_info(data: str):
    """Show station database information.
    
    Examples:
        jp-transit stations info
    """
    data_path = Path(data)
    
    if not data_path.exists():
        console.print(f"[red]Station data file not found:[/red] {data_path}")
        console.print("Run 'jp-transit stations crawl' first to create the database")
        return
    
    try:
        crawler = StationCrawler()
        stations = crawler.load_from_csv(data_path)
        searcher = StationSearcher(stations)
        
        # Gather statistics
        total_stations = len(stations)
        prefectures = searcher.get_all_prefectures()
        
        # Count stations by prefecture
        prefecture_counts = {}
        for prefecture in prefectures:
            prefecture_counts[prefecture] = len(searcher.search_by_prefecture(prefecture))
        
        # Display info
        console.print(f"[bold]Station Database Information[/bold]")
        console.print(f"Database file: {data_path}")
        console.print(f"Total stations: {total_stations}")
        console.print(f"Prefectures: {len(prefectures)}")
        
        if prefecture_counts:
            console.print("\n[bold]Stations by Prefecture:[/bold]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Prefecture", style="cyan")
            table.add_column("Station Count", style="green", justify="right")
            
            for prefecture in sorted(prefecture_counts.keys()):
                table.add_row(prefecture, str(prefecture_counts[prefecture]))
            
            console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error reading station info:[/red] {e}")