#!/usr/bin/env python3
"""
serp-snapshot.py
================
Validate a per-query SERP snapshot for `rank-monitor --features`.

Search Console gives positions for a verified property but not the SERP-feature
layout of each query. Any SERP API or rank tracker can export that layout; this
script reads the export (a JSON array or a CSV file), checks every row, and prints
a normalised snapshot plus a summary the skill can diff against the last one.
It reads only the file you name: no network, no API keys, no provider code.

Format (one row per query + gl + hl; see skills/rank-monitor/serp-snapshot-format.md):
    query                   required  the search query
    gl, hl                  optional  country (2 letters) and language (en, en-GB)
    position                optional  the brand's organic position (1+); empty = not ranking
    ai_overview_present     optional  true/false
    ai_overview_cited       optional  true/false (only true when an AI Overview is present)
    paa_present             optional  true/false (People Also Ask)
    featured_snippet_owner  optional  domain that owns the featured snippet; empty = none

Usage:
    python serp-snapshot.py --file snapshot.csv
    python serp-snapshot.py --file snapshot.json --brand-domain example.com

Exit codes: 0 valid, 1 one or more rows invalid (all errors are listed, `refused: true`, and no
summary is given), 2 bad arguments or an unreadable file.

Dependencies: none (stdlib only)
"""

import argparse
import csv
import io
import json
import re
import sys

for _stream in (sys.stdout, sys.stderr):  # UTF-8 output, even where a Windows pipe defaults to cp1252
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from pathlib import Path

MAX_BYTES = 10 * 1024 * 1024
FIELDS = ("query", "gl", "hl", "position", "ai_overview_present", "ai_overview_cited",
          "paa_present", "featured_snippet_owner")
BOOL_FIELDS = ("ai_overview_present", "ai_overview_cited", "paa_present")
TRUE = {"true", "yes", "y", "1"}
FALSE = {"false", "no", "n", "0"}
GL_RE = re.compile(r"^[A-Za-z]{2}$")
HL_RE = re.compile(r"^[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,4})?$")
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _bool(value, row, field, errors):
    if _blank(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in TRUE:
        return True
    if text in FALSE:
        return False
    errors.append(f"row {row} '{field}' {value!r} is not true/false")
    return None


def _position(value, row, errors):
    if _blank(value):
        return None
    if isinstance(value, bool):
        errors.append(f"row {row} 'position' must be a whole number of 1 or more")
        return None
    try:
        number = float(str(value).strip())
    except ValueError:
        number = None
    if number is None or number != int(number) or number < 1:
        errors.append(f"row {row} 'position' {value!r} must be a whole number of 1 or more, or empty")
        return None
    return int(number)


def normalise_domain(value):
    """example.com from 'https://www.Example.com/page'; None for a blank value."""
    if _blank(value):
        return None
    text = str(value).strip().lower()
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text)
    text = text.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].split(":", 1)[0]
    return text[4:] if text.startswith("www.") else text


def owned_by(owner, brand_domain):
    return bool(owner and brand_domain and (owner == brand_domain or owner.endswith("." + brand_domain)))


def read_rows(path, fmt):
    raw = Path(path).read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError(f"{path} is larger than {MAX_BYTES // (1024 * 1024)} MB")
    text = raw.decode("utf-8-sig")
    if fmt == "auto":
        fmt = "json" if Path(path).suffix.lower() == ".json" or text.lstrip().startswith("[") else "csv"
    if fmt == "json":
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("a JSON snapshot must be an array of row objects")
        return data
    return list(csv.DictReader(io.StringIO(text)))


def validate(rows, brand_domain=None):
    errors, out, seen, ignored = [], [], {}, set()
    if not rows:
        errors.append("the snapshot has no rows")
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            errors.append(f"row {i} is not an object")
            continue
        row = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
        ignored.update(k for k in row if k not in FIELDS)
        query = row.get("query")
        if _blank(query) or not isinstance(query, str):
            errors.append(f"row {i} is missing 'query'")
            continue
        gl = None if _blank(row.get("gl")) else str(row["gl"]).strip()
        hl = None if _blank(row.get("hl")) else str(row["hl"]).strip()
        if gl is not None and not GL_RE.match(gl):
            errors.append(f"row {i} 'gl' {gl!r} must be a 2-letter country code")
        if hl is not None and not HL_RE.match(hl):
            errors.append(f"row {i} 'hl' {hl!r} must be a language code such as en or en-GB")
        clean = {"query": " ".join(query.split()),
                 "gl": gl.lower() if gl else None,
                 "hl": hl.replace("_", "-") if hl else None,
                 "position": _position(row.get("position"), i, errors)}
        for field in BOOL_FIELDS:
            clean[field] = _bool(row.get(field), i, field, errors)
        if clean["ai_overview_cited"] and clean["ai_overview_present"] is False:
            errors.append(f"row {i} says the brand is cited in an AI Overview that is not present")
        owner = normalise_domain(row.get("featured_snippet_owner"))
        if owner is not None and not DOMAIN_RE.match(owner):
            errors.append(f"row {i} 'featured_snippet_owner' {row.get('featured_snippet_owner')!r} is not a domain")
        clean["featured_snippet_owner"] = owner
        if brand_domain:
            clean["brand_owns_featured_snippet"] = owned_by(owner, brand_domain)
        key = (clean["query"].lower(), clean["gl"], (clean["hl"] or "").lower() or None)
        if key in seen:
            errors.append(f"row {i} repeats row {seen[key]} (same query, gl and hl)")
        else:
            seen[key] = i
        out.append(clean)

    def count(field):
        return sum(1 for r in out if r[field])

    summary = {
        "queries": len(out),
        "ranking": sum(1 for r in out if r["position"] is not None),
        "ai_overview_present": count("ai_overview_present"),
        "ai_overview_cited": count("ai_overview_cited"),
        "paa_present": count("paa_present"),
        "featured_snippets": count("featured_snippet_owner"),
    }
    if brand_domain:
        summary["featured_snippets_owned_by_brand"] = count("brand_owns_featured_snippet")
    if errors:
        # A refused snapshot has no summary: counts that include a bad row (an AI Overview
        # "cited" with none present, say) would be read as facts.
        summary = None
    result = {"rows": out, "summary": summary, "errors": errors}
    if errors:
        result["refused"] = True
    if ignored:
        result["ignored_columns"] = sorted(ignored)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate a SERP snapshot export for rank-monitor --features.")
    parser.add_argument("--file", required=True, help="JSON array or CSV exported from any SERP API or rank tracker")
    parser.add_argument("--format", choices=["auto", "json", "csv"], default="auto")
    parser.add_argument("--brand-domain", help="the brand's domain, to mark featured snippets it owns")
    args = parser.parse_args(argv)
    brand = normalise_domain(args.brand_domain)
    if args.brand_domain and (not brand or not DOMAIN_RE.match(brand)):
        print(json.dumps({"error": f"--brand-domain {args.brand_domain!r} is not a domain"}))
        return 2
    try:
        rows = read_rows(args.file, args.format)
    except (OSError, UnicodeDecodeError, ValueError, csv.Error) as exc:
        print(json.dumps({"error": f"could not read {args.file}: {exc}"}))
        return 2
    result = validate(rows, brand)
    result["source_file"] = Path(args.file).name
    print(json.dumps(result, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
