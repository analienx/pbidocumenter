"""Agent-first CLI: predictable subcommands and one machine-readable contract.

The historical pbip-documenter [path] syntax remains delegated to cli.main.
Generation delegates to that exact same document engine; no second renderer.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
from collections.abc import Sequence
from importlib import metadata
from pathlib import Path
from typing import Any, NoReturn
from zipfile import BadZipFile, ZipFile

from copiloter import PbipProject, _resolve_reports_dir
from pbip_documenter.cli_artifacts import artifact_record, manifest_path, write_manifest
from pbip_documenter.cli_validation import SCHEMA_VERSION, diagnostic, inventory, source_fingerprint, validate_project
from pbip_documenter.config import VERSION

COMMANDS = {"generate", "validate", "inspect", "doctor"}
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_VALIDATION = 3
EXIT_ENVIRONMENT = 4
EXIT_INTERNAL = 5


class _ArgumentError(ValueError):
    """Invalid CLI syntax, handled through the same JSON response contract."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _ArgumentError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="pbip-documenter",
        description="Generate and validate source-grounded Power BI Word documentation.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    for command in ("generate", "validate", "inspect"):
        p = sub.add_parser(command, help={
            "generate": "Validate and generate native, editable Word specifications",
            "validate": "Check source integrity and report parser diagnostics",
            "inspect": "Read safe model and report metadata without document generation",
        }[command])
        p.add_argument("reports_dir", nargs="?", default=None, help="One PBIP project or a directory of projects")
        p.add_argument("--strict", action="store_true", help="Treat parser uncertainty warnings as validation failures")
        p.add_argument("--json", action="store_true", help="Emit one JSON result on stdout (all diagnostics included)")
        if command == "generate":
            p.add_argument("--mode", choices=["default", "full"], default="default")
            p.add_argument("-o", "--output", type=Path, help="A single DOCX output path")
            p.add_argument("--template", "-t", type=Path)
            p.add_argument("--logo", type=Path)
            p.add_argument("--output-dir", type=Path, help="Batch output directory, one DOCX per project")
            p.add_argument("--dry-run", action="store_true", help="Preview destinations without writing files")
            p.add_argument("--no-overwrite", action="store_true", help="Reject existing documents or manifests")
            p.add_argument("--manifest", action="store_true", help="Write source and DOCX SHA-256 evidence beside output")
        elif command == "inspect":
            p.add_argument("--details", action="store_true", help="Show model table and report page names (no source code)")
    doctor = sub.add_parser("doctor", help="Check basic installed CLI and document dependencies")
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument("--template", type=Path)
    return parser


def _component(root: Path, candidate: Path) -> bool:
    for extension in (".Report", ".SemanticModel"):
        if candidate.name.endswith(extension):
            return (root / f"{candidate.name[:-len(extension)]}.pbip").exists()
    return False


def _discover(raw: str | None) -> tuple[list[PbipProject], list[dict[str, str]]]:
    root = _resolve_reports_dir(raw)
    if not root.is_dir():
        return [], [diagnostic("PATH_NOT_FOUND", "error", "Project path is not a readable directory", str(root))]
    project = PbipProject(root)
    if project.is_valid:
        return [project], []
    candidates = [
        d for d in sorted(root.iterdir())
        if d.is_dir() and not _component(root, d) and not d.name.startswith(".")
    ]
    found = [PbipProject(d) for d in candidates]
    valid = [p for p in found if p.is_valid]
    if not valid:
        return [], [diagnostic("NO_PROJECTS", "error", "No PBIP/PBIR projects found", str(root))]
    return valid, []


def _format(payload: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
        return
    status = "OK" if payload["exit_code"] == EXIT_OK else "FAILED"
    print(f"PBIP Documenter {VERSION} | {payload['command']} | {status}")
    for item in payload.get("projects", []):
        print(f"  {item['project']}: {'valid' if item['valid'] else 'invalid'}")
        if "inventory" in item:
            data = item["inventory"]
            print(f"    {data['tables']} tables · {data['measures']} measures · "
                  f"{data['relationships']} relationships · {data['report_pages']} pages · "
                  f"{data['report_visuals']} visuals")
        for diag in item["diagnostics"]:
            print(f"    {diag['severity'].upper()} [{diag['code']}]: {diag['message']}")
            if diag.get("hint"):
                print(f"      Next: {diag['hint']}")
    for finding in payload.get("diagnostics", []):
        print(f"  {finding['severity'].upper()} [{finding['code']}]: {finding['message']}")
        if finding.get("hint"):
            print(f"    Next: {finding['hint']}")
    if payload.get("dry_run"):
        for path in payload.get("planned_outputs", []):
            print(f"  Planned (no files written): {path}")
    for path in payload.get("outputs", []):
        print(f"  Word document: {path}")
    for artifact in payload.get("artifacts", []):
        if artifact.get("manifest"):
            print(f"  Provenance manifest: {artifact['manifest']}")
    if payload["command"] == "doctor":
        for check in payload.get("checks", []):
            print(f"  {'OK' if check['ok'] else 'FAIL'} {check['name']}: {check['detail']}")


def _result(command: str, exit_code: int, **fields: Any) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION, "command": command,
        "status": "ok" if exit_code == EXIT_OK else "error", "exit_code": exit_code,
        **fields,
    }


