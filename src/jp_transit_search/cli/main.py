"""CLI main entry point for Japanese transit search."""

import sys
from datetime import datetime as dt_module

import click
from rich.console import Console

from ..core import (
    RouteNotFoundError,
    ScrapingError,
    ValidationError,
    YahooTransitScraper,
)
from .formatters import format_route_detailed, format_route_json, format_route_table
from .station_commands import stations

console = Console()
error_console = Console(stderr=True)


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Japanese Transit Search - Search transit routes between Japanese stations."""
    pass


@cli.command()
@click.argument("from_station")
@click.argument("to_station")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "detailed"]),
    default="table",
    help="Output format",
)
@click.option("--timeout", "-t", default=30, help="Request timeout in seconds")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed information")
@click.option(
    "--datetime",
    "-d",
    "datetime_str",
    help="Departure datetime (YYYY-MM-DD HH:MM format)",
    type=str,
)
@click.option(
    "--search-type",
    "-s",
    type=click.Choice(["earliest", "cheapest", "easiest"]),
    default="earliest",
    help="Search type preference",
)
@click.option(
    "--save-html",
    help="Save raw HTML response to file for debugging",
    type=click.Path(),
)
def search(
    from_station: str,
    to_station: str,
    output_format: str,
    timeout: int,
    verbose: bool,
    datetime_str: str,
    search_type: str,
    save_html: str,
) -> None:
    """Search for transit routes between stations.

    Examples:
        jp-transit search "横浜" "豊洲"
        jp-transit search "東京" "新宿" --format json
        jp-transit search "渋谷" "品川" --verbose
        jp-transit search "大船" "羽田空港" --datetime "2025-10-31 16:31"
    """
    try:
        # Parse datetime if provided
        search_datetime = None
        if datetime_str:
            try:
                search_datetime = dt_module.strptime(datetime_str, "%Y-%m-%d %H:%M")
            except ValueError:
                error_console.print(
                    "[red]Invalid datetime format. Use YYYY-MM-DD HH:MM[/red]"
                )
                sys.exit(1)

        with console.status(
            f"[bold green]Searching route from {from_station} to {to_station}..."
        ):
            scraper = YahooTransitScraper(timeout=timeout)
            routes = scraper.search_route(
                from_station=from_station,
                to_station=to_station,
                search_datetime=search_datetime,
                search_type=search_type,
                save_html_path=save_html,
            )

        # Format and display results
        if len(routes) == 0:
            error_console.print("[yellow]No routes found[/yellow]")
            return

        if output_format == "json":
            click.echo(format_route_json(routes))
        elif output_format == "detailed":
            format_route_detailed(routes)
        else:
            format_route_table(routes, verbose=verbose)

    except ValidationError as e:
        error_console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except RouteNotFoundError as e:
        error_console.print(f"[yellow]No route found:[/yellow] {e}")
        sys.exit(1)
    except ScrapingError as e:
        error_console.print(f"[red]Scraping error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[red]Unexpected error:[/red] {e}")
        if verbose:
            error_console.print_exception()
        sys.exit(1)


# Add the imported stations command group to the main CLI
cli.add_command(stations)


@cli.group()
def config() -> None:
    """Configuration management."""
    pass


@config.command("show")
def show_config() -> None:
    """Show current configuration."""
    console.print("[bold]Current Configuration:[/bold]")
    console.print("• Default timeout: 30 seconds")
    console.print("• Default format: table")
    console.print("• Station database: Not configured")


@config.command("set")
@click.argument("key")
@click.argument("value")
def set_config(key: str, value: str) -> None:
    """Set configuration value.

    Examples:
        jp-transit config set timeout 60
        jp-transit config set default_format json
    """
    console.print("[yellow]Configuration setting not implemented yet.[/yellow]")
    console.print(f"Would set {key} = {value}")


if __name__ == "__main__":
    cli()
