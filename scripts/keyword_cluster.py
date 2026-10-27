#!/usr/bin/env python3
"""
keyword_cluster.py — cluster keywords into pillar+spokes content architecture.

Two clustering modes (auto-selected based on input shape):

  1. SERP-overlap clustering (preferred) — when --serps JSON is provided
     mapping keyword -> list of top-N result URLs. Two keywords cluster
     together when Jaccard(SERP_a, SERP_b) >= --overlap (default 0.4).

  2. Lexical clustering (fallback) — when only --keywords CSV is given.
     Uses token-overlap Jaccard on normalized tokens (stopword-stripped).
     Lower confidence; SERP mode strongly preferred.

For each cluster, picks a pillar (highest-volume keyword with broad-intent
score) and spokes (long-tail or question variants). Computes priority score:

    priority = 0.40 * volume_pct + 0.30 * (1 - kd_pct) + 0.30 * commercial_pct

Quality scorecard gates ALL must pass for status=ready:

  - cannibalisation: "warn" when two clusters' pillar keywords share >= 60%
    of their token sets (Jaccard) AND have the same primary intent — those
    pillars will likely compete for the same SERP; the offending pairs are
    listed in cannibalisation_pairs. "pass" otherwise.
  - orphan: every cluster has >= 1 spoke (or it's marked pillar-only)
  - coverage: >= 80% of input seeds assigned to a cluster
  - anchor_diversity: each cluster has >= 2 anchor-text variants suggested

Stdlib only. No third-party deps.

Usage
-----

  # SERP-overlap clustering (preferred)
  python scripts/keyword_cluster.py \\
      --keywords seeds.csv --serps serps.json \\
      --overlap 0.4 --min-volume 100 --max-kd 60 \\
      --out clusters.json

  # Lexical fallback (when SERPs not available)
  python scripts/keyword_cluster.py --keywords seeds.csv --out clusters.json

  # Plain text output for skill agents to read
  python scripts/keyword_cluster.py --keywords seeds.csv --format text

Input CSV columns
-----------------
  Required: keyword
  Optional: volume, kd (keyword difficulty 0-100), intent
            (one of: informational | navigational | commercial | transactional)

Output JSON shape
-----------------
  {
    "mode": "serp" | "lexical",
    "clusters": [
      {
        "id": 1,
        "pillar": "ecommerce SEO",
        "spokes": ["ecommerce SEO guide", "ecommerce product page SEO", ...],
        "primary_intent": "informational",
        "estimated_volume": 12400,
        "average_kd": 45,
        "priority_score": 0.78,
        "anchor_suggestions": ["ecommerce SEO", "SEO for ecommerce", "online store SEO"],
        "internal_link_targets": [{"from_cluster": 2, "anchor": "..."}, ...]
      },
      ...
    ],
    "quality_scorecard": {
      "cannibalisation": "pass" | "warn",
      "cannibalisation_pairs": [...],
      "orphan": "pass" | "fail",
      "coverage": "pass" | "fail",
      "anchor_diversity": "pass" | "fail",
      "status": "ready" | "needs_review"
    },
    "stats": { "input_seeds": N, "clusters": K, "coverage_pct": 87.5 }
  }

Exit codes
----------
  0 = success (regardless of scorecard status — caller inspects JSON)
  2 = bad input (CSV missing keyword column, SERP JSON malformed)
"""

from __future__ import annotations
import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "for", "to", "in", "on", "at",
    "with", "by", "from", "is", "are", "was", "were", "be", "been", "as",
    "vs", "v", "how", "what", "why", "when", "where", "best", "top", "free",
    "online", "site", "page", "guide",
}

COMMERCIAL_INTENT_TERMS = {
    "buy", "price", "cost", "cheap", "deal", "discount", "review", "vs",
    "compare", "best", "top", "alternative", "pricing", "subscription",
}

QUESTION_PREFIXES = {"how", "what", "why", "when", "where", "which", "who", "is", "are", "can", "should", "does", "do"}


def _tokenize(text: str) -> set[str]:
    # [^\W_] = Unicode letters and digits, no underscore. The old [a-z0-9]+
    # split every non-ASCII letter: "bürohaftpflicht" -> ["b", "rohaftpflicht"],
    # which silently broke clustering, the link map, and the cannibalisation
    # gate for any non-English keyword set (GitHub issue #11).
    toks = re.findall(r"[^\W_]+", text.lower())
    return {t for t in toks if t not in STOPWORDS and len(t) > 1}


def _jaccard(a: set, b: set) -> float:
    """Pure set Jaccard — used for SERP URL overlap, where exact match is right."""
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


