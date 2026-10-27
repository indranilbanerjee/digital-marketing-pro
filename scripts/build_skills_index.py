#!/usr/bin/env python3
"""
build_skills_index.py — The Depth Contract: what each skill actually guarantees.

WHY THIS EXISTS
---------------
A large skill catalogue is a strength only if you can tell what each one does WITHOUT
reading it. Before this index, depth was invisible: some skills execute real
scripts with exit-code gates, some route their output through the /check
quality machinery, some are structured guidance — and nothing distinguished
them from the outside. A skill count read as a claim nobody could verify.

This script derives, for every skill, a DEPTH TIER from what the skill's own
files actually reference:

    E  (executes)  — invokes at least one real script under scripts/; behavior
                     is machine-enforced, not just described.
    M  (measured)  — no direct script, but output is routed through the
                     quality machinery (/check gate, eval runner, validators).
    G  (guided)    — a structured process with an output contract, no
                     machine gate.

The result is committed as skills-index.json at the repo root and becomes a
CONTRACT: tests/test_skills_index.py regenerates it and fails on any drift, so
a skill cannot silently lose its script, reference a script that does not
exist, or arrive unindexed. The index doubles as the machine-readable routing
surface for /help — name, tier, description, scripts, and cross-references in
one place, generated, never hand-maintained.

Usage (a maintainer tool; it ships with the plugin, so the default writes nothing):
    python scripts/build_skills_index.py            # same as --check
    python scripts/build_skills_index.py --check    # exit 1 if committed file drifted
    python scripts/build_skills_index.py --write    # regenerate skills-index.json
    python scripts/build_skills_index.py --stdout   # print, don't write
"""
from __future__ import annotations

import argparse
import json
import re
import sys

for _stream in (sys.stdout, sys.stderr):  # UTF-8 output, even where a Windows pipe defaults to cp1252
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / "skills"
SCRIPTS_DIR = REPO / "scripts"
INDEX_PATH = REPO / "skills-index.json"

# A reference to any of these routes the skill's output through the quality
# machinery — the M tier. Order matters only for reporting.
GATE_MARKERS = (
    "digital-marketing-pro:check",
    "eval-runner",
    "output-validator",
    "quality-assurance",
    "brand-guardian",
    "hallucination-detector",
    "claim-verifier",
)

SCRIPT_REF = re.compile(r"scripts[/\\]([A-Za-z0-9_.-]+\.(?:py|sh))")
CROSS_REF = re.compile(r"digital-marketing-pro:([a-z0-9][a-z0-9-]*)")
FRONT_FIELD = re.compile(r"^(name|description):\s*(.*)$")


def parse_frontmatter(text: str) -> dict[str, str]:
    """Minimal single-line YAML field extraction — stdlib only, matching how
    the repo's frontmatter is actually written (quoted single-line values)."""
    out: dict[str, str] = {}
    if not text.startswith("---"):
        return out
    body = text.split("---", 2)
    if len(body) < 3:
        return out
    for line in body[1].splitlines():
        m = FRONT_FIELD.match(line.strip())
        if m:
            val = m.group(2).strip()
            if val[:1] in "\"'" and val[-1:] == val[:1]:
                val = val[1:-1]
            out[m.group(1)] = val
    return out


def analyze_skill(skill_dir: Path, skill_names: set[str]) -> dict:
    files = sorted(skill_dir.rglob("*.md"))
    # Normalize line endings before measuring: git converts LF<->CRLF per
    # checkout config, so on-disk sizes differ between a dev clone and an
    # installed copy of the SAME commit. The contract must not care.
    texts = [f.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
             for f in files]
    all_text = "\n".join(texts)
    skill_md = skill_dir / "SKILL.md"
    front = parse_frontmatter(
        skill_md.read_text(encoding="utf-8-sig", errors="replace")) if skill_md.exists() else {}

    referenced = sorted(set(SCRIPT_REF.findall(all_text)))
    existing = [s for s in referenced if (SCRIPTS_DIR / s).exists()]
    missing = [s for s in referenced if not (SCRIPTS_DIR / s).exists()]
    gates = [g for g in GATE_MARKERS if g in all_text]
    cross = sorted({c for c in CROSS_REF.findall(all_text)
                    if c in skill_names and c != skill_dir.name})

    if existing:
        tier = "E"
    elif gates:
        tier = "M"
    else:
        tier = "G"

    return {
        "name": skill_dir.name,
        "tier": tier,
        "description": front.get("description", ""),
        "scripts": existing,
        "missing_scripts": missing,
        "gates": gates,
        "cross_refs": cross,
        "doc_files": len(files),
        "bytes": sum(len(t.encode("utf-8")) for t in texts),
    }


def build_index() -> dict:
    skill_dirs = sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir())
    names = {d.name for d in skill_dirs}
    entries = [analyze_skill(d, names) for d in skill_dirs]
    tiers = {"E": 0, "M": 0, "G": 0}
    for e in entries:
        tiers[e["tier"]] += 1
    return {
        "_comment": (
            "GENERATED by scripts/build_skills_index.py — do not hand-edit. "
            "Tiers: E executes real scripts; M routes output through the quality "
            "machinery; G structured guidance. tests/test_skills_index.py fails "
            "the suite if this file drifts from reality."),
        "skill_count": len(entries),
        "tiers": tiers,
        "skills": entries,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build or check the skills depth index.")
    ap.add_argument("--check", action="store_true",
                    help="Compare against committed skills-index.json; exit 1 on drift")
    ap.add_argument("--stdout", action="store_true", help="Print instead of writing")
    ap.add_argument("--write", action="store_true",
                    help="Regenerate skills-index.json (the default only checks: an installed copy can be read-only)")
    args = ap.parse_args()

    index = build_index()
    rendered = json.dumps(index, indent=2, ensure_ascii=False) + "\n"

    if args.stdout:
        sys.stdout.write(rendered)
        return 0
    if args.check or not args.write:
        if not INDEX_PATH.exists():
            print(f"DRIFT: {INDEX_PATH.name} missing — run build_skills_index.py --write",
                  file=sys.stderr)
            return 1
        committed = INDEX_PATH.read_text(encoding="utf-8-sig")
        if committed != rendered:
            print(f"DRIFT: {INDEX_PATH.name} does not match the repo — "
                  "run build_skills_index.py --write and commit the result.", file=sys.stderr)
            return 1
        print(f"{INDEX_PATH.name}: in sync "
              f"({index['skill_count']} skills — E:{index['tiers']['E']} "
              f"M:{index['tiers']['M']} G:{index['tiers']['G']})")
        return 0
    try:
        INDEX_PATH.write_text(rendered, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot write {INDEX_PATH}: {exc.strerror or exc}", file=sys.stderr)
        return 2
    print(f"Wrote {INDEX_PATH.name}: {index['skill_count']} skills — "
          f"E:{index['tiers']['E']} M:{index['tiers']['M']} G:{index['tiers']['G']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
