import os
import rich
import requests
import pathlib
import configparser

from rich import print
from rich.filesize import decimal
from rich.markup import escape
from rich.text import Text
from rich.tree import Tree

from graphviper.utils import logger


class GraphQuery:
    def __init__(self):
        config_file = "/".join((str(pathlib.Path(__file__).parent.resolve()), ".graph/config.cfg"))

        logger.info(f"{config_file}")

        if not pathlib.Path(config_file).exists():
            print("Missing configuration file.")

        config = configparser.ConfigParser()
        config.read(config_file)

        self.app_token = config.get("msgraph", "app_token")
        self.hostname = config.get("msgraph", "hostname")
        self.version = config.get("msgraph", "version")

        if os.getenv("APP_TOKEN"):
            # Could add some verification that the token is correct here
            self.app_token = os.getenv("APP_TOKEN")

        if self.app_token == "None":
            from security.encryption import get_credentials

            logger.info("Attempting to get credentials ...")
            self.app_token = get_credentials(persistent=True)
            # Could add some verification that the token is correct here

        self.header = {
            "Host": "graph.microsoft.com",
            "Authorization": f"Bearer {self.app_token}",
            "Content-Type": "application/json"
        }

        self.drive = None
        self.response = None

    def listdir(self, path: str) -> None:

        self.response = requests.get(
            url=f"https://{self.hostname}/{self.version}/me/drive/root:/{path}:/children",
            headers=self.header
        )

        tree = Tree(
            f":open_file_folder: [link file://{path}]{path}",
            guide_style="bold bright_blue",
        )

        for entry in self.response.json()["value"]:
            if "folder" in entry.keys():
                style = ""
                tree.add(
                    f"[bold magenta]:open_file_folder: [link file://{path}]{escape(entry['name'])}",
                    style=style,
                    guide_style=style,
                )

            else:
                text_filename = Text(entry["name"], "green")

                #text_filename.highlight_regex(r"\..*$", "bold red")
                text_filename.stylize(f" link file://{entry['parentReference']['path']}")

                #file_size = path.stat().st_size
                #text_filename.append(f" ({decimal(file_size)})", "blue")
                icon = "📦 " if entry['name'].rsplit(".")[-1] == "zip" else "📄 "

                #icon = "📄 "
                #icon = "📦 "
                tree.add(Text(icon) + text_filename)

        rich.print(tree)
