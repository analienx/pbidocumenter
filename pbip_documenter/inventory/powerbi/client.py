"""Power BI Admin API client with retry and throttling handling."""

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)


@dataclass
class PagingState:
    """Tracks pagination state for API calls."""

    next_link: str | None = None
    has_more: bool = True


class PowerBIClient:
    """Client for Power BI Admin API with retry and throttling support."""

    BASE_URL = "https://api.powerbi.com/v1.0/myorg/admin"
    DEFAULT_PAGE_SIZE = 5000
    MAX_RETRIES = 3
    BACKOFF_BASE_SECONDS = 2

    def __init__(self, auth, page_size: int = DEFAULT_PAGE_SIZE):
        self.auth = auth
        self.page_size = page_size

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authorization."""
        return {
            "Authorization": f"Bearer {self.auth.get_token()}",
            "Content-Type": "application/json",
        }

    def _handle_throttle(self, response: requests.Response, attempt: int) -> bool:
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

    def _handle_error(self, response: requests.Response, attempt: int) -> bool:
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
        self,
        url: str,
        params: dict[str, Any] | None = None,
        attempt: int = 0,
    ) -> requests.Response:
        """Make HTTP request with retry logic."""
        try:
            response = requests.get(url, headers=self._get_headers(), params=params or {}, timeout=120)
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

    def _paginate(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Paginate through API results."""
        results = []
        state = PagingState()

        url = f"{self.BASE_URL}/{endpoint}"
        request_params = params.copy() if params else {}
        if "$top" not in request_params:
            request_params["$top"] = self.page_size

        while state.has_more:
            logger.debug(f"Fetching: {url}")
            response = self._make_request(url, request_params)
            data = response.json()

            # Extract values from response
            batch = data["value"] if "value" in data else data if isinstance(data, list) else [data]

            results.extend(batch)
            logger.debug(f"Retrieved {len(batch)} items, total: {len(results)}")

            # Check for continuation
            state.next_link = data.get("@odata.nextLink")
            if state.next_link:
                url = state.next_link
                request_params = {}  # nextLink contains all params
            else:
                state.has_more = False

        logger.info(f"Completed pagination: {len(results)} total items from {endpoint}")
        return results

    def get_reports(self) -> list[dict[str, Any]]:
        """Get all reports across workspaces (requires Admin rights)."""
        logger.info("Fetching all reports from Power BI")
        return self._paginate("reports")

    def get_groups(self) -> list[dict[str, Any]]:
        """Get all workspaces (groups)."""
        logger.info("Fetching all workspaces from Power BI")
        return self._paginate("groups")

    def get_apps(self) -> list[dict[str, Any]]:
        """Get all apps."""
        logger.info("Fetching all apps from Power BI")
        return self._paginate("apps")

    def get_reports_in_group(self, group_id: str) -> list[dict[str, Any]]:
        """Get reports within a specific workspace (for testing/deep-dive)."""
        logger.info(f"Fetching reports in group {group_id}")
        return self._paginate(f"groups/{group_id}/reports")
