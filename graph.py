import rich
import scp
import paramiko
import requests
import pathlib
import configparser

from rich import print
from rich.filesize import decimal
from rich.markup import escape
from rich.text import Text
from rich.tree import Tree


class GraphQuery:
    def __init__(self, config=None):
        if not pathlib.Path(config).exists():
            print("Missing configuration file.")

        settings = configparser.ConfigParser()

        self.settings = settings.read(config)
        self.hostname = settings.get("msgraph", "hostname")
        self.app_token = settings.get("msgraph", "app_token")
        self.version = settings.get("msgraph", "version")

        self.response = None

    def listdir(self, path: str)->None:
        header = {
            "Host": "graph.microsoft.com",
            "Authorization": f"Bearer {self.app_token}",
            "Content-Type": "application/json"
        }

        self.response = requests.get(
            url=f"https://{self.hostname}/{self.version}/me/drive/root:/{path}:/children",
            headers=header
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
                print(entry['name'].rsplit(".")[-1])
                #icon = "📄 "
                #icon = "📦 "
                tree.add(Text(icon) + text_filename)

        rich.print(tree)
