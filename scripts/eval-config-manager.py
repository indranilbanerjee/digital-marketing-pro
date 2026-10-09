#!/usr/bin/env python3
"""
eval-config-manager.py
======================
Manages quality threshold configuration per brand for content evaluation.

Stores per-brand evaluation config (minimum scores, dimension weights,
auto-reject thresholds) at ~/.claude-marketing/brands/{slug}/quality/_config.json.
Creates sensible defaults on first access. Supports content-type-specific
minimum score overrides.

Dependencies: stdlib only (json, sys, argparse, pathlib, datetime)

Usage:
    python eval-config-manager.py --action get-config --brand acme
    python eval-config-manager.py --action get-config
    python eval-config-manager.py --action set-threshold --brand acme --dimension brand_voice --threshold 70
    python eval-config-manager.py --action set-threshold --brand acme --dimension hallucination --threshold 80 --content-type ad_copy
    python eval-config-manager.py --action set-weights --brand acme --weights '{"content_quality": 0.30, "hallucination": 0.25}'
    python eval-config-manager.py --action set-auto-reject --brand acme --threshold 45
    python eval-config-manager.py --action reset --brand acme

Actions:
    get-config      Return current config (creates default if none exists)
    set-threshold   Set minimum score for a dimension, optionally per content-type
    set-weights     Override dimension weights (validates sum ~1.0)
    set-auto-reject Set the auto-reject composite threshold
    reset           Reset config to defaults
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

BRANDS_DIR = _common.brands_root()

# ---------------------------------------------------------------------------
# Valid dimensions
# ---------------------------------------------------------------------------

VALID_DIMENSIONS = [
    "content_quality",
    "brand_voice",
    "hallucination",
    "claim_verification",
    "output_structure",
    "readability",
]

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def default_config() -> dict:
    """Return the default evaluation config."""
    now = _now_iso()
    return {
        "version": "1.0",
        "auto_reject_threshold": 40,
        "minimum_scores": {
            "default": {
                "content_quality": 50,
                "brand_voice": 50,
                "hallucination": 60,
                "readability": 40,
            },
            "blog_post": {
                "content_quality": 60,
                "brand_voice": 60,
                "hallucination": 70,
                "readability": 50,
            },
            "ad_copy": {
                "content_quality": 70,
                "brand_voice": 70,
                "hallucination": 80,
                "readability": 60,
            },
            "email": {
                "content_quality": 60,
                "brand_voice": 60,
                "hallucination": 70,
                "readability": 50,
            },
            "press_release": {
                "content_quality": 70,
                "brand_voice": 60,
                "hallucination": 80,
                "readability": 60,
            },
        },
        "weights": {
            "content_quality": 0.25,
            "brand_voice": 0.20,
            "hallucination": 0.20,
            "claim_verification": 0.15,
            "output_structure": 0.10,
            "readability": 0.10,
        },
        "created_at": now,
        "updated_at": now,
    }


# ---------------------------------------------------------------------------
# Brand resolution
# ---------------------------------------------------------------------------


def resolve_brand(slug: str | None) -> str:
    """Resolve brand slug from argument or active-brand file."""
    if slug:
        return slug

    active_path = BRANDS_DIR / "_active-brand.json"
    if not active_path.exists():
        print(json.dumps({
            "error": "No --brand provided and no active brand found.",
            "hint": "Provide --brand <slug> or set an active brand via /digital-marketing-pro:switch-brand.",
        }, indent=2))
        sys.exit(1)

    try:
        data = json.loads(active_path.read_text(encoding="utf-8"))
        active_slug = data.get("slug") or data.get("brand") or data.get("active")
        if not active_slug:
            print(json.dumps({
                "error": "Active brand file exists but contains no slug.",
                "path": str(active_path),
            }, indent=2))
            sys.exit(1)
        return active_slug
    except (json.JSONDecodeError, OSError) as exc:
        print(json.dumps({
            "error": f"Could not read active brand file: {exc}",
            "path": str(active_path),
        }, indent=2))
        sys.exit(1)


# ---------------------------------------------------------------------------
# Config I/O
# ---------------------------------------------------------------------------


def _config_path(slug: str) -> Path:
    """Return the config file path for a brand (legacy raw-name dirs honoured)."""
    return _common.brand_dir(slug) / "quality" / "_config.json"


def load_config(slug: str) -> dict:
    """Load config for a brand, creating defaults if none exists."""
    path = _config_path(slug)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # Corrupted file — recreate with defaults
            pass

    # Create default config
    config = default_config()
    save_config(slug, config)
    return config


def save_config(slug: str, config: dict) -> None:
    """Save config to disk, creating directories as needed."""
    path = _config_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


def action_get_config(slug: str) -> dict:
    """Return current config (create default if needed)."""
    config = load_config(slug)
    return {"brand": slug, "config": config}


def action_set_threshold(slug: str, dimension: str, threshold: int,
                         content_type: str | None) -> dict:
    """Set minimum score for a dimension, optionally per content-type."""
    if dimension not in VALID_DIMENSIONS:
        return {
            "error": f"Unknown dimension: '{dimension}'",
            "valid_dimensions": VALID_DIMENSIONS,
        }

    if not 0 <= threshold <= 100:
        return {"error": f"Threshold must be 0-100, got {threshold}"}

    config = load_config(slug)
    target_key = content_type if content_type else "default"

    if target_key not in config["minimum_scores"]:
        # Create a new content-type entry copied from defaults
        config["minimum_scores"][target_key] = dict(
            config["minimum_scores"].get("default", {})
        )

    config["minimum_scores"][target_key][dimension] = threshold
    config["updated_at"] = _now_iso()
    save_config(slug, config)

    return {
        "brand": slug,
        "action": "set_threshold",
        "dimension": dimension,
        "threshold": threshold,
        "content_type": target_key,
        "config": config,
    }


def action_set_weights(slug: str, weights_json: str) -> dict:
    """Override dimension weights. Validates sum ~1.0 (tolerance 0.05)."""
    try:
        overrides = json.loads(weights_json)
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid JSON for --weights: {exc}"}

    if not isinstance(overrides, dict):
        return {"error": "--weights must be a JSON object (dict)."}

    # Validate dimension names
    invalid = [k for k in overrides if k not in VALID_DIMENSIONS]
    if invalid:
        return {
            "error": f"Unknown dimensions: {invalid}",
            "valid_dimensions": VALID_DIMENSIONS,
        }

    # Validate values are numeric and in range
    for k, v in overrides.items():
        if not isinstance(v, (int, float)):
            return {"error": f"Weight for '{k}' must be numeric, got {type(v).__name__}"}
        if v < 0 or v > 1:
            return {"error": f"Weight for '{k}' must be 0.0-1.0, got {v}"}

    config = load_config(slug)
    current_weights = config["weights"]

    # Apply overrides
    for k, v in overrides.items():
        current_weights[k] = v

    # Check if weights sum to ~1.0
    total = sum(current_weights.values())
    tolerance = 0.05

    if abs(total - 1.0) > tolerance:
        # Redistribute remaining weight proportionally among non-overridden dimensions
        overridden_sum = sum(overrides.values())
        remaining = 1.0 - overridden_sum
        non_overridden = {k: v for k, v in current_weights.items() if k not in overrides}
        non_overridden_sum = sum(non_overridden.values())

        if non_overridden and non_overridden_sum > 0 and remaining > 0:
            scale = remaining / non_overridden_sum
            for k in non_overridden:
                current_weights[k] = round(current_weights[k] * scale, 4)
        elif non_overridden and remaining > 0:
            # Distribute equally
            per_dim = round(remaining / len(non_overridden), 4)
            for k in non_overridden:
                current_weights[k] = per_dim

        # Final normalization pass to handle floating point drift
        total = sum(current_weights.values())
        if total > 0 and abs(total - 1.0) > 0.001:
            current_weights = {k: round(v / total, 4) for k, v in current_weights.items()}

    config["weights"] = current_weights
    config["updated_at"] = _now_iso()
    save_config(slug, config)

    return {
        "brand": slug,
        "action": "set_weights",
        "overrides_applied": overrides,
        "final_weights": current_weights,
        "weights_sum": round(sum(current_weights.values()), 4),
        "config": config,
    }


def action_set_auto_reject(slug: str, threshold: int) -> dict:
    """Set the auto-reject composite threshold."""
    if not 0 <= threshold <= 100:
        return {"error": f"Threshold must be 0-100, got {threshold}"}

    config = load_config(slug)
    config["auto_reject_threshold"] = threshold
    config["updated_at"] = _now_iso()
    save_config(slug, config)

    return {
        "brand": slug,
        "action": "set_auto_reject",
        "auto_reject_threshold": threshold,
        "config": config,
    }


def action_reset(slug: str) -> dict:
    """Reset config to defaults."""
    config = default_config()
    save_config(slug, config)

    return {
        "brand": slug,
        "action": "reset",
        "message": "Config reset to defaults.",
        "config": config,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage quality threshold configuration per brand.",
        epilog=(
            "Actions:\n"
            "  get-config      Return current config (creates default if none exists)\n"
            "  set-threshold   Set minimum score for a dimension, optionally per content-type\n"
            "  set-weights     Override dimension weights (validates sum ~1.0)\n"
            "  set-auto-reject Set the auto-reject composite threshold\n"
            "  reset           Reset config to defaults\n\n"
            "Valid dimensions: "
            + ", ".join(VALID_DIMENSIONS)
            + "\n\n"
            "Examples:\n"
            "  python eval-config-manager.py --action get-config --brand acme\n"
            "  python eval-config-manager.py --action set-threshold --brand acme --dimension brand_voice --threshold 70\n"
            "  python eval-config-manager.py --action set-threshold --dimension hallucination --threshold 80 --content-type ad_copy\n"
            '  python eval-config-manager.py --action set-weights --brand acme --weights \'{"content_quality": 0.30}\'\n'
            "  python eval-config-manager.py --action set-auto-reject --brand acme --threshold 45\n"
            "  python eval-config-manager.py --action reset --brand acme"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=["get-config", "set-threshold", "set-weights", "set-auto-reject", "reset"],
        help="Action to perform.",
    )
    parser.add_argument(
        "--brand",
        type=_common.path_component,
        default=None,
        help="Brand slug (if omitted, reads from active brand).",
    )
    parser.add_argument(
        "--dimension",
        type=str,
        default=None,
        help="Evaluation dimension (e.g., content_quality, brand_voice, hallucination).",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=None,
        help="Score threshold value (0-100).",
    )
    parser.add_argument(
        "--weights",
        type=str,
        default=None,
        help='JSON string of weight overrides (e.g., \'{"content_quality": 0.30}\').',
    )
    parser.add_argument(
        "--content-type",
        type=str,
        default=None,
        help="Content type for content-type-specific thresholds (e.g., blog_post, ad_copy).",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    slug = _common.slugify_brand(resolve_brand(args.brand))

    # --- get-config ---
    if args.action == "get-config":
        result = action_get_config(slug)
        print(json.dumps(result, indent=2))
        return

    # --- set-threshold ---
    if args.action == "set-threshold":
        if not args.dimension:
            print(json.dumps({"error": "--dimension is required for set-threshold."}, indent=2))
            sys.exit(1)
        if args.threshold is None:
            print(json.dumps({"error": "--threshold is required for set-threshold."}, indent=2))
            sys.exit(1)
        result = action_set_threshold(slug, args.dimension, args.threshold, args.content_type)
        if "error" in result:
            print(json.dumps(result, indent=2))
            sys.exit(1)
        print(json.dumps(result, indent=2))
        return

    # --- set-weights ---
    if args.action == "set-weights":
        if not args.weights:
            print(json.dumps({"error": "--weights is required for set-weights."}, indent=2))
            sys.exit(1)
        result = action_set_weights(slug, args.weights)
        if "error" in result:
            print(json.dumps(result, indent=2))
            sys.exit(1)
        print(json.dumps(result, indent=2))
        return

    # --- set-auto-reject ---
    if args.action == "set-auto-reject":
        if args.threshold is None:
            print(json.dumps({"error": "--threshold is required for set-auto-reject."}, indent=2))
            sys.exit(1)
        result = action_set_auto_reject(slug, args.threshold)
        if "error" in result:
            print(json.dumps(result, indent=2))
            sys.exit(1)
        print(json.dumps(result, indent=2))
        return

    # --- reset ---
    if args.action == "reset":
        result = action_reset(slug)
        print(json.dumps(result, indent=2))
        return


if __name__ == "__main__":
    main()
