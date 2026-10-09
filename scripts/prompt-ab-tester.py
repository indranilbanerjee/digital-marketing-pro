#!/usr/bin/env python3
"""
prompt-ab-tester.py
===================
Prompt/output A/B testing tracker for Digital Marketing Pro.

Creates named tests, logs quality scores for each variant, compares averages,
determines a winner, and provides a statistical-significance hint.

Storage:
    ~/.claude-marketing/brands/{slug}/quality/ab-tests/{test-name}.json

Actions:
    create-test   Create a new A/B test
    log-variant   Log eval scores for a variant
    get-results   Compare variants and determine winner
    list-tests    List all tests for the brand

Usage:
    python prompt-ab-tester.py --action create-test --test-name email-subject-q1 --data '{"description":"Testing email subject line styles"}'
    python prompt-ab-tester.py --action log-variant --test-name email-subject-q1 --variant A --data '{"description":"Direct benefit","scores":{"content_quality":85,"brand_voice":78,"composite":82}}'
    python prompt-ab-tester.py --action log-variant --test-name email-subject-q1 --variant B --data '{"description":"Question-based","scores":{"content_quality":78,"brand_voice":82,"composite":80}}'
    python prompt-ab-tester.py --action get-results --test-name email-subject-q1
    python prompt-ab-tester.py --action list-tests
    python prompt-ab-tester.py --brand acme --action list-tests
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

BRANDS_DIR = _common.brands_root()
ACTIVE_BRAND_FILE = BRANDS_DIR / "_active-brand.json"


# ---------------------------------------------------------------------------
# Brand resolution
# ---------------------------------------------------------------------------

def resolve_brand(slug):
    """Resolve brand slug — use provided value or fall back to active brand."""
    if slug:
        return slug

    if ACTIVE_BRAND_FILE.exists():
        try:
            active = json.loads(ACTIVE_BRAND_FILE.read_text(encoding="utf-8"))
            return active.get("active_slug")
        except (json.JSONDecodeError, OSError):
            pass

    return None


def sanitize_test_name(name):
    """Slugify a test name for safe filename use. Returns (slug, error)."""
    raw = (name or "").strip()
    if not raw or ".." in raw or "/" in raw or "\\" in raw:
        return None, ("Invalid --test-name: must be non-empty and must not "
                      "contain path separators or '..'.")
    slug = re.sub(r"[^a-z0-9-]+", "-", raw.lower()).strip("-")
    if not slug:
        return None, ("Invalid --test-name: no usable characters after "
                      "slugifying (use letters, digits, hyphens).")
    return slug, None


def get_tests_dir(slug):
    """Return the A/B tests directory for a brand, creating if needed."""
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return None, f"Brand '{slug}' not found. Run /digital-marketing-pro:brand-setup first."

    tests_dir = brand_dir / "quality" / "ab-tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    return tests_dir, None


# ---------------------------------------------------------------------------
# Test file I/O
# ---------------------------------------------------------------------------

def load_test(tests_dir, test_name):
    """Load a test file by name. Returns (data, error)."""
    filepath = tests_dir / f"{test_name}.json"
    if not filepath.exists():
        return None, f"Test '{test_name}' not found."
    try:
        return json.loads(filepath.read_text(encoding="utf-8")), None
    except json.JSONDecodeError:
        return None, f"Test file corrupted: {test_name}.json"


def save_test(tests_dir, test_name, data):
    """Save a test file."""
    filepath = tests_dir / f"{test_name}.json"
    filepath.write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def action_create_test(slug, test_name, data):
    """Create a new A/B test."""
    tests_dir, err = get_tests_dir(slug)
    if err:
        return {"error": err}

    # Check if test already exists
    filepath = tests_dir / f"{test_name}.json"
    if filepath.exists():
        return {"error": f"Test '{test_name}' already exists. Choose a different name."}

    now = datetime.now().isoformat()
    test = {
        "test_name": test_name,
        "description": data.get("description", ""),
        "created_at": now,
        "updated_at": now,
        "status": "active",
        "variants": {},
    }

    save_test(tests_dir, test_name, test)

    return {
        "status": "created",
        "test_name": test_name,
        "description": test["description"],
        "created_at": now,
    }


def action_log_variant(slug, test_name, variant_label, data):
    """Log eval scores for a variant in an existing test."""
    tests_dir, err = get_tests_dir(slug)
    if err:
        return {"error": err}

    test, err = load_test(tests_dir, test_name)
    if err:
        return {"error": err}

    scores = data.get("scores")
    if not scores or not isinstance(scores, dict):
        return {"error": "Missing or invalid 'scores' object in --data."}
    if "composite" not in scores:
        return {"error": "'scores.composite' is required."}

    variants = test.get("variants", {})

    # Create variant if it does not exist
    if variant_label not in variants:
        variants[variant_label] = {
            "description": data.get("description", ""),
            "evals": [],
        }
    elif data.get("description") and not variants[variant_label].get("description"):
        # Update description if it was empty and now provided
        variants[variant_label]["description"] = data["description"]

    # Append eval
    eval_entry = {
        "scores": scores,
        "timestamp": datetime.now().isoformat(),
    }
    variants[variant_label]["evals"].append(eval_entry)

    test["variants"] = variants
    test["updated_at"] = datetime.now().isoformat()
    save_test(tests_dir, test_name, test)

    return {
        "status": "logged",
        "test_name": test_name,
        "variant": variant_label,
        "eval_number": len(variants[variant_label]["evals"]),
        "composite": scores["composite"],
        "variant_data": {
            "description": variants[variant_label]["description"],
            "total_evals": len(variants[variant_label]["evals"]),
        },
    }


def action_get_results(slug, test_name):
    """Compare variants and determine the winner."""
    tests_dir, err = get_tests_dir(slug)
    if err:
        return {"error": err}

    test, err = load_test(tests_dir, test_name)
    if err:
        return {"error": err}

    variants = test.get("variants", {})
    if not variants:
        return {
            "test_name": test_name,
            "status": test.get("status", "active"),
            "variants": {},
            "winner": None,
            "note": "No variants logged yet.",
        }

    # Compute averages per variant
    variant_results = {}
    for label, vdata in variants.items():
        evals = vdata.get("evals", [])
        if not evals:
            variant_results[label] = {
                "description": vdata.get("description", ""),
                "eval_count": 0,
                "avg_composite": None,
                "avg_scores": {},
            }
            continue

        composites = [e["scores"].get("composite", 0) for e in evals]
        avg_composite = round(mean(composites), 1)

        # Average per dimension
        all_dims = set()
        for e in evals:
            all_dims.update(e["scores"].keys())

        avg_scores = {}
        for dim in sorted(all_dims):
            vals = [e["scores"][dim] for e in evals if dim in e["scores"]]
            avg_scores[dim] = round(mean(vals), 1) if vals else None

        variant_results[label] = {
            "description": vdata.get("description", ""),
            "eval_count": len(evals),
            "avg_composite": avg_composite,
            "avg_scores": avg_scores,
        }

    # Determine winner by highest average composite
    scored_variants = {
        label: vr["avg_composite"]
        for label, vr in variant_results.items()
        if vr["avg_composite"] is not None
    }

    winner = None
    margin = 0
    significance = "insufficient_data"
    recommendation = "Not enough data to determine a winner."

    if len(scored_variants) >= 2:
        sorted_variants = sorted(scored_variants.items(), key=lambda x: x[1], reverse=True)
        winner = sorted_variants[0][0]
        runner_up = sorted_variants[1][0]
        margin = round(sorted_variants[0][1] - sorted_variants[1][1], 1)

        # Statistical significance hint
        winner_count = variant_results[winner]["eval_count"]
        runner_up_count = variant_results[runner_up]["eval_count"]

        if winner_count >= 5 and runner_up_count >= 5:
            if abs(margin) > 10:
                significance = "significant"
            elif abs(margin) > 5:
                significance = "likely significant"
            else:
                significance = "inconclusive"
        else:
            min_needed = 5 - min(winner_count, runner_up_count)
            significance = f"insufficient_data (need {min_needed} more evals on smallest variant)"

        winner_desc = variant_results[winner].get("description", winner)
        if margin > 0:
            recommendation = (
                f"Variant {winner} ({winner_desc}) outperforms by "
                f"{margin} points. Significance: {significance}."
            )
        else:
            recommendation = (
                f"Variants are tied or within noise. "
                f"Significance: {significance}. Continue testing."
            )
    elif len(scored_variants) == 1:
        winner = list(scored_variants.keys())[0]
        recommendation = "Only one variant has data. Log evals for other variants to compare."

    return {
        "test_name": test_name,
        "description": test.get("description", ""),
        "status": test.get("status", "active"),
        "variants": variant_results,
        "winner": winner,
        "margin": margin,
        "significance": significance,
        "recommendation": recommendation,
    }


def action_list_tests(slug, limit):
    """List all A/B tests for the brand."""
    tests_dir, err = get_tests_dir(slug)
    if err:
        return {"error": err}

    tests = []
    for fp in sorted(tests_dir.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        variants = data.get("variants", {})
        total_evals = sum(
            len(v.get("evals", [])) for v in variants.values()
        )

        tests.append({
            "test_name": data.get("test_name", fp.stem),
            "description": data.get("description", ""),
            "status": data.get("status", "active"),
            "variant_count": len(variants),
            "total_evals": total_evals,
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
        })

    # Most recently updated first
    tests.sort(key=lambda t: t.get("updated_at", ""), reverse=True)

    if limit:
        tests = tests[:limit]

    return {
        "tests": tests,
        "returned": len(tests),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Prompt/output A/B testing tracker for Digital Marketing Pro.",
        epilog=(
            "Actions:\n"
            "  create-test   Create a new A/B test\n"
            "  log-variant   Log eval scores for a variant\n"
            "  get-results   Compare variants and determine winner\n"
            "  list-tests    List all tests for the brand\n"
            "\n"
            "Examples:\n"
            "  python prompt-ab-tester.py --action create-test "
            "--test-name email-subject-q1 "
            "--data '{\"description\":\"Testing subject lines\"}'\n"
            "  python prompt-ab-tester.py --action log-variant "
            "--test-name email-subject-q1 --variant A "
            "--data '{\"description\":\"Direct benefit\","
            "\"scores\":{\"composite\":82}}'\n"
            "  python prompt-ab-tester.py --action get-results "
            "--test-name email-subject-q1\n"
            "  python prompt-ab-tester.py --action list-tests\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--action", required=True,
        choices=["create-test", "log-variant", "get-results", "list-tests"],
        help="Action to perform.",
    )
    parser.add_argument(
        "--brand", type=_common.path_component, default=None,
        help="Brand slug (defaults to active brand).",
    )
    parser.add_argument(
        "--test-name", default=None,
        help="Test identifier (required for create-test, log-variant, get-results).",
    )
    parser.add_argument(
        "--variant", default=None,
        help="Variant label, e.g. 'A', 'B', 'control' (for log-variant).",
    )
    parser.add_argument(
        "--data", default=None,
        help="JSON data (for create-test and log-variant).",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max tests to return (for list-tests).",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Resolve brand
    slug = resolve_brand(args.brand)
    if not slug:
        print(json.dumps({
            "error": "No brand specified and no active brand set. "
                     "Use --brand <slug> or run /digital-marketing-pro:brand-setup first."
        }))
        sys.exit(1)

    # Sanitize --test-name before it is used to build file paths
    if args.test_name:
        args.test_name, name_err = sanitize_test_name(args.test_name)
        if name_err:
            print(json.dumps({"error": name_err}))
            sys.exit(1)

    # Parse --data if provided
    data = {}
    if args.data:
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data."}))
            sys.exit(1)

    # Dispatch
    if args.action == "create-test":
        if not args.test_name:
            print(json.dumps({"error": "Provide --test-name for create-test."}))
            sys.exit(1)
        result = action_create_test(slug, args.test_name, data)

    elif args.action == "log-variant":
        if not args.test_name:
            print(json.dumps({"error": "Provide --test-name for log-variant."}))
            sys.exit(1)
        if not args.variant:
            print(json.dumps({"error": "Provide --variant label (e.g. 'A', 'B')."}))
            sys.exit(1)
        result = action_log_variant(slug, args.test_name, args.variant, data)

    elif args.action == "get-results":
        if not args.test_name:
            print(json.dumps({"error": "Provide --test-name for get-results."}))
            sys.exit(1)
        result = action_get_results(slug, args.test_name)

    elif args.action == "list-tests":
        result = action_list_tests(slug, args.limit)

    _common.finish(result)


if __name__ == "__main__":
    main()
