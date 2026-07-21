"""
Command-line interface for the PBI Design Specification generator.

This module provides the main entry point for generating Word documents
from Power BI project (PBIP) files.
"""

import argparse
import os
import re
import sys
import typing
from collections.abc import Sequence
from pathlib import Path

from pbip_documenter.config import VERSION
from pbip_documenter.dependencies import augmentation_enabled
from pbip_documenter.services.document_service import build_doc


def _get_bundle_dir() -> typing.Any:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    if getattr(sys, "frozen", False):
        return Path(sys.argv[0]).resolve().parent
    return Path(__file__).resolve().parent.parent


def _get_exe_dir() -> typing.Any:
    if getattr(sys, "frozen", False):
        return Path(sys.argv[0]).resolve().parent
    return Path(__file__).resolve().parent.parent


BUNDLE_DIR = _get_bundle_dir()
EXE_DIR = _get_exe_dir()


def _print_banner() -> typing.Any:
    ver = VERSION
    banner = rf"""
     ██████╗ ██████╗ ██╗██████╗
     ██╔══██╗██╔══██╗██║██╔══██╗
     ██████╔╝██████╔╝██║██████╔╝
     ██╔═══╝ ██╔══██╗██║██╔═══╝
     ██║     ██████╔╝██║██║
     ╚═╝     ╚═════╝ ╚═╝╚═╝
    Power BI Design Spec Generator  v{ver}
    ───────────── ⚡ ─────────────
"""
    print(banner)


# Import from copiloter (sibling script, or bundled via PyInstaller)
sys.path.insert(0, str(BUNDLE_DIR))

try:
    from copiloter import VERSION as COP_VER
    from copiloter import PbipProject, _resolve_reports_dir, build_project_summary
except ImportError:
    print("ERROR: copiloter.py not found alongside pbip_documenter/")
    sys.exit(1)


def main(argv: Sequence[str] | None = None) -> typing.Any:
    """
    Main entry point for the CLI.

    Parses command-line arguments and processes all PBIP projects
    in the specified reports directory.
    """
    ap = argparse.ArgumentParser(description="Generate PBI Design Spec .docx from PBIP")
    ap.add_argument("reports_dir", nargs="?", default=None, help="Directory containing PBIP project folders")
    ap.add_argument(
        "--mode",
        choices=["default", "full"],
        default="default",
        help="Documentation detail level (default: concise, full: complete)",
    )
    ap.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path (default: Exported Documents/<ProjectName>/ in repo root)",
    )
    ap.add_argument("--logo", type=str, default=None, help="Path to logo image for document header")
    ap.add_argument("--template", "-t", type=str, default=None, help="Path to Word template (.docx)")
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = ap.parse_args(argv)

    # Resolve reports directory
    REPORTS_DIR = _resolve_reports_dir(args.reports_dir)

    # Find template if not specified
    template_path = args.template
    if not template_path:
        for name in [
            "Design Specification Template.docx",
            "Design_Specification_Roman_Template.docx",
            "Design_Specification.docx",
        ]:
            for base in [BUNDLE_DIR, BUNDLE_DIR / "Templates"]:
                candidate = base / name
                if candidate.is_file():
                    template_path = str(candidate)
                    break
            if template_path:
                break

    _print_banner()

    if template_path and os.path.isfile(template_path):
        print(f"Template: {template_path}")
    else:
        print("No template found - building from scratch")
        template_path = None

    print(f"documenter.py v{VERSION} (mode: {args.mode})")
    print(f"Using copiloter.py v{COP_VER}")
    print(f"Reports: {REPORTS_DIR}\n")

    if not REPORTS_DIR.is_dir():
        print(f"ERROR: Reports folder not found at {REPORTS_DIR}")
        return 2

    def _is_component_folder(d: Path) -> typing.Any:
        """Check if folder is a component of a parent PBIP project (.Report or .SemanticModel)."""
        name = d.name
        if name.endswith(".Report") or name.endswith(".SemanticModel"):
            # Check if parent has a .pbip file with matching base name
            base_name = name.replace(".Report", "").replace(".SemanticModel", "")
            # Use exact filename match instead of glob
            pbip_file = d.parent / f"{base_name}.pbip"
            return pbip_file.exists()
        return False

    # Process each project directory (filter out component folders)
    direct_project = PbipProject(REPORTS_DIR)
    projects = (
        [REPORTS_DIR]
        if direct_project.is_valid
        else [d for d in sorted(REPORTS_DIR.iterdir()) if d.is_dir() and not _is_component_folder(d)]
    )
    if not projects:
        print(f"ERROR: No PBIP projects found in {REPORTS_DIR}")
        return 2

    generated = 0
    for pd in projects:
        proj = PbipProject(pd)
        if not proj.is_valid:
            print(f"  SKIP: {proj.name}")
            continue

        print(f"  Extracting: {proj.name}")
        summary = build_project_summary(proj)
        augmentation = None
        if augmentation_enabled():
            # pandas and the Parquet engine are optional in local-only mode.
            from pbip_documenter.augmentation.service import build_augmentation_bundle

            augmentation = build_augmentation_bundle(summary)
        print(f"  Completeness: {summary.get('completeness', {}).get('score', '?')}")
        print(f"  Building {args.mode} document...")

        doc = build_doc(summary, args.mode, args.logo, template_path, augmentation=augmentation)

        # Determine output path
        if args.output:
            op = Path(args.output)
        else:
            proj_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", proj.name)
            op = EXE_DIR / "Exported Documents" / proj.name / f"{proj_slug}_DesignSpecification_{args.mode}.docx"

        op.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(op))
        generated += 1
        print(f"  [OK] {op} ({op.stat().st_size:,} bytes)\n")

    if not generated:
        print(f"ERROR: No valid PBIP projects found in {REPORTS_DIR}")
        return 2
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
