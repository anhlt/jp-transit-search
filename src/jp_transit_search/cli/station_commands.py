"""CLI commands for station management."""

from pathlib import Path
from typing import Any, cast

import click
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
)
from rich.table import Table

from ..crawler import StationCrawler, StationSearcher

console = Console()


@click.group()
def stations() -> None:
    """Station management commands."""
    pass


@stations.command("crawl")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="data/stations.csv",
    help="Output CSV file path",
)
@click.option("--timeout", "-t", default=30, help="Request timeout in seconds")
@click.option(
    "--resume", "-r", is_flag=True, help="Resume from existing CSV and state file"
)
@click.option(
    "--state-file",
    "-s",
    type=click.Path(),
    default="data/crawl_state.json",
    help="State file for tracking progress",
)
def crawl_stations(output: str, timeout: int, resume: bool, state_file: str) -> None:
    """Crawl station data from Yahoo Transit with resumable functionality.

    The crawler shows detailed progress including:
    - Number of stations found and processed
    - Current prefecture and railway line being crawled
    - Duplicate detection and filtering
    - Automatic checkpointing every 50 stations

    Use --resume to continue from a previous interrupted crawl.

    Examples:
        jp-transit stations crawl
        jp-transit stations crawl --output my_stations.csv
        jp-transit stations crawl --resume --timeout 60
    """
    output_path = Path(output)
    state_path = Path(state_file)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    # Progress tracking variables
    progress_data = {
        "stations_found": 0,
        "duplicates_filtered": 0,
        "prefectures_completed": 0,
        "lines_completed": 0,
        "current_prefecture": "",
        "current_line": "",
        "errors": 0,
        "elapsed_time": 0,
    }

    def update_progress_display(data: dict[str, Any]) -> None:
        """Update progress display with current crawling status."""
        nonlocal progress_data
        progress_data.update(data)

        # Format elapsed time
        elapsed_min = int(data["elapsed_time"] // 60)
        elapsed_sec = int(data["elapsed_time"] % 60)
        time_str = f"{elapsed_min:02d}:{elapsed_sec:02d}"

        # Create detailed status message
        status_parts = []
        if data["current_prefecture"]:
            status_parts.append(f"Prefecture: {data['current_prefecture']}")
        if data["current_line"]:
            status_parts.append(f"Line: {data['current_line']}")
        if data["stations_found"] > 0:
            status_parts.append(f"Stations: {data['stations_found']}")
        if data["duplicates_filtered"] > 0:
            status_parts.append(f"Filtered: {data['duplicates_filtered']}")

        status = " | ".join(status_parts) if status_parts else data["message"]

        # Update progress displays
        overall_progress.update(overall_task, description=f"[cyan]{status}[/cyan]")
        stats_progress.update(
            stats_task,
            description=f"[green]Found: {data['stations_found']}[/green] | "
            f"[yellow]Duplicates: {data['duplicates_filtered']}[/yellow] | "
            f"[blue]Time: {time_str}[/blue] | "
            f"[red]Errors: {data['errors']}[/red]",
        )

    # Setup Rich progress display

    with (
        Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            expand=True,
        ) as overall_progress,
        Progress(
            TextColumn("[progress.description]{task.description}"),
            console=console,
            expand=True,
        ) as stats_progress,
    ):
        overall_task = overall_progress.add_task("Initializing crawler...", total=None)
        stats_task = stats_progress.add_task("", total=None)

        try:
            # Initialize crawler with progress callback
            crawler = StationCrawler(
                timeout=timeout, progress_callback=update_progress_display
            )

            # Determine resume parameters
            resume_csv = output_path if (resume and output_path.exists()) else None
            resume_state = state_path if resume else None

            if resume and resume_csv:
                console.print(f"[yellow]Resuming crawl from:[/yellow] {resume_csv}")
                console.print(f"[yellow]State file:[/yellow] {resume_state}")

            overall_progress.update(overall_task, description="Starting crawl...")

            # Start crawling with resume capability
            stations = crawler.crawl_all_stations(
                resume_from_csv=resume_csv, state_file=resume_state
            )

            overall_progress.update(overall_task, description="Saving final results...")

            # Save final results (if not using incremental saves)
            if not resume or not output_path.exists():
                crawler.save_to_csv(stations, output_path)

            overall_progress.update(
                overall_task, description="[green]Crawl completed![/green]"
            )

        except KeyboardInterrupt:
            overall_progress.update(
                overall_task, description="[yellow]Crawl interrupted by user[/yellow]"
            )
            console.print(
                f"\n[yellow]Crawl interrupted! Progress saved to:[/yellow] {state_path}"
            )
            console.print(
                "[yellow]Resume with:[/yellow] jp-transit stations crawl --resume"
            )
            return

        except Exception as e:
            overall_progress.update(overall_task, description="[red]Crawl failed[/red]")
            console.print(f"[red]Error crawling stations:[/red] {e}")
            console.print(
                f"[yellow]Partial progress may be saved to:[/yellow] {output_path}"
            )
            return

    # Final summary
    console.print(
        f"\n[green]✓ Successfully crawled {progress_data['stations_found']} stations[/green]"
    )
    console.print(
        f"[green]✓ Filtered {progress_data['duplicates_filtered']} duplicates[/green]"
    )
    console.print(
        f"[green]✓ Processed {progress_data['prefectures_completed']} prefectures, {progress_data['lines_completed']} lines[/green]"
    )
    console.print(f"[green]✓ Results saved to:[/green] {output_path}")

    if cast(int, progress_data["errors"]) > 0:
        console.print(
            f"[yellow]⚠ {progress_data['errors']} errors encountered during crawling[/yellow]"
        )


