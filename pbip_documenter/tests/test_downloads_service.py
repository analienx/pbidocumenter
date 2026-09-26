"""Tests for SharePoint download service platform handling."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pbip_documenter.downloads.service import DownloadService


def test_get_windows_downloads_dir_rejects_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-Windows hosts must import the package but reject the Windows-only operation."""
    monkeypatch.setattr(sys, "platform", "linux")

    with pytest.raises(RuntimeError, match="requires Windows"):
        DownloadService._get_windows_downloads_dir()


def test_get_windows_downloads_dir_reads_registry_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows behavior still resolves the redirected Downloads folder through the registry."""

    class _KeyContext:
        def __enter__(self) -> object:
            return object()

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            return None

    open_key = Mock(return_value=_KeyContext())
    query_value = Mock(return_value=(r"%USERPROFILE%\Downloads", 0))
    expand = Mock(return_value=r"C:\Users\tester\Downloads")
    fake_winreg = SimpleNamespace(
        HKEY_CURRENT_USER=object(),
        OpenKey=open_key,
        QueryValueEx=query_value,
        ExpandEnvironmentStrings=expand,
    )

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg)

    result = DownloadService._get_windows_downloads_dir()

    assert result == Path(r"C:\Users\tester\Downloads")
    open_key.assert_called_once_with(
        fake_winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
    )
    query_value.assert_called_once()
    expand.assert_called_once_with(r"%USERPROFILE%\Downloads")
