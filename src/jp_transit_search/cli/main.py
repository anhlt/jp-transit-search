"""CLI main entry point for Japanese transit search."""

import sys

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
def search(
    from_station: str, to_station: str, output_format: str, timeout: int, verbose: bool
) -> None:
    """Search for transit routes between stations.

    Examples:
        jp-transit search "横浜" "豊洲"
        jp-transit search "東京" "新宿" --format json
        jp-transit search "渋谷" "品川" --verbose
    """
    try:
        with console.status(
            f"[bold green]Searching route from {from_station} to {to_station}..."
        ):
            scraper = YahooTransitScraper(timeout=timeout)
            route = scraper.search_route(from_station, to_station)

        # Format and display results
        if output_format == "json":
            click.echo(format_route_json(route))
        elif output_format == "detailed":
            click.echo(format_route_detailed(route))
        else:
            click.echo(format_route_table(route, verbose=verbose))

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