# Compounding languages (German, Dutch, the Scandinavian languages) write
# "betriebshaftpflichtversicherung" where English writes three words, so exact
# token match scores related keywords at 0.0. Two tokens also count as a match
# when one CONTAINS the other and the shorter is at least this long — long
# enough that "in"/"kosten" prefixes don't create noise, short enough that real
# compound stems ("betriebshaftpflicht") do match their extensions.
_COMPOUND_MIN_LEN = 6


def _tokens_match(x: str, y: str) -> bool:
    if x == y:
        return True
    shorter, longer = (x, y) if len(x) <= len(y) else (y, x)
    return len(shorter) >= _COMPOUND_MIN_LEN and shorter in longer


def _lexical_similarity(a: set, b: set) -> float:
    """Jaccard generalised with compound-aware token matching (greedy one-to-one).

    Identical to _jaccard whenever no containment pairs exist, so English
    keyword sets score exactly as before."""
    if not a or not b:
        return 0.0
    exact = a & b
    matched = len(exact)
    remaining_b = [t for t in b if t not in exact]
    for x in (t for t in a if t not in exact):
        for i, y in enumerate(remaining_b):
            if _tokens_match(x, y):
                matched += 1
                del remaining_b[i]
                break
    union = len(a) + len(b) - matched
    return matched / union if union else 0.0


def _classify_intent(keyword: str, override: str | None = None) -> str:
    if override:
        return override.lower().strip()
    toks = _tokenize(keyword)
    first_word = keyword.lower().split()[0] if keyword else ""
    if first_word in QUESTION_PREFIXES or any(q in toks for q in {"how", "what", "why"}):
        return "informational"
    if toks & COMMERCIAL_INTENT_TERMS:
        return "commercial"
    if any(t in toks for t in {"signup", "signin", "login", "checkout", "order"}):
        return "transactional"
    return "informational"


def _commercial_score(keyword: str) -> float:
    toks = _tokenize(keyword)
    hits = len(toks & COMMERCIAL_INTENT_TERMS)
    return min(1.0, hits / 2.0)


def _load_keywords(csv_path: Path) -> list[dict]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if "keyword" not in (reader.fieldnames or []):
            raise ValueError(f"CSV must have a 'keyword' column. Found: {reader.fieldnames}")
        rows = []
        for row in reader:
            kw = (row.get("keyword") or "").strip()
            if not kw:
                continue
            try:
                volume = int((row.get("volume") or "0").replace(",", "") or 0)
            except (ValueError, TypeError):
                volume = 0
            try:
                kd = float((row.get("kd") or "0") or 0)
            except (ValueError, TypeError):
                kd = 0.0
            rows.append({
                "keyword": kw,
                "volume": volume,
                "kd": kd,
                "intent": _classify_intent(kw, (row.get("intent") or "").strip() or None),
                "commercial": _commercial_score(kw),
                "tokens": _tokenize(kw),
            })
    return rows


def _load_serps(serps_path: Path | None) -> dict[str, set[str]]:
    if serps_path is None:
        return {}
    if not serps_path.is_file():
        raise FileNotFoundError(f"SERPs JSON not found: {serps_path}")
    raw = json.loads(serps_path.read_text(encoding="utf-8-sig"))
    out: dict[str, set[str]] = {}
    for kw, urls in raw.items():
        if isinstance(urls, list):
            out[kw.strip().lower()] = set(u.strip() for u in urls if isinstance(u, str))
    return out


def _filter(keywords: list[dict], min_volume: int, max_kd: float) -> list[dict]:
    return [k for k in keywords if k["volume"] >= min_volume and (k["kd"] <= max_kd if k["kd"] else True)]


def _cluster_by_serp(keywords: list[dict], serps: dict[str, set[str]], overlap: float) -> list[list[dict]]:
    n = len(keywords)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        a_urls = serps.get(keywords[i]["keyword"].lower(), set())
        if not a_urls:
            continue
        for j in range(i + 1, n):
            b_urls = serps.get(keywords[j]["keyword"].lower(), set())
            if not b_urls:
                continue
            if _jaccard(a_urls, b_urls) >= overlap:
                union(i, j)

    groups: dict[int, list[dict]] = defaultdict(list)
    for i, k in enumerate(keywords):
        groups[find(i)].append(k)
    return [g for g in groups.values() if g]


def _cluster_by_lexical(keywords: list[dict], overlap: float) -> list[list[dict]]:
    n = len(keywords)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        a = keywords[i]["tokens"]
        for j in range(i + 1, n):
            if _lexical_similarity(a, keywords[j]["tokens"]) >= overlap:
                union(i, j)

    groups: dict[int, list[dict]] = defaultdict(list)
    for i, k in enumerate(keywords):
        groups[find(i)].append(k)
    return [g for g in groups.values() if g]


