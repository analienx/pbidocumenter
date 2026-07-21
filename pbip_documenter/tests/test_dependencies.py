"""Tests for dependency-safe application startup."""

import os
import subprocess
import sys
import typing
from unittest.mock import patch

import pytest

from pbip_documenter.dependencies import (
    Dependency,
    DependencyInstallationError,
    _module_available,
    check_dependencies,
    startup_profiles,
)


def test_startup_profiles_default_to_core() -> typing.Any:
    assert startup_profiles({}) == ("core",)


def test_frozen_application_stays_local_only() -> typing.Any:
    with patch.object(sys, "frozen", True, create=True):
        assert startup_profiles({"PBIP_DOCUMENTER_LOCAL_ONLY": "0"}) == ("core",)


@pytest.mark.parametrize("value", ["0", "false", "False", "no"])
def test_startup_profiles_include_explicit_augmentation(value: str) -> typing.Any:
    assert startup_profiles({"PBIP_DOCUMENTER_LOCAL_ONLY": value}) == ("core", "augmentation")


def test_nested_missing_module_is_reported_as_unavailable() -> typing.Any:
    with patch("pbip_documenter.dependencies.importlib.util.find_spec", side_effect=ModuleNotFoundError):
        assert _module_available("missing_parent.child") is False


def test_check_dependencies_installs_and_rechecks_missing_packages() -> typing.Any:
    missing: list[typing.Any] = [Dependency("docx", "python-docx>=1.0.0")]
    with (
        patch("pbip_documenter.dependencies._missing_dependencies", side_effect=[missing, []]),
        patch("pbip_documenter.dependencies.subprocess.check_call") as install,
        patch.dict(os.environ, {"PBIP_DOCUMENTER_AUTO_INSTALL": "1"}),
    ):
        check_dependencies(("core",))

    install.assert_called_once_with([sys.executable, "-m", "pip", "install", "python-docx>=1.0.0"])


def test_check_dependencies_explains_disabled_auto_install() -> typing.Any:
    missing: list[typing.Any] = [Dependency("docx", "python-docx>=1.0.0")]
    with (
        patch("pbip_documenter.dependencies._missing_dependencies", return_value=missing),
        patch.dict(os.environ, {"PBIP_DOCUMENTER_AUTO_INSTALL": "0"}),
        pytest.raises(DependencyInstallationError, match="Automatic dependency installation is disabled"),
    ):
        check_dependencies(("core",))


def test_check_dependencies_detects_unsuccessful_post_install_import() -> typing.Any:
    missing: list[typing.Any] = [Dependency("docx", "python-docx>=1.0.0")]
    with (
        patch("pbip_documenter.dependencies._missing_dependencies", side_effect=[missing, missing]),
        patch("pbip_documenter.dependencies.subprocess.check_call"),
        patch.dict(os.environ, {"PBIP_DOCUMENTER_AUTO_INSTALL": "1"}),
        pytest.raises(DependencyInstallationError, match="still unavailable"),
    ):
        check_dependencies(("core",))


def test_package_and_cli_import_do_not_eagerly_import_pandas() -> typing.Any:
    command: list[typing.Any] = [
        sys.executable,
        "-c",
        "import sys; import pbip_documenter; import pbip_documenter.cli; assert 'pandas' not in sys.modules",
    ]
    result = subprocess.run(command, cwd=os.getcwd(), capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
