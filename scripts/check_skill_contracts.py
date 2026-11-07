#!/usr/bin/env python3
"""
check_skill_contracts.py
========================
Doc-vs-argparse contract linter. Parses every fenced bash block and backticked
`*.py` mention across all SKILL.md / commands / agents markdown, extracts the
`python .../<script>.py <action/flags>` invocations, and validates the action
names and flags against each script's argparse surface.

This mechanically enforces the SKILL-to-script contract: it catches the whole
class of "the skill documents a flag/action the script doesn't have" bugs
(D3 script-contract findings, D4 M1-M17 arg mismatches, D5 findings 5-11).

Static analysis only — it does NOT execute the scripts. For each script it
extracts, from the source:
  * every `--flag` defined via add_argument(...)
  * subcommand names from add_parser("name")
  * the known --action values, from an --action choices=[...] list AND from
    `args.action == "x"` / `args.action in {...}` dispatch comparisons.

Usage:
    python check_skill_contracts.py                 # lint the whole repo
    python check_skill_contracts.py --json          # machine-readable report
    python check_skill_contracts.py --script foo.py # only invocations of one script

It also fails on JSON typed inline in single quotes (`--data '{...}'`, `--channels '[...]'`) in any
shipped markdown file outside CHANGELOG.md: such a payload often carries outside text (scraped titles,
lead names, report text), and one single quote in it ends the quoting and runs the rest as shell.
The docs write the JSON to a file with the Write tool and pass `--data "@{data_file}"` (3.42.0).

Exit code: 0 when there are zero mismatches, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"

# argparse always provides these.
UNIVERSAL_FLAGS = {"--help", "-h"}

# Placeholder tokens that must never be treated as real action values.
_PLACEHOLDER_RE = re.compile(r"[<>{}\[\]]|\.\.\.|\$\{|^\$")


# ── Script spec extraction (static) ─────────────────────────────────

def extract_script_spec(path: Path) -> dict | None:
    """Return {flags, subcommands, actions, uses_argparse} for a script, or
    None if the script does not use argparse."""
    try:
        src = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    if "argparse" not in src and "add_argument" not in src:
        return None

    flags = set(UNIVERSAL_FLAGS)
    for m in re.finditer(r"""add_argument\(\s*['"](--[A-Za-z0-9][\w-]*)['"]""", src):
        flags.add(m.group(1))
    # Short options too (rarely used in docs but harmless to know).
    for m in re.finditer(r"""add_argument\(\s*['"](-[A-Za-z])['"]""", src):
        flags.add(m.group(1))

    subcommands = set()
    for m in re.finditer(r"""add_parser\(\s*['"]([\w-]+)['"]""", src):
        subcommands.add(m.group(1))

    actions = set()
    # --action choices=[...]  (allow the choices list to span lines)
    for m in re.finditer(r"""['"]--action['"].*?choices\s*=\s*\[(.*?)\]""", src, re.DOTALL):
        for lit in re.findall(r"""['"]([\w-]+)['"]""", m.group(1)):
            actions.add(lit)
    # args.action == "x"
    for m in re.finditer(r"""args\.action\s*==\s*['"]([\w-]+)['"]""", src):
        actions.add(m.group(1))
    # args.action in {"a", "b"} / ("a", "b") / ["a", "b"]
    for m in re.finditer(r"""args\.action\s+in\s*[\{\(\[](.*?)[\}\)\]]""", src, re.DOTALL):
        for lit in re.findall(r"""['"]([\w-]+)['"]""", m.group(1)):
            actions.add(lit)

    return {
        "flags": flags,
        "subcommands": subcommands,
        "actions": actions,
        "uses_argparse": True,
    }


def load_all_specs() -> dict[str, dict]:
    specs = {}
    for p in sorted(SCRIPTS_DIR.glob("*.py")):
        if p.name.startswith("_") or p.name in ("check_skill_contracts.py",):
            continue
        spec = extract_script_spec(p)
        if spec:
            specs[p.name] = spec
    return specs


# ── Invocation extraction from markdown ─────────────────────────────

# A python invocation of a repo script: capture the script basename + the tail.
_INVOKE_RE = re.compile(
    r"python3?\s+"                      # python or python3
    r"(?:[^\s`|&;]*?/)?"                # optional path prefix (…/scripts/)
    r"([A-Za-z0-9_.\-]+\.py)"          # script basename
    r"([^\n`]*)"                        # the argument tail (stop at newline/backtick)
)


def _iter_command_snippets(text: str):
    """Yield candidate command strings: every line inside a fenced code block
    plus every inline-backtick span."""
    # Fenced code blocks
    for block in re.findall(r"```[^\n]*\n(.*?)```", text, re.DOTALL):
        for line in block.splitlines():
            yield line
    # Inline backtick spans
    for span in re.findall(r"`([^`\n]+)`", text):
        yield span


def parse_invocation(tail: str) -> dict:
    """Split the argument tail into flags used, the leading subcommand (if any),
    and the --action value (if any)."""
    # Cut the tail at a shell separator so we don't swallow a following command.
    tail = re.split(r"[|&;]| >|>>", tail, maxsplit=1)[0]
    tokens = tail.split()
    flags = [t for t in tokens if t.startswith("--") or (len(t) == 2 and t.startswith("-") and t[1].isalpha())]
    # Leading subcommand = first non-flag token that isn't a value of a flag.
    subcommand = None
    if tokens and not tokens[0].startswith("-"):
        cand = tokens[0]
        if re.fullmatch(r"[\w-]+", cand):
            subcommand = cand
    # --action VALUE
    action = None
    for i, t in enumerate(tokens):
        if t == "--action" and i + 1 < len(tokens):
            action = tokens[i + 1]
            break
        if t.startswith("--action="):
            action = t.split("=", 1)[1]
            break
    return {"flags": flags, "subcommand": subcommand, "action": action}


def validate_invocation(spec: dict, inv: dict, script: str) -> list[dict]:
    """Validate a single parsed invocation against a script spec. Returns a
    (possibly empty) list of mismatch dicts. Exposed for unit testing."""
    problems = []
    for flag in inv["flags"]:
        flag_name = flag.split("=", 1)[0]
        if _PLACEHOLDER_RE.search(flag_name):
            continue
        if flag_name not in spec["flags"]:
            problems.append({"script": script, "kind": "unknown-flag", "detail": flag_name})
    if spec["subcommands"] and inv["subcommand"]:
        sc = inv["subcommand"]
        if not _PLACEHOLDER_RE.search(sc) and sc not in spec["subcommands"]:
            problems.append({"script": script, "kind": "unknown-subcommand", "detail": sc})
    if spec["actions"] and inv["action"]:
        act = inv["action"]
        if not _PLACEHOLDER_RE.search(act) and act not in spec["actions"]:
            problems.append({"script": script, "kind": "unknown-action", "detail": act})
    return problems


# `--flag '{` or `--flag '[`: a JSON payload typed inline between single quotes.
INLINE_JSON_RE = re.compile(r"--[a-z][a-z0-9-]* '[\{\[]")
_SKIP_PARTS = {".git", "node_modules", "results", "__pycache__"}


def inline_json_sites(text: str) -> list[tuple[int, str]]:
    """(line number, line) for every single-quoted inline JSON option in a markdown text."""
    return [(n, line.strip()) for n, line in enumerate(text.splitlines(), 1) if INLINE_JSON_RE.search(line)]


def lint_inline_json(root: Path = PLUGIN_ROOT) -> list[dict]:
    """Every shipped .md file except CHANGELOG.md (history) must pass JSON options through a file."""
    found = []
    for md in sorted(root.rglob("*.md")):
        rel_parts = md.relative_to(root).parts
        if md.name == "CHANGELOG.md" or set(rel_parts) & _SKIP_PARTS:
            continue
        text = md.read_text(encoding="utf-8-sig", errors="replace")
        for n, line in inline_json_sites(text):
            found.append({"script": "-", "kind": "inline-json", "detail": f"line {n}: write the JSON to a file "
                          "and pass --flag \"@{file}\"", "file": "/".join(rel_parts), "snippet": line[:160]})
    return found


def lint(specs: dict[str, dict], only_script: str | None = None) -> list[dict]:
    doc_dirs = [PLUGIN_ROOT / "skills", PLUGIN_ROOT / "commands", PLUGIN_ROOT / "agents"]
    mismatches = []
    for base in doc_dirs:
        if not base.exists():
            continue
        for md in sorted(base.rglob("*.md")):
            text = md.read_text(encoding="utf-8-sig")
            rel = md.relative_to(PLUGIN_ROOT).as_posix()
            for snippet in _iter_command_snippets(text):
                for m in _INVOKE_RE.finditer(snippet):
                    script = m.group(1)
                    if only_script and script != only_script:
                        continue
                    spec = specs.get(script)
                    if not spec:
                        continue  # unknown/local script or non-argparse — skip
                    inv = parse_invocation(m.group(2))
                    for prob in validate_invocation(spec, inv, script):
                        prob["file"] = rel
                        prob["snippet"] = snippet.strip()[:160]
                        mismatches.append(prob)
    return mismatches


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint doc invocations against script argparse.")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--script", help="Only lint invocations of this script basename")
    args = parser.parse_args()

    _common.ensure_utf8_stdout()
    specs = load_all_specs()
    mismatches = lint(specs, only_script=args.script)
    if not args.script:
        mismatches += lint_inline_json()

    if args.json:
        print(json.dumps({"mismatch_count": len(mismatches),
                          "scripts_scanned": len(specs),
                          "mismatches": mismatches}, indent=2))
    else:
        if not mismatches:
            print(f"OK — 0 contract mismatches across {len(specs)} scripts.")
        else:
            by_file: dict[str, list] = {}
            for mm in mismatches:
                by_file.setdefault(mm["file"], []).append(mm)
            print(f"{len(mismatches)} contract mismatch(es) in {len(by_file)} file(s):\n")
            for f, items in sorted(by_file.items()):
                print(f"  {f}")
                for it in items:
                    print(f"    [{it['kind']}] {it['script']}: {it['detail']}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