def _preflight(
    command: str, args: argparse.Namespace
) -> tuple[list[PbipProject], list[dict[str, Any]], list[dict[str, str]], int]:
    projects, discovery = _discover(args.reports_dir)
    if discovery:
        return [], [], discovery, EXIT_USAGE
    results: list[dict[str, Any]] = []
    for project in projects:
        # Capture stray output from optional parsers so --json is never polluted.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            validation, summary = validate_project(project, strict=args.strict)
        if command == "inspect":
            validation["inventory"] = inventory(summary, details=args.details)
        if command in {"inspect", "generate"}:
            validation["source_sha256"] = source_fingerprint(project)
        results.append(validation)
    code = EXIT_VALIDATION if any(not item["valid"] for item in results) else EXIT_OK
    return projects, results, [], code


def _generation_paths(projects: list[PbipProject], args: argparse.Namespace) -> list[str]:
    if args.output:
        return [str(args.output.expanduser().resolve())]
    base = args.output_dir.expanduser().resolve() if args.output_dir else Path.cwd() / "Exported Documents"
    paths: list[str] = []
    for project in projects:
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", project.name)
        path = base / project.name / f"{slug}_DesignSpecification_{args.mode}.docx"
        paths.append(str(path.resolve()))
    return paths


def _generate_precheck(
    args: argparse.Namespace, projects: list[PbipProject], paths: list[str]
) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    if args.output and args.output_dir:
        problems.append(diagnostic("OUTPUT_CONFLICT", "error", "Choose --output or --output-dir, not both"))
    if args.output and len(projects) > 1:
        problems.append(diagnostic("MULTIPLE_PROJECTS", "error", "--output requires exactly one project"))
    if args.template and not args.template.is_file():
        problems.append(diagnostic("TEMPLATE_NOT_FOUND", "error", "Explicit Word template does not exist"))
    elif args.template:
        if args.template.suffix.lower() != ".docx":
            problems.append(diagnostic("TEMPLATE_INVALID", "error", "Template must be a .docx file"))
        else:
            try:
                with ZipFile(args.template) as package:
                    if "word/document.xml" not in package.namelist():
                        problems.append(diagnostic("TEMPLATE_INVALID", "error", "Template is not a valid Word document"))
            except (OSError, BadZipFile):
                problems.append(diagnostic("TEMPLATE_INVALID", "error", "Template is not a valid DOCX archive"))
    if args.logo and not args.logo.is_file():
        problems.append(diagnostic("LOGO_NOT_FOUND", "error", "Logo path does not exist"))
    elif args.logo and args.logo.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff"}:
        problems.append(diagnostic("LOGO_INVALID", "error", "Logo must be a supported raster image"))
    if args.output and args.output.suffix.lower() != ".docx":
        problems.append(diagnostic("OUTPUT_INVALID", "error", "Word output filename must end with .docx"))
    if args.output_dir and args.output_dir.exists() and not args.output_dir.is_dir():
        problems.append(diagnostic("OUTPUT_DIRECTORY_INVALID", "error", "Output directory path points to a file"))
    if args.template:
        template = args.template.expanduser().resolve()
        if any(Path(path) == template for path in paths):
            problems.append(diagnostic("TEMPLATE_OUTPUT_COLLISION", "error", "Output must not replace the input template"))
    if len({str(Path(path)).casefold() if sys.platform == "win32" else path for path in paths}) != len(paths):
        problems.append(diagnostic("DUPLICATE_OUTPUT", "error", "Multiple projects resolve to the same output path"))
    if args.no_overwrite:
        for path in paths:
            docx = Path(path)
            targets = (docx, manifest_path(docx)) if args.manifest else (docx,)
            for target in targets:
                if target.exists():
                    problems.append(diagnostic("OUTPUT_EXISTS", "error", "Target already exists", str(target)))
    return problems


