"""Public CLI: python -m pbip_documenter.visual_quality ..."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evidence import load
from .runner import audit, iterate, request, save, snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independent Power BI and Word visual quality gate")
    commands = parser.add_subparsers(dest="command", required=True)
    for operation in ("preflight", "request-review", "verify"):
        item = commands.add_parser(operation)
        item.add_argument("surface", choices=("report", "document"))
        item.add_argument("source", type=Path)
        item.add_argument("--renders", type=Path)
        item.add_argument("--review", type=Path)
        item.add_argument("--fixer-id", default="generation_executor")
        item.add_argument("--output", type=Path)
    loop = commands.add_parser("iterate")
    loop.add_argument("workflow", type=Path, help="JSON with renderer/reviewer/fixer argv adapters")
    args = parser.parse_args(argv)
    if args.command == "iterate":
        result = iterate(load(args.workflow))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["outcome"] == "passed" else 2
    if args.command == "preflight":
        result = snapshot(args.surface, args.source, args.renders)
        success = result["static_pass"] and result["render_pass"]
    elif args.command == "request-review":
        if args.renders is None:
            parser.error("request-review requires --renders")
        result = request(args.surface, args.source, args.renders, args.fixer_id)
        success = True
    else:
        result = audit(args.surface, args.source, args.renders, args.review, args.fixer_id)
        success = result["passed"]
    if args.output:
        save(args.output, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
