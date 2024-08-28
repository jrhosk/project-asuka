import json
import rich
import requests
import pathlib

from requests import Response
from rich.filesize import decimal
from rich.markup import escape
from rich.text import Text
from rich.tree import Tree

from vipertools.graph import codes as status_code
from vipertools.graph import GraphQuery
from vipertools.graph import handler

from graphviper.utils import logger
from graphviper.utils import parameter

from rich.console import Console

console = Console()


class DriveTool:
    __slots__ = ["graph", "response", "verbose"]

    def __init__(self, verbose: bool = False):
        self.graph = GraphQuery(verbose=verbose)
        self.response = None
        self.verbose = verbose

    def __repr__(self):
        return f"DriveTool(verbose={self.verbose})"

    def __str__(self, *args, **kwargs):
        return self.__repr__()

    def info(self):
        """
        Simple convenience wrapper to display object info
        Returns
        -------

        """

        rich.inspect(self.__class__, methods=True, all=False, private=False, dunder=False)

    #@parameter.validate(config_dir='ENV:TOOLS_CONFIG_PATH')
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

    #@parameter.validate(config_dir='ENV:TOOLS_CONFIG_PATH')
    def generate_manifest(self, path: str = "/", version: str = None, destination: str = None) -> None:
        """
        Generate a manifest file from files in NRAO one drive.
        Parameters
        ----------
        destination: str (defaults None)
            Destination path to generate manifest.

        version: str (defaults None)
                Version of newly generated manifest for.

        path: str, (default /)
            The remote path to generate the manifest file from.

        Returns
        -------
        None
        """

        sharepoint_url = "https://nrao-my.sharepoint.com/"

        # destination becomes current directory is not specified
        if destination is None:
            logger.debug("File destination not defined, writing to current working directory ...")
            destination = str(pathlib.Path())

        # Create the directory if it doesn't exist.
        if not pathlib.Path(destination).exists():
            logger.debug(f"Creating manifest directory: {str(pathlib.Path(destination).resolve())} ...")
            pathlib.Path(destination).resolve().mkdir(parents=True, exist_ok=True)

        manifest_path = pathlib.Path(destination).resolve().joinpath("file.download.json")
        if not manifest_path.exists():
            logger.debug(f"Creating new manifest file form template ...")
            manifest_path = _create_manifest(str(manifest_path.parent))

        logger.info(f"Generating manifest for {str(manifest_path)}")

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

            path = _format_path(path=path)
            # Query the graph to get the dpath information
            self.get_path(path)

            file_list = self.response.json()["value"]

            with console.status("[bold green] Building manifest...") as status:
                for entry in file_list:
                    url, body, header = self.graph.build_link_request(item_id=entry["id"])

                    self.response = requests.post(
                        url=url,
                        json=body,
                        headers=header
                    )

                    key_name = entry["name"].rsplit(".zip")[0]
                    link_id = self.response.json()['link']['webUrl'].split(sharepoint_url)[1]
                    console.print(f"[blue]processing[/]: {key_name} ...")

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

            json.dump(_manifest, file, indent=4, sort_keys=True)
            file.truncate()

    #@parameter.validate(config_dir='ENV:TOOLS_CONFIG_PATH')
    def download(self, path: str, filename: str) -> Response | int:
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
            handler.error(response, table=self.verbose)
            return response

        # Build the download request url
        url, header = self.graph.build_download_request(item_id=item_id)

        response = requests.get(
            url=url,
            headers=header
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

            return response.status_code

        else:
            handler.error(response, table=self.verbose)

    #@parameter.validate(config_dir='ENV:TOOLS_CONFIG_PATH')
    def upload(self, filename: str, path: str) -> requests.Response:
        """
        Upload a file on onedrive given a file path.
        Parameters
        ----------
        filename: str local filename of file to be uploaded.
        path: str  onedrive path where file exists.

        Returns
        -------

        """

        item_id = None

        logger.info(f"Uploading {filename} to {path}...")

        path = _format_path(path=path)

        # Get the path information
        response = self.get_path(path)

        # Find the item-id needed to download the file
        if response.status_code == status_code.OK:
            for entry in response.json()["value"]:
                if entry["name"] == filename:
                    item_id = entry["id"]
                    break

            # Need to separate the filename from the full file path before sending the request else we end up
            # uploading the full directory structure.
            name = pathlib.Path(filename).name

            # If the item_id is not set, the file doesn't exist in the remote directory; create it.
            if item_id is None:
                logger.info(f"{filename} not found, creating new remote file ...")
                return self.upload_new_file(filename=name, path=path)

            with open(f"{filename}", "rb") as file:
                data = file.read()

            # Build the upload request url
            url, header = self.graph.build_upload_request(item_id=item_id, filename=name, mode="update")

            with console.status("[bold green] Uploading file...") as status:
                response = requests.put(
                    url=url,
                    headers=header,
                    data=data
                )

            if response.status_code == status_code.OK:
                logger.info(f"Uploaded {filename} to {path}")
                return response

            else:
                handler.error(response, table=self.verbose)
                return response

        else:
            handler.error(response)
            return response

    def upload_new_file(self, filename: str, path: str) -> requests.Response:
        """
        Upload a new file on onedrive given a file path.
        Parameters
        ----------

        filename: str local filename of file to be uploaded.
        path: str  onedrive path where file exists.

        Returns
        -------

        """

        with open(f"{filename}", "rb") as file:
            data = file.read()

        # Build the upload request url
        url, header = self.graph.build_upload_request(filename=filename, path=path, mode="create")

        with console.status("[bold green] Uploading file...") as status:
            response = requests.put(
                url=url,
                headers=header,
                data=data
            )

        if response.status_code == response.status_code == status_code.CREATED:
            logger.info(f"Uploaded {filename} to {path}")
            return response

        else:
            handler.error(response, table=self.verbose)
            return response

    #@parameter.validate(config_dir='ENV:TOOLS_CONFIG_PATH')
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
        path = _format_path(path)

        response = self.get_path(path)

        # Check that folder exists
        if response.status_code == status_code.OK:
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

        else:
            handler.error(response, table=self.verbose)


def _format_path(path: str) -> str:
    """
    Format a remote path. The path that is sent to the remote query is picky about how the path is formatted so
    beginning and trailing slashes must be trimmed.

    Parameters
    ----------
    path: str
        Remote path to format.

    Returns str
    -------
        Trimmed path
    """

    if path == "/":
        return path

    if path.startswith("/"):
        path = path[1:]

    if path.endswith("/"):
        path = path[:-1]

    return path


def _create_manifest(path: str) -> str:
    manifest = {
        "version": "",
        "metadata": {

        }
    }
    manifest_path = pathlib.Path(path).joinpath("file.download.json")
    with open(manifest_path, "w") as file:
        json.dump(manifest, file, indent=4)

    return str(manifest_path)