@stations.command("search")
@click.argument("query")
@click.option("--prefecture", "-p", help="Filter by prefecture")
@click.option("--limit", "-l", default=10, help="Maximum number of results")
@click.option(
    "--data",
    "-d",
    type=click.Path(),
    default="data/stations.csv",
    help="Station data CSV file",
)
@click.option("--exact", is_flag=True, help="Exact match only")
def search_stations(
    query: str, prefecture: str | None, limit: int, data: str, exact: bool
) -> None:
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
            results = [
                s
                for s in searcher.search_by_prefecture(prefecture)
                if query.lower() in s.name.lower()
            ]
        else:
            results = searcher.search_by_name(query, exact=exact)

        # Limit results
        results = results[:limit]

        if not results:
            console.print(f"[yellow]No stations found matching '{query}'[/yellow]")
            return

        # Display results
        table = Table(
            title=f"Station Search Results: '{query}'",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Prefecture", style="green")
        table.add_column("City", style="yellow")
        table.add_column("Railway Company", style="blue")

        for station in results:
            table.add_row(
                station.name,
                station.prefecture or "",
                station.city or "",
                station.railway_company or "",
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error searching stations:[/red] {e}")


@stations.command("list")
@click.option("--prefecture", "-p", help="Filter by prefecture")
@click.option("--limit", "-l", default=20, help="Maximum number of results")
@click.option(
    "--data",
    "-d",
    type=click.Path(),
    default="data/stations.csv",
    help="Station data CSV file",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    help="Output format",
)
def list_stations(prefecture: str | None, limit: int, data: str, output_format: str) -> None:
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
                    "aliases": s.aliases,
                }
                for s in filtered_stations
            ]
            console.print(json.dumps(station_data, ensure_ascii=False, indent=2))

        elif output_format == "csv":
            import csv
            import io

            output = io.StringIO()
            fieldnames = [
                "name",
                "prefecture",
                "city",
                "railway_company",
                "line_name",
                "station_code",
                "latitude",
                "longitude",
                "aliases",
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for station in filtered_stations:
                writer.writerow(
                    {
                        "name": station.name,
                        "prefecture": station.prefecture or "",
                        "city": station.city or "",
                        "railway_company": station.railway_company or "",
                        "line_name": station.line_name or "",
                        "station_code": station.station_code or "",
                        "latitude": station.latitude or "",
                        "longitude": station.longitude or "",
                        "aliases": "|".join(station.aliases) if station.aliases else "",
                    }
                )

            console.print(output.getvalue())

        else:  # table format
            table = Table(
                title=f"Stations ({len(filtered_stations)})",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Prefecture", style="green")
            table.add_column("City", style="yellow")
            table.add_column("Railway Company", style="blue")

            for station in filtered_stations:
                table.add_row(
                    station.name,
                    station.prefecture or "",
                    station.city or "",
                    station.railway_company or "",
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing stations:[/red] {e}")


@stations.command("info")
@click.option(
    "--data",
    "-d",
    type=click.Path(),
    default="data/stations.csv",
    help="Station data CSV file",
)
def station_info(data: str) -> None:
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
            prefecture_counts[prefecture] = len(
                searcher.search_by_prefecture(prefecture)
            )

        # Display info
        console.print("[bold]Station Database Information[/bold]")
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