def _build_cluster_record(idx: int, group: list[dict], all_volumes: list[int]) -> dict:
    # Pillar = shortest informational keyword with highest volume (broadest)
    by_pillar_fitness = sorted(
        group,
        key=lambda k: (
            -(k["volume"] or 0),
            len(k["tokens"]),
        ),
    )
    pillar = by_pillar_fitness[0]["keyword"]
    spokes = [k["keyword"] for k in group if k["keyword"] != pillar][:12]

    intents = Counter(k["intent"] for k in group)
    primary_intent = intents.most_common(1)[0][0] if intents else "informational"

    total_vol = sum(k["volume"] for k in group)
    avg_kd = round(sum(k["kd"] for k in group) / max(1, len([k for k in group if k["kd"]])))
    avg_commercial = sum(k["commercial"] for k in group) / max(1, len(group))

    max_vol = max(all_volumes) if all_volumes else 1
    volume_pct = (total_vol / max_vol) if max_vol else 0
    volume_pct = min(1.0, math.log1p(volume_pct * 9) / math.log(10))  # log-normalize
    kd_pct = (avg_kd / 100.0) if avg_kd else 0.0
    priority = 0.40 * volume_pct + 0.30 * (1 - kd_pct) + 0.30 * avg_commercial

    anchor_suggestions = _suggest_anchors(pillar, spokes)
    pillar_only = len(spokes) == 0

    return {
        "id": idx,
        "pillar": pillar,
        "spokes": spokes,
        "pillar_only": pillar_only,
        "primary_intent": primary_intent,
        "estimated_volume": total_vol,
        "average_kd": avg_kd,
        "priority_score": round(priority, 3),
        "anchor_suggestions": anchor_suggestions,
        "internal_link_targets": [],
    }


def _suggest_anchors(pillar: str, spokes: list[str]) -> list[str]:
    anchors = {pillar}
    if spokes:
        anchors.add(spokes[0])
    if len(spokes) > 1:
        anchors.add(spokes[-1])
    if len(pillar.split()) > 2:
        anchors.add(" ".join(pillar.split()[:2]))
    return sorted(anchors)


def _build_internal_link_map(clusters: list[dict]) -> None:
    # Within each cluster: spokes link to pillar (intra-cluster).
    # Across clusters: shared-token clusters get cross-link suggestions.
    cluster_tokens = {c["id"]: _tokenize(c["pillar"]) for c in clusters}
    for c in clusters:
        targets = []
        for other in clusters:
            if other["id"] == c["id"]:
                continue
            sim = _lexical_similarity(cluster_tokens[c["id"]], cluster_tokens[other["id"]])
            if sim >= 0.2:
                targets.append({
                    "to_cluster": other["id"],
                    "anchor": other["pillar"],
                    "similarity": round(sim, 3),
                })
        c["internal_link_targets"] = sorted(targets, key=lambda t: -t["similarity"])[:3]


def _quality_scorecard(clusters: list[dict], n_input_seeds: int, n_clustered: int) -> dict:
    coverage_pct = (n_clustered / n_input_seeds * 100) if n_input_seeds else 0

    # Cannibalisation: two clusters whose pillar keywords share >=60% of their
    # token sets (compound-aware similarity — see _lexical_similarity) AND have
    # the same primary intent will likely compete for the same SERP. Reported
    # as "warn" with the offending pairs listed.
    cannibalisation_pairs = []
    for i, a in enumerate(clusters):
        a_tokens = _tokenize(a["pillar"])
        for b in clusters[i + 1:]:
            if a["primary_intent"] != b["primary_intent"]:
                continue
            if _lexical_similarity(a_tokens, _tokenize(b["pillar"])) >= 0.6:
                cannibalisation_pairs.append({
                    "cluster_ids": [a["id"], b["id"]],
                    "pillars": [a["pillar"], b["pillar"]],
                    "primary_intent": a["primary_intent"],
                })
    cannibalisation = "warn" if cannibalisation_pairs else "pass"

    # Multi-keyword clusters must have >=1 spoke (else they should have merged).
    # Single-keyword clusters are pillar_only and exempt — they represent
    # distinct intents that didn't share enough SERP/lexical signal to merge.
    multi_kw = [c for c in clusters if not c["pillar_only"]]
    orphan = "pass" if all(len(c["spokes"]) >= 1 for c in multi_kw) else "fail"

    coverage = "pass" if coverage_pct >= 80 else "fail"

    # Anchor diversity gate applies only to clusters with spokes — pillar-only
    # clusters only naturally have 1 anchor (the pillar itself), which is fine.
    diverse_targets = [c for c in clusters if not c["pillar_only"]]
    anchor_diversity = "pass" if all(len(c["anchor_suggestions"]) >= 2 for c in diverse_targets) else "fail"

    # Soft signal: too many pillar-only clusters (>50%) means clustering
    # threshold may be too strict. Reported as a separate warning.
    pillar_only_pct = (len([c for c in clusters if c["pillar_only"]]) / max(1, len(clusters))) * 100
    fragmentation_warning = pillar_only_pct > 50

    all_pass = all(v == "pass" for v in [cannibalisation, orphan, coverage, anchor_diversity])
    return {
        "cannibalisation": cannibalisation,
        "cannibalisation_pairs": cannibalisation_pairs,
        "orphan": orphan,
        "coverage": coverage,
        "anchor_diversity": anchor_diversity,
        "fragmentation_warning": fragmentation_warning,
        "pillar_only_pct": round(pillar_only_pct, 1),
        "status": "ready" if all_pass else "needs_review",
    }


