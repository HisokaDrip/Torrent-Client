from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from datetime import datetime

console = Console()


class FluxUI:
    def __init__(self):
        self.layout = Layout()
        self.console = console

    def header(self):
        """Returns the branding header."""
        grid = Table.grid(expand=True)
        grid.add_column(justify="center", ratio=1)
        grid.add_column(justify="right")

        title = Text("⚡ FluxTorrent", style="bold cyan", justify="center")
        subtitle = Text("Engineered by Mazy", style="bold magenta", justify="center")

        grid.add_row(title, datetime.now().strftime("%H:%M:%S"))
        grid.add_row(subtitle, "")

        return Panel(grid, style="white on black")

    def print_log(self, message, level="INFO"):
        """Prints a styled log message."""
        color = "green" if level == "INFO" else "red"
        if level == "WARNING": color = "yellow"

        time_str = f"[{datetime.now().strftime('%H:%M:%S')}]"
        self.console.print(f"{time_str} [bold {color}]{level}[/]: {message}")

    def show_peers(self, peers):
        """Displays the list of connected peers in a table."""
        table = Table(title="Swarm Connection Status", box=None)
        table.add_column("IP Address", style="cyan")
        table.add_column("Port", style="magenta")
        table.add_column("Status", style="green")

        for ip, port in peers[:10]:  # Show top 10
            table.add_row(str(ip), str(port), "Handshaking...")

        self.console.print(Panel(table, title="Active Peers", border_style="blue"))


ui = FluxUI()