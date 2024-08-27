import rich
import json
import requests

from rich.console import Console
from rich.table import Table


def error(response: requests.Response) -> None:
    """

    Returns
    -------

    """
    from rich import box
    console = Console()
    table = Table(title="", box=box.HORIZONTALS)

    table.add_column("Code", justify="center", style="red", no_wrap=True)
    table.add_column("Error", justify="center", style="red", no_wrap=True)
    table.add_column("Description", justify="center", style="red", no_wrap=True)

    table.add_row(f"{response.status_code}", f"{response.json()['error']['code']}", f"{response.json()['error']['message']}")

    console.print(table)
