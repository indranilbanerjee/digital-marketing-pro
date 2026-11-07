#!/usr/bin/env python3
"""Backlink profile analysis and quality scoring tool.

Analyzes a list of backlinks for quality signals including domain diversity,
authority distribution, follow/nofollow ratio, and anchor text patterns.
Returns a profile health score (0-100) with detailed breakdowns, flags for
concerning patterns, and actionable recommendations.

Usage:
    python link-profile-analyzer.py --links '[{"url":"https://example.com/page","anchor_text":"keyword","domain":"example.com","da":45,"follow":true}]'
    python link-profile-analyzer.py --file backlinks.json --brand-domain mybrand.com
"""

import argparse
import json
import sys
from pathlib import Path
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DA_BUCKETS = {
    "excellent_81_100": (81, 100),
    "strong_61_80": (61, 80),
    "good_41_60": (41, 60),
    "medium_21_40": (21, 40),
    "low_0_20": (0, 20),
}

GENERIC_ANCHORS = {
    "click here", "learn more", "read more", "here", "this", "visit",
    "website", "link", "go here", "check it out", "see more", "more info",
    "visit site", "click", "more", "view", "details", "info",
}


# ---------------------------------------------------------------------------
# Link parsing and validation
# ---------------------------------------------------------------------------

def parse_link(link_obj, brand_domain):
    """Parse and validate a single link object."""
    if not isinstance(link_obj, dict):
        return None

    url = link_obj.get("url", "")
    anchor = link_obj.get("anchor_text", "")
    domain = link_obj.get("domain", "")
    da = link_obj.get("da", 0)
    follow = link_obj.get("follow", True)

    # Extract domain from URL if not provided
    if not domain and url:
        try:
            # Simple domain extraction without urllib
            parts = url.split("//", 1)
            host = parts[1].split("/", 1)[0] if len(parts) > 1 else parts[0].split("/", 1)[0]
            domain = host.lower().strip()
        except (IndexError, AttributeError):
            domain = ""

    # Skip internal links
    if brand_domain and domain:
        brand_clean = brand_domain.lower().strip().replace("www.", "")
        domain_clean = domain.lower().strip().replace("www.", "")
        if domain_clean == brand_clean or domain_clean.endswith("." + brand_clean):
            return None

    return {
        "url": url,
        "anchor_text": anchor.strip() if anchor else "",
        "domain": domain.lower().strip() if domain else "",
        "da": max(0, min(100, int(da))) if da is not None else 0,
        "follow": bool(follow),
    }


# ---------------------------------------------------------------------------
# Authority distribution
# ---------------------------------------------------------------------------

def analyze_authority(links):
    """Bucket links by domain authority ranges."""
    total = len(links)
    if total == 0:
        return {}

    distribution = {}
    for bucket_name, (low, high) in DA_BUCKETS.items():
        count = sum(1 for link in links if low <= link["da"] <= high)
        distribution[bucket_name] = {
            "count": count,
            "percent": round(count / total * 100, 1),
        }

    return distribution


# ---------------------------------------------------------------------------
# Follow/nofollow analysis
# ---------------------------------------------------------------------------

def analyze_follow(links):
    """Analyze dofollow vs nofollow ratio."""
    total = len(links)
    if total == 0:
        return {"dofollow": {"count": 0, "percent": 0}, "nofollow": {"count": 0, "percent": 0}, "status": "no_data"}

    dofollow = sum(1 for link in links if link["follow"])
    nofollow = total - dofollow

    dofollow_pct = round(dofollow / total * 100, 1)
    nofollow_pct = round(nofollow / total * 100, 1)

    if nofollow_pct > 70:
        status = "high_nofollow"
    elif dofollow_pct > 95:
        status = "suspiciously_high_dofollow"
    else:
        status = "healthy"

    return {
        "dofollow": {"count": dofollow, "percent": dofollow_pct},
        "nofollow": {"count": nofollow, "percent": nofollow_pct},
        "status": status,
    }


