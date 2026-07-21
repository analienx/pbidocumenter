"""Jira authentication using Azure Key Vault."""

import logging
import typing

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)


class JiraAuth:
    """Handles Jira authentication via API token stored in Key Vault."""

    def __init__(
        self: typing.Any,
        key_vault_url: str,
        secret_name: str,
        email: str,
        base_url: str,
    ) -> None:
        self.key_vault_url = key_vault_url
        self.secret_name = secret_name
        self.email = email
        self.base_url = base_url.rstrip("/")
        self._token: str | None = None
        self._kv_client: SecretClient | None = None

    def _get_key_vault_client(self: typing.Any) -> typing.Any:
        """Get or create Key Vault client."""
        if self._kv_client is None:
            credential = DefaultAzureCredential()
            self._kv_client = SecretClient(
                vault_url=self.key_vault_url,
                credential=credential,
            )
        return self._kv_client

    def get_token(self: typing.Any) -> typing.Any:
        """Retrieve API token from Key Vault."""
        if self._token is None:
            client = self._get_key_vault_client()
            secret = client.get_secret(self.secret_name)
            self._token = secret.value
            logger.info(f"Retrieved secret '{self.secret_name}' from Key Vault")
        return self._token

    def get_auth_tuple(self: typing.Any) -> typing.Any:
        """Get (email, token) tuple for HTTP Basic Auth."""
        return (self.email, self.get_token())
