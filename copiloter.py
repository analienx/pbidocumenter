#!/usr/bin/env python3
"""
copiloter.py - Non-interactive PBIP/PBIR preprocessor for Copilot-friendly documentation.

Scans the Reports subfolder next to this script, detects PBIP-style Power BI
project structures, extracts best-effort report and semantic model metadata,
and generates standardized documentation files:
  - project-summary.json   (structured metadata)
  - project-summary.md     (human-readable markdown)
  - copilot-input.md       (Copilot-optimized context)
  - manifest.json          (inventory of generated outputs)

Handles incomplete projects gracefully. Never fabricates missing values.
Supports both PBIP (legacy single report.json) and PBIR (per-page/per-visual files).
"""

import contextlib
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
def _get_script_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.argv[0]).resolve().parent
    return Path(__file__).resolve().parent


SCRIPT_DIR = _get_script_dir()


def _resolve_reports_dir(cli_arg: str | None = None) -> Path:
    """Resolve the reports directory from (in priority order):
    1. CLI argument / explicit path passed in
    2. PBIP_REPORTS env variable
    3. ./Reports/ sibling folder next to the script
    """
    if cli_arg:
        return Path(cli_arg).expanduser().resolve()
    env = os.environ.get("PBIP_REPORTS", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return SCRIPT_DIR / "Reports"


REPORTS_DIR = _resolve_reports_dir()  # default; overridden by main() after arg parse


def _get_exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.argv[0]).resolve().parent
    return SCRIPT_DIR


EXE_DIR = _get_exe_dir()


def _resolve_export_root(cli_arg: str | None = None) -> Path:
    """Resolve export root in repository root (next to the EXE/script)."""
    if cli_arg:
        return Path(cli_arg).expanduser().resolve()
    return EXE_DIR / EXPORT_DIR_NAME


EXPORT_DIR_NAME = "Exported Documents"
UNKNOWN = "(not found)"
VERSION = "1.2.0"
EMIT_JSON = True  # Set True to also write project-summary.json
EMIT_MANIFEST = False  # Set True to also write manifest.json

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def safe_read_json(path: Path) -> dict | None:
    """Read a JSON file, return None on any failure."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return None


def safe_read_text(path: Path) -> str | None:
    """Read a text file, return None on any failure."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            return f.read()
    except Exception:
        return None


