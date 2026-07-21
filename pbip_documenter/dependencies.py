"""Dependency detection and first-run installation helpers."""

from __future__ import annotations

import importlib
import importlib.util
import os
import subprocess
import sys
import typing
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Dependency:
    """A Python import and the package specification that provides it."""

    import_name: str
    package: str


DEPENDENCY_PROFILES: Mapping[str, tuple[Dependency, ...]] = {
    "core": (
        Dependency("docx", "python-docx>=1.0.0"),
        Dependency("lxml", "lxml>=4.9.0"),
    ),
    "augmentation": (
        Dependency("pandas", "pandas>=1.5.0"),
        Dependency("pyarrow", "pyarrow>=12.0.0"),
    ),
    "inventory": (
        Dependency("requests", "requests>=2.28.0"),
        Dependency("msal", "msal>=1.20.0"),
        Dependency("azure.identity", "azure-identity>=1.15.0"),
        Dependency("azure.keyvault.secrets", "azure-keyvault-secrets>=4.7.0"),
    ),
}


class DependencyInstallationError(RuntimeError):
    """Raised when required packages cannot be installed or imported."""


def augmentation_enabled(environ: Mapping[str, str] | None = None) -> typing.Any:
    """Return whether cache-backed augmentation is explicitly enabled."""
    if getattr(sys, "frozen", False):
        return False
    values = os.environ if environ is None else environ
    return values.get("PBIP_DOCUMENTER_LOCAL_ONLY", "1").lower() in {"0", "false", "no"}


def startup_profiles(environ: Mapping[str, str] | None = None) -> typing.Any:
    """Select dependency profiles needed for normal document generation."""
    profiles: list[typing.Any] = ["core"]
    if augmentation_enabled(environ):
        profiles.append("augmentation")
    return tuple(profiles)


def _dependencies_for(profiles: Iterable[str]) -> typing.Any:
    dependencies: list[Dependency] = []
    seen: set[str] = set()
    for profile in profiles:
        try:
            selected = DEPENDENCY_PROFILES[profile]
        except KeyError as exc:
            raise ValueError(f"Unknown dependency profile: {profile}") from exc
        for dependency in selected:
            if dependency.import_name not in seen:
                dependencies.append(dependency)
                seen.add(dependency.import_name)
    return tuple(dependencies)


def _module_available(import_name: str) -> typing.Any:
    try:
        return importlib.util.find_spec(import_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _missing_dependencies(dependencies: Iterable[Dependency]) -> typing.Any:
    return [dependency for dependency in dependencies if not _module_available(dependency.import_name)]


def _manual_command(missing: Sequence[Dependency]) -> typing.Any:
    packages = " ".join(f'"{dependency.package}"' for dependency in missing)
    return f'"{sys.executable}" -m pip install {packages}'


def check_dependencies(profiles: Iterable[str] = ("core",)) -> typing.Any:
    """Install and verify dependencies for the requested feature profiles.

    Frozen applications must already contain their dependencies and never invoke
    pip. Set ``PBIP_DOCUMENTER_AUTO_INSTALL=0`` to disable automatic changes to
    the active Python environment.
    """
    if getattr(sys, "frozen", False):
        return

    selected_profiles = tuple(profiles)
    dependencies = _dependencies_for(selected_profiles)
    missing = _missing_dependencies(dependencies)
    if not missing:
        return

    print(f"[deps] Python: {sys.executable} ({sys.version.split()[0]})")
    print(f"[deps] Profiles: {', '.join(selected_profiles)}")
    print(f"[deps] Missing packages: {', '.join(dependency.package for dependency in missing)}")

    auto_install = os.environ.get("PBIP_DOCUMENTER_AUTO_INSTALL", "1").lower() not in {"0", "false", "no"}
    if not auto_install:
        raise DependencyInstallationError(
            "Automatic dependency installation is disabled. Run:\n  " + _manual_command(missing)
        )

    command: list[typing.Any] = [
        sys.executable,
        "-m",
        "pip",
        "install",
        *(dependency.package for dependency in missing),
    ]
    print(f"[deps] Installing with: {_manual_command(missing)}")
    try:
        subprocess.check_call(command)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise DependencyInstallationError(
            "Dependency installation failed. Check network access and environment permissions, then run:\n  "
            + _manual_command(missing)
        ) from exc

    importlib.invalidate_caches()
    still_missing = _missing_dependencies(missing)
    if still_missing:
        raise DependencyInstallationError(
            "pip completed, but these imports are still unavailable: "
            + ", ".join(dependency.import_name for dependency in still_missing)
            + ". Ensure pip targets the same interpreter, then run:\n  "
            + _manual_command(still_missing)
        )
    print("[deps] Installation verified.")
