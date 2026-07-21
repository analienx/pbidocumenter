"""Power BI authentication using Azure Key Vault and MSAL."""

import logging
import typing

import msal
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)


class PowerBIAuth:
    """Handles Power BI authentication via service principal + Key Vault."""

    AUTHORITY_BASE = "https://login.microsoftonline.com/"
    POWER_BI_RESOURCE = "https://analysis.windows.net/powerbi/api"

    def __init__(
        self: typing.Any,
        key_vault_url: str,
        tenant_id: str,
        client_id: str,
        secret_name: str,
    ) -> None:
        self.key_vault_url = key_vault_url
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.secret_name = secret_name
        self._token: str | None = None
        self._app: msal.ConfidentialClientApplication | None = None
        self._kv_client: SecretClient | None = None

    @property
    def authority(self: typing.Any) -> typing.Any:
        return f"{self.AUTHORITY_BASE}{self.tenant_id}"

    def _get_key_vault_client(self: typing.Any) -> typing.Any:
        """Get or create Key Vault client."""
        if self._kv_client is None:
            credential = DefaultAzureCredential()
            self._kv_client = SecretClient(
                vault_url=self.key_vault_url,
                credential=credential,
            )
        return self._kv_client

    def _get_client_secret(self: typing.Any) -> typing.Any:
        """Retrieve client secret from Key Vault."""
        client = self._get_key_vault_client()
        secret = client.get_secret(self.secret_name)
        logger.info(f"Retrieved secret '{self.secret_name}' from Key Vault")
        return secret.value

    def _get_app(self: typing.Any) -> typing.Any:
        """Get or create MSAL confidential client application."""
        if self._app is None:
            client_secret = self._get_client_secret()
            self._app = msal.ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=client_secret,
                authority=self.authority,
            )
        return self._app

    def acquire_token(self: typing.Any) -> typing.Any:
        """Acquire access token for Power BI API."""
        app = self._get_app()

        # Try to get token from cache first
        result = app.acquire_token_silent(
            scopes=[f"{self.POWER_BI_RESOURCE}/.default"],
            account=None,
        )

        if result and "access_token" in result:
            logger.debug("Acquired token from cache")
            self._token = result["access_token"]
            return self._token

        # Acquire new token
        logger.info("Acquiring new token from AAD")
        result = app.acquire_token_for_client(
            scopes=[f"{self.POWER_BI_RESOURCE}/.default"],
        )

        if "access_token" not in result:
            error = result.get("error_description", "Unknown error")
            raise RuntimeError(f"Failed to acquire token: {error}")

        self._token = result["access_token"]
        logger.info("Successfully acquired new token")
        return self._token

    def get_token(self: typing.Any) -> typing.Any:
        """Get valid token, acquiring if necessary."""
        if self._token is None:
            return self.acquire_token()
        return self._token
