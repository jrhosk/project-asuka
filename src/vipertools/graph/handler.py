import rich
import json
import requests

from graphviper.utils import logger

from rich.console import Console
from rich.table import Table


def _error_table(response: requests.Response):
    from rich import box
    console = Console()
    table = Table(title="", box=box.HORIZONTALS)

    table.add_column("Code", justify="center", style="red", no_wrap=True)
    table.add_column("Error", justify="center", style="red", no_wrap=True)
    table.add_column("Description", justify="center", style="red", no_wrap=True)

    table.add_row(f"{response.status_code}", f"{response.json()['error']['code']}",
                  f"{response.json()['error']['message']}")

    console.print(table)


def error(response: requests.Response, table=False) -> None:
    """
    Formatted, fancy requests error messages handling

    Returns
    -------

    """
    # This is super simple right now, but I think I will add more to it later so there you go ...
    if table:
        _error_table(response)

    else:
        logger.error(f"({response.status_code}) {response.json()['error']['code']}: {response.json()['error']['message']}")