def file_hash(path: Path) -> str | None:
    """SHA-256 of a file for manifest integrity tracking."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def timestamp_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def rel(path: Path, base: Path = SCRIPT_DIR) -> str:
    """Return a portable relative-to-script-dir path string (always forward slashes)."""
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


# Common first names (US/UK) for personal name detection
COMMON_FIRST_NAMES = frozenset(
    [
        "james",
        "john",
        "robert",
        "michael",
        "william",
        "david",
        "richard",
        "joseph",
        "thomas",
        "charles",
        "christopher",
        "daniel",
        "matthew",
        "anthony",
        "mark",
        "donald",
        "steven",
        "paul",
        "andrew",
        "joshua",
        "kenneth",
        "kevin",
        "brian",
        "george",
        "timothy",
        "ronald",
        "jason",
        "edward",
        "jeffrey",
        "ryan",
        "jacob",
        "gary",
        "nicholas",
        "eric",
        "jonathan",
        "stephen",
        "larry",
        "justin",
        "scott",
        "brandon",
        "benjamin",
        "samuel",
        "gregory",
        "frank",
        "alexander",
        "raymond",
        "patrick",
        "jack",
        "dennis",
        "jerry",
        "mary",
        "patricia",
        "jennifer",
        "linda",
        "elizabeth",
        "barbara",
        "susan",
        "jessica",
        "sarah",
        "karen",
        "nancy",
        "lisa",
        "betty",
        "margaret",
        "sandra",
        "ashley",
        "kimberly",
        "emily",
        "donna",
        "michelle",
        "dorothy",
        "carol",
        "amanda",
        "melissa",
        "deborah",
        "stephanie",
        "rebecca",
        "laura",
        "sharon",
        "cynthia",
        "kathleen",
        "amy",
        "shirley",
        "angela",
        "helen",
        "anna",
        "brenda",
        "pamela",
        "nicole",
        "samantha",
        "katherine",
        "emma",
        "ruth",
        "christine",
        "catherine",
        "debra",
        "rachel",
        "carolyn",
        "janet",
        "emily",
        "bree",
        "brian",
        "kim",
        "eory",
        "kathryn",
        "miranda",
        "hatheway",
        "madera",
        "harbin",
        "taylor",
    ]
)


def looks_like_personal_name(name: str) -> bool:
    """Heuristic to detect if a role name looks like a personal name rather than a functional role.

    Returns True if the name appears to be a person's name (e.g., '<PERSON_NAME_003>', '<PERSON_NAME_004>')
    rather than a functional role name (e.g., 'Manager', 'Admin', 'MSL').

    Detection criteria:
    - Contains two or more capitalized words (firstname lastname pattern)
    - Contains a common first name
    - Not in UPPERCASE (functional roles often are)
    - Not a single word that looks like an acronym
    """
    if not name or len(name) < 2:
        return False

    name_lower = name.lower()
    words = name.split()

    # Single word names: check if it's a common first name AND not all uppercase
    if len(words) == 1:
        return name_lower in COMMON_FIRST_NAMES and not name.isupper()

    # Multiple words: check for personal name patterns
    # Pattern 1: Two or more capitalized words (Firstname Lastname)
    has_multiple_caps = sum(1 for w in words if w and w[0].isupper()) >= 2

    # Pattern 2: Contains a known first name
    has_first_name = any(w.lower() in COMMON_FIRST_NAMES for w in words)

    # Pattern 3: Not all uppercase (functional roles tend to be UPPERCASE)
    not_uppercase = not name.isupper()

    # Pattern 4: Average word length > 3 (acronyms tend to be short)
    avg_word_len = sum(len(w) for w in words) / len(words) if words else 0
    not_acronym_style = avg_word_len > 3

    # It's likely a personal name if it has multiple capitalized words OR contains a first name,
    # AND it doesn't look like an uppercase functional role
    return (has_multiple_caps or has_first_name) and not_uppercase and not_acronym_style


def estimate_parser_confidence(sm: dict) -> str:
    """Best-effort confidence label for semantic-model extraction coverage."""
    if not sm:
        return "low"
    warnings = len(sm.get("warnings", []) or [])
    tables = sm.get("table_count", 0) or 0
    cols = sm.get("total_columns", 0) or 0
    meas = sm.get("total_measures", 0) or 0
    rels = sm.get("relationship_count", 0) or 0
    score = 0
    if tables > 0:
        score += 2
    if cols > 0:
        score += 1
    if meas > 0:
        score += 1
    if rels > 0:
        score += 1
    score -= min(3, warnings)
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# TMDL parser (best-effort)
# ---------------------------------------------------------------------------


class TmdlParser:
    """Lightweight parser for TMDL (Tabular Model Definition Language) files."""

    @staticmethod
    def parse_table(text: str) -> dict:
        """Extract table name, columns, measures, partitions, hierarchies and calc-group hints."""
        result = {
            "columns": [],
            "measures": [],
            "partitions": [],
            "hierarchies": [],
            "calculation_items": [],
            "name": None,
            "data_category": None,
            "lineage_tag": None,
            "is_calculation_group": False,
            "hierarchy_count": 0,
            "calculation_item_count": 0,
        }
        if not text:
            return result

        m = re.match(r"^table\s+(?:'([^']+)'|(\S+))", text, re.MULTILINE)
        if m:
            result["name"] = m.group(1) or m.group(2)

        m2 = re.search(r"dataCategory:\s*(.+)", text)
        if m2:
            result["data_category"] = m2.group(1).strip()

        m3 = re.search(r"^table\b.*?\n(?:.*?\n)*?\tlineageTag:\s*(\S+)", text)
        if m3:
            result["lineage_tag"] = m3.group(1).strip()

        if re.search(r"changedProperty\s*=\s*IsHidden", text):
            result["is_hidden"] = True
        if re.search(r"^\tcalculationGroup\b", text, re.MULTILINE):
            result["is_calculation_group"] = True

        for cm in re.finditer(
            r"^\tcolumn\s+(?:'([^']+)'|(\S+))\s*\n((?:\t\t.+\n)*)",
            text,
            re.MULTILINE,
        ):
            col_name = cm.group(1) or cm.group(2)
            col_body = cm.group(3)
            col = {"name": col_name}
            dt = re.search(r"dataType:\s*(\S+)", col_body)
            if dt:
                col["data_type"] = dt.group(1)
            fmt = re.search(r"formatString:\s*(.+)", col_body)
            if fmt:
                col["format_string"] = fmt.group(1).strip()
            if re.search(r"\bisKey\b", col_body):
                col["is_key"] = True
            src = re.search(r"sourceColumn:\s*(.+)", col_body)
            if src:
                col["source_column"] = src.group(1).strip()
            sb = re.search(r"summarizeBy:\s*(\S+)", col_body)
            if sb:
                col["summarize_by"] = sb.group(1)
            if re.search(r"isHidden", col_body):
                col["is_hidden"] = True
            sbc = re.search(r"sortByColumn:\s*(?:'([^']+)'|(\S+))", col_body)
            if sbc:
                col["sort_by_column"] = sbc.group(1) or sbc.group(2)
            dc = re.search(r"dataCategory:\s*(.+)", col_body)
            if dc:
                col["data_category"] = dc.group(1).strip()
            result["columns"].append(col)

        for mm in re.finditer(
            r"^\tmeasure\s+(?:'([^']+)'|(\S+))\s*=([\s\S]*?)(?=\n\t(?:measure|column|partition|hierarchy|calculationItem|annotation|changedProperty|calculationGroup)\b|\n\t\n|\Z)",
            text,
            re.MULTILINE,
        ):
            meas_name = mm.group(1) or mm.group(2)
            meas_body_raw = mm.group(3)
            meas = {"name": meas_name}
            dax_lines = []
            for line in meas_body_raw.split("\n"):
                stripped = line.strip()
                if (
                    stripped.startswith("lineageTag:")
                    or stripped.startswith("formatString:")
                    or stripped.startswith("annotation ")
                    or stripped.startswith("displayFolder:")
                ):
                    break
                if stripped and stripped != "```":
                    dax_lines.append(stripped)
            meas["expression"] = "\n".join(dax_lines).strip()
            fmt2 = re.search(r"formatString:\s*(.+)", meas_body_raw)
            if fmt2:
                meas["format_string"] = fmt2.group(1).strip()
            df = re.search(r"displayFolder:\s*(.+)", meas_body_raw)
            if df:
                meas["display_folder"] = df.group(1).strip().strip('"')
            if re.search(r"\bkpi\b", meas_body_raw, re.IGNORECASE):
                meas["has_kpi"] = True
            result["measures"].append(meas)

        for pm in re.finditer(
            r"^\tpartition\s+(?:'([^']+)'|(\S+))\s*=\s*(\w+)\s*\n((?:\t\t.+\n)*)",
            text,
            re.MULTILINE,
        ):
            part_name = pm.group(1) or pm.group(2)
            part_mode_type = pm.group(3)
            part_body = pm.group(4)
            part = {"name": part_name, "type": part_mode_type}
            if part_mode_type == "calculated":
                src_match2 = re.search(r"source\s*=\s*\n?([\s\S]*)", pm.group(4))
                if src_match2:
                    part["calculated_dax"] = src_match2.group(1).strip()
            mode_m = re.search(r"mode:\s*(\S+)", part_body)
            if mode_m:
                part["mode"] = mode_m.group(1)
            src_match = re.search(r"source\s*=\s*\n?([\s\S]*)", part_body)
            if src_match:
                src_lines = [line.strip() for line in src_match.group(1).split("\n") if line.strip()]
                part["m_expression"] = "\n".join(src_lines)
            result["partitions"].append(part)

        hierarchy_headers = list(re.finditer(r"^\thierarchy\s+(?:'([^']+)'|(\S+))\s*$", text, re.MULTILINE))
        for i, hm in enumerate(hierarchy_headers):
            hname = hm.group(1) or hm.group(2)
            start = hm.end()
            end = hierarchy_headers[i + 1].start() if i + 1 < len(hierarchy_headers) else len(text)
            hbody = text[start:end]
            hierarchy = {"name": hname, "levels": []}
            current_level = None
            for line in hbody.splitlines():
                lm = re.match(r"^\t\tlevel\s+(?:'([^']+)'|(\S+))\s*$", line)
                if lm:
                    current_level = {"name": lm.group(1) or lm.group(2)}
                    hierarchy["levels"].append(current_level)
                    continue
                if current_level:
                    cm = re.match(r"^\t\t\tcolumn:\s*(.+)$", line)
                    if cm:
                        current_level["column"] = cm.group(1).strip()
            result["hierarchies"].append(hierarchy)

        for cim in re.finditer(
            r"^\tcalculationItem\s+(?:'([^']+)'|(\S+))\s*=([\s\S]*?)(?=\n\t(?:calculationItem|annotation|changedProperty)\b|\n\t\n|\Z)",
            text,
            re.MULTILINE,
        ):
            iname = cim.group(1) or cim.group(2)
            ibody = cim.group(3)
            item = {"name": iname}
            expr_lines = []
            for line in ibody.split("\n"):
                stripped = line.strip()
                if stripped.startswith("formatStringDefinition:") or stripped.startswith("annotation "):
                    break
                if stripped and stripped != "```":
                    expr_lines.append(stripped)
            item["expression"] = "\n".join(expr_lines).strip()
            fsd = re.search(r"formatStringDefinition:\s*(.+)", ibody)
            if fsd:
                item["format_string_expression"] = fsd.group(1).strip()
            result["calculation_items"].append(item)
            result["is_calculation_group"] = True

        result["hierarchy_count"] = len(result["hierarchies"])
        result["calculation_item_count"] = len(result["calculation_items"])
        return result

    @staticmethod
    def parse_relationships(text: str) -> list:
        """Extract relationships from relationships.tmdl."""
        rels = []
        if not text:
            return rels
        for rm in re.finditer(r"^relationship\s+(\S+)\s*\n((?:\t.+\n)*)", text, re.MULTILINE):
            rel_id = rm.group(1)
            body = rm.group(2)
            rel = {"id": rel_id}
            fc = re.search(r"fromColumn:\s*(.+)", body)
            tc = re.search(r"toColumn:\s*(.+)", body)
            if fc:
                rel["from_column"] = fc.group(1).strip()
            if tc:
                rel["to_column"] = tc.group(1).strip()
            if fc:
                parts = fc.group(1).strip().split(".")
                if len(parts) == 2:
                    rel["from_table"] = parts[0].strip("' ")
                    rel["from_field"] = parts[1].strip("' ")
            if tc:
                parts = tc.group(1).strip().split(".")
                if len(parts) == 2:
                    rel["to_table"] = parts[0].strip("' ")
                    rel["to_field"] = parts[1].strip("' ")
            cf = re.search(r"crossFilteringBehavior:\s*(\S+)", body)
            if cf:
                rel["cross_filtering"] = cf.group(1)
            ia = re.search(r"isActive:\s*(\S+)", body)
            if ia:
                rel["is_active"] = ia.group(1).lower() == "true"
            cd = re.search(r"cardinality:\s*(\S+)", body)
            if cd:
                rel["cardinality"] = cd.group(1)
            sf = re.search(r"securityFilteringBehavior:\s*(\S+)", body)
            if sf:
                rel["security_filtering"] = sf.group(1)
            jd = re.search(r"joinOnDateBehavior:\s*(\S+)", body)
            if jd:
                rel["join_on_date_behavior"] = jd.group(1)
            rels.append(rel)
        return rels

    @staticmethod
    def parse_expressions(text: str) -> list:
        """Extract named expressions from expressions.tmdl."""
        exprs = []
        if not text:
            return exprs
        for em in re.finditer(
            r"^expression\s+(?:'([^']+)'|(\S+))\s*=([\s\S]*?)(?=\n^expression\s|\Z)", text, re.MULTILINE
        ):
            name = em.group(1) or em.group(2)
            body = em.group(3)
            expr = {"name": name}
            lt = re.search(r"lineageTag:\s*(\S+)", body)
            if lt:
                expr["lineage_tag"] = lt.group(1)
            qg = re.search(r"queryGroup:\s*(?:'([^']+)'|(\S+))", body)
            if qg:
                expr["query_group"] = qg.group(1) or qg.group(2)
            rt = re.search(r"PBI_ResultType\s*=\s*(\S+)", body)
            if rt:
                expr["result_type"] = rt.group(1)
            urls = re.findall(r'https?://[^\s"\')\]]+', body)
            if urls:
                expr["data_sources"] = list(set(urls))
            expr_lines = []
            for line in body.split("\n"):
                s = line.strip()
                if s.startswith("lineageTag:") or s.startswith("queryGroup:") or s.startswith("annotation "):
                    continue
                if s:
                    expr_lines.append(s)
            expr["expression"] = "\n".join(expr_lines)
            exprs.append(expr)
        return exprs

    @staticmethod
    def parse_model(text: str) -> dict:
        """Extract model-level metadata from model.tmdl."""
        info = {"culture": None, "table_refs": [], "annotations": {}, "query_groups": [], "data_source_version": None}
        if not text:
            return info
        cm = re.search(r"culture:\s*(\S+)", text)
        if cm:
            info["culture"] = cm.group(1)
        dv = re.search(r"defaultPowerBIDataSourceVersion:\s*(\S+)", text)
        if dv:
            info["data_source_version"] = dv.group(1)
        for tr in re.finditer(r"ref table\s+(?:'([^']+)'|(\S+))", text):
            info["table_refs"].append(tr.group(1) or tr.group(2))
        for qg in re.finditer(r"queryGroup\s+'([^']+)'", text):
            info["query_groups"].append(qg.group(1))
        qo = re.search(r"PBI_QueryOrder\s*=\s*\[([^\]]+)\]", text)
        if qo:
            info["query_order"] = [q.strip().strip('"') for q in qo.group(1).split(",")]
        return info

    @staticmethod
    def parse_role(text: str) -> dict:
        """Extract role definition with model and table permissions.

        Handles role definitions from TMDL files in /definition/roles/ directory.
        Supports:
        - Both quoted names ('<PERSON_NAME_002>') and unquoted names (MSL)
        - Single-line and multi-line DAX expressions
        - Table permissions with VAR/RETURN patterns
        """
        result = {
            "name": None,
            "model_permission": None,
            "table_permissions": [],
            "tables": [],
            "looks_like_personal_name": False,
            "filtered_table_count": 0,
            "has_rls": False,
            "role_filter_complexity": "none",
        }
        if not text:
            return result

        # Extract role name (quoted or unquoted)
        name_match = re.match(r"^role\s+(?:'([^']+)'|(\S+))", text, re.MULTILINE)
        if name_match:
            role_name = (name_match.group(1) or name_match.group(2) or "").strip()
            result["name"] = role_name or None
            result["looks_like_personal_name"] = looks_like_personal_name(role_name) if role_name else False

        # Extract modelPermission
        mp_match = re.search(r"modelPermission:\s*(\w+)", text)
        if mp_match:
            result["model_permission"] = mp_match.group(1)

        # Extract tablePermissions with their filter DAX expressions
        # Use a state machine approach to handle multi-line expressions
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            # Match tablePermission line - capture table name and optional inline expression
            # Pattern handles: tablePermission TABLENAME = EXPRESSION  or  tablePermission TABLENAME =
            tp_match = re.match(r"^(\s*)tablePermission\s+(?:'([^']+)'|(\S+))\s*=\s*(.*)", line)
            if tp_match:
                table_name = tp_match.group(2) or tp_match.group(3)
                indent = tp_match.group(1)
                remaining = tp_match.group(4).strip() if tp_match.group(4) else None
                expr_parts = []

                # If there's content after '=' on the same line, include it
                if remaining:
                    expr_parts.append(remaining)

                i += 1

                # Continue collecting lines until we hit another tablePermission, annotation,
                # or a line at the same or lower indentation level (indicating end of this permission)
                while i < len(lines):
                    next_line = lines[i]
                    next_line_stripped = next_line.strip()

                    # Skip empty lines but track them for proper formatting
                    if not next_line_stripped:
                        i += 1
                        continue

                    # Stop conditions (in order of priority)
                    # 1. Another tablePermission or annotation
                    if re.match(r"^\s*(tablePermission|annotation)\s+", next_line_stripped):
                        break

                    # 2. Role definition or modelPermission (top-level constructs)
                    if re.match(r"^(role|modelPermission)\s+", next_line_stripped):
                        break

                    # 3. A new construct at the same base level (role-level construct without prefix)
                    # The base indent is typically 1 tab for role contents
                    next_indent_level = len(next_line) - len(next_line.lstrip())
                    base_indent_level = len(indent) if indent else 0

                    # If line is at or less than base indent (and not DAX content), it's a new construct
                    # But we need to be careful - DAX expressions themselves may be indented
                    # Check if it looks like a TMDL construct (role, tablePermission, annotation, etc.)
                    if next_indent_level <= base_indent_level and re.match(
                        r"^[a-zA-Z_][a-zA-Z0-9_]*(?:\s|$)", next_line_stripped
                    ):
                        # Check that it's not just indented DAX code
                        first_word = next_line_stripped.split()[0] if next_line_stripped else ""
                        # Common TMDL constructs at role level
                        if first_word in (
                            "role",
                            "modelPermission",
                            "tablePermission",
                            "annotation",
                            "member",
                            "changedProperty",
                        ):
                            break

                    # This line is part of the expression (preserve original indentation in content)
                    expr_parts.append(next_line_stripped)
                    i += 1

                # Build the complete expression
                if expr_parts:
                    # Join with newlines to preserve multi-line structure better than spaces
                    full_expr = "\n".join(expr_parts)
                    # Normalize consecutive whitespace but preserve newlines
                    full_expr = re.sub(r"[ \t]+", " ", full_expr)
                    full_expr = full_expr.strip()
                else:
                    full_expr = "(no filter)"

                result["table_permissions"].append({"table": table_name, "filter": full_expr})
                continue
            i += 1

        result["tables"] = [tp.get("table") for tp in result.get("table_permissions", []) if tp.get("table")]
        result["filtered_table_count"] = len(result.get("table_permissions", []))
        result["has_rls"] = result["filtered_table_count"] > 0
        complexity_score = 0
        for tp in result.get("table_permissions", []):
            expr = (tp.get("expression") or "").upper()
            if not expr:
                continue
            if "VAR " in expr or " RETURN" in expr:
                complexity_score += 2
            elif any(tok in expr for tok in ("CALCULATE(", "FILTER(", "&&", "||", " IN {")):
                complexity_score += 1
            else:
                complexity_score += 1
        if complexity_score >= 3:
            result["role_filter_complexity"] = "high"
        elif complexity_score >= 2:
            result["role_filter_complexity"] = "medium"
        elif complexity_score >= 1 or result.get("table_permissions"):
            result["role_filter_complexity"] = "low"
        return result

    @staticmethod
    def parse_functions(text: str) -> list:
        """Extract user-defined DAX functions from functions.tmdl.

        Handles function definitions written as:
            createOrReplace function <name>(<params>) as <return_type>
                // documentation
                <body>

        Returns a list of dicts with:
            - name          : function name
            - params        : parameter string (may be empty)
            - return_type   : DAX type (e.g. DOUBLE, DATETIME, BOOLEAN)
            - documentation : list of comment lines
            - body          : cleaned DAX body
        """
        funcs = []
        if not text:
            return funcs
        # Match createOrReplace function blocks (case-insensitive)
        for m in re.finditer(
            r"createOrReplace\s+function\s+(\w+)\(([^)]*)\)\s+as\s+(\w+)\s*\n",
            text,
            re.IGNORECASE,
        ):
            name = m.group(1)
            params = m.group(2).strip()
            return_type = m.group(3)
            start = m.end()
            # Find the end of the block (next createOrReplace or EOF)
            next_match = re.search(r"createOrReplace\s+function", text[start:], re.IGNORECASE)
            block = text[start:start + next_match.start()] if next_match else text[start:]
            # Extract documentation comments and body
            doc = []
            body_lines = []
            for line in block.splitlines():
                s = line.strip()
                if s.startswith("//"):
                    doc.append(s.lstrip("/").strip())
                elif s:
                    body_lines.append(s)
            funcs.append(
                {
                    "name": name,
                    "params": params,
                    "return_type": return_type,
                    "documentation": doc,
                    "body": "\n".join(body_lines),
                }
            )
        return funcs

    @staticmethod
    def parse_functions_from_json(data: dict) -> list:
        """Extract user-defined DAX functions from a JSON structure.

        Looks for common patterns:
            - data["functions"] list
            - data["userDefinedFunctions"] list
            - data["model"]["functions"] list
            - Any list of dicts with name/params/returnType/body keys
        """
        funcs = []
        if not isinstance(data, dict):
            return funcs

        candidates = []
        # Direct keys
        for key in ("functions", "userDefinedFunctions", "udf", "userDefined"):
            if key in data and isinstance(data[key], list):
                candidates.extend(data[key])
        # Nested in model
        if "model" in data and isinstance(data["model"], dict):
            model = data["model"]
            for key in ("functions", "userDefinedFunctions", "udf"):
                if key in model and isinstance(model[key], list):
                    candidates.extend(model[key])

        for item in candidates:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("functionName") or item.get("id")
            if not name:
                continue
            params = item.get("params", "")
            if not params:
                params = item.get("parameters", "")
                if isinstance(params, list):
                    params = ", ".join(str(p) for p in params)
            return_type = item.get("returnType", "") or item.get("return_type", "") or item.get("type", "")
            docs = item.get("documentation", "")
            if isinstance(docs, list):
                doc_list = [str(d) for d in docs]
            elif isinstance(docs, str):
                doc_list = [docs] if docs else []
            else:
                doc_list = []
            body = item.get("body", "") or item.get("expression", "") or item.get("dax", "")
            funcs.append(
                {
                    "name": str(name),
                    "params": str(params),
                    "return_type": str(return_type),
                    "documentation": doc_list,
                    "body": str(body),
                }
            )
        return funcs

    @staticmethod
    def parse_functions_from_md(text: str) -> list:
        """Extract user-defined DAX functions from a Markdown file.

        Looks for:
            - Code blocks with createOrReplace function syntax
            - Section headers mentioning functions
            - Table rows describing functions
        """
        funcs = TmdlParser.parse_functions(text)
        if funcs:
            return funcs

        # Fallback: search for function signatures in code blocks
        if not text:
            return funcs

        # Match DAX function signatures in markdown code blocks or plain text
        pattern = re.compile(
            r"(?:^|\n)\s*(?:```(?:dax)?\s*\n)?\s*"
            r"(?:createOrReplace\s+)?function\s+(\w+)\s*\(([^)]*)\)\s*"
            r"(?:\s*(?:as|->|returns?)\s+(\w+))?\s*\n"
            r"([^`]*?)(?:```|\Z|\n\s*\n)",
            re.IGNORECASE | re.DOTALL,
        )
        for m in pattern.finditer(text):
            name = m.group(1)
            params = m.group(2).strip()
            return_type = m.group(3) or ""
            body = m.group(4).strip() if m.group(4) else ""
            funcs.append(
                {
                    "name": name,
                    "params": params,
                    "return_type": return_type,
                    "documentation": [],
                    "body": body,
                }
            )
        return funcs


# ---------------------------------------------------------------------------
# PBIP Project Scanner
# ---------------------------------------------------------------------------


class PbipProject:
    """Represents one detected PBIP or PBIR project folder.

    Supports three layouts:
      A) Full PBIP:           folder contains *.pbip + Name.Report/ + Name.SemanticModel/
      B) Standalone .Report:  the folder *is* the .Report (has .platform + definition.pbir)
      C) PBIR report format:  .Report/definition/pages/<name>/page.json  (per-page files)
         vs legacy format:    .Report/definition/report.json              (single monolithic file)

    Both PBIR and legacy report formats are detected and handled transparently.
    """

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.name = project_dir.name
        self.pbip_file: Path | None = None
        self.pbip_data: dict | None = None
        self.pbir_file: Path | None = None  # definition.pbir inside .Report
        self.report_dir: Path | None = None
        self.semantic_model_dir: Path | None = None
        self.report_format: str = "unknown"  # "pbir" | "legacy" | "unknown"
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self._detect_structure()

    def _detect_structure(self):
        """Walk the project directory and locate PBIP/PBIR artifacts."""

        # ── Layout B: this folder itself IS a .Report ──────────────────────
        if self.project_dir.name.endswith(".Report") and (self.project_dir / ".platform").exists():
            self.report_dir = self.project_dir
            self._detect_report_format()
            self.warnings.append("Standalone .Report folder (no .pbip wrapper)")
            return

        # ── Layout A: full PBIP/PBIR project ──────────────────────────────
        # .pbip file
        pbip_files = list(self.project_dir.glob("*.pbip"))
        if pbip_files:
            self.pbip_file = pbip_files[0]
            self.pbip_data = safe_read_json(self.pbip_file)
            if not self.pbip_data:
                self.warnings.append(f"Could not parse {self.pbip_file.name}")
        else:
            self.warnings.append("No .pbip file found")

        # .Report folder
        report_dirs = [d for d in self.project_dir.iterdir() if d.is_dir() and d.name.endswith(".Report")]
        if report_dirs:
            self.report_dir = report_dirs[0]
            self._detect_report_format()
        else:
            self.warnings.append("No .Report folder found")

        # .SemanticModel folder
        sm_dirs = [d for d in self.project_dir.iterdir() if d.is_dir() and d.name.endswith(".SemanticModel")]
        if sm_dirs:
            self.semantic_model_dir = sm_dirs[0]
        else:
            self.warnings.append("No .SemanticModel folder found")

    def _detect_report_format(self):
        """Determine whether the .Report uses PBIR (per-file) or legacy (monolithic) format.

        PBIR format:  definition/pages/<PageName>/page.json exists
        Legacy format: definition/report.json has a "sections" key

        Sets self.report_format and self.pbir_file.
        """
        if not self.report_dir:
            return

        # Check for definition.pbir (present in PBIR format)
        pbir_candidate = self.report_dir / "definition.pbir"
        if pbir_candidate.exists():
            self.pbir_file = pbir_candidate

        defn = self.report_dir / "definition"
        pages_dir = defn / "pages"

        # PBIR: pages directory with subfolders containing page.json
        if pages_dir.is_dir():
            page_subdirs = [d for d in pages_dir.iterdir() if d.is_dir() and (d / "page.json").exists()]
            if page_subdirs:
                self.report_format = "pbir"
                return

        # Legacy: single report.json with sections[]
        report_json_path = defn / "report.json"
        if report_json_path.exists():
            rj = safe_read_json(report_json_path)
            if rj and "sections" in rj:
                self.report_format = "legacy"
                return

        # Fallback: if report.json exists but no sections, treat as PBIR-like
        if report_json_path.exists():
            self.report_format = "pbir"
        else:
            self.warnings.append("Could not determine report format (no page subfolders or report.json sections)")

    @property
    def is_valid(self) -> bool:
        """A project is valid if it has at least a .pbip/.pbir or .Report or .SemanticModel."""
        return bool(self.pbip_file or self.pbir_file or self.report_dir or self.semantic_model_dir)


# ---------------------------------------------------------------------------
# Report Metadata Extractor
# ---------------------------------------------------------------------------


class ReportExtractor:
    """Extracts metadata from a .Report folder.

    Transparently handles both:
    - PBIR format: individual page.json + visual.json files per page/visual
    - Legacy PBIP format: single monolithic definition/report.json with sections[]
    """

    def __init__(self, report_dir: Path, report_format: str = "pbir"):
        self.report_dir = report_dir
        self.report_format = report_format
        self.platform: dict | None = None
        self.pbir: dict | None = None
        self.report_json: dict | None = None
        self.version_json: dict | None = None
        self.pages_meta: dict | None = None
        self.pages: list[dict] = []
        self.warnings: list[str] = []

    def extract(self) -> dict:
        """Run full extraction, return structured dict."""
        self.platform = safe_read_json(self.report_dir / ".platform")
        self.pbir = safe_read_json(self.report_dir / "definition.pbir")
        defn = self.report_dir / "definition"
        self.report_json = safe_read_json(defn / "report.json")
        self.version_json = safe_read_json(defn / "version.json")
        self.pages_meta = safe_read_json(defn / "pages" / "pages.json")

        result = {}

        # Platform info
        if self.platform:
            meta = self.platform.get("metadata", {})
            result["display_name"] = meta.get("displayName", UNKNOWN)
            result["type"] = meta.get("type", UNKNOWN)
            cfg = self.platform.get("config", {})
            result["logical_id"] = cfg.get("logicalId", UNKNOWN)
        else:
            self.warnings.append(".platform file missing or unreadable")

        # Dataset reference
        if self.pbir:
            ds_ref = self.pbir.get("datasetReference", {})
            by_path = ds_ref.get("byPath", {})
            if by_path:
                result["dataset_reference_path"] = by_path.get("path", UNKNOWN)
                result["dataset_mode"] = "local"
            by_conn = ds_ref.get("byConnection", {})
            if by_conn:
                result["dataset_mode"] = "live_connection"
                result["dataset_connection"] = {
                    "connection_type": by_conn.get("connectionType", UNKNOWN),
                    "name": by_conn.get("name", UNKNOWN),
                }
                conn_str = by_conn.get("connectionString", "")
                if conn_str:
                    result["dataset_connection"]["connection_string"] = conn_str
                    cat = re.search(r'Initial Catalog="?([^";]+)"?', conn_str, re.IGNORECASE)
                    if cat:
                        result["dataset_connection"]["catalog"] = cat.group(1)
                    ds_match = re.search(r'Data Source="?([^";]+)"?', conn_str, re.IGNORECASE)
                    if ds_match:
                        result["dataset_connection"]["data_source"] = ds_match.group(1)
                    smid = re.search(r'semanticmodelid=([^";]+)', conn_str, re.IGNORECASE)
                    if smid:
                        result["dataset_connection"]["semantic_model_id"] = smid.group(1)
                pbi_db = by_conn.get("pbiModelDatabaseName")
                if pbi_db:
                    result["dataset_connection"]["pbi_model_database"] = pbi_db
            if not by_path and not by_conn:
                result["dataset_reference_path"] = UNKNOWN
        else:
            # Legacy: try to infer dataset reference from report.json
            if self.report_json:
                ds_ref = self.report_json.get("datasetReference", {})
                if ds_ref:
                    result["dataset_reference_path"] = ds_ref.get("byPath", {}).get("path", UNKNOWN)
                    result["dataset_mode"] = "local"
            self.warnings.append("definition.pbir missing — using legacy report.json for dataset ref")

        # Report settings
        if self.report_json:
            result["themes"] = self._extract_themes()
            result["report_filters"] = self._extract_report_filters()
            result["settings"] = self.report_json.get("settings", {})
            result["resource_packages"] = self._extract_resource_packages()
            # Custom visuals
            pcv = self.report_json.get("publicCustomVisuals", [])
            if pcv:
                result["public_custom_visuals"] = pcv
        else:
            self.warnings.append("report.json missing or unreadable")

        # Version
        if self.version_json:
            result["definition_version"] = self.version_json.get("version", UNKNOWN)

        # Pages — route by format
        if self.report_format == "legacy" and self.report_json and "sections" in self.report_json:
            self._extract_pages_legacy(self.report_json)
        else:
            self._extract_pages_pbir(defn / "pages")

        # Pages metadata (page order) from pages.json if available
        if self.pages_meta:
            result["page_order"] = self.pages_meta.get("pageOrder", [])
            result["active_page"] = self.pages_meta.get("activePageName", UNKNOWN)
        result["pages"] = self.pages
        result["total_pages"] = len(self.pages)
        result["total_visuals"] = sum(len(p.get("visuals", [])) for p in self.pages)

        result["bookmarks"] = self._extract_bookmarks(defn / "bookmarks")
        result["dax_queries"] = self._extract_dax_queries(self.report_dir / "DAXQueries")
        result["warnings"] = self.warnings
        result["_report_format"] = self.report_format

        # Cross-reference: which visuals trigger which bookmarks
        self._cross_reference_bookmarks(result["bookmarks"], result.get("pages", []))

        return result

    def _cross_reference_bookmarks(self, bookmarks: list, pages: list):
        """Add triggered_by to each bookmark based on visual actions."""
        if not bookmarks:
            return
        bm_map = {bm["id"]: bm for bm in bookmarks}
        for page in pages:
            page_id = page.get("id", "")
            page_name = page.get("display_name", "")
            for visual in page.get("visuals", []):
                action = visual.get("action")
                if not action:
                    continue
                if action.get("type") == "Bookmark":
                    bm_id = action.get("target_bookmark_id", "")
                    if bm_id and bm_id in bm_map:
                        trigger = {
                            "visual_id": visual.get("id", ""),
                            "visual_type": visual.get("visual_type", ""),
                            "page_id": page_id,
                            "page_name": page_name,
                        }
                        if visual.get("button_text"):
                            trigger["button_text"] = visual["button_text"]
                        if "triggered_by" not in bm_map[bm_id]:
                            bm_map[bm_id]["triggered_by"] = []
                        bm_map[bm_id]["triggered_by"].append(trigger)

    # ── PBIR format: per-page folders ──────────────────────────────────────

    def _extract_pages_pbir(self, pages_dir: Path):
        """Extract pages from PBIR-style per-folder structure."""
        if not pages_dir.is_dir():
            self.warnings.append("pages directory not found")
            return
        page_order = []
        if self.pages_meta:
            page_order = self.pages_meta.get("pageOrder", [])
        page_folders = [d for d in pages_dir.iterdir() if d.is_dir()]
        order_map = {pid: idx for idx, pid in enumerate(page_order)}
        page_folders.sort(key=lambda d: order_map.get(d.name, 999))

        for pf in page_folders:
            page_json = safe_read_json(pf / "page.json")
            if not page_json:
                self.warnings.append(f"Could not read page.json in {pf.name}")
                continue
            page = {
                "id": page_json.get("name", pf.name),
                "display_name": page_json.get("displayName", UNKNOWN),
                "type": page_json.get("type", "Standard"),
                "display_option": page_json.get("displayOption", UNKNOWN),
                "width": page_json.get("width"),
                "height": page_json.get("height"),
            }
            fc = page_json.get("filterConfig", {})
            filters = fc.get("filters", [])
            if filters:
                page["filters"] = self._summarize_filters(filters)
            pb = page_json.get("pageBinding", {})
            if pb:
                page["page_binding_type"] = pb.get("type", UNKNOWN)
            page["visuals"] = self._extract_visuals_pbir(pf / "visuals")
            page["visual_count"] = len(page["visuals"])
            type_counts = {}
            for v in page["visuals"]:
                vt = v.get("visual_type", "unknown")
                type_counts[vt] = type_counts.get(vt, 0) + 1
            page["visual_type_summary"] = type_counts
            vi_raw = page_json.get("visualInteractions", [])
            if vi_raw:
                page["visual_interactions"] = vi_raw
                vi_types = {}
                for vi in vi_raw:
                    vt = vi.get("type", "unknown")
                    vi_types[vt] = vi_types.get(vt, 0) + 1
                page["visual_interaction_summary"] = vi_types
            self.pages.append(page)

    def _extract_visual_link(self, vis: dict) -> dict | None:
        """Extract visual link / action from visualContainerObjects.visualLink."""
        vco = vis.get("visualContainerObjects", {})
        vlinks = vco.get("visualLink", [])
        if not vlinks:
            return None
        vl = vlinks[0]
        props = vl.get("properties", {})

        # Check if show is true
        show_val = ""
        with contextlib.suppress(Exception):
            show_val = props.get("show", {}).get("expr", {}).get("Literal", {}).get("Value", "")
        if show_val.strip("'\"") != "true":
            return None

        action = {}

        # Action type
        try:
            action["type"] = props.get("type", {}).get("expr", {}).get("Literal", {}).get("Value", "").strip("'\"")
        except Exception:
            action["type"] = ""
        if not action["type"]:
            return None

        # Tooltip
        try:
            tooltip = props.get("tooltip", {}).get("expr", {}).get("Literal", {}).get("Value", "")
            if tooltip:
                action["tooltip"] = tooltip.strip("'\"")
        except Exception:
            pass

        # PageNavigation target
        if action["type"] == "PageNavigation":
            try:
                nav = (
                    props.get("navigationSection", {}).get("expr", {}).get("Literal", {}).get("Value", "").strip("'\"")
                )
                if nav:
                    action["target_page_id"] = nav
            except Exception:
                pass

        # Bookmark target
        if action["type"] == "Bookmark":
            try:
                bm = props.get("bookmarks", {}).get("expr", {}).get("Literal", {}).get("Value", "").strip("'\"")
                if bm:
                    action["target_bookmark_id"] = bm
            except Exception:
                pass

        # DataFunction
        if action["type"] == "DataFunction":
            try:
                df_meta = props.get("dataFunction", {}).get("metadata", {}).get("dataFunction", {})
                action["function_name"] = df_meta.get("name", "")
                action["auto_refresh"] = df_meta.get("autoRefresh", False)
                params = []
                for p in df_meta.get("parameters", []):
                    param = {
                        "name": p.get("name", ""),
                        "data_type": p.get("dataType", ""),
                        "is_optional": p.get("isOptional", False),
                    }
                    # Extract value binding (Measure/Column/Literal)
                    val_expr = p.get("value", {}).get("expr", {})
                    if "Measure" in val_expr:
                        m = val_expr["Measure"]
                        src = m.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
                        prop = m.get("Property", "")
                        param["value"] = f"Measure: {src}.{prop}" if src and prop else "Measure"
                    elif "Column" in val_expr:
                        c = val_expr["Column"]
                        src = c.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
                        prop = c.get("Property", "")
                        param["value"] = f"Column: {src}.{prop}" if src and prop else "Column"
                    elif "Literal" in val_expr:
                        param["value"] = val_expr["Literal"].get("Value", "")
                    else:
                        param["value"] = ""
                    params.append(param)
                if params:
                    action["parameters"] = params
            except Exception:
                pass

        return action

    def _extract_button_text(self, vis: dict) -> str:
        """Extract button text label from visual.objects.text[]."""
        try:
            text_objs = vis.get("objects", {}).get("text", [])
            for to in text_objs:
                txt = to.get("properties", {}).get("text", {}).get("expr", {}).get("Literal", {}).get("Value", "")
                if txt:
                    return txt.strip("'\"")
        except Exception:
            pass
        return ""

    def _extract_visuals_pbir(self, visuals_dir: Path) -> list:
        """Extract visuals from PBIR-style per-folder structure."""
        visuals = []
        if not visuals_dir.is_dir():
            return visuals
        for vf in sorted(visuals_dir.iterdir()):
            if not vf.is_dir():
                continue
            vj = safe_read_json(vf / "visual.json")
            if not vj:
                continue
            vis = vj.get("visual", {})
            visual = {
                "id": vj.get("name", vf.name),
                "visual_type": vis.get("visualType", UNKNOWN),
            }
            pos = vj.get("position", {})
            if pos:
                visual["position"] = {
                    "x": pos.get("x"),
                    "y": pos.get("y"),
                    "width": pos.get("width"),
                    "height": pos.get("height"),
                }
            query = vis.get("query", {})
            qs = query.get("queryState", {})
            fields_used = []
            for role_name, role_data in qs.items():
                projections = role_data.get("projections", [])
                for proj in projections:
                    field = proj.get("field", {})
                    qref = proj.get("queryRef", "")
                    field_info = {"role": role_name, "query_ref": qref, "native_ref": proj.get("nativeQueryRef", "")}
                    for ftype in ("Column", "Measure"):
                        if ftype in field:
                            expr = field[ftype].get("Expression", {})
                            src = expr.get("SourceRef", {})
                            field_info["entity"] = src.get("Entity", UNKNOWN)
                            field_info["property"] = field[ftype].get("Property", UNKNOWN)
                            field_info["field_type"] = ftype.lower()
                            break
                    fields_used.append(field_info)
            if fields_used:
                visual["fields"] = fields_used
            if vis.get("visualType", "").lower() in ("slicer", "advancedslicervisual"):
                mode_val = ""
                with contextlib.suppress(Exception):
                    mode_val = (
                        vis.get("objects", {})
                        .get("data", [{}])[0]
                        .get("properties", {})
                        .get("mode", {})
                        .get("expr", {})
                        .get("Literal", {})
                        .get("Value", "")
                    )
                visual["slicer_mode"] = mode_val.strip("'\"") if mode_val else "List"
            vfc = vj.get("filterConfig", {})
            vfilters = vfc.get("filters", [])
            if vfilters:
                visual["filters"] = self._summarize_filters(vfilters)
            # Extract visual link / action
            action = self._extract_visual_link(vis)
            if action:
                visual["action"] = action
            # Extract button text for action buttons
            if vis.get("visualType", "").lower() in ("actionbutton", "button"):
                btn_text = self._extract_button_text(vis)
                if btn_text:
                    visual["button_text"] = btn_text
            visuals.append(visual)
            # Recurse into group children so bookmark targets can resolve their real IDs
            if visual.get("visual_type") == "group":
                for child in vis.get("children", []):
                    cid = child.get("name", "")
                    if not cid:
                        continue
                    child_vis = {
                        "id": cid,
                        "visual_type": child.get("visualType", UNKNOWN),
                    }
                    if child.get("visualType", "").lower() in ("actionbutton", "button"):
                        btn_text = self._extract_button_text(child)
                        if btn_text:
                            child_vis["button_text"] = btn_text
                    visuals.append(child_vis)
        return visuals

    # ── Legacy format: monolithic report.json with sections[] ──────────────

    def _extract_pages_legacy(self, report_json: dict):
        """Extract pages and visuals from old-style monolithic report.json.

        In the legacy format all pages live in report_json["sections"] and
        each page's visuals are in section["visualContainers"].  The visual
        type and query bindings are serialised as JSON-inside-JSON strings
        in the "config" and "query" fields of each visualContainer.
        """
        sections = report_json.get("sections", [])
        for sec in sections:
            page = {
                "id": sec.get("name", UNKNOWN),
                "display_name": sec.get("displayName", UNKNOWN),
                "type": sec.get("displayOption", "Standard"),
                "display_option": sec.get("displayOption", UNKNOWN),
                "width": sec.get("width"),
                "height": sec.get("height"),
            }

            # Page-level filters — stored as JSON string in "filters" field
            raw_filters = sec.get("filters", "[]")
            try:
                filter_list = json.loads(raw_filters) if isinstance(raw_filters, str) else raw_filters
                if filter_list:
                    page["filters"] = self._summarize_filters_legacy(filter_list)
            except Exception:
                pass

            visuals = []
            for vc in sec.get("visualContainers", []):
                visual = self._parse_legacy_visual_container(vc)
                if visual:
                    visuals.append(visual)

            page["visuals"] = visuals
            page["visual_count"] = len(visuals)
            type_counts = {}
            for v in visuals:
                vt = v.get("visual_type", "unknown")
                type_counts[vt] = type_counts.get(vt, 0) + 1
            page["visual_type_summary"] = type_counts

            # Visual interactions (stored at section level in legacy)
            raw_vi = sec.get("visualInteractions", "[]")
            try:
                vi_list = json.loads(raw_vi) if isinstance(raw_vi, str) else raw_vi
                if vi_list:
                    page["visual_interactions"] = vi_list
                    vi_types = {}
                    for vi in vi_list:
                        vt = vi.get("type", "unknown")
                        vi_types[vt] = vi_types.get(vt, 0) + 1
                    page["visual_interaction_summary"] = vi_types
            except Exception:
                pass

            self.pages.append(page)

    def _parse_legacy_visual_container(self, vc: dict) -> dict | None:
        """Parse one visualContainer from legacy report.json.

        The config, query, and dataTransforms fields are JSON-encoded strings.
        """
        # Config: contains visualType, name, etc.
        config_raw = vc.get("config", "{}")
        try:
            config = json.loads(config_raw) if isinstance(config_raw, str) else config_raw
        except Exception:
            config = {}

        visual_type = UNKNOWN
        visual_id = UNKNOWN

        # Type lives at config.singleVisual.visualType
        sv = config.get("singleVisual", {})
        if sv:
            visual_type = sv.get("visualType", UNKNOWN)
        visual_id = config.get("name", vc.get("id", UNKNOWN))

        visual = {
            "id": visual_id,
            "visual_type": visual_type,
            "position": {
                "x": vc.get("x"),
                "y": vc.get("y"),
                "width": vc.get("width"),
                "height": vc.get("height"),
            },
        }

        # Query bindings — in "query" field as JSON string
        query_raw = vc.get("query", "{}")
        try:
            query_obj = json.loads(query_raw) if isinstance(query_raw, str) else query_raw
        except Exception:
            query_obj = {}

        fields_used = []
        qs = query_obj.get("Commands", [])
        # Also try the queryState path used by some legacy versions
        for cmd in qs:
            query_state = cmd.get("SemanticQueryDataShapeCommand", {}).get("Query", {}).get("Select", [])
            for sel in query_state:
                prop = UNKNOWN
                entity = UNKNOWN
                role = sel.get("Name", "")
                if "Column" in sel:
                    col = sel["Column"]
                    prop = col.get("Property", UNKNOWN)
                    entity = col.get("Expression", {}).get("SourceRef", {}).get("Entity", UNKNOWN)
                    field_type = "column"
                elif "Measure" in sel:
                    meas = sel["Measure"]
                    prop = meas.get("Property", UNKNOWN)
                    entity = meas.get("Expression", {}).get("SourceRef", {}).get("Entity", UNKNOWN)
                    field_type = "measure"
                else:
                    continue
                fields_used.append(
                    {
                        "role": role,
                        "entity": entity,
                        "property": prop,
                        "field_type": field_type,
                        "query_ref": f"{entity}.{prop}",
                    }
                )
        if fields_used:
            visual["fields"] = fields_used

        if visual_type.lower() in ("slicer", "advancedslicervisual"):
            mode_val = ""
            with contextlib.suppress(Exception):
                mode_val = (
                    sv.get("objects", {})
                    .get("data", [{}])[0]
                    .get("properties", {})
                    .get("mode", {})
                    .get("expr", {})
                    .get("Literal", {})
                    .get("Value", "")
                )
            visual["slicer_mode"] = mode_val.strip("'\"") if mode_val else "List"

        # Visual-level filters
        vf_raw = vc.get("filters", "[]")
        try:
            vf_list = json.loads(vf_raw) if isinstance(vf_raw, str) else vf_raw
            if vf_list:
                visual["filters"] = self._summarize_filters_legacy(vf_list)
        except Exception:
            pass

        # Visual link / action from config
        try:
            vlinks = sv.get("visualContainerObjects", {}).get("visualLink", [])
            if vlinks:
                vl = vlinks[0]
                props = vl.get("properties", {})
                show_val = props.get("show", {}).get("expr", {}).get("Literal", {}).get("Value", "")
                if show_val.strip("'\"") == "true":
                    action = {
                        "type": props.get("type", {}).get("expr", {}).get("Literal", {}).get("Value", "").strip("'\"")
                    }
                    if action["type"] == "PageNavigation":
                        nav = (
                            props.get("navigationSection", {})
                            .get("expr", {})
                            .get("Literal", {})
                            .get("Value", "")
                            .strip("'\"")
                        )
                        if nav:
                            action["target_page_id"] = nav
                    elif action["type"] == "Bookmark":
                        bm = props.get("bookmarks", {}).get("expr", {}).get("Literal", {}).get("Value", "").strip("'\"")
                        if bm:
                            action["target_bookmark_id"] = bm
                    elif action["type"] == "DataFunction":
                        df_meta = props.get("dataFunction", {}).get("metadata", {}).get("dataFunction", {})
                        action["function_name"] = df_meta.get("name", "")
                        action["auto_refresh"] = df_meta.get("autoRefresh", False)
                        params = []
                        for p in df_meta.get("parameters", []):
                            param = {
                                "name": p.get("name", ""),
                                "data_type": p.get("dataType", ""),
                                "is_optional": p.get("isOptional", False),
                            }
                            val_expr = p.get("value", {}).get("expr", {})
                            if "Measure" in val_expr:
                                m = val_expr["Measure"]
                                src = m.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
                                prop = m.get("Property", "")
                                param["value"] = f"Measure: {src}.{prop}" if src and prop else "Measure"
                            elif "Column" in val_expr:
                                c = val_expr["Column"]
                                src = c.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
                                prop = c.get("Property", "")
                                param["value"] = f"Column: {src}.{prop}" if src and prop else "Column"
                            elif "Literal" in val_expr:
                                param["value"] = val_expr["Literal"].get("Value", "")
                            else:
                                param["value"] = ""
                            params.append(param)
                        if params:
                            action["parameters"] = params
                    if action.get("type"):
                        visual["action"] = action
        except Exception:
            pass

        # Button text from config
        try:
            text_objs = sv.get("objects", {}).get("text", [])
            for to in text_objs:
                txt = to.get("properties", {}).get("text", {}).get("expr", {}).get("Literal", {}).get("Value", "")
                if txt:
                    visual["button_text"] = txt.strip("'\"")
                    break
        except Exception:
            pass

        return visual

    def _summarize_filters_legacy(self, filters: list) -> list:
        """Summarise filters from legacy JSON-in-JSON format."""
        summaries = []
        for f in filters:
            # Legacy filters have "expression" as a nested object
            expr = f.get("expression", {})
            s = {"type": f.get("howCreated", f.get("type", UNKNOWN))}
            for ftype in ("Column", "Measure"):
                if ftype in expr:
                    src = expr[ftype].get("Expression", {}).get("SourceRef", {})
                    s["entity"] = src.get("Entity", UNKNOWN)
                    s["property"] = expr[ftype].get("Property", UNKNOWN)
                    s["field_type"] = ftype.lower()
                    break
            summaries.append(s)
        return summaries

    # ── Shared helpers ──────────────────────────────────────────────────────

    def _summarize_filters(self, filters: list) -> list:
        """Summarise filters from PBIR format."""
        summaries = []
        for f in filters:
            s = {"type": f.get("type", UNKNOWN)}
            field = f.get("field", {})
            for ftype in ("Column", "Measure"):
                if ftype in field:
                    expr = field[ftype].get("Expression", {})
                    src = expr.get("SourceRef", {})
                    s["entity"] = src.get("Entity", UNKNOWN)
                    s["property"] = field[ftype].get("Property", UNKNOWN)
                    s["field_type"] = ftype.lower()
                    break
            if f.get("howCreated"):
                s["how_created"] = f["howCreated"]
            if f.get("isHiddenInViewMode"):
                s["hidden"] = True
            summaries.append(s)
        return summaries

    def _extract_bookmarks(self, bookmarks_dir: Path) -> list:
        bookmarks = []
        if not bookmarks_dir.is_dir():
            return bookmarks
        meta = safe_read_json(bookmarks_dir / "bookmarks.json")

        # Build group lookup from metadata
        group_map = {}  # bookmark_id -> group_name
        child_to_parent = {}  # child_id -> parent_id

        if meta:
            for group in meta.get("groups", []):
                gid = group.get("name", "")
                gname = group.get("displayName", gid)
                for child in group.get("children", []):
                    cid = child.get("name", "")
                    group_map[cid] = gname
                    child_to_parent[cid] = gid

        for bf in sorted(bookmarks_dir.glob("*.bookmark.json")):
            bdata = safe_read_json(bf)
            if not bdata:
                continue
            bm = {
                "id": bdata.get("name", bf.stem),
                "display_name": bdata.get("displayName", UNKNOWN),
            }
            opts = bdata.get("options", {})
            targets = opts.get("targetVisualNames", [])
            if targets:
                bm["target_visuals"] = targets
            exp = bdata.get("explorationState", {})
            if exp.get("activeSection"):
                bm["active_section"] = exp["activeSection"]
            filters = exp.get("filters", {})
            filter_entities = set()
            for fgroup in filters.get("byExpr", []) + filters.get("byColumn", []):
                expr = fgroup.get("expression", {})
                for ftype in ("Column", "Measure"):
                    if ftype in expr:
                        src = expr[ftype].get("Expression", {}).get("SourceRef", {})
                        ent = src.get("Entity")
                        if ent:
                            filter_entities.add(ent)
            if filter_entities:
                bm["filter_entities"] = sorted(filter_entities)
            # Group info
            bid = bm["id"]
            if bid in group_map:
                bm["group"] = group_map[bid]
                bm["is_group"] = False
            if bid in child_to_parent:
                bm["parent_group_id"] = child_to_parent[bid]
            # triggered_by populated later by _cross_reference_bookmarks
            bookmarks.append(bm)
        return bookmarks

    def _extract_dax_queries(self, dax_dir: Path) -> list:
        queries = []
        if not dax_dir.is_dir():
            return queries
        for df in sorted(dax_dir.glob("*.dax")):
            content = safe_read_text(df)
            q = {"name": df.stem, "file": df.name}
            if content:
                lines = [l for l in content.strip().split("\n") if not l.strip().startswith("//")]
                q["expression"] = "\n".join(lines).strip()
                q["total_lines"] = len(content.strip().split("\n"))
            queries.append(q)
        return queries

    def _extract_themes(self) -> dict:
        tc = self.report_json.get("themeCollection", {})
        themes = {}
        bt = tc.get("baseTheme", {})
        if bt:
            themes["base_theme"] = bt.get("name", UNKNOWN)
        ct = tc.get("customTheme", {})
        if ct:
            themes["custom_theme"] = ct.get("name", UNKNOWN)
        return themes

    def _extract_report_filters(self) -> list:
        fc = self.report_json.get("filterConfig", {})
        return self._summarize_filters(fc.get("filters", []))

    def _extract_resource_packages(self) -> list:
        rps = self.report_json.get("resourcePackages", [])
        summaries = []
        for rp in rps:
            pkg = {"name": rp.get("name"), "type": rp.get("type")}
            items = []
            for item in rp.get("items", []):
                items.append({"name": item.get("name"), "type": item.get("type")})
            pkg["items"] = items
            summaries.append(pkg)
        return summaries


# ---------------------------------------------------------------------------
# Semantic Model Extractor
# ---------------------------------------------------------------------------


class SemanticModelExtractor:
    """Extracts metadata from a .SemanticModel folder."""

    def __init__(self, sm_dir: Path):
        self.sm_dir = sm_dir
        self.warnings: list[str] = []

    def extract(self) -> dict:
        result = {}

        platform = safe_read_json(self.sm_dir / ".platform")
        if platform:
            meta = platform.get("metadata", {})
            result["display_name"] = meta.get("displayName", UNKNOWN)
            result["type"] = meta.get("type", UNKNOWN)
            cfg = platform.get("config", {})
            result["logical_id"] = cfg.get("logicalId", UNKNOWN)
        else:
            self.warnings.append(".platform file missing or unreadable in SemanticModel")

        pbism = safe_read_json(self.sm_dir / "definition.pbism")
        if pbism:
            result["pbism_version"] = pbism.get("version", UNKNOWN)
        else:
            self.warnings.append("definition.pbism missing or unreadable")

        db_text = safe_read_text(self.sm_dir / "definition" / "database.tmdl")
        if db_text:
            cl = re.search(r"compatibilityLevel:\s*(\d+)", db_text)
            if cl:
                result["compatibility_level"] = int(cl.group(1))
        else:
            self.warnings.append("database.tmdl missing")

        model_text = safe_read_text(self.sm_dir / "definition" / "model.tmdl")
        model_info = TmdlParser.parse_model(model_text)
        result["model"] = model_info

        rel_text = safe_read_text(self.sm_dir / "definition" / "relationships.tmdl")
        result["relationships"] = TmdlParser.parse_relationships(rel_text)

        expr_text = safe_read_text(self.sm_dir / "definition" / "expressions.tmdl")
        result["expressions"] = TmdlParser.parse_expressions(expr_text)

        func_text = safe_read_text(self.sm_dir / "definition" / "functions.tmdl")
        funcs = TmdlParser.parse_functions(func_text)

        # If functions.tmdl yielded nothing, search broader in the semantic model
        if not funcs:
            # Search JSON files
            for json_file in self.sm_dir.rglob("*.json"):
                try:
                    data = safe_read_json(json_file)
                    if isinstance(data, dict):
                        found = TmdlParser.parse_functions_from_json(data)
                        if found:
                            funcs.extend(found)
                except Exception:
                    pass

            # Search .md and .txt files
            for ext in ("*.md", "*.txt"):
                for text_file in self.sm_dir.rglob(ext):
                    text = safe_read_text(text_file)
                    if text:
                        found = TmdlParser.parse_functions_from_md(text)
                        if found:
                            funcs.extend(found)

        # Deduplicate by name
        seen = set()
        deduped = []
        for f in funcs:
            if f["name"] not in seen:
                seen.add(f["name"])
                deduped.append(f)
        result["functions"] = deduped

        all_sources = set()
        for expr in result["expressions"]:
            for src in expr.get("data_sources", []):
                all_sources.add(src)
        result["data_sources"] = sorted(all_sources)

        tables_dir = self.sm_dir / "definition" / "tables"
        result["tables"] = []
        if tables_dir.is_dir():
            for tf in sorted(tables_dir.glob("*.tmdl")):
                ttext = safe_read_text(tf)
                tdata = TmdlParser.parse_table(ttext)
                tdata["file"] = tf.name
                result["tables"].append(tdata)
        else:
            self.warnings.append("tables directory not found")

        result["table_count"] = len(result["tables"])
        result["total_columns"] = sum(len(t.get("columns", [])) for t in result["tables"])
        result["total_measures"] = sum(len(t.get("measures", [])) for t in result["tables"])
        result["partition_count"] = sum(len(t.get("partitions", [])) for t in result["tables"])
        result["hierarchy_count"] = sum(len(t.get("hierarchies", [])) for t in result["tables"])
        result["calculation_item_count"] = sum(len(t.get("calculation_items", [])) for t in result["tables"])
        result["relationship_count"] = len(result["relationships"])
        result["expression_count"] = len(result["expressions"])
        result["function_count"] = len(result["functions"])

        cultures_dir = self.sm_dir / "definition" / "cultures"
        result["cultures"] = []
        if cultures_dir.is_dir():
            for cf in cultures_dir.glob("*.tmdl"):
                result["cultures"].append(cf.stem)

        roles_dir = self.sm_dir / "definition" / "roles"
        result["roles"] = []
        if roles_dir.is_dir():
            for rf in sorted(roles_dir.glob("*.tmdl")):
                rtext = safe_read_text(rf)
                rdata = TmdlParser.parse_role(rtext)
                rdata["file"] = rf.name
                result["roles"].append(rdata)
        result["role_count"] = len(result["roles"])
        result["has_rls"] = any(r.get("table_permissions") for r in result["roles"])
        result["parser_mode"] = "python_fallback"
        result["parser_warnings"] = list(self.warnings)
        result["parser_confidence"] = estimate_parser_confidence(result)

        diagram = safe_read_json(self.sm_dir / "diagramLayout.json")
        if diagram:
            nodes = []
            for d in diagram.get("diagrams", []):
                for n in d.get("nodes", []):
                    nodes.append(n.get("nodeIndex", UNKNOWN))
            result["diagram_tables"] = nodes

        result["warnings"] = self.warnings
        return result


# ---------------------------------------------------------------------------
# Output Generators
# ---------------------------------------------------------------------------


def build_project_summary(project: PbipProject) -> dict:
    """Build the full project-summary structure."""
    summary = {
        "_generator": "copiloter.py",
        "_version": VERSION,
        "_generated_at": timestamp_iso(),
        "project_name": project.name,
        "project_path": rel(project.project_dir),
        "pbip_file": project.pbip_file.name if project.pbip_file else None,
    }

    if project.pbip_data:
        summary["pbip_schema"] = project.pbip_data.get("$schema")
        summary["pbip_version"] = project.pbip_data.get("version")
        summary["pbip_artifacts"] = project.pbip_data.get("artifacts", [])
        settings = project.pbip_data.get("settings", {})
        if settings:
            summary["pbip_settings"] = settings

    if project.report_dir:
        extractor = ReportExtractor(project.report_dir, project.report_format)
        summary["report"] = extractor.extract()
    else:
        summary["report"] = None

    if project.semantic_model_dir:
        extractor = SemanticModelExtractor(project.semantic_model_dir)
        summary["semantic_model"] = extractor.extract()
    else:
        summary["semantic_model"] = None

    sm = summary.get("semantic_model") or {}
    if sm:
        sm.setdefault("parser_mode", "python_fallback")
        sm.setdefault("parser_warnings", list(sm.get("warnings", []) or []))
        sm.setdefault("parser_confidence", estimate_parser_confidence(sm))
        sm.setdefault("partition_count", sum(len(t.get("partitions", [])) for t in sm.get("tables", [])))
        sm.setdefault("hierarchy_count", sum(len(t.get("hierarchies", [])) for t in sm.get("tables", [])))
        sm.setdefault("calculation_item_count", sum(len(t.get("calculation_items", [])) for t in sm.get("tables", [])))
        sm.setdefault("has_rls", any((r.get("table_permissions") or []) for r in sm.get("roles", [])))
        for role in sm.get("roles", []):
            role.setdefault("tables", [tp.get("table") for tp in role.get("table_permissions", []) if tp.get("table")])
            role.setdefault("filtered_table_count", len(role.get("table_permissions", []) or []))
            role.setdefault("has_rls", bool(role.get("table_permissions")))
            role.setdefault("role_filter_complexity", "low" if role.get("table_permissions") else "none")
        for table in sm.get("tables", []):
            table.setdefault("hierarchies", [])
            table.setdefault("calculation_items", [])
            table.setdefault("hierarchy_count", len(table.get("hierarchies", [])))
            table.setdefault("calculation_item_count", len(table.get("calculation_items", [])))
            table.setdefault("is_calculation_group", bool(table.get("calculation_items")))

    summary["completeness"] = assess_completeness(summary)
    summary["project_warnings"] = project.warnings

    return summary


def assess_completeness(summary: dict) -> dict:
    checks = {}
    rpt = summary.get("report")
    sm = summary.get("semantic_model")
    dataset_mode = (rpt or {}).get("dataset_mode", "unknown")

    if dataset_mode != "live_connection":
        checks["has_pbip_file"] = summary.get("pbip_file") is not None
        checks["has_semantic_model"] = sm is not None
    checks["has_report"] = rpt is not None

    if rpt:
        checks["has_report_pages"] = rpt.get("total_pages", 0) > 0
        checks["has_report_visuals"] = rpt.get("total_visuals", 0) > 0
        has_path = rpt.get("dataset_reference_path", UNKNOWN) != UNKNOWN
        has_conn = bool(rpt.get("dataset_connection"))
        checks["has_dataset_reference"] = has_path or has_conn
        checks["has_themes"] = bool(rpt.get("themes"))
        if rpt.get("bookmarks"):
            checks["has_bookmarks"] = True
        if rpt.get("dax_queries"):
            checks["has_dax_queries"] = True

    if sm:
        checks["has_tables"] = sm.get("table_count", 0) > 0
        checks["has_measures"] = sm.get("total_measures", 0) > 0
        checks["has_relationships"] = sm.get("relationship_count", 0) > 0
        checks["has_expressions"] = sm.get("expression_count", 0) > 0
        checks["has_data_sources"] = len(sm.get("data_sources", [])) > 0

    found = sum(1 for v in checks.values() if v)
    total = len(checks)
    checks["score"] = f"{found}/{total}"
    checks["percent"] = round(found / total * 100) if total else 0
    return checks


# ---------------------------------------------------------------------------
# Markdown Generators
# ---------------------------------------------------------------------------


def generate_copilot_input_md(summary: dict) -> str:
    """Generate copilot-input.md — optimized for AI/Copilot consumption."""
    rpt = summary.get("report") or {}
    sm = summary.get("semantic_model") or {}

    lines = []
    lines.append(f"# {summary['project_name']}")
    lines.append("")
    lines.append(f"Generated by copiloter.py v{VERSION} on {summary['_generated_at']}")
    if rpt.get("_report_format"):
        lines.append(f"Report format: {rpt['_report_format']}")
    lines.append("")

    comp = summary.get("completeness", {})
    lines.append(f"## Completeness: {comp.get('score', '?')} ({comp.get('percent', 0)}%)")
    lines.append("")
    for k, v in comp.items():
        if k in ("score", "percent"):
            continue
        icon = "+" if v else "-"
        lines.append(f"  {icon} {k}")
    lines.append("")

    warnings = summary.get("project_warnings", [])
    rpt_warnings = rpt.get("warnings", [])
    sm_warnings = sm.get("warnings", [])
    all_warnings = warnings + rpt_warnings + sm_warnings
    if all_warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in all_warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("## Project Configuration")
    lines.append("")
    lines.append(f"- PBIP file: {summary.get('pbip_file', 'N/A')}")
    lines.append(f"- PBIP version: {summary.get('pbip_version', 'N/A')}")
    if rpt:
        lines.append(f"- Report display name: {rpt.get('display_name', UNKNOWN)}")
        lines.append(f"- Report logical ID: {rpt.get('logical_id', UNKNOWN)}")
        lines.append(f"- Definition version: {rpt.get('definition_version', UNKNOWN)}")
        themes = rpt.get("themes", {})
        if themes:
            lines.append(f"- Base theme: {themes.get('base_theme', UNKNOWN)}")
            lines.append(f"- Custom theme: {themes.get('custom_theme', UNKNOWN)}")
        dc = rpt.get("dataset_connection", {})
        if dc:
            lines.append("- Dataset mode: live_connection")
            if dc.get("catalog"):
                lines.append(f"- Remote catalog: {dc['catalog']}")
            if dc.get("data_source"):
                lines.append(f"- Remote data source: {dc['data_source']}")
            if dc.get("connection_type"):
                lines.append(f"- Connection type: {dc['connection_type']}")
            if dc.get("semantic_model_id"):
                lines.append(f"- Semantic model ID: {dc['semantic_model_id']}")
            if dc.get("pbi_model_database"):
                lines.append(f"- PBI model database: {dc['pbi_model_database']}")
        elif rpt.get("dataset_reference_path"):
            lines.append("- Dataset mode: local")
            lines.append(f"- Dataset reference: {rpt.get('dataset_reference_path')}")
    if sm:
        lines.append(f"- Semantic model display name: {sm.get('display_name', UNKNOWN)}")
        lines.append(f"- Semantic model logical ID: {sm.get('logical_id', UNKNOWN)}")
        lines.append(f"- Compatibility level: {sm.get('compatibility_level', UNKNOWN)}")
        lines.append(f"- Culture: {sm.get('model', {}).get('culture', UNKNOWN)}")
        cultures = sm.get("cultures", [])
        if cultures:
            lines.append(f"- Cultures: {', '.join(cultures)}")
    lines.append("")

    lines.append("## Quick Facts")
    lines.append("")
    lines.append(f"- Report pages: {rpt.get('total_pages', 0)}")
    lines.append(f"- Total visuals: {rpt.get('total_visuals', 0)}")
    lines.append(f"- Semantic model tables: {sm.get('table_count', 0)}")
    lines.append(f"- Total columns: {sm.get('total_columns', 0)}")
    lines.append(f"- DAX measures: {sm.get('total_measures', 0)}")
    lines.append(f"- Relationships: {sm.get('relationship_count', 0)}")
    lines.append(f"- M/Power Query expressions: {sm.get('expression_count', 0)}")
    lines.append(f"- Bookmarks: {len(rpt.get('bookmarks', []))}")
    lines.append(f"- DAX queries: {len(rpt.get('dax_queries', []))}")
    mode = rpt.get("dataset_mode", "unknown")
    lines.append(f"- Dataset mode: {mode}")
    dc = rpt.get("dataset_connection", {})
    if dc.get("catalog"):
        lines.append(f"- Remote catalog: {dc['catalog']}")
    if dc.get("data_source"):
        lines.append(f"- Remote data source: {dc['data_source']}")
    ds = sm.get("data_sources", [])
    if ds:
        lines.append(f"- Data sources: {', '.join(ds)}")
    lines.append("")

    if sm.get("tables"):
        lines.append("## Data Model Schema")
        lines.append("")
        dims, facts, others = [], [], []
        for t in sm["tables"]:
            name = t.get("name", "?")
            if name.upper().startswith("DIM"):
                dims.append(t)
            elif name.upper().startswith("FACT"):
                facts.append(t)
            else:
                others.append(t)

        def _render_table_block(tables, label):
            lines.append(f"### {label}")
            lines.append("")
            for t in tables:
                hidden = " [HIDDEN]" if t.get("is_hidden") else ""
                cat = f" [DataCategory: {t['data_category']}]" if t.get("data_category") else ""
                lines.append(f"#### {t['name']}{hidden}{cat}")
                lines.append("")
                cols = t.get("columns", [])
                if cols:
                    lines.append("| Column | Type | Key | SummarizeBy |")
                    lines.append("|--------|------|-----|-------------|")
                    for c in cols:
                        key = "PK" if c.get("is_key") else ""
                        sbc = c.get("sort_by_column", "")
                        sb = c.get("summarize_by", "")
                        extra = f" (sort: {sbc})" if sbc else ""
                        lines.append(f"| {c['name']} | {c.get('data_type', '?')} | {key} | {sb}{extra} |")
                    lines.append("")
                meas = t.get("measures", [])
                if meas:
                    lines.append(f"Measures: {', '.join(m['name'] for m in meas)}")
                    lines.append("")

        if facts:
            _render_table_block(facts, "Fact Tables")
        if dims:
            _render_table_block(dims, "Dimension Tables")
        if others:
            _render_table_block(others, "Other Tables")

    roles = sm.get("roles", [])
    if roles:
        lines.append("## Row Level Security (RLS)")
        lines.append("")
        lines.append(f"**Total Roles:** {len(roles)}")
        lines.append("")
        for role in roles:
            role_name = role.get("name", "Unnamed")
            model_perm = role.get("model_permission", "read")
            lines.append(f"### Role: {role_name}")
            lines.append("")
            lines.append(f"- **Model Permission:** {model_perm}")
            table_perms = role.get("table_permissions", [])
            if table_perms:
                lines.append("- **Table Filters:**")
                for tp in table_perms:
                    table_name = tp.get("table", "Unknown")
                    filter_expr = tp.get("filter", "None")
                    # Check if expression is multi-line
                    if "\n" in filter_expr:
                        lines.append(f"  - `{table_name}`:")
                        lines.append("    ```dax")
                        # Indent each line for proper markdown code block
                        for line in filter_expr.split("\n"):
                            lines.append(f"    {line}")
                        lines.append("    ```")
                    else:
                        lines.append(f"  - `{table_name}`: `{filter_expr}`")
            else:
                lines.append("- **Table Filters:** None (full access to all tables)")
            lines.append("")

    rels = sm.get("relationships", [])
    if rels:
        lines.append("## Relationships")
        lines.append("")
        for r in rels:
            fr = f"{r.get('from_table', '?')}.{r.get('from_field', '?')}"
            to = f"{r.get('to_table', '?')}.{r.get('to_field', '?')}"
            lines.append(f"- {fr} -> {to}")
        lines.append("")

    all_measures = []
    for t in sm.get("tables", []):
        for m_item in t.get("measures", []):
            all_measures.append({**m_item, "table": t.get("name", "?")})
    if all_measures:
        lines.append("## DAX Measures")
        lines.append("")
        for m_item in all_measures:
            fmt_str = f" [{m_item['format_string']}]" if m_item.get("format_string") else ""
            lines.append(f"### {m_item['table']}.{m_item['name']}{fmt_str}")
            lines.append("")
            if m_item.get("expression"):
                lines.append("```dax")
                lines.append(m_item["expression"])
                lines.append("```")
                lines.append("")

    if rpt.get("pages"):
        lines.append("## Report Pages & Visuals")
        lines.append("")
        for page in rpt["pages"]:
            ptype_str = f" [{page['type']}]" if page.get("type", "Standard") != "Standard" else ""
            lines.append(f"### {page['display_name']}{ptype_str}")
            lines.append("")
            lines.append(f"- ID: {page['id']}")
            lines.append(f"- Dimensions: {page.get('width')}x{page.get('height')}, {page.get('display_option', '?')}")
            if page.get("page_binding_type"):
                lines.append(f"- Page binding: {page['page_binding_type']}")
            vts = page.get("visual_type_summary", {})
            if vts:
                lines.append(f"- Visual composition: {', '.join(f'{t}({c})' for t, c in sorted(vts.items()))}")
            lines.append("")

            pf = page.get("filters", [])
            if pf:
                lines.append("Page filters:")
                for flt in pf:
                    ent = flt.get("entity", "")
                    prop = flt.get("property", "")
                    lines.append(f"  - {ent}.{prop} ({flt.get('type', '?')})")
                lines.append("")

            vis_int = page.get("visual_interaction_summary", {})
            if vis_int:
                lines.append(f"Cross-filter overrides: {', '.join(f'{t}({c})' for t, c in sorted(vis_int.items()))}")
                lines.append("")
            vi_list = page.get("visual_interactions", [])
            if vi_list:
                for vi in vi_list:
                    lines.append(f"  {vi.get('source', '?')} -> {vi.get('target', '?')}: {vi.get('type', '?')}")
                lines.append("")

            for vis in page.get("visuals", []):
                vtype = vis.get("visual_type", "?")
                vid = vis.get("id", "?")
                pos = vis.get("position", {})
                pos_str = ""
                if pos and pos.get("x") is not None:
                    pos_str = f" @ ({pos.get('x', 0):.0f},{pos.get('y', 0):.0f} {pos.get('width', 0):.0f}x{pos.get('height', 0):.0f})"
                if vis.get("fields"):
                    field_strs = []
                    for f in vis["fields"]:
                        entity = f.get("entity", "")
                        prop = f.get("property", "")
                        role = f.get("role", "")
                        field_strs.append(f"{entity}.{prop} ({role})")
                    lines.append(f"- **{vtype}** [{vid}]{pos_str}: {'; '.join(field_strs)}")
                else:
                    lines.append(f"- **{vtype}** [{vid}]{pos_str} (no data bindings)")
                vf = vis.get("filters", [])
                if vf:
                    for flt in vf:
                        ent = flt.get("entity", "")
                        prop = flt.get("property", "")
                        lines.append(f"    filter: {ent}.{prop} ({flt.get('type', '?')})")
            lines.append("")

    if sm.get("tables"):
        has_partitions = any(
            p.get("m_expression") or p.get("calculated_dax") for t in sm["tables"] for p in t.get("partitions", [])
        )
        if has_partitions:
            lines.append("## Table Load Queries (M / DAX)")
            lines.append("")
            for t in sm["tables"]:
                for p in t.get("partitions", []):
                    m_code = p.get("m_expression", "")
                    calc_dax = p.get("calculated_dax", "")
                    if m_code:
                        mode = p.get("mode", "?")
                        lines.append(f"### {t['name']} (partition: {p['name']}, mode: {mode})")
                        lines.append("")
                        lines.append("```m")
                        lines.append(m_code)
                        lines.append("```")
                        lines.append("")
                    elif calc_dax:
                        lines.append(f"### {t['name']} (calculated table)")
                        lines.append("")
                        lines.append("```dax")
                        lines.append(calc_dax)
                        lines.append("```")
                        lines.append("")

    bmarks = rpt.get("bookmarks", [])
    if bmarks:
        lines.append("## Bookmarks")
        lines.append("")
        for bm in bmarks:
            fe = f" -- filters: {', '.join(bm['filter_entities'])}" if bm.get("filter_entities") else ""
            lines.append(f"- **{bm['display_name']}**{fe}")
        lines.append("")

    dqs = rpt.get("dax_queries", [])
    if dqs:
        lines.append("## DAX Queries (authored)")
        lines.append("")
        for dq in dqs:
            lines.append(f"### {dq['name']}")
            if dq.get("expression"):
                lines.append("```dax")
                lines.append(dq["expression"])
                lines.append("```")
            lines.append("")

    exprs = sm.get("expressions", [])
    if exprs:
        lines.append("## Power Query / M Expressions")
        lines.append("")
        for expr in exprs:
            rt = f" [{expr['result_type']}]" if expr.get("result_type") else ""
            lines.append(f"### {expr['name']}{rt}")
            if expr.get("data_sources"):
                lines.append(f"  Sources: {', '.join(expr['data_sources'])}")
            if expr.get("expression"):
                lines.append("```m")
                lines.append(expr["expression"])
                lines.append("```")
            lines.append("")

    rps = rpt.get("resource_packages", [])
    if rps:
        lines.append("## Resource Packages")
        lines.append("")
        for rp in rps:
            lines.append(f"- **{rp.get('name')}** ({rp.get('type')})")
            for item in rp.get("items", []):
                lines.append(f"  - {item.get('name')} [{item.get('type')}]")
        lines.append("")

    return "\n".join(lines)


def generate_manifest(project_name: str, output_dir: Path, files_written: list) -> dict:
    manifest = {
        "_generator": "copiloter.py",
        "_version": VERSION,
        "_generated_at": timestamp_iso(),
        "project_name": project_name,
        "output_directory": rel(output_dir),
        "files": [],
    }
    for fpath in files_written:
        p = Path(fpath)
        entry = {
            "filename": p.name,
            "path": rel(p),
            "size_bytes": p.stat().st_size if p.exists() else 0,
            "sha256": file_hash(p),
        }
        manifest["files"].append(entry)
    return manifest


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def process_project(project_dir: Path, emit_files: bool = False, export_root: Path | None = None) -> dict:
    """Process a single PBIP/PBIR project folder.

    Default behavior is metadata-only (no sidecar files written).
    When emit_files=True, files are written under:
        <repo-root>/Exported Documents/<ProjectName>/
    """
    project = PbipProject(project_dir)
    if not project.is_valid:
        print(f"  SKIP: {project.name} (not a valid PBIP/PBIR project)")
        return {"project": project.name, "status": "skipped", "reason": "not a valid PBIP/PBIR structure"}

    fmt = f" [{project.report_format}]" if project.report_format != "unknown" else ""
    print(f"  Processing: {project.name}{fmt}")

    summary = build_project_summary(project)
    files_written = []
    output_dir = None

    if emit_files:
        resolved_export_root = export_root or _resolve_export_root()
        output_dir = resolved_export_root / project.name
        output_dir.mkdir(parents=True, exist_ok=True)

        if EMIT_JSON:
            json_path = output_dir / "project-summary.json"
            write_json(json_path, summary)
            files_written.append(json_path)
            print(f"    -> {json_path.name}")

        copilot_path = output_dir / "copilot-input.md"
        copilot_content = generate_copilot_input_md(summary)
        write_text(copilot_path, copilot_content)
        files_written.append(copilot_path)
        print(f"    -> {copilot_path.name}")

        if EMIT_MANIFEST:
            manifest_path = output_dir / "manifest.json"
            manifest = generate_manifest(project.name, output_dir, files_written)
            write_json(manifest_path, manifest)
            files_written.append(manifest_path)
            print(f"    -> {manifest_path.name}")

    comp = summary.get("completeness", {})
    print(f"    Completeness: {comp.get('score', '?')} ({comp.get('percent', 0)}%)")
    if project.warnings:
        for w in project.warnings:
            print(f"    WARNING: {w}")

    return {
        "project": project.name,
        "status": "ok",
        "output_dir": rel(output_dir) if output_dir else None,
        "files": [rel(f) for f in files_written],
        "completeness": comp,
    }


def main():
    import argparse as _ap

    parser = _ap.ArgumentParser(description="PBIP/PBIR metadata extractor")
    parser.add_argument(
        "reports_dir",
        nargs="?",
        default=None,
        help="Path to folder containing PBIP project subfolders (default: ./Reports/ next to script, or $PBIP_REPORTS env var)",
    )
    parser.add_argument(
        "--emit-files",
        action="store_true",
        help="Write Copiloter sidecar outputs to <repo-root>/Exported Documents/<ProjectName>/",
    )
    parser.add_argument(
        "--export-root", default=None, help="Override the default export root (default: <repo-root>/Exported Documents)"
    )
    args = parser.parse_args()

    global REPORTS_DIR
    REPORTS_DIR = _resolve_reports_dir(args.reports_dir)
    export_root = _resolve_export_root(args.export_root)

    print(f"copiloter.py v{VERSION}")
    print(f"Script directory: {SCRIPT_DIR}")
    print(f"Reports directory: {REPORTS_DIR}")
    if args.emit_files:
        print(f"Export root: {export_root}")
    else:
        print("Export root: disabled (metadata-only mode; no files written)")
    print()

    if not REPORTS_DIR.is_dir():
        print(f"ERROR: Reports folder not found at {REPORTS_DIR}")
        print("Options:")
        print("  1. Pass path as argument:  python copiloter.py /path/to/reports")
        print("  2. Set env variable:       PBIP_REPORTS=/path/to/reports python copiloter.py")
        print("  3. Place projects in:      ./Reports/ next to this script")
        sys.exit(1)

    def _is_component_folder(d: Path) -> bool:
        name = d.name
        if name.endswith(".Report") or name.endswith(".SemanticModel"):
            base_name = name.replace(".Report", "").replace(".SemanticModel", "")
            parent_pbip = list(d.parent.glob(f"{base_name}.pbip"))
            return len(parent_pbip) > 0
        return False

    all_dirs = [d for d in sorted(REPORTS_DIR.iterdir()) if d.is_dir()]
    project_dirs = [d for d in all_dirs if not _is_component_folder(d)]
    if not project_dirs:
        print("No project folders found in Reports/")
        sys.exit(0)

    print(f"Found {len(project_dirs)} folder(s) to scan:")
    print()

    results = []
    for pd in project_dirs:
        result = process_project(pd, emit_files=args.emit_files, export_root=export_root)
        results.append(result)
        print()

    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    print("=" * 60)
    print(f"Done. Processed: {ok}, Skipped: {skipped}, Total: {len(results)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
