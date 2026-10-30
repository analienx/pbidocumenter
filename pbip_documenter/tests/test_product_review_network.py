"""Network trust and pagination fault probes for optional inventory connectors."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from pbip_documenter.inventory.jira.client import JiraClient
from pbip_documenter.inventory.powerbi.client import PowerBIClient


class Response:
    status_code = 200
    headers: dict[str, str] = {}

    def __init__(self, payload: object) -> None:
        self.payload = payload

    def json(self) -> object:
        return self.payload


@pytest.mark.parametrize(
    "malicious_link",
    [
        "https://attacker.example/exfil",
        "http://api.powerbi.com/v1.0/myorg/admin/reports",
        "https://api.powerbi.com.evil.test/v1.0/myorg/admin/reports",
        "https://api.powerbi.com@attacker.example/v1.0/myorg/admin/reports",
        "https://api.powerbi.com/v1.0/myorg/other",
    ],
)
def test_powerbi_blocks_untrusted_continuation_without_leaking_bearer_token(
    monkeypatch: pytest.MonkeyPatch, malicious_link: str
) -> None:
    auth = Mock()
    auth.get_token.return_value = "never-forward-this-bearer-token"
    client = PowerBIClient(auth)
    get = Mock(return_value=Response({"value": [{"id": "first"}], "@odata.nextLink": malicious_link}))
    monkeypatch.setattr("pbip_documenter.inventory.powerbi.client.requests.get", get)
    with pytest.raises(ValueError, match="Untrusted Power BI continuation"):
        client.get_reports()
    get.assert_called_once()
    assert get.call_args.args[0] == "https://api.powerbi.com/v1.0/myorg/admin/reports"


def test_powerbi_valid_continuation_and_list_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    auth = Mock()
    auth.get_token.return_value = "test-token"
    client = PowerBIClient(auth)
    pages = iter([
        Response({"value": [{"id": "first"}], "@odata.nextLink": "https://api.powerbi.com/v1.0/myorg/admin/reports?$skip=1"}),
        Response([{"id": "second"}]),
    ])
    get = Mock(side_effect=lambda *_a, **_kw: next(pages))
    monkeypatch.setattr("pbip_documenter.inventory.powerbi.client.requests.get", get)
    assert client.get_reports() == [{"id": "first"}, {"id": "second"}]
    assert get.call_count == 2


def test_powerbi_repeated_continuation_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    auth = Mock()
    auth.get_token.return_value = "test-token"
    client = PowerBIClient(auth)
    url = "https://api.powerbi.com/v1.0/myorg/admin/reports?$skip=1"
    get = Mock(return_value=Response({"value": [], "@odata.nextLink": url}))
    monkeypatch.setattr("pbip_documenter.inventory.powerbi.client.requests.get", get)
    with pytest.raises(ValueError, match="repeated"):
        client.get_reports()
    assert get.call_count == 2


def test_jira_repeated_pagination_token_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    auth = Mock()
    auth.base_url = "https://jira.example.test"
    auth.get_auth_tuple.return_value = ("a@example.test", "token")
    client = JiraClient(auth)
    get = Mock(return_value=Response({"issues": [{"key": "TEST-1"}], "nextPageToken": "unchanged"}))
    monkeypatch.setattr("pbip_documenter.inventory.jira.client.requests.get", get)
    with pytest.raises(ValueError, match="repeated nextPageToken"):
        client.search_issues()
    assert get.call_count == 2