def cluster(keywords_csv: Path, serps_json: Path | None, overlap: float, min_volume: int, max_kd: float) -> dict:
    keywords = _load_keywords(keywords_csv)
    n_input = len(keywords)
    keywords = _filter(keywords, min_volume, max_kd)
    serps = _load_serps(serps_json)

    if serps:
        mode = "serp"
        groups = _cluster_by_serp(keywords, serps, overlap)
    else:
        mode = "lexical"
        groups = _cluster_by_lexical(keywords, overlap)

    all_volumes = [k["volume"] for k in keywords]
    clusters = [_build_cluster_record(i + 1, g, all_volumes) for i, g in enumerate(groups)]
    clusters.sort(key=lambda c: -c["priority_score"])
    for i, c in enumerate(clusters, start=1):
        c["id"] = i
    _build_internal_link_map(clusters)

    n_clustered = sum(len(g) for g in groups)
    scorecard = _quality_scorecard(clusters, n_input, n_clustered)

    return {
        "mode": mode,
        "clusters": clusters,
        "quality_scorecard": scorecard,
        "stats": {
            "input_seeds": n_input,
            "after_filter": len(keywords),
            "clusters": len(clusters),
            "coverage_pct": round((n_clustered / n_input * 100) if n_input else 0, 1),
        },
    }


def _format_text(result: dict) -> str:
    lines = []
    lines.append("Keyword cluster plan")
    lines.append("=" * 40)
    lines.append(f"Mode: {result['mode']}")
    s = result["stats"]
    lines.append(f"Stats: {s['input_seeds']} seeds -> {s['after_filter']} after filter -> {s['clusters']} clusters ({s['coverage_pct']}% coverage)")
    sc = result["quality_scorecard"]
    lines.append(f"Scorecard: status={sc['status']} | cannibalisation={sc['cannibalisation']} orphan={sc['orphan']} coverage={sc['coverage']} anchor_diversity={sc['anchor_diversity']}")
    lines.append("")
    for c in result["clusters"]:
        lines.append(f"[{c['id']}] PILLAR: {c['pillar']}  (priority {c['priority_score']}, vol {c['estimated_volume']}, KD {c['average_kd']}, intent {c['primary_intent']})")
        for sp in c["spokes"][:8]:
            lines.append(f"     - {sp}")
        if c["internal_link_targets"]:
            link_str = ", ".join(f"->{t['to_cluster']}" for t in c["internal_link_targets"])
            lines.append(f"     links: {link_str}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--keywords", required=True, type=Path, help="CSV with at least a 'keyword' column")
    p.add_argument("--serps", type=Path, default=None, help="Optional JSON: {keyword: [top result URLs]}")
    p.add_argument("--overlap", type=float, default=0.4, help="Jaccard threshold to merge (default 0.4)")
    p.add_argument("--min-volume", type=int, default=0, help="Filter: minimum search volume")
    p.add_argument("--max-kd", type=float, default=100.0, help="Filter: maximum keyword difficulty (0-100)")
    p.add_argument("--out", type=Path, default=None, help="Output JSON path (omit for stdout)")
    p.add_argument("--format", choices=["json", "text"], default="json")
    args = p.parse_args()

    try:
        result = cluster(args.keywords, args.serps, args.overlap, args.min_volume, args.max_kd)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr); return 2
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr); return 2
    except OSError as e:  # an empty path (a folder), no permission, a name too long
        print(f"ERROR: cannot read --keywords or --serps: {e.strerror or e}", file=sys.stderr); return 2

    out_text = json.dumps(result, indent=2, ensure_ascii=False) if args.format == "json" else _format_text(result)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)  # create the folder on demand
        args.out.write_text(out_text, encoding="utf-8")
        print(f"Wrote {args.out} ({result['stats']['clusters']} clusters, status={result['quality_scorecard']['status']})")
    else:
        print(out_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
