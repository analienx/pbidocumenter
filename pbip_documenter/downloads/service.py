"""Service for downloading files from SharePoint."""

import json
import re
import shutil
import sys
import time
import typing
import webbrowser
from pathlib import Path

from pbip_documenter.downloads.config import DownloadConfig, DownloadTarget


class DownloadService:
    """Handles SharePoint file downloads with automatic detection and caching."""

    def __init__(self: typing.Any, config: DownloadConfig) -> None:
        self.config = config
        self.downloads_dir = self._get_windows_downloads_dir()
        self.cache_dir = config.cache_root / "downloads"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _get_windows_downloads_dir() -> typing.Any:
        """Resolve real Windows Downloads folder, including redirected folders."""
        if sys.platform != "win32":
            raise RuntimeError("SharePoint browser download monitoring requires Windows.")

        # winreg is available only on Windows. Keep the import local so the
        # package and its tests remain importable on Linux/macOS.
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        downloads_guid = "{<UUID_097>}"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            raw, _ = winreg.QueryValueEx(key, downloads_guid)
        return Path(winreg.ExpandEnvironmentStrings(raw))

    @staticmethod
    def _snapshot_files(folder: Path) -> typing.Any:
        """Snapshot current files in folder with size and modification time."""
        snap: dict[typing.Any, typing.Any] = {}
        if not folder.exists():
            return snap

        for p in folder.iterdir():
            if p.is_file():
                try:
                    st = p.stat()
                    snap[p] = (st.st_size, st.st_mtime)
                except FileNotFoundError:
                    pass
        return snap

    @staticmethod
    def _is_partial_file(p: Path) -> typing.Any:
        """Check if file is a partial browser download."""
        name = p.name.lower()
        return name.endswith(".crdownload") or name.endswith(".tmp") or name.endswith(".part")

    def _compile_similar_name_regex(self: typing.Any, prefix: str, suffix: str | None) -> typing.Any:
        """
        Compile regex to match downloaded files.

        Matches:
          ReportInventory_Full.json
          ReportInventory_Full (1).json
          JiraDetails_<JIRA_PROJECT_KEY>.xlsx
          JiraDetails_<JIRA_PROJECT_KEY> (2).xlsx
          JiraDetails_<JIRA_PROJECT_KEY> (if suffix=None and file has no extension)
        """
        pfx = re.escape(prefix)
        if suffix:
            sfx = re.escape(suffix)
            pattern = rf"^{pfx}( \(\d+\))?{sfx}$"
        else:
            # any extension or none
            pattern = rf"^{pfx}( \(\d+\))?(\.[^.]+)?$"
        return re.compile(pattern, re.IGNORECASE)

    def _looks_like_target_file(self: typing.Any, p: Path, prefix: str, suffix: str | None) -> typing.Any:
        """Check if file matches the expected download pattern."""
        if self._is_partial_file(p):
            return False

        rx = self._compile_similar_name_regex(prefix, suffix)
        return bool(rx.match(p.name))

    def _pick_best_candidate(
        self: typing.Any,
        folder: Path,
        before: dict[Path, tuple[int, float]],
        prefix: str,
        suffix: str | None,
    ) -> typing.Any:
        """Pick the best candidate from newly downloaded files."""
        candidates: list[typing.Any] = []

        for p in folder.iterdir():
            if not p.is_file():
                continue
            if not self._looks_like_target_file(p, prefix, suffix):
                continue

            try:
                st = p.stat()
            except FileNotFoundError:
                continue

            old = before.get(p)
            changed = old is None or old != (st.st_size, st.st_mtime)
            if changed:
                candidates.append((p, st.st_mtime, st.st_size))

        if not candidates:
            return None

        # newest matching file wins
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def _wait_until_file_stable(
        self: typing.Any,
        p: Path,
        stable_checks: int = 2,
    ) -> typing.Any:
        """Wait until file size and timestamp stop changing."""
        last = None
        stable = 0
        print(f"\nWaiting for file to stabilize: {p.name}")

        while True:
            if not p.exists():
                print(".", end="", flush=True)
                stable = 0
                time.sleep(self.config.poll_seconds)
                continue

            try:
                st = p.stat()
                cur = (st.st_size, st.st_mtime)
            except FileNotFoundError:
                print(".", end="", flush=True)
                stable = 0
                time.sleep(self.config.poll_seconds)
                continue

            if self._is_partial_file(p):
                print(".", end="", flush=True)
                stable = 0
                time.sleep(self.config.poll_seconds)
                continue

            if cur == last and st.st_size > 0:
                stable += 1
                print("✓", end="", flush=True)
                if stable >= stable_checks:
                    print(f"\nFile stable: {st.st_size:,} bytes")
                    return p
            else:
                print(".", end="", flush=True)
                stable = 0
                last = cur

            time.sleep(self.config.poll_seconds)

    def _wait_for_matching_download(
        self: typing.Any,
        folder: Path,
        prefix: str,
        suffix: str | None,
        before_snapshot: dict[Path, tuple[int, float]],
    ) -> typing.Any:
        """Wait for a file matching the pattern to appear and stabilize."""
        deadline = time.time() + self.config.timeout_seconds
        start_time = time.time()
        print(f"\nWaiting for download to appear (timeout: {self.config.timeout_seconds}s)...")

        while time.time() < deadline:
            elapsed = int(time.time() - start_time)
            remaining = self.config.timeout_seconds - elapsed
            print(f"\rScanning... ({elapsed}s elapsed, {remaining}s remaining)", end="", flush=True)

            hit = self._pick_best_candidate(folder, before_snapshot, prefix, suffix)
            if hit:
                print(f"\n✓ Detected file: {hit.name}")
                return self._wait_until_file_stable(hit, stable_checks=2)
            time.sleep(self.config.poll_seconds)

        print()  # newline after progress
        raise TimeoutError(
            f"Did not detect downloaded file with prefix '{prefix}' in '{folder}' "
            f"within {self.config.timeout_seconds}s."
        )

    @staticmethod
    def _open_download_in_browser(download_url: str) -> typing.Any:
        """Open download URL in browser."""
        webbrowser.open(download_url, new=2)

    def _cache_file(self: typing.Any, src: Path, cache_name: str) -> typing.Any:
        """Copy downloaded file to cache directory."""
        # preserve detected extension unless cache_name already has one
        cache_path = self.cache_dir / cache_name
        if cache_path.suffix == "":
            cache_path = cache_path.with_suffix(src.suffix)

        shutil.copy2(src, cache_path)
        return cache_path

    def download_target(self: typing.Any, target: DownloadTarget) -> typing.Any:
        """Download a single target file."""
        print(f"\n{'=' * 60}")
        print(f"Downloading: {target.name}")
        print(f"{'=' * 60}")
        print(f"Watching folder: {self.downloads_dir}")
        print(f"Matching prefix: {target.prefix}")
        print(f"Matching suffix: {target.suffix or '<any>'}")
        print("Opening browser...")

        before = self._snapshot_files(self.downloads_dir)

        download_url = self.config.build_download_url(target.file_id)
        self._open_download_in_browser(download_url)

        downloaded = self._wait_for_matching_download(
            folder=self.downloads_dir,
            prefix=target.prefix,
            suffix=target.suffix,
            before_snapshot=before,
        )

        print("\nCaching file...")
        cached = self._cache_file(downloaded, target.cache_name)

        print("\n✓ Download complete")
        print(f"  Downloaded: {downloaded}")
        print(f"  Cached to:  {cached}")

        return {
            "name": target.name,
            "downloaded": str(downloaded),
            "cached": str(cached),
        }

    def download_all_targets(self: typing.Any) -> typing.Any:
        """
        Download all configured targets sequentially.

        Sequential is intentional:
        - first download triggers browser sign-in if needed
        - second download reuses the same browser/SharePoint session
        """
        results: dict[typing.Any, typing.Any] = {}
        targets = self.config.get_targets()

        print(f"\n{'#' * 60}")
        print(f"Starting download batch: {len(targets)} files")
        print(f"{'#' * 60}")

        for i, target in enumerate(targets):
            print(f"\nProgress: [{i + 1}/{len(targets)}]")
            result = self.download_target(target)
            results[target.name] = result

            # tiny pause between downloads so browser/session settles
            if i < len(targets) - 1:
                print("\nPausing 2s before next download...")
                time.sleep(2)

        print(f"\n{'#' * 60}")
        print(f"All downloads complete: {len(results)} files cached")
        print(f"{'#' * 60}")
        return results

    def load_report_inventory_from_cache(self: typing.Any) -> typing.Any:
        """Load report inventory JSON from cache."""
        cache_path = self.cache_dir / self.config.report_inventory_cache_name
        if cache_path.suffix == "":
            cache_path = cache_path.with_suffix(".json")

        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        reports_raw = payload.get("reports", "[]")
        return json.loads(reports_raw) if isinstance(reports_raw, str) else reports_raw