# ---------------------------------------------------------------------------
# Anchor text analysis
# ---------------------------------------------------------------------------

def classify_anchor(anchor, brand_domain):
    """Classify an anchor text into a category."""
    if not anchor or anchor.strip() == "":
        return "image_no_anchor"

    anchor_lower = anchor.lower().strip()

    # URL anchor
    if anchor_lower.startswith("http://") or anchor_lower.startswith("https://") or anchor_lower.startswith("www."):
        return "url"

    # Generic anchor
    if anchor_lower in GENERIC_ANCHORS:
        return "generic"

    # Branded anchor: contains the brand domain name (without TLD)
    if brand_domain:
        brand_name = brand_domain.lower().replace("www.", "").split(".")[0]
        if brand_name and brand_name in anchor_lower:
            return "branded"

    # If no brand domain, treat company-looking names as branded (heuristic)
    # For now, classify remaining as partial_match or exact_match based on length
    word_count = len(anchor_lower.split())
    if word_count <= 3:
        return "exact_match"
    else:
        return "partial_match"


def analyze_anchors(links, brand_domain):
    """Categorize and analyze anchor text distribution."""
    total = len(links)
    if total == 0:
        return {}

    categories = {
        "branded": 0,
        "exact_match": 0,
        "partial_match": 0,
        "generic": 0,
        "url": 0,
        "image_no_anchor": 0,
    }

    for link in links:
        cat = classify_anchor(link["anchor_text"], brand_domain)
        categories[cat] = categories.get(cat, 0) + 1

    result = {}
    for cat, count in categories.items():
        result[cat] = {
            "count": count,
            "percent": round(count / total * 100, 1),
        }

    # Distribution health check
    exact_pct = result.get("exact_match", {}).get("percent", 0)
    branded_pct = result.get("branded", {}).get("percent", 0)

    if exact_pct > 30:
        dist_status = "over_optimized"
    elif branded_pct < 20 and brand_domain:
        dist_status = "low_branded"
    else:
        dist_status = "healthy"

    result["distribution_status"] = dist_status
    return result


# ---------------------------------------------------------------------------
# Profile health score
# ---------------------------------------------------------------------------

def compute_profile_health(links, authority_dist, follow_analysis, anchor_analysis, domain_diversity_ratio):
    """Compute overall profile health score (0-100)."""
    score = 0.0
    total = len(links)
    if total == 0:
        return 0

    # Domain diversity (0-25): higher diversity = better
    score += min(25, domain_diversity_ratio * 35)

    # Authority distribution (0-25): reward higher DA links
    good_plus = (
        authority_dist.get("excellent_81_100", {}).get("percent", 0) +
        authority_dist.get("strong_61_80", {}).get("percent", 0) +
        authority_dist.get("good_41_60", {}).get("percent", 0)
    )
    score += min(25, good_plus * 0.35)

    # Follow ratio health (0-25)
    follow_status = follow_analysis.get("status", "healthy")
    dofollow_pct = follow_analysis.get("dofollow", {}).get("percent", 50)
    if follow_status == "healthy":
        score += 25
    elif follow_status == "suspiciously_high_dofollow":
        score += 15
    elif follow_status == "high_nofollow":
        score += max(5, dofollow_pct * 0.25)

    # Anchor distribution health (0-25)
    dist_status = anchor_analysis.get("distribution_status", "healthy")
    if dist_status == "healthy":
        score += 25
    elif dist_status == "low_branded":
        score += 15
    elif dist_status == "over_optimized":
        score += 10

    return min(100, max(0, round(score)))


# ---------------------------------------------------------------------------
# Flags and recommendations
# ---------------------------------------------------------------------------

