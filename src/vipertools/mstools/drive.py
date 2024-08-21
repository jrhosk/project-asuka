import rich
import requests

from rich import print
from rich.filesize import decimal
from rich.markup import escape
from rich.text import Text
from rich.tree import Tree

from vipertools.graph import GraphQuery
from graphviper.utils import logger


class DriveTool:
    def __init__(self):
        self.graph = GraphQuery(True)
        self.response = None

    def get_path(self, path="/"):
        if path == "/":
            # Root directory requires a different call - <sarcasim> this makes perfect sense.</sarcasim>
            url = f"https://{self.graph.hostname}/{self.graph.version}/me/drive/root/children"

        else:
            url = f"https://{self.graph.hostname}/{self.graph.version}/me/drive/root:/{path}:/children"

        logger.debug(url)
        self.response = requests.get(
            url=url,
            headers=self.graph.header
        )

    def create_link(self, path="/"):
        self.get_path(path)
        #file_list = self.response.json()["value"]

        #for entry in file_list:
        #    logger.debug(entry["id"])
        #    url = f"https://{self.graph.hostname}/{self.graph.version}/me/drive/items/{entry['id']}/createLink"
        #    requests.post(
        #        url=url,
        #        json={
        #            "type": "view",
        #            "scope": "anonymous"
        #        }
        #    )

            #logger.debug(self.response.json())

    def listdir(self, path: str = "/") -> None:
        self.get_path(path)

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