def _run_generate(
    args: argparse.Namespace, projects: list[PbipProject],
    results: list[dict[str, Any]], paths: list[str]
) -> tuple[int, list[str], list[dict[str, str]], list[dict[str, Any]]]:
    from pbip_documenter import cli

    if any(not item["valid"] for item in results):
        return EXIT_VALIDATION, [], [], []
    if args.dry_run:
        return EXIT_OK, [], [], []

    outputs: list[str] = []
    artifacts: list[dict[str, Any]] = []
    for project, result, raw_path in zip(projects, results, paths, strict=True):
        document = Path(raw_path)
        legacy_args = [
            str(project.project_dir), "--mode", args.mode, "--output", str(document),
            "--expect-source-sha256", result["source_sha256"],
        ]
        if args.template:
            legacy_args += ["--template", str(args.template)]
        if args.logo:
            legacy_args += ["--logo", str(args.logo)]
        if args.no_overwrite:
            legacy_args += ["--no-overwrite"]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(legacy_args)
        if code:
            if code == EXIT_VALIDATION:
                return EXIT_VALIDATION, outputs, [
                    diagnostic("SOURCE_CHANGED", "error", "Source changed during generation", project.name)
                ], artifacts
            return EXIT_INTERNAL, outputs, [
                diagnostic("GENERATION_FAILED", "error", f"Generation failed for {project.name}")
            ], artifacts
        if not document.is_file() or document.stat().st_size <= 0:
            return EXIT_INTERNAL, outputs, [
                diagnostic("OUTPUT_MISSING", "error", "Generated document could not be verified", raw_path)
            ], artifacts
        if source_fingerprint(project) != result["source_sha256"]:
            return EXIT_INTERNAL, outputs, [
                diagnostic("SOURCE_CHANGED", "error", "Source changed during generation", project.name)
            ], artifacts
        record = artifact_record(
            document, project=project.name, source_sha256=result["source_sha256"],
            mode=args.mode, parser=result["parser"]
        )
        if args.manifest:
            sidecar = manifest_path(document)
            write_manifest(sidecar, record, no_overwrite=args.no_overwrite)
            record["manifest"] = str(sidecar.resolve())
        artifacts.append(record)
        outputs.append(str(document.resolve()))
    return EXIT_OK, outputs, [], artifacts


def _doctor(template: Path | None) -> dict[str, Any]:
    from importlib.util import find_spec

    checks: list[dict[str, Any]] = []
    for module, package in (("docx", "python-docx"), ("lxml", "lxml"), ("copiloter", "pbip-documenter")):
        installed = find_spec(module) is not None
        try:
            version = metadata.version(package)
        except metadata.PackageNotFoundError:
            version = "not installed as a distribution"
        checks.append({"name": module, "ok": installed, "detail": version})
    checks.append({"name": "python", "ok": sys.version_info[:2] >= (3, 10),
                   "detail": ".".join(map(str, sys.version_info[:3]))})
    if template:
        checks.append({"name": "template", "ok": template.is_file(),
                       "detail": str(template.expanduser().resolve())})
    code = EXIT_OK if all(check["ok"] for check in checks) else EXIT_ENVIRONMENT
    return _result("doctor", code, checks=checks, projects=[], diagnostics=[], outputs=[])


def main(argv: Sequence[str] | None = None) -> int:
    tokens = list(argv) if argv is not None else sys.argv[1:]
    if not tokens or (tokens[0] not in COMMANDS and tokens[0] not in {"-h", "--help", "--version"}):
        # Legacy entry point remains unchanged, including existing syntax.
        from pbip_documenter.cli import main as legacy_main

        return int(legacy_main(tokens))
    if tokens == ["--version"]:
        print(f"pbip-documenter {VERSION}")
        return EXIT_OK
    if tokens and tokens[0] in {"-h", "--help"}:
        _parser().print_help()
        return EXIT_OK
    parser = _parser()
    try:
        args = parser.parse_args(tokens)
    except _ArgumentError as error:
        if "--json" in tokens:
            payload = _result(
                tokens[0] if tokens and tokens[0] in COMMANDS else "unknown",
                EXIT_USAGE,
                diagnostics=[diagnostic("ARGUMENT_INVALID", "error", str(error))],
                projects=[],
                outputs=[],
            )
            _format(payload, json_output=True)
        else:
            parser.print_usage(sys.stderr)
            print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE
    if args.command == "doctor":
        result = _doctor(args.template)
        _format(result, json_output=args.json)
        return int(result["exit_code"])

    try:
        projects, results, errors, code = _preflight(args.command, args)
        planned = _generation_paths(projects, args) if args.command == "generate" and projects else []
        artifacts: list[dict[str, Any]] = []
        outputs: list[str] = []
        if args.command == "generate":
            precheck = _generate_precheck(args, projects, planned) if projects else []
            if precheck:
                errors.extend(precheck)
                code = EXIT_USAGE
            elif code == EXIT_OK:
                code, outputs, generation_errors, artifacts = _run_generate(args, projects, results, planned)
                errors.extend(generation_errors)
        payload = _result(
            args.command, code, projects=results, diagnostics=errors, outputs=outputs,
            **({"planned_outputs": planned, "dry_run": args.dry_run, "artifacts": artifacts}
               if args.command == "generate" else {}),
        )
    except (OSError, ValueError, TypeError, RuntimeError):
        payload = _result(
            args.command, EXIT_INTERNAL, projects=[], outputs=[],
            diagnostics=[diagnostic("UNEXPECTED_ERROR", "error", "Processing failed; inspect input source and environment")],
        )
    _format(payload, json_output=args.json)
    return int(payload["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