def generate_flags(links, authority_dist, follow_analysis, anchor_analysis, domain_diversity_ratio):
    """Generate warning flags for concerning patterns."""
    flags = []

    # Low authority dominance
    low_pct = authority_dist.get("low_0_20", {}).get("percent", 0)
    if low_pct > 40:
        flags.append({
            "severity": "high",
            "issue": f"Low authority links (DA 0-20) make up {low_pct:.1f}% of profile -- prioritize link building on DA 40+ sites",
        })
    elif low_pct > 25:
        flags.append({
            "severity": "medium",
            "issue": f"Low authority links (DA 0-20) make up {low_pct:.1f}% of profile -- focus link building on DA 40+ sites",
        })

    # Follow ratio issues
    follow_status = follow_analysis.get("status", "healthy")
    if follow_status == "high_nofollow":
        nf_pct = follow_analysis.get("nofollow", {}).get("percent", 0)
        flags.append({
            "severity": "high",
            "issue": f"Nofollow ratio at {nf_pct:.1f}% is very high -- pursue more dofollow link opportunities",
        })
    elif follow_status == "suspiciously_high_dofollow":
        df_pct = follow_analysis.get("dofollow", {}).get("percent", 0)
        flags.append({
            "severity": "medium",
            "issue": f"Dofollow ratio at {df_pct:.1f}% is suspiciously high -- natural profiles have 20-30% nofollow",
        })

    # Anchor text issues
    dist_status = anchor_analysis.get("distribution_status", "healthy")
    if dist_status == "over_optimized":
        exact_pct = anchor_analysis.get("exact_match", {}).get("percent", 0)
        flags.append({
            "severity": "high",
            "issue": f"Exact-match anchors at {exact_pct:.1f}% exceeds safe threshold (30%) -- diversify anchor text to avoid penalties",
        })
    elif dist_status == "low_branded":
        branded_pct = anchor_analysis.get("branded", {}).get("percent", 0)
        flags.append({
            "severity": "medium",
            "issue": f"Branded anchors at only {branded_pct:.1f}% -- natural profiles typically have 30%+ branded anchors",
        })

    # Low domain diversity
    if domain_diversity_ratio < 0.3:
        flags.append({
            "severity": "high",
            "issue": f"Domain diversity ratio is only {domain_diversity_ratio:.2f} -- too many links from the same domains",
        })
    elif domain_diversity_ratio < 0.5:
        flags.append({
            "severity": "medium",
            "issue": f"Domain diversity ratio is {domain_diversity_ratio:.2f} -- aim for 0.5+ by acquiring links from new domains",
        })

    return flags


