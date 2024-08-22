import json
import rich
import requests
import pathlib

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

    def get_path(self, path: str = "/") -> requests.Response:
        """

        Parameters
        ----------
        path: str (defaults /)
            Remote path to retrieve.

        Returns
        -------
        requires.Response

        """
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

        return self.response

    def generate_manifest(self, path: str = "/") -> None:
        """
        Generate a manifest file from files in NRAO one drive.
        Parameters
        ----------
        path: str, (default /)
            The remote path to generate the manifest file from.

        Returns
        -------
        None
        """
        sharepoint_url = "https://nrao-my.sharepoint.com/"

        manifest_path = "/".join((str(pathlib.Path(__file__).parent.resolve()), ".manifest/file.download.json"))

        # Open template download manifest
        with open(manifest_path, "r") as file:
            manifest = json.load(file)

        new_manifest = {
            "version": manifest["version"],
            "metadata": {}
        }

        # Query the graph to get the dpath information
        self.get_path(path)

        file_list = self.response.json()["value"]

        for entry in file_list:
            url = f"https://{self.graph.hostname}/{self.graph.version}/me/drive/items/{entry['id']}/createLink"

            logger.debug(f"processing: {entry['name']} ...")
            self.response = requests.post(
                url=url,
                json={
                    "type": "view",
                    "scope": "anonymous"
                },
                headers=self.graph.header

            )

            logger.debug(f"link> {self.response.json()['link']['webUrl']}\n")

    def listdir(self, path: str = "/") -> None:
        """
        List the contents of a remote directory.
        Parameters
        ----------
        path: str, (default "/")
            Remote path to list the contents from.

        Returns
        -------
        None

        """
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
