#!/usr/bin/env python3
"""
gsc-ai-performance.py — read and summarize Google Search Console's new
AI Performance Report (rolled out 3 June 2026).

As of the June 2026 rollout, Google ships this report UI-only with no
public API surface. This script handles the realistic path: the user exports a CSV
from Search Console and points this script at it.

When Google adds the report to the Search Analytics API
(searchanalytics.query — currently has searchType=web, image, video,
news, discover but no ai-features / ai-overview / ai-mode value), this
script's --api flag will become real. For now --api returns a structured
"not yet supported" message with a date-stamp for future readiness checks.

Usage
-----

  # From an exported Search Console CSV
  python gsc-ai-performance.py --brand acme --csv ~/Downloads/gsc-export.csv

  # API path (placeholder until Google ships it)
  python gsc-ai-performance.py --brand acme --api --site https://acme.example.com

  # JSON output for downstream pipelines
  python gsc-ai-performance.py --brand acme --csv path.csv --format json

The CSV format Google currently exports has columns matching the report
columns (impressions, pages, country, device, date). Column names vary
slightly during rollout; this script auto-detects common variants.

Reads / writes
--------------

Reads CSV. Optionally archives a copy under
<workspace>/brands/{brand}/gsc-ai/{YYYY-MM-DD}.csv for trend tracking.

Exit codes
----------
  0 = success
  2 = bad input (no CSV, no brand)
  3 = CSV format not recognized
  4 = API not yet supported by Google
"""

from __future__ import annotations
import argparse
import csv
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

# Ensure stdout can render em-dashes etc on Windows cp1252 terminals
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


CSV_COLUMN_ALIASES = {
    "impressions": {"impressions", "impr", "search impressions", "ai impressions"},
    "pages": {"pages", "page", "url", "top urls", "page url"},
    "country": {"country", "countries", "country code", "geo"},
    "device": {"device", "device category", "platform"},
    "date": {"date", "day", "report date"},
}


def _norm(col: str) -> str:
    return col.strip().lower().replace("_", " ")


def _detect_columns(headers: list[str]) -> dict[str, str]:
    """Map canonical column names to actual headers in the CSV."""
    normalized = {h: _norm(h) for h in headers}
    mapping: dict[str, str] = {}
    for canonical, aliases in CSV_COLUMN_ALIASES.items():
        for h, n in normalized.items():
            if n in aliases:
                mapping[canonical] = h
                break
    return mapping


def _summarize_csv(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        col_map = _detect_columns(headers)
        if "impressions" not in col_map:
            raise ValueError(
                f"CSV has no impressions column. Found columns: {headers}. "
                f"Expected one of: {sorted(CSV_COLUMN_ALIASES['impressions'])}"
            )
        total_impressions = 0
        countries: dict[str, int] = {}
        devices: dict[str, int] = {}
        dates: set[str] = set()
        page_count = 0
        seen_pages: set[str] = set()
        for row in reader:
            try:
                imp = int(row[col_map["impressions"]].replace(",", "") or 0)
            except (ValueError, KeyError):
                imp = 0
            total_impressions += imp
            if "country" in col_map:
                c = row.get(col_map["country"], "").strip()
                if c:
                    countries[c] = countries.get(c, 0) + imp
            if "device" in col_map:
                d = row.get(col_map["device"], "").strip()
                if d:
                    devices[d] = devices.get(d, 0) + imp
            if "date" in col_map:
                dt = row.get(col_map["date"], "").strip()
                if dt:
                    dates.add(dt)
            if "pages" in col_map:
                p = row.get(col_map["pages"], "").strip()
                if p and p not in seen_pages:
                    seen_pages.add(p)
                    page_count += 1

    return {
        "report": "google-search-console-ai-performance",
        "report_rolled_out": "2026-06-03",
        "columns_detected": col_map,
        "total_impressions": total_impressions,
        "unique_pages": page_count,
        "countries": dict(sorted(countries.items(), key=lambda kv: kv[1], reverse=True)),
        "devices": dict(sorted(devices.items(), key=lambda kv: kv[1], reverse=True)),
        "date_range": {"min": min(dates) if dates else None, "max": max(dates) if dates else None, "days": len(dates)},
        "click_data_note": "GSC AI report intentionally excludes clicks. Use GA4 AI Assistant channel for attribution.",
    }


def _archive_copy(brand: str, src: Path) -> str | None:
    # Archive under the canonical brand dir (env-aware, slugified) so the CSV
    # lands in the same workspace the rest of the plugin reads from.
    dest_dir = _common.brand_dir(brand) / "gsc-ai"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{date.today().isoformat()}.csv"
    dest.write_bytes(src.read_bytes())
    return str(dest)


def _api_not_supported() -> dict:
    return {
        "report": "google-search-console-ai-performance",
        "api_status": "not_supported",
        "as_of_check": date.today().isoformat(),
        "reason": (
            "Google Search Analytics API (searchanalytics.query) does not yet "
            "expose the AI Performance Report. As of the 3 June 2026 rollout the "
            "report is UI-only with CSV export."
        ),
        "workaround": "Export CSV from Search Console UI; pass with --csv.",
        "ref": "https://developers.google.com/webmaster-tools/v1/searchanalytics/query",
        "recheck_after": "2026-09-01",
    }


def _format_text(summary: dict) -> str:
    lines = []
    lines.append("GSC AI Performance Report — summary")
    lines.append("=" * 40)
    if summary.get("api_status") == "not_supported":
        lines.append(f"API: NOT YET SUPPORTED (checked {summary['as_of_check']})")
        lines.append(f"  Reason: {summary['reason']}")
        lines.append(f"  Workaround: {summary['workaround']}")
        lines.append(f"  Recheck: {summary.get('recheck_after')}")
        return "\n".join(lines)
    lines.append(f"Total impressions: {summary['total_impressions']:,}")
    lines.append(f"Unique pages cited: {summary['unique_pages']:,}")
    dr = summary["date_range"]
    if dr["min"]:
        lines.append(f"Date range: {dr['min']} -> {dr['max']} ({dr['days']} days)")
    if summary["countries"]:
        top_countries = list(summary["countries"].items())[:5]
        lines.append("Top countries: " + ", ".join(f"{c}={n:,}" for c, n in top_countries))
    if summary["devices"]:
        lines.append("Devices: " + ", ".join(f"{d}={n:,}" for d, n in summary["devices"].items()))
    lines.append("")
    lines.append("NOTE: " + summary["click_data_note"])
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--brand", type=_common.path_component, required=True, help="Brand slug")
    p.add_argument("--csv", help="Path to GSC AI report CSV export")
    p.add_argument("--api", action="store_true", help="Try the API path (currently not supported by Google)")
    p.add_argument("--site", help="Site URL for --api mode")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--archive", action="store_true", help="Archive the CSV under <workspace>/brands/{brand}/gsc-ai/")
    args = p.parse_args()

    if args.api:
        summary = _api_not_supported()
    elif args.csv:
        try:
            summary = _summarize_csv(Path(args.csv).expanduser())
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 3
        if args.archive:
            archived = _archive_copy(args.brand, Path(args.csv).expanduser())
            if archived:
                summary["archived_to"] = archived
    else:
        print("ERROR: pass either --csv <path> or --api", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(_format_text(summary))
    if args.api:
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
