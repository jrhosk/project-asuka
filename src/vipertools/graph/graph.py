import os
import rich
import asyncio
import requests
import pathlib
import configparser

from graphviper.utils import logger
from vipertools.graph import codes as status_code
from vipertools.graph import handler

from azure.identity import DeviceCodeCredential

from msgraph import GraphServiceClient


class GraphQuery:
    def __init__(self, verbose: bool = False):

        self.drive = None
        self.response = None
        self.device_code_credential = None
        self.user_client = None
        self.client_id = None
        self.verbose = verbose

        if verbose:
            logger.get_logger().setLevel("DEBUG")

        self.config_file = "/".join((str(pathlib.Path(__file__).parent.resolve()), ".graph/config.cfg"))

        logger.debug(f"{self.config_file}")

        # Verify that the configuration file exists
        if not pathlib.Path(self.config_file).exists():
            logger.error("Missing configuration file, instantiation failed...")
            self.config_file = None
            return

        self.config = configparser.ConfigParser()
        self.config.read(self.config_file)

        self.hostname = self.config["graph"]["hostname"]
        self.version = self.config["graph"]["version"]
        self.app_token = self.config["graph"]["app_token"]

        # If client-id doesn't exist yet, retrieve it from NRAO
        if self.config["azure"]["client_id"] == "None":
            from vipertools.security import encryption
            logger.info("Azure client-id not found, retrieving ...")
            self.client_id = encryption.get_credentials(persistent=True)

        # Does the app-token exist in the environment
        if os.getenv("APP_TOKEN"):
            # Could add some verification that the token is correct here
            self.app_token = os.getenv("APP_TOKEN")
            logger.debug(f"Using app-token from environment...")

        # If app-token is not defined in configuration file, get it from msgraph
        if self.app_token == "None":
            logger.info("Configuration file has no app-token, attempting to get credentials from server...")
            self.app_token = asyncio.run(self.get_app_token(write=True))

        # Authenticate app-token that you have
        else:
            logger.debug("Authenticating app-token with server ...")
            self.authenticate()

        self.header = {
            "Host": f"{self.hostname}",
            "Authorization": f"Bearer {self.app_token}",
            "Content-Type": "application/json"
        }

    def info(self):
        """
        Simple convenience wrapper to display object info
        Returns
        -------

        """

        rich.inspect(self.__class__, methods=True, all=False, private=False)

    def authenticate(self) -> requests.Response:
        """
        Authenticate with app-token and refresh is expired.
        Returns requests.Response
        -------

        """
        url = f"https://graph.microsoft.com/v1.0/me"

        # Send a simple request and check response to validate the current app token
        self.response = requests.get(
            url=url,
            headers={
                "Host": f"{self.hostname}",
                "Authorization": f"Bearer {self.app_token}",
                "Content-Type": "application/json"
            }
        )

        # Find a more robust way to do this
        if self.response.status_code != status_code.OK:
            if self.response.json()["error"]["code"] == "InvalidAuthenticationToken":
                logger.warning("App token is invalid or expired, refreshing...")
                self.app_token = asyncio.run(self.get_app_token(write=True))

            else:
                handler.error(self.response, table=self.verbose)

        return self.response

    async def get_app_token(self, write: bool = False) -> str:
        """
        Retrieve app-token from Azure client and return it. Token can be written to configuration file if requested.
        In addition, the Azure client-id is checked as well.
        Parameters
        ----------
        write: bool (default False) to write to configuration file

        Returns str
        -------

        """
        from vipertools.security.encryption import write_to_config

        tenant_id = self.config["azure"]["tenant_id"]
        scopes = self.config["azure"]["scopes"]

        self.client_id = self.config["azure"]["client_id"]

        if self.client_id == "None":
            from vipertools.security import encryption
            logger.info("Azure client-id not found, retrieving ...")
            self.client_id = encryption.get_credentials(persistent=True)

        self.device_code_credential = DeviceCodeCredential(client_id=self.client_id, tenant_id=tenant_id)
        self.user_client = GraphServiceClient(self.device_code_credential, scopes.split(" "))

        access_token = self.device_code_credential.get_token(scopes)

        if write:
            write_to_config(
                file=self.config_file,
                credential="graph.app_token",
                value=access_token.token
            )

        return access_token.token

    def build_download_request(self, item_id: int) -> tuple[str, dict[str, str]]:
        """

        Parameters
        ----------
        item_id: int
            Onedrive specific id associated with file.

        Returns tuple[str, dict[str, str]]
        -------
            url and minimal header required for download request.

        """
        # Build the download request url
        url = f"https://{self.hostname}/{self.version}/me/drive/items/{item_id}/content"

        headers = {
            "Authorization": f"Bearer {self.app_token}"
        }

        return url, headers

    def build_link_request(
            self,
            item_id: int,
            permissions: str = "view",
            scope: str = "anonymous") -> tuple[str, dict[str, str], dict[str, str]]:
        """

        Parameters
        ----------
        item_id: int
            Onedrive specific id associated with file.
        permissions: str
            One of "view", "edit" or "embed".
        scope: str
            The scope of the created link. "anonymous", "organization" or "users"

        Returns tuple[str, dict[str, str], dict[str, str]]
        -------
            url, body and minimal header required for download request.

        """
        url = f"https://{self.hostname}/{self.version}/me/drive/items/{item_id}/createLink"

        body = {
            "type": f"{permissions}",
            "scope": f"{scope}"
        }
        return url, body, self.header

    def build_upload_request(
            self, item_id: int = None,
            path: str = None,
            filename: str = "",
            mode:str = "update"
    ) -> tuple[str, dict[str, str]]:
        """

        Parameters
        ----------
        path: str
            The path of the file to be uploaded.
        mode: str
            Mode with which to upload file.
        item_id: int
            Onedrive specific id associated with file.
        filename: str
            The name of the file to be uploaded.

        Returns tuple[str, dict[str, str]]
        -------
            url and minimal header required for upload request.
        """
        import mimetypes

        mimetypes.add_type("application/x-binary", ".npy")
        mimetypes.add_type("application/x-binary", ".npz")

        if (item_id is None) and (mode == "update"):
            logger.error("Must specify item_id when running in update mode")

        if (path is None) and (mode == "create"):
            logger.error("Must specify path when running in create mode")

        file_type = mimetypes.guess_type(filename)[0] if mimetypes.guess_type(filename)[0] else "application/octet-stream"

        if mode == "create":
            url = f"https://{self.hostname}/{self.version}/me/drive/root:/{path}/{filename}:/content"

        else:
            url = f"https://{self.hostname}/{self.version}/me/drive/items/{item_id}/content"

        header = {
            "Authorization": f"Bearer {self.app_token}",
            "Content-Type": f"application/{file_type}"
        }

        return url, header


