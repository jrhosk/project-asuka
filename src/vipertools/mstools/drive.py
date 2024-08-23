import json
import rich
import requests
import pathlib

from rich.filesize import decimal
from rich.markup import escape
from rich.text import Text
from rich.tree import Tree

from vipertools.graph import codes as status_code
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

    def generate_manifest(self, path: str = "/", version: str = None) -> None:
        """
        Generate a manifest file from files in NRAO one drive.
        Parameters
        ----------
        version: str (defaults None)
                Version of newly generated manifest for.

        path: str, (default /)
            The remote path to generate the manifest file from.

        Returns
        -------
        None
        """
        sharepoint_url = "https://nrao-my.sharepoint.com/"

        manifest_path = "/".join((str(pathlib.Path(__file__).parent.resolve()), ".manifest/file.download.json"))

        # Open download manifest
        with open(manifest_path, "r+") as file:
            manifest = json.load(file)
            file.seek(0)

            if version is not None:
                manifest["version"] = version

            # This is the base skeleton from the download manifest
            _manifest = {
                "version": manifest["version"],
                "metadata": {}
            }

            # Query the graph to get the dpath information
            self.get_path(path)

            file_list = self.response.json()["value"]

            for entry in file_list:
                url = f"https://{self.graph.hostname}/{self.graph.version}/me/drive/items/{entry['id']}/createLink"

                self.response = requests.post(
                    url=url,
                    json={
                        "type": "view",
                        "scope": "anonymous"
                    },
                    headers=self.graph.header
                )

                key_name = entry["name"].rsplit(".zip")[0]
                link_id = self.response.json()['link']['webUrl'].split(sharepoint_url)[1]
                logger.debug(f"processing: {key_name} ...")

                _manifest["metadata"][key_name] = manifest["metadata"].setdefault(
                    key_name, {
                        "file": entry["name"],
                        "id": "",
                        "dtype": "",
                        "telescope": "",
                        "size": entry["size"],
                        "mode": ""
                    })

                _manifest["metadata"][key_name]["id"] = link_id

            json.dump(_manifest, file)
            file.truncate()

    def download(self, path: str, filename: str) -> None:
        """
        Download a file from onedrive give a path.
        Parameters
        ----------
        path: str  onedrive path where file exists.
        filename: str file to download

        Returns
        -------

        """
        from rich.progress import (Progress, SpinnerColumn, TotalFileSizeColumn, TransferSpeedColumn,
                                   TaskProgressColumn, BarColumn, TextColumn, TimeRemainingColumn)

        item_id = None

        logger.info(f"Downloading {filename} from {path}...")

        # Get the path information
        response = self.get_path(path)

        # Find the item-id needed to download the file
        if response.status_code == status_code.OK:
            for entry in response.json()["value"]:
                if entry["name"] == filename:
                    item_id = entry["id"]
                    break

        else:
            logger.error(f"{filename} not found")
            return None

        # Build the download request url
        url = f"https://{self.graph.hostname}/{self.graph.version}/me/drive/items/{item_id}/content"

        response = requests.get(
            url=url,
            headers={
                "Authorization": f"Bearer {self.graph.app_token}"
            }
        )

        if response.status_code == status_code.OK:
            total = int(response.headers.get("content-length", 0))

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                TotalFileSizeColumn()
            ) as progress:
                task = progress.add_task(f"Downloading: {filename}", total=total)

                with open(filename, "wb") as file:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            size = file.write(chunk)
                            progress.update(task, advance=size)
        else:
            logger.error(f"(error {response.status_code}): {filename} failed to download ...")

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

                text_filename.highlight_regex(r"\..*$", "bold red")
                text_filename.stylize(f" link file://{entry['parentReference']['path']}")
                text_filename.append(f" ({decimal(entry['size'])})", "blue")

                icon = "📦 " if entry['name'].rsplit(".")[-1] == "zip" else "📄 "

                tree.add(Text(icon) + text_filename)

        rich.print(tree)