def generate_recommendations(flags, authority_dist, follow_analysis, anchor_analysis, health_score):
    """Generate actionable recommendations."""
    recs = []

    # Authority-based recommendations
    excellent_count = authority_dist.get("excellent_81_100", {}).get("count", 0)
    strong_count = authority_dist.get("strong_61_80", {}).get("count", 0)
    if excellent_count + strong_count < 10:
        recs.append(
            "Pursue 5-10 high-authority (DA 60+) links through digital PR, "
            "guest posting on industry publications, or expert roundups."
        )

    low_count = authority_dist.get("low_0_20", {}).get("count", 0)
    low_pct = authority_dist.get("low_0_20", {}).get("percent", 0)
    if low_count > 0 and low_pct > 20:
        recs.append(
            f"Address {low_count} low-authority links: disavow if spammy, "
            f"otherwise acceptable as part of a natural profile."
        )

    # Anchor text recommendations
    dist_status = anchor_analysis.get("distribution_status", "healthy")
    if dist_status == "over_optimized":
        recs.append(
            "Diversify anchor text immediately -- increase branded and generic "
            "anchors to reduce over-optimization risk."
        )
    elif dist_status == "low_branded":
        recs.append(
            "Diversify anchor text -- increase branded anchors to 35%+ through "
            "brand mentions and citations."
        )

    # Follow ratio recommendations
    follow_status = follow_analysis.get("status", "healthy")
    if follow_status == "high_nofollow":
        recs.append(
            "Focus on earning dofollow links through content partnerships, "
            "resource pages, and editorial mentions."
        )
    elif follow_status == "suspiciously_high_dofollow":
        recs.append(
            "A natural link profile includes nofollow links from social media, "
            "forums, and directories -- these are expected and healthy."
        )

    # General health recommendations
    if health_score >= 80:
        recs.append(
            "Profile health is strong. Maintain current link building cadence "
            "and focus on quality over quantity."
        )
    elif health_score >= 60:
        recs.append(
            "Profile health is moderate. Address flagged issues to improve "
            "overall link equity and reduce penalty risk."
        )
    else:
        recs.append(
            "Profile health needs attention. Prioritize diversifying link sources, "
            "improving authority distribution, and cleaning up anchor text patterns."
        )

    return recs


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze_profile(links_raw, brand_domain):
    """Run full backlink profile analysis."""
    # Parse and filter links
    links = []
    for link_obj in links_raw:
        parsed = parse_link(link_obj, brand_domain)
        if parsed:
            links.append(parsed)

    total_links = len(links)
    if total_links == 0:
        return {"error": "No valid external links found after filtering"}

    # Domain diversity
    domains = set(link["domain"] for link in links if link["domain"])
    unique_domains = len(domains)
    domain_diversity_ratio = round(unique_domains / total_links, 2) if total_links > 0 else 0

    # Authority distribution
    authority_dist = analyze_authority(links)

    # Follow/nofollow analysis
    follow_analysis = analyze_follow(links)

    # Anchor text analysis
    anchor_analysis = analyze_anchors(links, brand_domain)

    # Profile health score
    health_score = compute_profile_health(
        links, authority_dist, follow_analysis, anchor_analysis, domain_diversity_ratio
    )

    # Flags
    flags = generate_flags(
        links, authority_dist, follow_analysis, anchor_analysis, domain_diversity_ratio
    )

    # Recommendations
    recommendations = generate_recommendations(
        flags, authority_dist, follow_analysis, anchor_analysis, health_score
    )

    output = {
        "profile_summary": {
            "total_links": total_links,
            "unique_domains": unique_domains,
            "domain_diversity_ratio": domain_diversity_ratio,
            "health_score": health_score,
        },
        "authority_distribution": authority_dist,
        "follow_analysis": follow_analysis,
        "anchor_text_analysis": anchor_analysis,
        "flags": flags,
        "recommendations": recommendations,
    }

    if brand_domain:
        output["brand_domain"] = brand_domain

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Backlink profile analysis and quality scoring"
    )
    parser.add_argument(
        "--links", default=None,
        help='JSON array of link objects: [{"url":"...","anchor_text":"...","domain":"...","da":45,"follow":true}]',
    )
    parser.add_argument(
        "--file", default=None,
        help="Path to JSON file containing the links array",
    )
    parser.add_argument(
        "--brand-domain", default=None,
        help="Brand domain to exclude internal links (e.g., mybrand.com)",
    )
    args = parser.parse_args()

    if not args.links and not args.file:
        json.dump(
            {"error": "Provide either --links (JSON array) or --file (path to JSON file)"},
            sys.stdout, indent=2,
        )
        print()
        sys.exit(2)

    # Load links
    links_raw = None
    if args.file:
        path = Path(args.file)
        if not path.exists():
            json.dump({"error": f"File not found: {args.file}"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
        try:
            content = path.read_text(encoding="utf-8-sig")
            links_raw = json.loads(content)
        except json.JSONDecodeError as exc:
            json.dump({"error": f"Invalid JSON in file: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
        except Exception as exc:
            json.dump({"error": f"Could not read file: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
    else:
        try:
            links_raw = _common.json_text(args.links, "--links")
        except json.JSONDecodeError as exc:
            json.dump({"error": f"Invalid JSON in --links: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(2)

    if not isinstance(links_raw, list):
        json.dump({"error": "Links data must be a JSON array"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    if len(links_raw) == 0:
        json.dump({"error": "Links array is empty"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    try:
        result = analyze_profile(links_raw, args.brand_domain)
        _common.finish(result)
    except Exception as exc:
        json.dump({"error": f"Analysis failed: {exc}"}, sys.stdout, indent=2)
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
