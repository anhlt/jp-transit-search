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
@click.option(
    "--max-lines",
    "-m",
    type=int,
    help="Maximum railway lines to crawl per prefecture (default: no limit)",
)
def crawl_stations(
    output: str, timeout: int, resume: bool, state_file: str, max_lines: int | None
) -> None:
    """Crawl station data from Yahoo Transit with resumable functionality.

    The crawler shows detailed real-time progress including:
    - Current prefecture (1-47) and railway line being crawled
    - Individual stations being processed with names
    - Number of stations found and duplicates filtered
    - Crawl rate (stations per minute) and elapsed time
    - Automatic checkpointing and state saving

    Use --resume to continue from a previous interrupted crawl.
    Use --max-lines to limit railway lines per prefecture (useful for testing).

    Examples:
        jp-transit stations crawl
        jp-transit stations crawl --output my_stations.csv --max-lines 5
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

        # Create detailed status message based on what's available
        status_parts = []

        # Show prefecture progress
        if data.get("prefectures_completed", 0) > 0 or data.get("current_prefecture"):
            pref_progress = f"[{data.get('prefectures_completed', 0):2d}/47]"
            if data.get("current_prefecture"):
                status_parts.append(f"{pref_progress} {data['current_prefecture']}")
            else:
                status_parts.append(f"{pref_progress} Prefectures")

        # Show current line if available
        if data.get("current_line"):
            status_parts.append(f"Line: {data['current_line']}")

        # Show current station if available
        if data.get("current_station"):
            status_parts.append(f"Station: {data['current_station']}")

        # If no specific status, use the message
        if not status_parts and data.get("message"):
            status_parts.append(data["message"])

        status = " | ".join(status_parts) if status_parts else "Processing..."

        # Calculate rate if we have enough data
        rate_info = ""
        if data["elapsed_time"] > 0 and data["stations_found"] > 0:
            rate = (
                data["stations_found"] / data["elapsed_time"] * 60
            )  # stations per minute
            rate_info = f" | [magenta]Rate: {rate:.1f}/min[/magenta]"

        # Update progress displays
        overall_progress.update(overall_task, description=f"[cyan]{status}[/cyan]")
        stats_progress.update(
            stats_task,
            description=f"[green]Stations: {data['stations_found']}[/green] | "
            f"[yellow]Duplicates: {data['duplicates_filtered']}[/yellow] | "
            f"[blue]Lines: {data['lines_completed']}[/blue] | "
            f"[orange1]Time: {time_str}[/orange1]{rate_info} | "
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
                timeout=timeout,
                progress_callback=update_progress_display,
                max_lines_per_prefecture=max_lines,
            )

            # Determine resume parameters
            resume_csv = output_path if (resume and output_path.exists()) else None
            resume_state = state_path if resume else None

            if resume and resume_csv:
                console.print(f"[yellow]Resuming crawl from:[/yellow] {resume_csv}")
                console.print(f"[yellow]State file:[/yellow] {resume_state}")

            overall_progress.update(overall_task, description="Starting crawl...")

            # Start crawling with resume capability (with incremental CSV writing)
            crawler.crawl_all_stations(
                resume_from_csv=resume_csv,
                state_file=resume_state,
                output_path=output_path,
            )

            overall_progress.update(
                overall_task, description="[green]Crawl completed![/green]"
            )

            # Incremental CSV writing is handled automatically during crawling
            # Final results are already saved to CSV file

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
@click.option(
    "--fuzzy-threshold",
    "-t",
    default=70,
    help="Minimum fuzzy match score (0-100, default: 70)",
)
@click.option("--show-scores", is_flag=True, help="Show fuzzy match scores")
def search_stations(
    query: str,
    prefecture: str | None,
    limit: int,
    data: str,
    exact: bool,
    fuzzy_threshold: int,
    show_scores: bool,
) -> None:
    """Search for stations by name with enhanced fuzzy matching.

    Supports searching in Japanese (kanji, hiragana, katakana) and romaji.
    Uses fuzzy matching to find stations even with slight misspellings.

    Examples:
        jp-transit stations search "新宿"
        jp-transit stations search "shinjuku" --show-scores
        jp-transit stations search "駅" --prefecture "東京都" --limit 5
        jp-transit stations search "東京" --exact
        jp-transit stations search "shibuya" --fuzzy-threshold 80
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
        if exact:
            results = searcher.search_by_name(query, exact=True)
            if prefecture:
                # Filter exact results by prefecture
                results = [s for s in results if s.prefecture == prefecture]
        else:
            # Use enhanced search_by_name for fuzzy matching
            results = searcher.search_by_name(
                query, exact=False, fuzzy_threshold=fuzzy_threshold
            )
            if prefecture:
                # Filter results by prefecture
                results = [s for s in results if s.prefecture == prefecture]

        # Limit results
        results = results[:limit]

        if not results:
            console.print(f"[yellow]No stations found matching '{query}'[/yellow]")
            if not exact and fuzzy_threshold > 50:
                console.print(
                    f"[dim]Try lowering --fuzzy-threshold (currently {fuzzy_threshold}) or use exact search with --exact[/dim]"
                )
            return

        # Display results
        title = f"Station Search Results: '{query}'"
        if not exact:
            title += f" (fuzzy threshold: {fuzzy_threshold})"

        table = Table(
            title=title,
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Name", style="cyan", no_wrap=True)
        if show_scores and not exact:
            table.add_column("Score", style="magenta", no_wrap=True)
        table.add_column("Hiragana", style="dim cyan", no_wrap=True)
        table.add_column("Katakana", style="dim cyan", no_wrap=True)
        table.add_column("Romaji", style="dim cyan", no_wrap=True)
        table.add_column("Station Code", style="yellow", no_wrap=True)
        table.add_column("Line Name", style="blue")
        table.add_column("Prefecture", style="green")

        for item in results:
            if isinstance(item, tuple) and len(item) == 2:
                # Fuzzy search result with score
                station, score = item
                row_data = [station.name]
                if show_scores and not exact:
                    row_data.append(f"{score:.1f}")
                row_data.extend(
                    [
                        station.name_hiragana or "",
                        station.name_katakana or "",
                        station.name_romaji or "",
                        str(station.station_id) if station.station_id else "",
                        station.line_name or "",
                        station.prefecture or "",
                    ]
                )
            else:
                # Regular station result
                station = item
                row_data = [station.name]
                if show_scores and not exact:
                    row_data.append("100.0")
                row_data.extend(
                    [
                        station.name_hiragana or "",
                        station.name_katakana or "",
                        station.name_romaji or "",
                        str(station.station_id) if station.station_id else "",
                        station.line_name or "",
                        station.prefecture or "",
                    ]
                )

            table.add_row(*row_data)

        console.print(table)

        if not exact and len(results) > 0:
            console.print(
                f"[dim]Found {len(results)} stations. Use --show-scores to see match quality.[/dim]"
            )

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
def list_stations(
    prefecture: str | None, limit: int, data: str, output_format: str
) -> None:
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
                    "name_hiragana": s.name_hiragana,
                    "name_katakana": s.name_katakana,
                    "name_romaji": s.name_romaji,
                    "prefecture": s.prefecture,
                    "prefecture_id": s.prefecture_id,
                    "station_id": s.station_id,
                    "railway_company": s.railway_company,
                    "line_name": s.line_name,
                    "aliases": s.aliases,
                    "all_lines": s.all_lines,
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
                "name_hiragana",
                "name_katakana",
                "name_romaji",
                "prefecture",
                "prefecture_id",
                "station_id",
                "railway_company",
                "line_name",
                "aliases",
                "all_lines",
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for station in filtered_stations:
                writer.writerow(
                    {
                        "name": station.name,
                        "name_hiragana": station.name_hiragana or "",
                        "name_katakana": station.name_katakana or "",
                        "name_romaji": station.name_romaji or "",
                        "prefecture": station.prefecture or "",
                        "prefecture_id": station.prefecture_id or "",
                        "station_id": station.station_id or "",
                        "railway_company": station.railway_company or "",
                        "line_name": station.line_name or "",
                        "aliases": "|".join(station.aliases) if station.aliases else "",
                        "all_lines": "|".join(station.all_lines)
                        if station.all_lines
                        else "",
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
            table.add_column("Station Code", style="yellow", no_wrap=True)
            table.add_column("Line Name", style="blue")
            table.add_column("Prefecture", style="green")

            for station in filtered_stations:
                table.add_row(
                    station.name,
                    str(station.station_id) if station.station_id else "",
                    station.line_name or "",
                    station.prefecture or "",
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
