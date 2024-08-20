import os
import asyncio
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

from azure.identity import DeviceCodeCredential
from msgraph import GraphServiceClient


class GraphQuery:
    def __init__(self):

        logger.get_logger().setLevel("DEBUG")
        self.config_file = "/".join((str(pathlib.Path(__file__).parent.resolve()), ".graph/config.cfg"))

        logger.debug(f"{self.config_file}")

        if not pathlib.Path(self.config_file).exists():
            print("Missing configuration file.")
            self.config_file = None

        self.drive = None
        self.response = None
        self.device_code_credential = None
        self.user_client = None

        self.config = configparser.ConfigParser()
        self.config.read(self.config_file)

        self.hostname = self.config.get("graph", "hostname")
        self.version = self.config.get("graph", "version")
        self.app_token = self.config.get("graph", "app_token")

        if os.getenv("APP_TOKEN"):
            # Could add some verification that the token is correct here
            self.app_token = os.getenv("APP_TOKEN")
            logger.debug(f"Using env token: {self.app_token}")

        if self.app_token == "None":
            logger.info("Attempting to get credentials ...")
            self.app_token = asyncio.run(self.get_app_token(write=True))

        else:
            self.authenticate()

        self.header = {
            "Host": "graph.microsoft.com",
            "Authorization": f"Bearer {self.app_token}",
            "Content-Type": "application/json"
        }

    def authenticate(self):
        # Send a simple request and check response to validate the current app token

        url = f"https://graph.microsoft.com/v1.0/me"

        self.response = requests.get(
            url=url,
            headers={
                "Host": "graph.microsoft.com",
                "Authorization": f"Bearer {self.app_token}",
                "Content-Type": "application/json"
            }
        )

        if self.response.status_code == 401:
            if self.response.json()["error"]["code"] == "InvalidAuthenticationToken":
                logger.warning("App token is invalid or expired, refreshing...")
                self.app_token = asyncio.run(self.get_app_token(write=True))

            else:
                logger.warning("Something went wrong while authentication...")

        return self.response

    async def get_app_token(self, write=False):
        from vipertools.security.encryption import write_token

        client_id = self.config.get("azure", "client_id")
        tenant_id = self.config.get("azure", "tenant_id")
        graph_scopes = self.config.get("azure", "scopes").split(" ")

        self.device_code_credential = DeviceCodeCredential(client_id, tenant_id=tenant_id)
        self.user_client = GraphServiceClient(self.device_code_credential, graph_scopes)

        graph_scopes = self.config.get("azure", "scopes")
        access_token = self.device_code_credential.get_token(graph_scopes)
        if write:
            write_token(file=self.config_file, app_token=access_token.token)

        return access_token.token

    def listdir(self, path: str = "/") -> None:
        if path == "/":
            # Root directory requires a different call - <sarcasim> this makes perfect sense.</sarcasim>
            url = f"https://{self.hostname}/{self.version}/me/drive/root/children"

        else:
            url = f"https://{self.hostname}/{self.version}/me/drive/root:/{path}:/children"

        logger.debug(url)
        self.response = requests.get(
            url=url,
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
