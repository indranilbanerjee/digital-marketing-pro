#!/usr/bin/env python3
"""Local SEO scoring tool for NAP consistency and GBP completeness.

Evaluates Name/Address/Phone/Website consistency across citation sources and
scores Google Business Profile completeness across 16 weighted fields. Returns
per-citation scores, aggregate consistency score, GBP completeness score, and
prioritized action items.

Dependencies: none (stdlib only)

Usage:
    python local-seo-checker.py --nap '{"name":"Acme Inc","address":"123 Main Street, Austin, TX 78701","phone":"(512) 555-1234","website":"https://acme.com"}' --citations '[{"source":"Yelp","name":"Acme Inc.","address":"123 Main St, Austin, TX 78701","phone":"512-555-1234","website":""}]'
    python local-seo-checker.py --gbp '{"business_name":"Acme Inc","primary_category":"Plumber","address":"123 Main Street","phone":"512-555-1234","website":"https://acme.com","hours":"Mon-Fri 9-5","description":"Full service plumbing...","photos_count":12}' --industry restaurant
    python local-seo-checker.py --nap '{"name":"Acme"}' --file citations.json --gbp '{"business_name":"Acme"}'
"""

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

# ---------------------------------------------------------------------------
# Address normalization maps
# ---------------------------------------------------------------------------

ADDRESS_EXPANSIONS = {
    "st": "street", "ave": "avenue", "blvd": "boulevard", "dr": "drive",
    "ln": "lane", "ct": "court", "rd": "road", "ste": "suite",
    "apt": "apartment", "fl": "floor", "hwy": "highway", "pkwy": "parkway",
    "pl": "place", "cir": "circle", "trl": "trail", "ter": "terrace",
    "expy": "expressway", "fwy": "freeway",
}

# ---------------------------------------------------------------------------
# GBP field weights
# ---------------------------------------------------------------------------

GBP_FIELDS = {
    "business_name":       {"max": 8,  "required": True},
    "primary_category":    {"max": 10, "required": True},
    "secondary_categories": {"max": 5,  "required": False},
    "address":             {"max": 8,  "required": True},
    "phone":               {"max": 8,  "required": True},
    "website":             {"max": 8,  "required": True},
    "hours":               {"max": 8,  "required": True},
    "description":         {"max": 10, "required": False},
    "photos_count":        {"max": 8,  "required": False},
    "posts_recent":        {"max": 5,  "required": False},
    "reviews_count":       {"max": 5,  "required": False},
    "review_response_rate": {"max": 5,  "required": False},
    "q_and_a":             {"max": 3,  "required": False},
    "services_products":   {"max": 5,  "required": False},
    "attributes":          {"max": 4,  "required": False},
    "booking_link":        {"max": 2,  "required": False},
}

# ---------------------------------------------------------------------------
# Industry-specific recommendation templates
# ---------------------------------------------------------------------------

INDUSTRY_TIPS = {
    "restaurant": [
        "Add high-quality food and menu photos to your GBP listing",
        "Enable online ordering or reservation links if available",
        "Post weekly specials or seasonal menu updates",
        "Ensure menu is uploaded as a PDF or linked on your website",
    ],
    "doctor": [
        "Add an appointment booking link to your GBP profile",
        "List all accepted insurance providers in the services section",
        "Include photos of the office and waiting area for patient comfort",
        "Respond to all reviews professionally (HIPAA-compliant, no patient details)",
    ],
    "lawyer": [
        "List all practice areas in the services/products section",
        "Add case result highlights or client testimonials (with permission)",
        "Include attorney headshots and office photos",
        "Ensure bar admission details are consistent across citations",
    ],
    "dentist": [
        "Add an appointment booking link for new patients",
        "Include photos of the office, treatment rooms, and staff",
        "List services like cleanings, orthodontics, and cosmetic dentistry",
        "Post before/after photos (with patient consent) for cosmetic procedures",
    ],
    "plumber": [
        "Highlight 24/7 emergency service availability in your description",
        "List all service areas and zip codes covered",
        "Add photos of completed jobs and work vehicles for trust signals",
        "Include licensing and bonding information in business attributes",
    ],
    "realtor": [
        "Add recent listing photos and virtual tour links",
        "Highlight neighborhoods and areas you specialize in",
        "Post market updates and open house announcements regularly",
        "Ensure license number is consistent across all citations",
    ],
}

# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def normalize_phone(phone):
    """Strip all non-digit characters from a phone number."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    # Strip leading 1 for US numbers
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def normalize_website(url):
    """Normalize a website URL for comparison."""
    if not url:
        return ""
    url = url.lower().strip()
    # Strip protocol
    url = re.sub(r"^https?://", "", url)
    # Strip www.
    url = re.sub(r"^www\.", "", url)
    # Strip trailing slash
    url = url.rstrip("/")
    return url


def normalize_address(address):
    """Normalize an address string for fuzzy comparison."""
    if not address:
        return ""
    addr = address.lower().strip()
    # Normalize common punctuation
    addr = addr.replace(",", " ").replace(".", " ").replace("#", " ")
    # Expand abbreviations (word boundary aware)
    words = addr.split()
    expanded = []
    for word in words:
        clean = word.strip(".,;:")
        expanded.append(ADDRESS_EXPANSIONS.get(clean, clean))
    addr = " ".join(expanded)
    # Collapse whitespace
    addr = re.sub(r"\s+", " ", addr).strip()
    return addr


def compare_names(canonical, citation):
    """Compare business names. Returns 'exact', 'contains', or 'mismatch'."""
    if not canonical or not citation:
        return "mismatch"
    c = canonical.lower().strip().rstrip(".,")
    t = citation.lower().strip().rstrip(".,")
    if c == t:
        return "exact"
    if c in t or t in c:
        return "contains"
    return "mismatch"


def compare_addresses(canonical, citation):
    """Compare addresses after normalization. Returns 'exact', 'partial', or 'mismatch' and issues."""
    c_norm = normalize_address(canonical)
    t_norm = normalize_address(citation)
    issues = []

    if not c_norm or not t_norm:
        return "mismatch", ["Address missing from citation"]

    if c_norm == t_norm:
        return "exact", []

    # Check if one contains the other (partial match)
    if c_norm in t_norm or t_norm in c_norm:
        # Identify specific differences
        if canonical.lower() != citation.lower():
            issues.append(f"Address formatting differs: '{citation}' vs canonical '{canonical}'")
        return "partial", issues

    # Check word overlap for partial matching
    c_words = set(c_norm.split())
    t_words = set(t_norm.split())
    overlap = c_words & t_words
    total = c_words | t_words
    similarity = len(overlap) / max(len(total), 1)

    if similarity >= 0.6:
        diff_words = (c_words - t_words) | (t_words - c_words)
        for word in diff_words:
            # Check if this is an abbreviation difference
            if word in ADDRESS_EXPANSIONS.values():
                abbrev = [k for k, v in ADDRESS_EXPANSIONS.items() if v == word]
                if abbrev:
                    issues.append(f"Address uses '{abbrev[0].title()}' instead of '{word.title()}'")
        if not issues:
            issues.append(f"Address partially matches (formatting difference)")
        return "partial", issues

    issues.append(f"Address mismatch: '{citation}' does not match canonical '{canonical}'")
    return "mismatch", issues


# ---------------------------------------------------------------------------
# NAP analysis
# ---------------------------------------------------------------------------

def analyze_nap(canonical, citations):
    """Analyze NAP consistency across citation sources."""
    citation_results = []
    total_score = 0

    for cit in citations:
        issues = []
        score = 0

        # Name comparison (30 pts max)
        name_match = compare_names(canonical.get("name", ""), cit.get("name", ""))
        if name_match == "exact":
            score += 30
        elif name_match == "contains":
            score += 15
            issues.append(f"Business name is a partial match: '{cit.get('name', '')}' vs '{canonical.get('name', '')}'")
        else:
            issues.append(f"Business name mismatch: '{cit.get('name', '')}' vs '{canonical.get('name', '')}'")

        # Address comparison (30 pts max)
        addr_match, addr_issues = compare_addresses(canonical.get("address", ""), cit.get("address", ""))
        if addr_match == "exact":
            score += 30
        elif addr_match == "partial":
            score += 15
        issues.extend(addr_issues)

        # Phone comparison (25 pts max)
        c_phone = normalize_phone(canonical.get("phone", ""))
        t_phone = normalize_phone(cit.get("phone", ""))
        if c_phone and t_phone and c_phone == t_phone:
            phone_match = "exact"
            score += 25
        else:
            phone_match = "mismatch"
            if not t_phone:
                issues.append("Phone number missing from citation")
            elif not c_phone:
                issues.append("Canonical phone number not provided for comparison")
            else:
                issues.append(f"Phone mismatch: '{cit.get('phone', '')}' vs '{canonical.get('phone', '')}'")

        # Website comparison (15 pts max)
        c_web = normalize_website(canonical.get("website", ""))
        t_web = normalize_website(cit.get("website", ""))
        if c_web and t_web and c_web == t_web:
            web_match = "exact"
            score += 15
        else:
            web_match = "mismatch"
            if not t_web:
                issues.append("Website missing from listing")
            elif not c_web:
                issues.append("Canonical website not provided for comparison")
            else:
                issues.append(f"Website mismatch: '{cit.get('website', '')}' vs '{canonical.get('website', '')}'")

        citation_results.append({
            "source": cit.get("source", "Unknown"),
            "name_match": name_match,
            "address_match": addr_match,
            "phone_match": phone_match,
            "website_match": web_match,
            "score": score,
            "issues": issues,
        })
        total_score += score

    consistency_score = round(total_score / max(len(citations), 1))

    # Build recommendations
    recommendations = []
    for cr in citation_results:
        if cr["issues"]:
            source = cr["source"]
            for issue in cr["issues"]:
                recommendations.append(f"Update {source} listing: {issue}")

    return {
        "canonical": canonical,
        "citations_checked": len(citations),
        "consistency_score": consistency_score,
        "citations": citation_results,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# GBP completeness analysis
# ---------------------------------------------------------------------------

def analyze_gbp(gbp, industry=None):
    """Score GBP profile completeness."""
    fields_result = {}
    total_score = 0
    total_possible = sum(f["max"] for f in GBP_FIELDS.values())
    missing_fields = []

    for field_name, config in GBP_FIELDS.items():
        max_pts = config["max"]
        value = gbp.get(field_name)
        present = value is not None and value != "" and value != 0 and value != [] and value is not False
        earned = 0

        if field_name == "business_name":
            earned = max_pts if present else 0
        elif field_name == "primary_category":
            earned = max_pts if present else 0
        elif field_name == "secondary_categories":
            if isinstance(value, list) and len(value) >= 2:
                earned = max_pts
            elif isinstance(value, list) and len(value) >= 1:
                earned = 3
            elif isinstance(value, int) and value >= 2:
                earned = max_pts
            elif isinstance(value, int) and value >= 1:
                earned = 3
        elif field_name == "address":
            earned = max_pts if present else 0
        elif field_name == "phone":
            earned = max_pts if present else 0
        elif field_name == "website":
            earned = max_pts if present else 0
        elif field_name == "hours":
            earned = max_pts if present else 0
        elif field_name == "description":
            if present:
                desc = str(value)
                earned = 8
                if len(desc) > 250:
                    earned = max_pts  # 10 (8 base + 2 bonus)
        elif field_name == "photos_count":
            count = int(value) if isinstance(value, (int, float)) else 0
            if count >= 10:
                earned = max_pts
            elif count >= 5:
                earned = 4
        elif field_name == "posts_recent":
            # Boolean or truthy: posted in last 7 days
            earned = max_pts if present else 0
        elif field_name == "reviews_count":
            count = int(value) if isinstance(value, (int, float)) else 0
            if count >= 10:
                earned = max_pts
            elif count >= 5:
                earned = 3
        elif field_name == "review_response_rate":
            rate = float(value) if isinstance(value, (int, float)) else 0
            # Accept both 0-1 and 0-100 formats
            if rate > 1:
                rate = rate / 100.0
            if rate >= 0.80:
                earned = max_pts
            elif rate >= 0.50:
                earned = 3
        elif field_name == "q_and_a":
            count = int(value) if isinstance(value, (int, float)) else 0
            earned = max_pts if count >= 5 else 0
        elif field_name == "services_products":
            if present:
                earned = max_pts
        elif field_name == "attributes":
            count = int(value) if isinstance(value, (int, float)) else 0
            if isinstance(value, list):
                count = len(value)
            earned = max_pts if count >= 3 else 0
        elif field_name == "booking_link":
            earned = max_pts if present else 0

        if not present:
            missing_fields.append(field_name)

        fields_result[field_name] = {
            "present": present,
            "score": earned,
            "max": max_pts,
        }
        total_score += earned

    completeness_score = round((total_score / max(total_possible, 1)) * 100)

    # Recommendations
    recommendations = []
    if "description" in missing_fields:
        recommendations.append("Write a compelling business description (aim for 250+ characters)")
    elif gbp.get("description") and len(str(gbp["description"])) <= 250:
        recommendations.append("Expand your business description beyond 250 characters for bonus points")

    photos = gbp.get("photos_count", 0)
    if isinstance(photos, (int, float)):
        if photos < 5:
            recommendations.append(f"Add {5 - int(photos)}+ photos to GBP (currently {int(photos)})")
        elif photos < 10:
            recommendations.append(f"Add {10 - int(photos)} more photos to reach the 10-photo threshold (currently {int(photos)})")

    if not gbp.get("posts_recent"):
        recommendations.append("Post a Google Business update this week (0 recent posts detected)")

    reviews = gbp.get("reviews_count", 0)
    if isinstance(reviews, (int, float)) and reviews < 10:
        recommendations.append(f"Build review count to 10+ (currently {int(reviews)}). Send review request emails after service.")

    response_rate = gbp.get("review_response_rate", 0)
    if isinstance(response_rate, (int, float)):
        rate = response_rate if response_rate <= 1 else response_rate / 100.0
        if rate < 0.80:
            recommendations.append(f"Respond to more reviews (current rate: {rate:.0%}, target: 80%+)")

    qa = gbp.get("q_and_a", 0)
    if isinstance(qa, (int, float)) and qa < 5:
        recommendations.append("Seed 5+ Q&A questions with answers about common customer questions")

    if not gbp.get("services_products"):
        recommendations.append("Add your services or products list to your GBP profile")

    attrs = gbp.get("attributes", 0)
    attr_count = len(attrs) if isinstance(attrs, list) else (int(attrs) if isinstance(attrs, (int, float)) else 0)
    if attr_count < 3:
        recommendations.append("Set at least 3 business attributes (accessibility, amenities, etc.)")

    if not gbp.get("booking_link"):
        recommendations.append("Add an online booking or appointment link if applicable")

    if not gbp.get("secondary_categories"):
        recommendations.append("Add 2+ secondary categories to improve visibility for related searches")

    # Industry-specific tips
    if industry and industry.lower() in INDUSTRY_TIPS:
        for tip in INDUSTRY_TIPS[industry.lower()]:
            if tip not in recommendations:
                recommendations.append(tip)

    return {
        "completeness_score": completeness_score,
        "total_possible": total_possible,
        "fields": fields_result,
        "missing_fields": missing_fields,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Priority actions builder
# ---------------------------------------------------------------------------

def build_priority_actions(nap_result, gbp_result):
    """Combine findings into prioritized action list."""
    actions = []

    # NAP priority actions
    if nap_result:
        inconsistent = [c for c in nap_result.get("citations", []) if c["score"] < 70]
        if inconsistent:
            sources = ", ".join(c["source"] for c in inconsistent)
            actions.append({"priority": "high", "action": f"Fix NAP inconsistencies on {sources}"})

        missing_web = [c for c in nap_result.get("citations", []) if c["website_match"] == "mismatch"]
        if missing_web:
            sources = ", ".join(c["source"] for c in missing_web)
            actions.append({"priority": "medium", "action": f"Add or correct website URL on {sources}"})

    # GBP priority actions
    if gbp_result:
        missing = gbp_result.get("missing_fields", [])
        required_missing = [f for f in missing if GBP_FIELDS.get(f, {}).get("required")]
        if required_missing:
            actions.append({"priority": "high", "action": f"Complete required GBP fields: {', '.join(required_missing)}"})

        fields = gbp_result.get("fields", {})
        photos_info = fields.get("photos_count", {})
        if photos_info.get("score", 0) < photos_info.get("max", 8):
            actions.append({"priority": "high", "action": "Add more photos to GBP to reach the 10-photo threshold"})

        if fields.get("posts_recent", {}).get("score", 0) == 0:
            actions.append({"priority": "medium", "action": "Create weekly Google Posts schedule"})

        if fields.get("review_response_rate", {}).get("score", 0) < fields.get("review_response_rate", {}).get("max", 5):
            actions.append({"priority": "medium", "action": "Implement a review response workflow (target 80%+ response rate)"})

        if fields.get("q_and_a", {}).get("score", 0) == 0:
            actions.append({"priority": "low", "action": "Seed Google Q&A with frequently asked questions and answers"})

    return actions


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Local SEO scoring tool for NAP consistency and GBP completeness"
    )
    parser.add_argument("--nap", default=None,
                        help='JSON object with canonical name, address, phone, website')
    parser.add_argument("--citations", default=None,
                        help='JSON array of citation objects [{source, name, address, phone, website}]')
    parser.add_argument("--file", default=None,
                        help="Path to JSON file with citations array")
    parser.add_argument("--gbp", default=None,
                        help="JSON object with GBP profile fields for completeness check")
    parser.add_argument("--industry", default=None,
                        help="Industry for industry-specific recommendations")
    args = parser.parse_args()

    # --- Validate at least one mode ---
    if not args.nap and not args.gbp:
        json.dump({"error": "Provide --nap (with --citations or --file) and/or --gbp for analysis"}, sys.stdout, indent=2)
        print()
        sys.exit(2)

    nap_result = None
    gbp_result = None

    # --- NAP analysis ---
    if args.nap:
        try:
            canonical = json.loads(args.nap)
        except json.JSONDecodeError as exc:
            json.dump({"error": f"Invalid JSON in --nap: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(2)

        citations = []
        if args.citations:
            try:
                citations = json.loads(args.citations)
            except json.JSONDecodeError as exc:
                json.dump({"error": f"Invalid JSON in --citations: {exc}"}, sys.stdout, indent=2)
                print()
                sys.exit(2)
        if args.file:
            path = Path(args.file)
            if not path.exists():
                json.dump({"error": f"File not found: {args.file}"}, sys.stdout, indent=2)
                print()
                sys.exit(1)
            try:
                file_data = json.loads(path.read_text(encoding="utf-8-sig"))
                if isinstance(file_data, list):
                    citations.extend(file_data)
                else:
                    json.dump({"error": "Citations file must contain a JSON array"}, sys.stdout, indent=2)
                    print()
                    sys.exit(1)
            except json.JSONDecodeError as exc:
                json.dump({"error": f"Invalid JSON in file: {exc}"}, sys.stdout, indent=2)
                print()
                sys.exit(1)
            except Exception as exc:
                json.dump({"error": f"Could not read file: {exc}"}, sys.stdout, indent=2)
                print()
                sys.exit(1)

        if not citations:
            json.dump({"error": "NAP analysis requires --citations or --file with citation data"}, sys.stdout, indent=2)
            print()
            sys.exit(2)

        if not isinstance(citations, list):
            json.dump({"error": "--citations must be a JSON array"}, sys.stdout, indent=2)
            print()
            sys.exit(2)

        nap_result = analyze_nap(canonical, citations)

    # --- GBP analysis ---
    if args.gbp:
        try:
            gbp_data = json.loads(args.gbp)
        except json.JSONDecodeError as exc:
            json.dump({"error": f"Invalid JSON in --gbp: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(2)

        gbp_result = analyze_gbp(gbp_data, industry=args.industry)

    # --- Combine output ---
    output = {}

    if nap_result:
        output["nap_analysis"] = nap_result
    if gbp_result:
        output["gbp_analysis"] = gbp_result

    # Overall score: weighted average of available analyses
    scores = []
    if nap_result:
        scores.append(nap_result["consistency_score"])
    if gbp_result:
        scores.append(gbp_result["completeness_score"])
    output["overall_score"] = round(sum(scores) / max(len(scores), 1))

    # Priority actions
    output["priority_actions"] = build_priority_actions(nap_result, gbp_result)

    json.dump(output, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
