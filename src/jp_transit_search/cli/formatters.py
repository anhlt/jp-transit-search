"""Output formatters for CLI display."""

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..core.models import Route

console = Console()


def format_route_table(routes: Route | list[Route], verbose: bool = False) -> None:
    """Display route(s) as a rich table."""
    if isinstance(routes, Route):
        routes = [routes]

    if not routes:
        console.print("No routes found.")
        return

    for idx, route in enumerate(routes, 1):
        if len(routes) > 1:
            console.print(f"\n[bold cyan]Route {idx}:[/bold cyan]")

        # Use resolved station names if available, otherwise fall back to user input
        display_from = route.resolved_from_station or route.from_station
        display_to = route.resolved_to_station or route.to_station

        # Create main route info table
        table = Table(
            title=f"Route: {display_from} → {display_to}",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        table.add_row("Duration", route.duration)
        table.add_row("Cost", route.cost)
        table.add_row("Transfers", str(route.transfer_count))

        console.print(table)

        # Add transfer details if verbose or if there are transfers
        if verbose or route.transfers:
            console.print()

            if route.transfers:
                transfer_table = Table(
                    title="Transfer Details", show_header=True, header_style="bold blue"
                )
                transfer_table.add_column("From", style="cyan")
                transfer_table.add_column("To", style="cyan")
                transfer_table.add_column("Line", style="yellow")
                transfer_table.add_column("Time", style="magenta")
                transfer_table.add_column("Duration", style="green")
                transfer_table.add_column("Cost", style="green")
                transfer_table.add_column("Platform", style="blue")
                if (
                    verbose
                ):  # Only show riding position in verbose mode to avoid cluttering
                    transfer_table.add_column("Riding Position", style="dim blue")

                for transfer in route.transfers:
                    # Format timing information
                    time_info = ""
                    if transfer.departure_time and transfer.arrival_time:
                        time_info = f"{transfer.departure_time}→{transfer.arrival_time}"
                    elif transfer.departure_time:
                        time_info = f"dep: {transfer.departure_time}"
                    elif transfer.arrival_time:
                        time_info = f"arr: {transfer.arrival_time}"

                    # Format platform information
                    platform_info = ""
                    if transfer.departure_platform and transfer.arrival_platform:
                        platform_info = (
                            f"{transfer.departure_platform}→{transfer.arrival_platform}"
                        )
                    elif transfer.departure_platform:
                        platform_info = f"dep: {transfer.departure_platform}"
                    elif transfer.arrival_platform:
                        platform_info = f"arr: {transfer.arrival_platform}"
                    else:
                        platform_info = "-"

                    row_data = [
                        transfer.from_station,
                        transfer.to_station,
                        transfer.line_name,
                        time_info or "-",
                        f"{transfer.duration_minutes}分",
                        f"{transfer.cost_yen}円",
                        platform_info,
                    ]
                    if verbose:  # Add riding position column in verbose mode
                        row_data.append(transfer.riding_position or "-")

                    transfer_table.add_row(*row_data)

                console.print(transfer_table)
            else:
                console.print("[dim]No transfer details available[/dim]")


def format_route_detailed(routes: Route | list[Route]) -> None:
    """Display route(s) with detailed information."""
    if isinstance(routes, Route):
        routes = [routes]

    if not routes:
        console.print("No routes found.")
        return

    for idx, route in enumerate(routes, 1):
        if len(routes) > 1:
            console.print(f"\n[bold cyan]Route {idx}:[/bold cyan]")

        # Use resolved station names if available, otherwise fall back to user input
        display_from = route.resolved_from_station or route.from_station
        display_to = route.resolved_to_station or route.to_station

        # Route summary panel
        summary_text = f"""[bold]From:[/bold] {display_from}
[bold]To:[/bold] {display_to}
[bold]Duration:[/bold] {route.duration}
[bold]Cost:[/bold] {route.cost}
[bold]Transfers:[/bold] {route.transfer_count}"""

        console.print(Panel(summary_text, title="Route Summary", border_style="blue"))

        # Transfer details
        if route.transfers:
            console.print()
            console.print("[bold]Transfer Details:[/bold]")

            for i, transfer in enumerate(route.transfers, 1):
                transfer_text = f"""[cyan]{transfer.from_station}[/cyan] → [cyan]{transfer.to_station}[/cyan]
[bold]Line:[/bold] {transfer.line_name}
[bold]Duration:[/bold] {transfer.duration_minutes}分
[bold]Cost:[/bold] {transfer.cost_yen}円"""

                # Add timing information if available
                if transfer.departure_time or transfer.arrival_time:
                    timing = []
                    if transfer.departure_time:
                        timing.append(f"Departure: {transfer.departure_time}")
                    if transfer.arrival_time:
                        timing.append(f"Arrival: {transfer.arrival_time}")
                    transfer_text += f"\n[bold]Time:[/bold] {' → '.join(timing)}"

                # Add platform information if available
                if transfer.departure_platform or transfer.arrival_platform:
                    platforms = []
                    if transfer.departure_platform:
                        platforms.append(f"From: {transfer.departure_platform}")
                    if transfer.arrival_platform:
                        platforms.append(f"To: {transfer.arrival_platform}")
                    transfer_text += f"\n[bold]Platform:[/bold] {' | '.join(platforms)}"

                # Add riding position information if available
                if transfer.riding_position:
                    transfer_text += (
                        f"\n[bold]Riding Position:[/bold] {transfer.riding_position}"
                    )

                # Add intermediate stations if available
                if transfer.intermediate_stations:
                    transfer_text += "\n[bold]Intermediate Stations:[/bold]"
                    for station in transfer.intermediate_stations:
                        station_info = station.name
                        if station.arrival_time:
                            station_info += f" ({station.arrival_time})"
                        transfer_text += f"\n  • {station_info}"

                console.print(
                    Panel(transfer_text, title=f"Segment {i}", border_style="green")
                )


def format_route_json(routes: Route | list[Route]) -> str:
    """Format route(s) as JSON."""
    if isinstance(routes, Route):
        routes = [routes]

    if not routes:
        return json.dumps([], ensure_ascii=False, indent=2)

    routes_data = []
    for route in routes:
        # Use resolved station names if available, otherwise fall back to user input
        display_from = route.resolved_from_station or route.from_station
        display_to = route.resolved_to_station or route.to_station

        route_dict = {
            "from_station": display_from,
            "to_station": display_to,
            "duration": route.duration,
            "cost": route.cost,
            "transfer_count": route.transfer_count,
            "transfers": [
                {
                    "from_station": t.from_station,
                    "to_station": t.to_station,
                    "line_name": t.line_name,
                    "duration_minutes": t.duration_minutes,
                    "cost_yen": t.cost_yen,
                    "departure_time": t.departure_time,
                    "arrival_time": t.arrival_time,
                    "departure_platform": t.departure_platform,
                    "arrival_platform": t.arrival_platform,
                    "riding_position": t.riding_position,
                    "intermediate_stations": [
                        {
                            "name": station.name,
                            "arrival_time": station.arrival_time,
                        }
                        for station in t.intermediate_stations
                    ],
                }
                for t in route.transfers
            ],
        }
        routes_data.append(route_dict)

    return json.dumps(routes_data, ensure_ascii=False, indent=2)


def format_station_table(stations: list[object], verbose: bool = False) -> None:
    """Display stations as a table."""
    table = Table(title="Stations", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Prefecture", style="green")

    if verbose:
        table.add_column("Company", style="blue")
        table.add_column("Line", style="red")

    # This would be populated with actual station data
    # For now, just display placeholder
    console.print(table)
