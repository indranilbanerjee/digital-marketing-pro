#!/usr/bin/env python3
"""
seo_drift.py — compare two SEO snapshots and surface biggest movers.

Inputs two CSV exports (baseline + current) from any of:

  - GSC Performance Report (Search Analytics export)
  - GSC AI Performance Report (new, see scripts/gsc-ai-performance.py)
  - Generic rank-tracker export (keyword, position, impressions)
  - AEO probe results (synthetic AI-engine visibility per query)

Computes per-row deltas (impressions / clicks / position / AI-citations
when present), surfaces top N gainers + top N losers per dimension,
classifies decay vs growth patterns, and produces a structured JSON
suitable for /digital-marketing-pro:seo-drift skill consumption.

Stdlib only.

Joining baseline ↔ current
--------------------------
By default joins on the union of:
  - `query` column (lower-cased, trimmed) when present
  - `page` / `url` column when present
  - else `keyword` column

Use --join-on to override (e.g., --join-on query,country for
per-geo drift analysis).

Metric autodetect
-----------------
Columns auto-detected:
  - impressions: "Impressions", "impressions"
  - clicks:      "Clicks", "clicks"
  - position:    "Position", "Average Position", "position", "avg_position"
  - ctr:         "CTR", "ctr"
  - ai_citations / ai_impressions: "AI Citations", "ai_impressions"

Missing columns are silently skipped — the script returns deltas
only for metrics present in BOTH files.

Drift classification per row
----------------------------
A metric move is "significant" when its absolute delta exceeds --noise
(default 5%). Position is inverted (lower = better): a position drop
counts as an improvement.

  growth:        1+ significant improvements, no significant declines
  decline:       1+ significant declines, no significant improvements
  reshuffle:     significant moves in opposite directions
                 (e.g., impressions up, position worsened — common for AI Mode)
  stable:        no metric moved more than --noise
  new:           absent in baseline, present in current
  lost:          present in baseline, absent in current

Usage
-----

  python scripts/seo_drift.py \\
      --baseline gsc-2026-04.csv --current gsc-2026-06.csv \\
      --top 30 --noise 5 \\
      --out drift.json

  # Compare AEO probe results
  python scripts/seo_drift.py --baseline aeo-q1.csv --current aeo-q2.csv \\
      --join-on query --format text

Quality scorecard
-----------------
  date_range_distinct:  always "warn" — the script cannot verify that the
                        two exports cover non-overlapping windows; confirm
                        the date ranges manually
  sample_size:          each input has >=50 rows
  metric_compatibility: at least 1 numeric metric exists in BOTH inputs
  no_lookup_collisions: no duplicate keys within a single input
                        (else deltas are ambiguous)

Exit codes
----------
  0 = success
  2 = bad input
"""

from __future__ import annotations
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


METRIC_ALIASES = {
    "impressions": ["impressions", "impr"],
    "clicks": ["clicks", "click"],
    "position": ["position", "average position", "avg position", "avg_position"],
    "ctr": ["ctr", "click_through_rate", "click through rate"],
    "ai_citations": ["ai citations", "ai_citations", "ai_impressions", "ai impressions"],
}
KEY_CANDIDATES = ["query", "keyword", "page", "url", "country", "device"]


def _norm_col(c: str) -> str:
    return c.strip().lower().replace("_", " ")


