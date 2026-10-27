#!/usr/bin/env python3
"""
backlink_gap.py — find domains linking to competitors but not to you.

Takes one "ours" CSV and 1..N "competitor" CSVs of backlink data
(Ahrefs / Semrush / SE Ranking export format), normalizes referring
domains, computes the gap set (domains linking to >=1 competitor but
not us), and scores each gap by an opinionated outreach-priority
formula.

Stdlib only.

CSV format expected
-------------------
Each backlink CSV row represents one backlink. Column auto-detection
handles common exporter variants:

  Referring domain column: "Referring Domain" | "Source URL" | "referring_domain"
                           | "source domain" | "from_url" | "source"
  Domain rating column:    "DR" | "Domain Rating" | "domain_rating" | "DA"
                           | "Domain Authority" | "authority"
  Traffic column:          "Domain Traffic" | "traffic" | "ahrefs_rank" (any)
  Topical relevance:       "Topical Relevance" | "topical_relevance" (optional)

If a column isn't present, the script proceeds with neutral defaults
(DR=0, traffic=0, topical=0.5).

Priority score (0-1)
--------------------
    priority = 0.40 * dr_normalised
             + 0.25 * link_count_normalised
             + 0.20 * traffic_normalised
             + 0.15 * topical_relevance

where link_count is "how many of the competitor domains we passed
also got linked from this referring domain" — high counts mean
high-confidence opportunity (the link target type clearly works in
this space).

Usage
-----

  python scripts/backlink_gap.py \\
      --ours ours.csv \\
      --competitors comp1.csv comp2.csv comp3.csv \\
      --min-dr 20 \\
      --top 50 \\
      --out gap.json

  # Text summary
  python scripts/backlink_gap.py --ours ours.csv --competitors comp1.csv --format text

Quality scorecard gates
-----------------------
  - data_freshness: input files mtime within 90 days
  - sample_size: each input has >=50 unique referring domains
  - competitor_coverage: at least 2 competitor files (1 is allowed but warned)
  - link_overlap_signal: at least 5 referring domains link to >=2 competitors
                        (otherwise the "shared signal" is too weak to act on)

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
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


REFERRING_DOMAIN_ALIASES = [
    "referring domain", "referring_domain", "source domain", "source_domain",
    "source url", "source_url", "from_url", "source", "domain", "site",
]
DR_ALIASES = [
    "dr", "domain rating", "domain_rating", "da", "domain authority",
    "domain_authority", "authority", "ahrefs_rank",
]
TRAFFIC_ALIASES = [
    "domain traffic", "domain_traffic", "traffic", "organic_traffic",
    "organic traffic", "estimated_traffic",
]
TOPICAL_ALIASES = [
    "topical relevance", "topical_relevance", "relevance", "category_relevance",
]


def _norm(col: str) -> str:
    return col.strip().lower().replace(" ", " ")


def _detect_columns(headers: list[str]) -> dict[str, str | None]:
    nmap = {h: _norm(h) for h in headers}

    def find(aliases: list[str]) -> str | None:
        for alias in aliases:
            for h, n in nmap.items():
                if n == alias:
                    return h
        # partial match (substring)
        for alias in aliases:
            for h, n in nmap.items():
                if alias in n:
                    return h
        return None

    return {
        "referring_domain": find(REFERRING_DOMAIN_ALIASES),
        "dr": find(DR_ALIASES),
        "traffic": find(TRAFFIC_ALIASES),
        "topical": find(TOPICAL_ALIASES),
    }


def _extract_root_domain(value: str) -> str:
    v = value.strip().lower()
    if not v:
        return ""
    # If it's a URL, parse netloc
    if v.startswith("http://") or v.startswith("https://"):
        parsed = urlparse(v)
        host = parsed.netloc or parsed.path
    else:
        host = v
    # Strip user@, port, trailing slash
    host = host.split("@")[-1].split(":")[0].split("/")[0]
    # Strip www.
    if host.startswith("www."):
        host = host[4:]
    return host


def _safe_int(s) -> int:
    try:
        if isinstance(s, int): return s
        return int(str(s).replace(",", "").strip() or 0)
    except (ValueError, TypeError):
        return 0


def _safe_float(s) -> float:
    try:
        if isinstance(s, (int, float)): return float(s)
        return float(str(s).replace(",", "").strip() or 0)
    except (ValueError, TypeError):
        return 0.0


def _load_backlinks(path: Path) -> tuple[dict[str, dict], list[str]]:
    """Return (domain -> {dr, traffic, topical, count}, list of warnings)."""
    warnings: list[str] = []
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    domain_data: dict[str, dict] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        cols = _detect_columns(headers)
        if not cols["referring_domain"]:
            raise ValueError(
                f"{path.name}: no referring-domain column. Tried: {REFERRING_DOMAIN_ALIASES}. "
                f"Found columns: {headers}"
            )
        if not cols["dr"]:
            warnings.append(f"{path.name}: no DR/DA column detected; using 0 for all rows.")
        for row in reader:
            raw = row.get(cols["referring_domain"]) or ""
            d = _extract_root_domain(raw)
            if not d:
                continue
            dr = _safe_float(row.get(cols["dr"], "")) if cols["dr"] else 0.0
            traffic = _safe_int(row.get(cols["traffic"], "")) if cols["traffic"] else 0
            topical = _safe_float(row.get(cols["topical"], "")) if cols["topical"] else 0.5
            if d not in domain_data:
                domain_data[d] = {"dr": dr, "traffic": traffic, "topical": topical, "count": 1}
            else:
                # If multiple rows reference same domain, take MAX dr/traffic and bump count
                domain_data[d]["dr"] = max(domain_data[d]["dr"], dr)
                domain_data[d]["traffic"] = max(domain_data[d]["traffic"], traffic)
                domain_data[d]["count"] += 1
    return domain_data, warnings


def _normalize(value: float, max_value: float) -> float:
    if max_value <= 0: return 0.0
    return min(1.0, value / max_value)


def _data_freshness(path: Path, max_age_days: int = 90) -> bool:
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return (datetime.now(tz=timezone.utc) - mtime) < timedelta(days=max_age_days)
    except Exception:
        return False


def compute_gap(ours_csv: Path, competitor_csvs: list[Path], min_dr: float, top: int) -> dict:
    ours_data, ours_warnings = _load_backlinks(ours_csv)
    our_domains = set(ours_data.keys())

    competitor_data: dict[str, dict[str, dict]] = {}
    comp_warnings: list[str] = []
    for cp in competitor_csvs:
        cd, w = _load_backlinks(cp)
        competitor_data[cp.name] = cd
        comp_warnings.extend(w)

    # For each domain in any competitor, count how many competitors it links to
    domain_link_count: dict[str, int] = defaultdict(int)
    domain_best_metadata: dict[str, dict] = {}
    for cname, cdata in competitor_data.items():
        for d, meta in cdata.items():
            domain_link_count[d] += 1
            existing = domain_best_metadata.get(d)
            if not existing or meta["dr"] > existing["dr"]:
                domain_best_metadata[d] = {
                    "dr": meta["dr"], "traffic": meta["traffic"], "topical": meta["topical"],
                }

    # Gap = links to >=1 competitor but not to us
    gap_domains = {d for d in domain_link_count if d not in our_domains}

    # Filter
    if min_dr > 0:
        gap_domains = {d for d in gap_domains if domain_best_metadata[d]["dr"] >= min_dr}

    # Normalisers based on the gap set
    max_dr = max((domain_best_metadata[d]["dr"] for d in gap_domains), default=1.0)
    max_traffic = max((domain_best_metadata[d]["traffic"] for d in gap_domains), default=1)
    max_count = max((domain_link_count[d] for d in gap_domains), default=1)

    prospects = []
    for d in gap_domains:
        m = domain_best_metadata[d]
        count = domain_link_count[d]
        dr_n = _normalize(m["dr"], max_dr)
        traffic_n = _normalize(m["traffic"], max_traffic)
        count_n = _normalize(count, max_count)
        topical = m["topical"]
        priority = 0.40 * dr_n + 0.25 * count_n + 0.20 * traffic_n + 0.15 * topical
        prospects.append({
            "domain": d,
            "dr": round(m["dr"], 1),
            "domain_traffic": m["traffic"],
            "linking_competitors": count,
            "topical_relevance": round(topical, 2),
            "priority_score": round(priority, 3),
        })
    prospects.sort(key=lambda p: -p["priority_score"])
    prospects_top = prospects[:top]

    # Quality scorecard
    freshness_ok = _data_freshness(ours_csv) and all(_data_freshness(p) for p in competitor_csvs)
    sample_ok = len(ours_data) >= 50 and all(len(cd) >= 50 for cd in competitor_data.values())
    cov_ok = len(competitor_csvs) >= 2
    shared_count = sum(1 for c in domain_link_count.values() if c >= 2)
    overlap_ok = shared_count >= 5

    scorecard = {
        "data_freshness": "pass" if freshness_ok else "fail",
        "sample_size": "pass" if sample_ok else "fail",
        "competitor_coverage": "pass" if cov_ok else "warn",
        "link_overlap_signal": "pass" if overlap_ok else "fail",
        "status": (
            "ready" if (freshness_ok and sample_ok and overlap_ok) else "needs_review"
        ),
    }

    return {
        "report": "backlink-gap",
        "inputs": {
            "ours": str(ours_csv),
            "competitors": [str(p) for p in competitor_csvs],
            "filters": {"min_dr": min_dr, "top": top},
        },
        "warnings": ours_warnings + comp_warnings,
        "quality_scorecard": scorecard,
        "stats": {
            "our_referring_domains": len(our_domains),
            "competitor_referring_domains_total": len(domain_link_count),
            "gap_domains_before_filter": len(gap_domains) if min_dr == 0 else "(post-filter shown)",
            "gap_domains_after_filter": len(prospects),
            "shared_across_2plus_competitors": shared_count,
        },
        "prospects": prospects_top,
    }


def _format_text(result: dict) -> str:
    lines = []
    lines.append("Backlink gap analysis")
    lines.append("=" * 40)
    s = result["stats"]
    lines.append(f"Our domains: {s['our_referring_domains']:,}")
    lines.append(f"Competitor domains (total unique): {s['competitor_referring_domains_total']:,}")
    lines.append(f"Gap (after DR filter): {s['gap_domains_after_filter']:,}")
    lines.append(f"Shared across 2+ competitors: {s['shared_across_2plus_competitors']:,}")
    sc = result["quality_scorecard"]
    lines.append(f"Scorecard: status={sc['status']} | freshness={sc['data_freshness']} sample={sc['sample_size']} coverage={sc['competitor_coverage']} overlap={sc['link_overlap_signal']}")
    if result["warnings"]:
        lines.append("")
        lines.append("Warnings:")
        for w in result["warnings"]:
            lines.append(f"  ! {w}")
    lines.append("")
    lines.append(f"Top {len(result['prospects'])} link prospects (sorted by priority):")
    for i, p in enumerate(result["prospects"], start=1):
        lines.append(f"  {i:3}. {p['domain']:40s} DR={p['dr']:5.1f} links-{p['linking_competitors']}-comps traffic={p['domain_traffic']:>10,} pri={p['priority_score']}")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ours", required=True, type=Path, help="CSV of our backlinks")
    p.add_argument("--competitors", required=True, type=Path, nargs="+", help="One or more competitor backlink CSVs")
    p.add_argument("--min-dr", type=float, default=20.0, help="Minimum DR/DA to include (default 20)")
    p.add_argument("--top", type=int, default=50, help="Top N prospects to return (default 50)")
    p.add_argument("--out", type=Path, default=None, help="Output JSON path (omit for stdout)")
    p.add_argument("--format", choices=["json", "text"], default="json")
    args = p.parse_args()

    try:
        result = compute_gap(args.ours, args.competitors, args.min_dr, args.top)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr); return 2
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr); return 2

    out_text = json.dumps(result, indent=2, ensure_ascii=False) if args.format == "json" else _format_text(result)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)  # create the folder on demand
        args.out.write_text(out_text, encoding="utf-8")
        print(f"Wrote {args.out} ({len(result['prospects'])} prospects, status={result['quality_scorecard']['status']})")
    else:
        print(out_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
