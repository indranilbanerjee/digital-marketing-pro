#!/usr/bin/env python3
"""
run-audit.py
============
Re-derives a content-engine run's gate claims from the artifacts on disk, using
this plugin's own scripts — so "the scorecard says ready" and "the artifacts
prove ready" cannot drift apart silently.

Why this exists
---------------
The pattern comes from the suite's long-form pipeline, where a self-run
campaign found thirty-eight defects that all shared one shape: every individual artifact
looked healthy while the run as a whole was lying about something. DMP's
content-engine has the same seams — a scorecard that declares `status: ready`,
gates whose measurements live in other files, and a humanize gate that a real
run once satisfied while the scan output sat *inside* the measured file,
corrupting the authorship record beside it.

Two disciplines, learned the hard way:

1. **Re-derive; never trust.** The humanize verdict is re-measured by running
   `ai-tell-scan.py` fresh, not read from the scorecard. The authorship record
   is re-computed and compared against the stored one.
2. **A missing input is reported-N/A, never silent-pass.** "Not checked" and
   "checked and fine" are different results; conflating them is how hollow
   gates are born.

Usage:
    python run-audit.py --run-dir <path-to-{slug}-run-directory> [--strict] [--out FILE]

The run directory is the content-engine output folder:
``${CLAUDE_PLUGIN_DATA}/{brand}/seo/content-engine/{YYYY-MM-DD}/{slug}/``

Writes ``run-audit.json`` into the run directory (``--out`` overrides).
Exit codes: 0 clean · 1 violations (with --strict, N/A too) · 2 usage error.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _common  # noqa: E402

_common.ensure_utf8_stdout()

SCRIPTS = pathlib.Path(__file__).resolve().parent

REQUIRED = ["00-input.md", "01-research.md", "02-outline.md", "03-draft-v1.md",
            "04-fact-check.md", "05-humanize.md", "05-scans.json",
            "06-brand-voice-check.md", "07-seo-checklist.md",
            "08-quality-scorecard.md", "09-publish-ready.md", "PLAN.md"]


def _read(p: pathlib.Path) -> str:
    with open(p, "r", encoding="utf-8-sig", newline="") as fh:
        return fh.read()


def _json(p: pathlib.Path):
    try:
        return json.loads(_read(p))
    except (OSError, json.JSONDecodeError):
        return None


class Audit:
    def __init__(self):
        self.checks = []

    def check(self, section, name, ok, detail=""):
        self.checks.append({"section": section, "name": name,
                            "result": "PASS" if ok else "FAIL",
                            "detail": detail or None})

    def na(self, section, name, reason):
        self.checks.append({"section": section, "name": name,
                            "result": "N/A", "detail": reason})

    def summary(self, strict=False):
        p = sum(1 for c in self.checks if c["result"] == "PASS")
        f = sum(1 for c in self.checks if c["result"] == "FAIL")
        n = sum(1 for c in self.checks if c["result"] == "N/A")
        verdict = "CLEAN" if f == 0 and (not strict or n == 0) else "VIOLATIONS"
        return {"pass": p, "fail": f, "na": n, "verdict": verdict}


def audit_run(run_dir: pathlib.Path, strict=False) -> dict:
    a = Audit()

    # ------------------------------------------------------------ A. artifacts
    missing = [f for f in REQUIRED if not (run_dir / f).is_file()]
    a.check("A artifacts", "all required numbered artifacts present",
            not missing, f"missing: {missing}")

    has_source = (run_dir / "00-source-draft.md").is_file()
    has_auth = (run_dir / "05-authorship.json").is_file()
    if has_source or has_auth:
        a.check("A artifacts",
                "source draft and authorship record travel together",
                has_source == has_auth,
                "00-source-draft.md and 05-authorship.json are a pair: one "
                "without the other means the provenance promise was half-kept")

    scorecard = _read(run_dir / "08-quality-scorecard.md") \
        if (run_dir / "08-quality-scorecard.md").is_file() else ""
    declares_ready = bool(re.search(r"status:\s*ready", scorecard, re.I))

    # ------------------------------------------------------------- B. humanize
    hum = run_dir / "05-humanize.md"
    if hum.is_file():
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "ai-tell-scan.py"),
             "--file", str(hum)],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        scan = None
        try:
            scan = json.loads(proc.stdout)
        except json.JSONDecodeError:
            pass
        a.check("B humanize", "ai-tell-scan runs on the humanized file",
                scan is not None, proc.stdout[:160] or proc.stderr[:160])
        if scan is not None and declares_ready:
            a.check("B humanize",
                    "scorecard 'ready' is backed by a fresh humanize scan",
                    bool(scan.get("humanize_passed")),
                    f"fresh scan says humanize_passed="
                    f"{scan.get('humanize_passed')} at "
                    f"{scan.get('flagged_paragraph_pct')}% flagged")
        # The corruption class that once flipped may_claim_authored: scan JSON
        # embedded in the measured file.
        text = _read(hum)
        a.check("B humanize", "no scan JSON embedded in the measured file",
                '"surface"' not in text and '"flagged_paragraph_pct"' not in text,
                "05-humanize.md is measured sentence-by-sentence by "
                "authorship.py; scan output belongs in 05-scans.json")
    else:
        a.na("B humanize", "humanize checks", "05-humanize.md absent")

    scans = _json(run_dir / "05-scans.json")
    if scans is not None:
        a.check("B humanize", "05-scans.json keyed {surface, structure}",
                isinstance(scans, dict) and
                {"surface", "structure"} <= set(scans.keys()),
                f"keys: {sorted(scans.keys()) if isinstance(scans, dict) else type(scans).__name__}")
    elif (run_dir / "05-scans.json").is_file():
        a.check("B humanize", "05-scans.json parses", False, "invalid JSON")

    # ----------------------------------------------------------- C. authorship
    if has_source and hum.is_file():
        spec = importlib.util.spec_from_file_location(
            "dmp_authorship_audit", SCRIPTS / "authorship.py")
        au = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(au)
        rec = au.classify(_read(run_dir / "00-source-draft.md"), _read(hum))
        v = rec["violations"]
        a.check("C authorship", "zero author sentences rewritten",
                v["author_sentences_rewritten"] == 0, str(v))
        a.check("C authorship", "zero author sentences dropped",
                v["author_sentences_dropped"] == 0, str(v))
        stored = _json(run_dir / "05-authorship.json")
        if stored is not None:
            a.check("C authorship",
                    "stored authorship record matches a fresh measurement",
                    stored.get("author_word_share") == rec["author_word_share"],
                    f"stored {stored.get('author_word_share')} vs fresh "
                    f"{rec['author_word_share']} — the record predates a change "
                    f"to the file it describes")
    elif has_source:
        a.na("C authorship", "authorship", "source draft present but no "
             "05-humanize.md to measure")
    else:
        a.na("C authorship", "authorship", "no source draft in this run")

    # ---------------------------------------------------------- D. brand voice
    voice = _read(run_dir / "06-brand-voice-check.md") \
        if (run_dir / "06-brand-voice-check.md").is_file() else ""
    distances = [float(m) for m in re.findall(
        r"distance[^0-9-]{0,12}(0?\.\d+|0|1\.0)", voice, re.I)]
    if distances:
        worst = max(distances)
        if declares_ready:
            a.check("D voice", "every axis distance within the 0.15 gate",
                    worst <= 0.15,
                    f"worst recorded distance {worst} — the scorecard declared "
                    f"ready past its own gate")
        else:
            a.na("D voice", "voice gate", "distances recorded but run not "
                 "declared ready")
    else:
        a.na("D voice", "voice gate",
             "no machine-readable distance values in 06-brand-voice-check.md")

    # -------------------------------------------------------------- E. honesty
    if declares_ready:
        a.check("E honesty", "'ready' has every required artifact behind it",
                not missing, f"scorecard declares ready with missing: {missing}")
        nine = run_dir / "09-publish-ready.md"
        body = _read(nine) if nine.is_file() else ""
        a.check("E honesty", "publish-ready copy is not a stub",
                len(body.split()) >= 50,
                f"{len(body.split())} words in 09-publish-ready.md")
        a.check("E honesty", "no production placeholders in publish-ready copy",
                not re.search(r"\[(?:TODO|TK|PLACEHOLDER|VISUAL-PLACEHOLDER)\b",
                              body, re.I),
                "a reader must never see a production instruction")
    else:
        a.na("E honesty", "ready-state checks",
             "scorecard does not declare status: ready")

    return {"run_dir": str(run_dir), "declares_ready": declares_ready,
            "checks": a.checks, **a.summary(strict)}


def main():
    ap = argparse.ArgumentParser(
        description="Re-derive a content-engine run's gates from its artifacts.")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    run_dir = pathlib.Path(args.run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        print(json.dumps({"error": f"no run directory at {run_dir}"}))
        sys.exit(2)

    result = audit_run(run_dir, strict=args.strict)
    out = pathlib.Path(args.out).expanduser() if args.out \
        else run_dir / "run-audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)  # create the folder on demand
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    result["written_to"] = str(out)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["verdict"] == "CLEAN" else 1)


if __name__ == "__main__":
    main()