def _detect_metric_cols(headers: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    nmap = {h: _norm_col(h) for h in headers}
    for metric, aliases in METRIC_ALIASES.items():
        for alias in aliases:
            for h, n in nmap.items():
                if n == alias:
                    out[metric] = h
                    break
            if metric in out:
                break
    return out


def _detect_key_cols(headers: list[str], requested: list[str] | None) -> list[str]:
    nmap = {_norm_col(h): h for h in headers}
    if requested:
        cols = []
        for req in requested:
            r = _norm_col(req)
            if r in nmap:
                cols.append(nmap[r])
            else:
                raise ValueError(f"--join-on requested '{req}' but not found in columns: {headers}")
        return cols
    # Auto: prefer query, fall back to keyword, then add page/url if present
    cols = []
    for cand in ["query", "keyword"]:
        if cand in nmap:
            cols.append(nmap[cand])
            break
    for cand in ["page", "url"]:
        if cand in nmap:
            cols.append(nmap[cand])
            break
    if not cols:
        raise ValueError(
            f"No join key detected. Tried {KEY_CANDIDATES}. Found: {headers}. Use --join-on."
        )
    return cols


def _safe_float(s) -> float:
    if s is None:
        return 0.0
    try:
        return float(str(s).replace(",", "").replace("%", "").strip() or 0)
    except (ValueError, TypeError):
        return 0.0


def _make_key(row: dict, key_cols: list[str]) -> str:
    return "|".join((row.get(c) or "").strip().lower() for c in key_cols)


def _load(path: Path, key_cols_req: list[str] | None) -> tuple[dict[str, dict], dict[str, str], list[str], list[str]]:
    """Returns: rows-keyed-by-join-key, metric-col-map, join-key-cols, list of duplicate-key warnings."""
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        metric_cols = _detect_metric_cols(headers)
        key_cols = _detect_key_cols(headers, key_cols_req)
        rows: dict[str, dict] = {}
        dupes: dict[str, int] = defaultdict(int)
        for row in reader:
            k = _make_key(row, key_cols)
            if not k.strip("|"):
                continue
            if k in rows:
                dupes[k] += 1
            rows[k] = {**rows.get(k, {}), **row}
        warnings = [f"duplicate key '{k}' (kept last of {n+1})" for k, n in list(dupes.items())[:5]]
        if len(dupes) > 5:
            warnings.append(f"... and {len(dupes) - 5} more duplicate keys")
    return rows, metric_cols, key_cols, warnings


def _classify(deltas: dict[str, float], noise_pct: float) -> str:
    significant = {m: d for m, d in deltas.items() if abs(d) > noise_pct}
    if not significant:
        return "stable"
    ups = [m for m, d in significant.items() if d > 0 and m != "position"]
    downs = [m for m, d in significant.items() if d < 0 and m != "position"]
    # Position: lower is better — invert
    if "position" in significant:
        if significant["position"] < 0: ups.append("position_improved")
        else: downs.append("position_worsened")
    if ups and downs:
        return "reshuffle"
    if len(ups) >= 2:
        return "growth"
    if len(downs) >= 2:
        return "decline"
    if len(ups) == 1:
        return "growth"
    if len(downs) == 1:
        return "decline"
    return "stable"


def compute_drift(baseline_csv: Path, current_csv: Path, join_on: list[str] | None,
                  top: int, noise_pct: float) -> dict:
    base_rows, base_metric_cols, base_key_cols, base_warn = _load(baseline_csv, join_on)
    cur_rows, cur_metric_cols, cur_key_cols, cur_warn = _load(current_csv, join_on)

    # Metric intersection
    shared_metrics = sorted(set(base_metric_cols) & set(cur_metric_cols))

    # Build delta records
    records = []
    all_keys = set(base_rows) | set(cur_rows)
    for k in all_keys:
        b = base_rows.get(k)
        c = cur_rows.get(k)
        if b is None:
            classification = "new"
            row_data = {"key": k, "classification": classification, "deltas_pct": {},
                        "current": {m: _safe_float(c.get(cur_metric_cols[m])) for m in shared_metrics}}
            records.append(row_data); continue
        if c is None:
            classification = "lost"
            row_data = {"key": k, "classification": classification, "deltas_pct": {},
                        "baseline": {m: _safe_float(b.get(base_metric_cols[m])) for m in shared_metrics}}
            records.append(row_data); continue

        deltas_pct: dict[str, float] = {}
        baseline_vals: dict[str, float] = {}
        current_vals: dict[str, float] = {}
        for m in shared_metrics:
            bv = _safe_float(b.get(base_metric_cols[m]))
            cv = _safe_float(c.get(cur_metric_cols[m]))
            baseline_vals[m] = round(bv, 3); current_vals[m] = round(cv, 3)
            if bv == 0:
                if cv == 0:
                    deltas_pct[m] = 0.0
                else:
                    deltas_pct[m] = 100.0  # infinity treated as 100% growth
            else:
                deltas_pct[m] = round(((cv - bv) / bv) * 100, 2)

        classification = _classify(deltas_pct, noise_pct)
        records.append({
            "key": k,
            "classification": classification,
            "baseline": baseline_vals,
            "current": current_vals,
            "deltas_pct": deltas_pct,
        })

    # Top movers per metric
    movers = {}
    for m in shared_metrics:
        with_delta = [r for r in records if m in r.get("deltas_pct", {})]
        # For position, lower is better — invert ranking
        invert = (m == "position")
        sorted_gain = sorted(with_delta, key=lambda r: r["deltas_pct"][m] if not invert else -r["deltas_pct"][m], reverse=True)
        sorted_loss = sorted(with_delta, key=lambda r: r["deltas_pct"][m] if not invert else -r["deltas_pct"][m])
        movers[m] = {
            "top_gainers": sorted_gain[:top],
            "top_losers": sorted_loss[:top],
        }

    # Counts per classification
    counts = defaultdict(int)
    for r in records:
        counts[r["classification"]] += 1

    # Quality scorecard
    sample_ok = len(base_rows) >= 50 and len(cur_rows) >= 50
    metric_ok = len(shared_metrics) >= 1
    no_collisions = (not base_warn) and (not cur_warn)
    # date_range_distinct is always "warn": the script cannot verify that the
    # two exports cover non-overlapping windows — confirm date ranges manually.
    date_distinct = "warn"

    scorecard = {
        "date_range_distinct": date_distinct,
        "sample_size": "pass" if sample_ok else "fail",
        "metric_compatibility": "pass" if metric_ok else "fail",
        "no_lookup_collisions": "pass" if no_collisions else "fail",
        "status": "ready" if (sample_ok and metric_ok and no_collisions) else "needs_review",
    }

    return {
        "report": "seo-drift",
        "inputs": {
            "baseline": str(baseline_csv),
            "current": str(current_csv),
            "noise_pct": noise_pct,
            "top": top,
            "join_on": base_key_cols,
        },
        "warnings": base_warn + cur_warn,
        "quality_scorecard": scorecard,
        "metrics_compared": shared_metrics,
        "counts": dict(counts),
        "stats": {
            "baseline_rows": len(base_rows),
            "current_rows": len(cur_rows),
            "shared_keys": sum(1 for r in records if r["classification"] not in ("new", "lost")),
            "new_keys": counts.get("new", 0),
            "lost_keys": counts.get("lost", 0),
        },
        "movers": movers,
    }


def _format_text(result: dict) -> str:
    lines = []
    lines.append("SEO drift report")
    lines.append("=" * 40)
    s = result["stats"]
    lines.append(f"Baseline: {s['baseline_rows']:,} rows  |  Current: {s['current_rows']:,} rows")
    lines.append(f"Shared keys: {s['shared_keys']:,}  |  New: {s['new_keys']:,}  |  Lost: {s['lost_keys']:,}")
    lines.append(f"Metrics: {', '.join(result['metrics_compared'])}")
    sc = result["quality_scorecard"]
    lines.append(f"Scorecard: status={sc['status']} | sample={sc['sample_size']} metric_compat={sc['metric_compatibility']} no_collisions={sc['no_lookup_collisions']} date_range={sc['date_range_distinct']}")
    lines.append("")
    lines.append("Classification counts:")
    for cls, n in sorted(result["counts"].items()):
        lines.append(f"  {cls:12s}  {n:,}")
    lines.append("")
    for m, mvr in result["movers"].items():
        lines.append(f"--- {m.upper()} top gainers ({len(mvr['top_gainers'])}) ---")
        for r in mvr["top_gainers"][:10]:
            delta = r["deltas_pct"].get(m, 0.0)
            lines.append(f"  {delta:+8.1f}%   {r['key'][:60]}")
        lines.append(f"--- {m.upper()} top losers ({len(mvr['top_losers'])}) ---")
        for r in mvr["top_losers"][:10]:
            delta = r["deltas_pct"].get(m, 0.0)
            lines.append(f"  {delta:+8.1f}%   {r['key'][:60]}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--baseline", required=True, type=Path, help="Baseline CSV (older period)")
    p.add_argument("--current", required=True, type=Path, help="Current CSV (newer period)")
    p.add_argument("--join-on", help="Comma-separated column names to join on (default: auto)")
    p.add_argument("--top", type=int, default=20, help="Top N movers per metric (default 20)")
    p.add_argument("--noise", type=float, default=5.0, help="Percent threshold below which movement is 'stable' (default 5)")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--format", choices=["json", "text"], default="json")
    args = p.parse_args()

    join_on = [c.strip() for c in args.join_on.split(",")] if args.join_on else None

    try:
        result = compute_drift(args.baseline, args.current, join_on, args.top, args.noise)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr); return 2
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr); return 2

    out_text = json.dumps(result, indent=2, ensure_ascii=False) if args.format == "json" else _format_text(result)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)  # create the folder on demand
        args.out.write_text(out_text, encoding="utf-8")
        print(f"Wrote {args.out} (status={result['quality_scorecard']['status']})")
    else:
        print(out_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
