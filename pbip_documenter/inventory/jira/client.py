"""Jira API client with retry and pagination handling."""

import base64
import logging
import time
import typing
from typing import Any

import requests

logger = logging.getLogger(__name__)


class JiraClient:
    """Client for Jira REST API with retry and pagination support."""

    MAX_RETRIES = 3
    BACKOFF_BASE_SECONDS = 2
    DEFAULT_PAGE_SIZE = 100

    def __init__(
        self: typing.Any,
        auth: typing.Any,
        page_size: int = DEFAULT_PAGE_SIZE,
        project_key: str = "<JIRA_PROJECT_KEY>",
    ) -> None:
        self.auth = auth
        self.page_size = page_size
        self.project_key = project_key

    def _get_headers(self: typing.Any) -> typing.Any:
        """Get request headers with authorization."""
        email, token = self.auth.get_auth_tuple()
        credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
        return {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _handle_throttle(self: typing.Any, response: requests.Response, attempt: int) -> typing.Any:
        """
        Handle throttling by checking for 429 status.
        Returns True if should retry.
        """
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", self.BACKOFF_BASE_SECONDS * (2**attempt)))
            logger.warning(f"Throttled (429). Waiting {retry_after}s before retry {attempt + 1}")
            time.sleep(retry_after)
            return True
        return False

    def _handle_error(self: typing.Any, response: requests.Response, attempt: int) -> typing.Any:
        """
        Handle other errors with exponential backoff.
        Returns True if should retry.
        """
        if response.status_code >= 500:
            backoff = self.BACKOFF_BASE_SECONDS * (2**attempt)
            logger.warning(f"Server error {response.status_code}. Waiting {backoff}s before retry {attempt + 1}")
            time.sleep(backoff)
            return True
        return False

    def _make_request(
        self: typing.Any,
        url: str,
        params: dict[str, Any] | None = None,
        attempt: int = 0,
    ) -> typing.Any:
        """Make HTTP request with retry logic."""
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params or {},
                timeout=120,
            )
        except requests.exceptions.RequestException as e:
            if attempt < self.MAX_RETRIES - 1:
                backoff = self.BACKOFF_BASE_SECONDS * (2**attempt)
                logger.warning(f"Request failed: {e}. Retrying in {backoff}s...")
                time.sleep(backoff)
                return self._make_request(url, params, attempt + 1)
            raise

        if response.status_code == 200:
            return response

        if self._handle_throttle(response, attempt) or self._handle_error(response, attempt):
            if attempt < self.MAX_RETRIES - 1:
                return self._make_request(url, params, attempt + 1)

        response.raise_for_status()
        return response

    def search_issues(
        self: typing.Any,
        jql: str | None = None,
        fields: list[str] | None = None,
        expand: list[str] | None = None,
    ) -> typing.Any:
        """
        Search issues using JQL with nextPageToken pagination.

        Args:
            jql: JQL query string. Defaults to project filter.
            fields: List of fields to return. None returns all.
            expand: List of entities to expand.

        Returns:
            List of issue dictionaries.
        """
        if jql is None:
            jql = f"project = {self.project_key}"

        logger.info(f"Searching Jira issues with JQL: {jql}")

        url = f"{self.auth.base_url}/rest/api/3/search/jql"
        results: list[typing.Any] = []
        next_page_token: str | None = None
        page = 0

        while True:
            params: dict[str, Any] = {
                "jql": jql,
                "maxResults": self.page_size,
            }

            if fields:
                params["fields"] = ",".join(fields)

            if expand:
                params["expand"] = ",".join(expand)

            if next_page_token:
                params["nextPageToken"] = next_page_token

            logger.debug(f"Fetching page {page} from Jira search")
            response = self._make_request(url, params)
            data = response.json()

            issues = data.get("issues", [])
            results.extend(issues)
            logger.debug(f"Retrieved {len(issues)} issues, total: {len(results)}")

            # Check for next page
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break

            page += 1

        logger.info(f"Completed pagination: {len(results)} total issues from Jira")
        return results

    def get_issue(self: typing.Any, issue_key: str, fields: list[str] | None = None) -> typing.Any:
        """Get a single issue by key."""
        url = f"{self.auth.base_url}/rest/api/3/issue/{issue_key}"
        params: dict[str, Any] = {}

        if fields:
            params["fields"] = ",".join(fields)

        response = self._make_request(url, params)
        return response.json()
