"""Output formatters for CLI display."""

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..core.models import Route

console = Console()


def format_route_table(route: Route, verbose: bool = False) -> str:
    """Format route as a rich table."""
    # Create main route info table
    table = Table(
        title=f"Route: {route.from_station} → {route.to_station}",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    table.add_row("Duration", route.duration)
    table.add_row("Cost", route.cost)
    table.add_row("Transfers", str(route.transfer_count))

    output = ""
    with console.capture() as capture:
        console.print(table)
    output += capture.get()

    # Add transfer details if verbose or if there are transfers
    if verbose or route.transfers:
        output += "\n"

        if route.transfers:
            transfer_table = Table(
                title="Transfer Details", show_header=True, header_style="bold blue"
            )
            transfer_table.add_column("From", style="cyan")
            transfer_table.add_column("To", style="cyan")
            transfer_table.add_column("Line", style="yellow")
            transfer_table.add_column("Duration", style="green")
            transfer_table.add_column("Cost", style="green")

            for transfer in route.transfers:
                transfer_table.add_row(
                    transfer.from_station,
                    transfer.to_station,
                    transfer.line_name,
                    f"{transfer.duration_minutes}分",
                    f"{transfer.cost_yen}円",
                )

            with console.capture() as capture:
                console.print(transfer_table)
            output += capture.get()
        else:
            with console.capture() as capture:
                console.print("[dim]No transfer details available[/dim]")
            output += capture.get()

    return output


def format_route_detailed(route: Route) -> str:
    """Format route with detailed information."""
    output = ""

    # Route summary panel
    summary_text = f"""[bold]From:[/bold] {route.from_station}
[bold]To:[/bold] {route.to_station}
[bold]Duration:[/bold] {route.duration}
[bold]Cost:[/bold] {route.cost}
[bold]Transfers:[/bold] {route.transfer_count}"""

    with console.capture() as capture:
        console.print(Panel(summary_text, title="Route Summary", border_style="blue"))
    output += capture.get()

    # Transfer details
    if route.transfers:
        output += "\n"
        with console.capture() as capture:
            console.print("[bold]Transfer Details:[/bold]")
        output += capture.get()

        for i, transfer in enumerate(route.transfers, 1):
            transfer_text = f"""[cyan]{transfer.from_station}[/cyan] → [cyan]{transfer.to_station}[/cyan]
[bold]Line:[/bold] {transfer.line_name}
[bold]Duration:[/bold] {transfer.duration_minutes}分
[bold]Cost:[/bold] {transfer.cost_yen}円"""

            with console.capture() as capture:
                console.print(
                    Panel(transfer_text, title=f"Segment {i}", border_style="green")
                )
            output += capture.get()

    return output


def format_route_json(route: Route) -> str:
    """Format route as JSON."""
    route_dict = {
        "from_station": route.from_station,
        "to_station": route.to_station,
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
            }
            for t in route.transfers
        ],
    }

    return json.dumps(route_dict, ensure_ascii=False, indent=2)


def format_station_table(stations: list[object], verbose: bool = False) -> str:
    """Format stations as a table."""
    table = Table(title="Stations", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Prefecture", style="green")

    if verbose:
        table.add_column("Company", style="blue")
        table.add_column("Line", style="red")

    # This would be populated with actual station data
    # For now, just return placeholder
    output = ""
    with console.capture() as capture:
        console.print(table)
    output += capture.get()

    return output
