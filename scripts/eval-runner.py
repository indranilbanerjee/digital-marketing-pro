#!/usr/bin/env python3
"""
eval-runner.py
==============
Master orchestrator for the Digital Marketing Pro evaluation suite.

Runs the full eval pipeline via subprocess, calling sibling scripts for each
scoring dimension, then produces a unified composite report with weighted
scores, letter grades, and pass/fail gate checks.

Dependencies: stdlib only (json, sys, argparse, pathlib, datetime,
              subprocess, os, tempfile)

Usage:
    python eval-runner.py --action run-full --text "Your marketing copy..."
    python eval-runner.py --action run-full --file draft.md --brand acme
    python eval-runner.py --action run-full --file draft.md --evidence claims.json --schema blog_post --log
    python eval-runner.py --action run-quick --text "Quick check on this copy."
    python eval-runner.py --action run-compliance --file page.md --evidence facts.json --schema landing_page

Actions:
    run-full        Full eval pipeline (all 6 dimensions)
    run-quick       Quick eval (hallucination + content quality + readability)
    run-compliance  Compliance-focused eval (hallucination + claims + brand voice + structure)

Scoring:
    A+  95-100    A  90-94    A-  85-89
    B+  80-84     B  75-79    B-  70-74
    C+  65-69     C  60-64    C-  55-59
    D   40-54     F  <40
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BRANDS_DIR = _common.brands_root()
ACTIVE_BRAND_FILE = BRANDS_DIR / "_active-brand.json"
SCRIPTS_DIR = Path(__file__).resolve().parent
SUBPROCESS_TIMEOUT = 30  # seconds
K = _common.EVAL_CONFIG_KEYS  # the key names eval-config-manager.py writes

# Exit codes: 0 PASS or WARN, 1 error (every dimension failed), 2 bad input (a missing --file, an
# unknown --schema), 3 BLOCKED (a CRITICAL issue, or the composite under the auto-reject line).
EXIT_BLOCKED = 3


class InputError(ValueError):
    """Bad input: printed as {"error": ...} plus any extra fields, exit 2."""

    def __init__(self, message, **extra):
        super().__init__(message)
        self.extra = extra

# ---------------------------------------------------------------------------
# Default dimension weights for each eval type
# ---------------------------------------------------------------------------

FULL_EVAL_WEIGHTS = {
    "content_quality":    0.25,
    "brand_voice":        0.20,
    "hallucination":      0.20,
    "claim_verification": 0.15,
    "output_structure":   0.10,
    "readability":        0.10,
}

QUICK_EVAL_WEIGHTS = {
    "hallucination":   0.40,
    "content_quality": 0.35,
    "readability":     0.25,
}

COMPLIANCE_EVAL_WEIGHTS = {
    "hallucination":      0.35,
    "claim_verification": 0.30,
    "brand_voice":        0.20,
    "output_structure":   0.15,
}

# ---------------------------------------------------------------------------
# Grade scale
# ---------------------------------------------------------------------------

GRADE_SCALE = [
    (95, "A+"),
    (90, "A"),
    (85, "A-"),
    (80, "B+"),
    (75, "B"),
    (70, "B-"),
    (65, "C+"),
    (60, "C"),
    (55, "C-"),
    (40, "D"),
    (0,  "F"),
]

GRADE_INTERPRETATIONS = {
    "A+": "Excellent quality -- publish-ready",
    "A":  "Excellent quality -- publish-ready",
    "A-": "Very good quality -- minimal improvements possible",
    "B+": "Good quality -- minor improvements recommended",
    "B":  "Good quality -- minor improvements recommended",
    "B-": "Above average -- some improvements needed",
    "C+": "Fair quality -- notable improvements needed",
    "C":  "Fair quality -- revision recommended",
    "C-": "Below average -- significant revision needed",
    "D":  "Poor quality -- major revision required",
    "F":  "Failing quality -- rewrite recommended",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_eval_id():
    """Generate a unique eval run identifier."""
    now = datetime.now(timezone.utc)
    return f"eval-{now.strftime('%Y%m%d-%H%M%S')}"


def _utc_timestamp():
    """Return the current UTC timestamp in ISO 8601."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_grade(score):
    """Map a 0-100 composite score to a letter grade."""
    for threshold, grade in GRADE_SCALE:
        if score >= threshold:
            return grade
    return "F"


def _get_interpretation(grade):
    """Return a human-readable interpretation for a letter grade."""
    return GRADE_INTERPRETATIONS.get(grade, "Unknown grade")


def _resolve_active_brand():
    """Read the active brand slug from the standard location.

    Returns the slug string, or None if no active brand is set.
    """
    if not ACTIVE_BRAND_FILE.exists():
        return None
    try:
        data = json.loads(ACTIVE_BRAND_FILE.read_text(encoding="utf-8-sig"))
        return data.get("active_slug") or None
    except (json.JSONDecodeError, OSError):
        return None


def _resolve_content(args):
    """Resolve content text from --text or --file arguments.

    Returns the content string, or None on error (with error dict printed).
    """
    if args.text:
        return args.text

    if args.file:
        file_path = Path(args.file)
        if not file_path.is_file():
            raise InputError(f"--file not found: {args.file}")
        try:
            return _common.decode_text(file_path.read_bytes(), file_path.name)
        except (OSError, ValueError) as exc:
            raise InputError(f"--file can't be read: {exc}") from None

    return None


def _write_temp_content(content):
    """Write content to a temporary file and return the path.

    Using a temp file avoids command-line length limits when passing
    long content to subprocess calls.
    """
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".txt",
        prefix="eval-content-",
        delete=False,
        encoding="utf-8",
    )
    try:
        tmp.write(content)
        tmp.flush()
        return tmp.name
    finally:
        tmp.close()


def _cleanup_temp(path):
    """Remove a temporary file if it exists."""
    try:
        if path and os.path.exists(path):
            os.unlink(path)
    except OSError:
        pass


def _redistribute_weights(base_weights, active_dimensions):
    """Redistribute weights so only active dimensions participate.

    Skipped dimensions get weight 0. Remaining weights are scaled
    proportionally so they sum to 1.0.
    """
    active_total = sum(
        w for dim, w in base_weights.items() if dim in active_dimensions
    )
    if active_total <= 0:
        # Fallback: equal weights among active dimensions
        n = len(active_dimensions) or 1
        return {dim: (1.0 / n if dim in active_dimensions else 0.0)
                for dim in base_weights}

    result = {}
    for dim, w in base_weights.items():
        if dim in active_dimensions:
            result[dim] = round(w / active_total, 4)
        else:
            result[dim] = 0.0
    return result


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------

def _run_script(script_name, args_list):
    """Run a sibling Python script via subprocess.

    Returns (success: bool, data: dict, error: str | None).
    """
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return False, {}, f"Script not found: {script_name}"

    cmd = [sys.executable, str(script_path)] + args_list

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False, {}, f"Script timed out after {SUBPROCESS_TIMEOUT}s: {script_name}"
    except Exception as exc:
        return False, {}, f"Failed to execute {script_name}: {exc}"

    if result.returncode != 0:
        stderr_snippet = (result.stderr or "").strip()[:300]
        # Try to parse stdout even on non-zero exit -- some scripts print
        # JSON error objects and exit(1)
        try:
            data = json.loads(result.stdout)
            said = data.get("error") if isinstance(data, dict) else None
            return False, data, f"Non-zero exit ({result.returncode}): {said or stderr_snippet or 'no message'}"
        except (json.JSONDecodeError, TypeError):
            return False, {}, (
                f"Non-zero exit ({result.returncode}) from {script_name}. "
                f"stderr: {stderr_snippet}"
            )

    # Parse JSON stdout
    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return False, {}, (
            f"Could not parse JSON output from {script_name}. "
            f"stdout (first 300 chars): {(result.stdout or '')[:300]}"
        )

    # Treat "fallback" scripts (missing optional deps) as partial success
    if data.get("fallback"):
        return False, data, f"{script_name} ran in fallback mode: {data.get('message', 'missing dependency')}"

    return True, data, None


# ---------------------------------------------------------------------------
# Score extractors -- pull the score from each script's JSON output
# ---------------------------------------------------------------------------

def _extract_content_quality_score(data):
    """Extract score from content-scorer.py output."""
    if "overall_score" in data:
        return data["overall_score"]
    if "content_score" in data:
        return data["content_score"]
    return None


def _extract_brand_voice_score(data):
    """Extract score from brand-voice-scorer.py output."""
    if "overall_score" in data:
        return data["overall_score"]
    if "voice_score" in data:
        return data["voice_score"]
    return None


def _extract_hallucination_score(data):
    """Extract score from hallucination-detector.py output."""
    if "hallucination_score" in data:
        return data["hallucination_score"]
    return None


def _extract_verification_score(data):
    """Extract score from claim-verifier.py output."""
    if "verification_score" in data:
        return data["verification_score"]
    if "overall_score" in data:
        return data["overall_score"]
    return None


def _extract_validation_score(data):
    """Extract score from output-validator.py output."""
    if "validation_score" in data:
        return data["validation_score"]
    return None


def _extract_readability_score(data):
    """Extract score from readability-analyzer.py output.

    The readability-analyzer returns metrics (flesch_reading_ease) rather
    than a single 0-100 score. We convert Reading Ease to a 0-100 score.
    """
    # Direct score field (if the script adds one in the future)
    if "readability_score" in data:
        return data["readability_score"]
    if "overall_score" in data:
        return data["overall_score"]
    # Derive from Flesch Reading Ease (0-100 scale, higher = easier)
    metrics = data.get("metrics", data)
    ease = metrics.get("flesch_reading_ease")
    if ease is not None:
        # Clamp to 0-100
        return round(max(0, min(100, ease)), 2)
    return None


# ---------------------------------------------------------------------------
# Eval config loader
# ---------------------------------------------------------------------------

def _load_eval_config(brand_slug):
    """Load eval configuration via eval-config-manager.py.

    Returns config dict, or a sensible default if the script is unavailable.
    """
    if brand_slug:
        ok, data, err = _run_script(
            "eval-config-manager.py",
            ["--action", "get-config", "--brand", brand_slug],
        )
        if ok and data:
            return _unwrap_config(data)
    # Also try without brand
    ok, data, err = _run_script(
        "eval-config-manager.py",
        ["--action", "get-config"],
    )
    if ok and data:
        return _unwrap_config(data)
    # Fallback defaults
    return {K["auto_reject"]: 40, K["minimums"]: {}, K["weights"]: {}}


def _unwrap_config(reply):
    """get-config answers {"brand": ..., "config": {...}}; the settings are inside "config"."""
    config = reply.get("config") if isinstance(reply.get("config"), dict) else reply
    return config if isinstance(config, dict) else {}


def _brand_weights(base_weights, config):
    """Apply the brand's dimension weights to an eval type's base weights.

    The manager stores one flat map per brand (its defaults equal FULL_EVAL_WEIGHTS). Each base
    weight is scaled by the brand's weight relative to that default, so a full eval takes the
    brand's weights as they are, and quick and compliance keep their own balance unless the brand
    moved a dimension (hallucination 0.2 -> 0.9 weighs it 4.5x more in every eval type). The scores
    are renormalised over the dimensions that ran."""
    brand = config.get(K["weights"]) or {}
    out = {}
    for dim, weight in base_weights.items():
        chosen, shipped = brand.get(dim), FULL_EVAL_WEIGHTS.get(dim)
        ok = isinstance(chosen, (int, float)) and not isinstance(chosen, bool) and chosen >= 0 and shipped
        out[dim] = weight * chosen / shipped if ok else weight
    return out


def _collect_issues(dimension, data):
    """Flagged items a dimension script reported, each with its severity (critical, high, medium,
    low). A count of critical flags with no item to show still counts as one critical issue."""
    found = []

    def visit(obj, depth=0):
        if depth > 4:
            return
        if isinstance(obj, dict):
            sev = obj.get("severity")
            if isinstance(sev, str) and any(k in obj for k in ("value", "reason", "message")):
                found.append({"dimension": dimension, "severity": sev.lower(),
                              "type": obj.get("type") or obj.get("claim_type") or obj.get("check") or "",
                              "value": str(obj.get("value", ""))[:200],
                              "reason": str(obj.get("reason") or obj.get("message") or "")[:300]})
                return
            for value in obj.values():
                visit(value, depth + 1)
        elif isinstance(obj, list):
            for value in obj:
                visit(value, depth + 1)

    visit(data)
    count = data.get("critical_flags") if isinstance(data, dict) else None
    if isinstance(count, int) and count > 0 and not any(i["severity"] == "critical" for i in found):
        found.append({"dimension": dimension, "severity": "critical", "type": "critical_flags", "value": "",
                      "reason": f"{count} critical flag(s) reported; see the script's own output"})
    return found


def _grade_rank(grade):
    return [g for _, g in GRADE_SCALE].index(grade)


# ---------------------------------------------------------------------------
# Dimension runner definitions
# ---------------------------------------------------------------------------

# Map eval-runner --content-type labels to content-scorer.py --type choices
# (blog / email / ad / landing_page / social). Unknown types fall back to blog.
CONTENT_SCORER_TYPE_MAP = {
    "blog": "blog",
    "blog_post": "blog",
    "email": "email",
    "ad": "ad",
    "ad_copy": "ad",
    "landing_page": "landing_page",
    "social": "social",
    "social_post": "social",
}


def _map_content_scorer_type(content_type):
    """Map the user's --content-type to a content-scorer.py --type choice."""
    return CONTENT_SCORER_TYPE_MAP.get((content_type or "").lower(), "blog")


def _build_dimension_runners(content_file, brand_slug, evidence_path,
                             schema_name, content_type=None):
    """Build a dict mapping dimension name -> (script, args, extractor, skip_reason).

    If a dimension should be conditionally skipped (e.g., no evidence file),
    skip_reason is set; otherwise it is None.
    """
    runners = {}

    # Content quality
    runners["content_quality"] = {
        "script": "content-scorer.py",
        "args": ["--file", content_file,
                 "--type", _map_content_scorer_type(content_type)],
        "extractor": _extract_content_quality_score,
        "skip_reason": None,
    }

    # Brand voice
    if brand_slug:
        runners["brand_voice"] = {
            "script": "brand-voice-scorer.py",
            "args": ["--file", content_file, "--brand", brand_slug],
            "extractor": _extract_brand_voice_score,
            "skip_reason": None,
        }
    else:
        runners["brand_voice"] = {
            "script": "brand-voice-scorer.py",
            "args": [],
            "extractor": _extract_brand_voice_score,
            "skip_reason": "No brand specified and no active brand found",
        }

    # Hallucination
    runners["hallucination"] = {
        "script": "hallucination-detector.py",
        "args": ["--action", "detect", "--file", content_file],
        "extractor": _extract_hallucination_score,
        "skip_reason": None,
    }

    # Claim verification (conditional)
    if evidence_path:
        runners["claim_verification"] = {
            "script": "claim-verifier.py",
            "args": ["--action", "verify", "--file", content_file,
                      "--evidence", evidence_path],
            "extractor": _extract_verification_score,
            "skip_reason": None,
        }
    else:
        runners["claim_verification"] = {
            "script": "claim-verifier.py",
            "args": [],
            "extractor": _extract_verification_score,
            "skip_reason": "No evidence file provided",
        }

    # Output structure (conditional)
    if schema_name:
        runners["output_structure"] = {
            "script": "output-validator.py",
            "args": ["--action", "validate", "--file", content_file,
                      "--schema", schema_name],
            "extractor": _extract_validation_score,
            "skip_reason": None,
        }
    else:
        runners["output_structure"] = {
            "script": "output-validator.py",
            "args": [],
            "extractor": _extract_validation_score,
            "skip_reason": "No schema specified",
        }

    # Readability
    runners["readability"] = {
        "script": "readability-analyzer.py",
        "args": ["--file", content_file],
        "extractor": _extract_readability_score,
        "skip_reason": None,
    }

    return runners


# ---------------------------------------------------------------------------
# Core eval orchestrator
# ---------------------------------------------------------------------------

def _run_eval(dimensions_to_run, base_weights, content, brand_slug,
              evidence_path, schema_name, content_type, eval_type,
              log_results, config):
    """Execute the eval pipeline for the given dimensions.

    Parameters:
        dimensions_to_run : list of dimension names to execute
        base_weights      : dict of dimension -> default weight
        content           : the raw content string
        brand_slug        : brand slug or None
        evidence_path     : path to evidence file or None
        schema_name       : output schema name or None
        content_type      : content type label (e.g. "blog_post")
        eval_type         : "full", "quick", or "compliance"
        log_results       : whether to persist via quality-tracker
        config            : eval config dict

    Returns:
        dict -- the complete eval report
    """
    eval_id = _generate_eval_id()
    timestamp = _utc_timestamp()

    # Write content to temp file for subprocess calls
    tmp_path = _write_temp_content(content)

    try:
        all_runners = _build_dimension_runners(
            tmp_path, brand_slug, evidence_path, schema_name, content_type,
        )

        # Filter to only requested dimensions
        runners = {
            dim: all_runners[dim]
            for dim in dimensions_to_run
            if dim in all_runners
        }

        # --- Execute each dimension ---
        results = {}       # dim -> {"score", "weight", "status", ...}
        active_dims = []   # dims that produced a score
        skipped_dims = []  # dims that were skipped (not applicable, or failed)
        failed_dims = []   # dims that should have run and didn't (a script error, a missing package)
        errors = {}        # dim -> error detail
        issues = []        # flagged items from every dimension, with severity

        for dim, runner in runners.items():
            # Pre-skip if skip_reason is set
            if runner["skip_reason"]:
                results[dim] = {
                    "score": None,
                    "weight": 0,
                    "status": "skipped",
                    "reason": runner["skip_reason"],
                }
                skipped_dims.append(dim)
                continue

            # Run the script
            ok, data, err = _run_script(runner["script"], runner["args"])

            if not ok:
                results[dim] = {
                    "score": None,
                    "weight": 0,
                    "status": "skipped",
                    "reason": err or f"{runner['script']} failed",
                }
                skipped_dims.append(dim)
                failed_dims.append(dim)
                errors[dim] = err
                continue

            # Extract score
            score = runner["extractor"](data)
            if score is None:
                results[dim] = {
                    "score": None,
                    "weight": 0,
                    "status": "skipped",
                    "reason": f"Could not extract score from {runner['script']} output",
                }
                skipped_dims.append(dim)
                failed_dims.append(dim)
                continue
            issues.extend(_collect_issues(dim, data))

            # Clamp to 0-100
            score = round(max(0, min(100, score)), 2)
            results[dim] = {
                "score": score,
                "weight": 0,  # placeholder -- computed after redistribution
                "status": "pass",  # updated below after threshold checks
            }
            active_dims.append(dim)

        # --- Redistribute weights among active dimensions ---
        final_weights = _redistribute_weights(base_weights, set(active_dims))
        for dim in results:
            results[dim]["weight"] = final_weights.get(dim, 0)

        # --- Compute composite score ---
        if not active_dims:
            return {
                "error": "All eval scripts failed",
                "eval_id": eval_id,
                "eval_type": eval_type,
                "details": errors,
                "skipped_dimensions": skipped_dims,
                "timestamp": timestamp,
            }

        composite = 0.0
        for dim in active_dims:
            composite += results[dim]["score"] * final_weights.get(dim, 0)
        composite = round(max(0, min(100, composite)), 2)

        # --- Grade ---
        # A composite over dimensions that failed to run is partial: never graded above B, and
        # "incomplete" when fewer than two dimensions ran. Before 3.40.0 a fresh install (no
        # textstat) graded A+ from the hallucination dimension alone.
        grade = _get_grade(composite)
        capped_from = None
        if failed_dims:
            if len(active_dims) < 2:
                capped_from, grade = grade, "incomplete"
            elif _grade_rank(grade) < _grade_rank("B"):
                capped_from, grade = grade, "B"
        interpretation = (f"Partial: {len(active_dims)} of {len(runners)} dimensions ran "
                          f"({', '.join(failed_dims)} did not; see script_errors). "
                          + (_get_interpretation(grade) if grade != "incomplete" else "No grade.")
                          if failed_dims else _get_interpretation(grade))

        # --- Auto-reject check ---
        auto_reject_threshold = config.get(K["auto_reject"], 40)
        auto_rejected = composite < auto_reject_threshold

        # --- Minimum dimension score checks ---
        min_scores_cfg = config.get(K["minimums"], {})
        # Check content-type-specific minimums first, then fallback to default
        ct_minimums = min_scores_cfg.get(content_type, min_scores_cfg.get("default", {}))
        dimension_alerts = []

        for dim in active_dims:
            min_required = ct_minimums.get(dim)
            if min_required is not None and results[dim]["score"] < min_required:
                results[dim]["status"] = "below_minimum"
                dimension_alerts.append({
                    "dimension": dim,
                    "score": results[dim]["score"],
                    "minimum_required": min_required,
                    "message": (
                        f"{dim} score ({results[dim]['score']}) is below "
                        f"the minimum threshold ({min_required})"
                    ),
                })
            else:
                results[dim]["status"] = "pass"

        # --- Build weights_used (only active dims with non-zero weight) ---
        weights_used = {
            dim: final_weights[dim]
            for dim in active_dims
            if final_weights.get(dim, 0) > 0
        }

        # --- Optional: log results via quality-tracker ---
        logged = False
        if log_results:
            log_data = {
                "eval_id": eval_id,
                "composite_score": composite,
                "grade": grade,
                "eval_type": eval_type,
                "content_type": content_type,
                "dimensions": results,
                "timestamp": timestamp,
            }
            log_args = ["--action", "log-eval", "--data", json.dumps(log_data)]
            if brand_slug:
                log_args += ["--brand", brand_slug]

            log_ok, _, log_err = _run_script("quality-tracker.py", log_args)
            logged = log_ok

        # --- Decision (the check skill's PASS / WARN / BLOCKED) ---
        critical = [i for i in issues if i["severity"] == "critical"]
        warnings = [i for i in issues if i["severity"] in ("high", "medium")]
        if critical or auto_rejected:
            decision = "BLOCKED"
        elif dimension_alerts or warnings or failed_dims:
            decision = "WARN"
        else:
            decision = "PASS"

        # --- Assemble output ---
        output = {
            "eval_id": eval_id,
            "eval_type": eval_type,
            "decision": decision,
            "composite_score": composite,
            "grade": grade,
            "interpretation": interpretation,
            "auto_rejected": auto_rejected,
            "issues": issues,
            "partial": bool(failed_dims),
            "missing_dimensions": failed_dims,
            "dimensions": results,
            "dimension_alerts": dimension_alerts,
            "skipped_dimensions": skipped_dims,
            "weights_used": weights_used,
            "content_type": content_type or "unknown",
            "logged": logged,
            "timestamp": timestamp,
        }

        if capped_from:
            output["grade_capped_from"] = capped_from
        if errors:
            output["script_errors"] = errors

        return output

    finally:
        _cleanup_temp(tmp_path)


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

def action_run_full(args):
    """Full eval pipeline -- all 6 scoring dimensions."""
    content = _resolve_content(args)
    if not content or not content.strip():
        raise InputError("No content provided. Use --text, or --file with a non-empty file.")

    brand_slug = args.brand or _resolve_active_brand()
    config = _load_eval_config(brand_slug)

    base_weights = _brand_weights(FULL_EVAL_WEIGHTS, config)

    dimensions = list(FULL_EVAL_WEIGHTS.keys())

    return _run_eval(
        dimensions_to_run=dimensions,
        base_weights=base_weights,
        content=content,
        brand_slug=brand_slug,
        evidence_path=args.evidence,
        schema_name=args.schema,
        content_type=args.content_type or "general",
        eval_type="full",
        log_results=args.log,
        config=config,
    )


def action_run_quick(args):
    """Quick eval -- 3 fastest/most critical checks."""
    content = _resolve_content(args)
    if not content or not content.strip():
        raise InputError("No content provided. Use --text, or --file with a non-empty file.")

    brand_slug = args.brand or _resolve_active_brand()
    config = _load_eval_config(brand_slug)

    base_weights = _brand_weights(QUICK_EVAL_WEIGHTS, config)

    dimensions = list(QUICK_EVAL_WEIGHTS.keys())

    return _run_eval(
        dimensions_to_run=dimensions,
        base_weights=base_weights,
        content=content,
        brand_slug=brand_slug,
        evidence_path=None,
        schema_name=None,
        content_type=args.content_type or "general",
        eval_type="quick",
        log_results=args.log,
        config=config,
    )


def action_run_compliance(args):
    """Compliance-focused eval -- regulatory and brand compliance checks."""
    content = _resolve_content(args)
    if not content or not content.strip():
        raise InputError("No content provided. Use --text, or --file with a non-empty file.")

    brand_slug = args.brand or _resolve_active_brand()
    config = _load_eval_config(brand_slug)

    base_weights = _brand_weights(COMPLIANCE_EVAL_WEIGHTS, config)

    dimensions = list(COMPLIANCE_EVAL_WEIGHTS.keys())

    return _run_eval(
        dimensions_to_run=dimensions,
        base_weights=base_weights,
        content=content,
        brand_slug=brand_slug,
        evidence_path=args.evidence,
        schema_name=args.schema,
        content_type=args.content_type or "general",
        eval_type="compliance",
        log_results=args.log,
        config=config,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    """Build the argument parser with comprehensive --help output."""
    parser = argparse.ArgumentParser(
        description=(
            "Master orchestrator for the Digital Marketing Pro evaluation suite.\n"
            "Runs sibling eval scripts via subprocess and produces a unified\n"
            "composite quality report with weighted scores, letter grades,\n"
            "and pass/fail gate checks."
        ),
        epilog=(
            "Actions:\n"
            "  run-full        Full eval: content quality, brand voice, hallucination,\n"
            "                  claim verification, output structure, readability\n"
            "  run-quick       Quick eval: hallucination, content quality, readability\n"
            "  run-compliance  Compliance eval: hallucination, claim verification,\n"
            "                  brand voice, output structure\n"
            "\n"
            "Grading scale:\n"
            "  A+ (95-100)  A (90-94)   A- (85-89)\n"
            "  B+ (80-84)   B (75-79)   B- (70-74)\n"
            "  C+ (65-69)   C (60-64)   C- (55-59)\n"
            "  D  (40-54)   F  (<40)\n"
            "\n"
            "Weight redistribution:\n"
            "  When a dimension is skipped (no evidence file, no schema, or script\n"
            "  unavailable), its weight is redistributed proportionally among the\n"
            "  remaining active dimensions so weights always sum to 1.0.\n"
            "\n"
            "Examples:\n"
            "  python eval-runner.py --action run-full --text \"Your copy here.\"\n"
            "  python eval-runner.py --action run-full --file draft.md --brand acme\n"
            "  python eval-runner.py --action run-full --file draft.md --evidence claims.json --schema blog_post --log\n"
            "  python eval-runner.py --action run-quick --file email.txt\n"
            "  python eval-runner.py --action run-compliance --file page.md --evidence facts.json --schema landing_page\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--action",
        required=True,
        choices=["run-full", "run-quick", "run-compliance"],
        help="Evaluation mode to run.",
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--text",
        type=str,
        help="Content text to evaluate (inline). For long content, prefer --file.",
    )
    input_group.add_argument(
        "--file",
        type=str,
        help="Path to a file containing content to evaluate.",
    )

    parser.add_argument(
        "--brand",
        type=_common.path_component,
        default=None,
        help=(
            "Brand slug for brand-voice scoring. Defaults to the active brand "
            "from ~/.claude-marketing/brands/_active-brand.json."
        ),
    )
    parser.add_argument(
        "--schema",
        type=str,
        default=None,
        help=(
            "Output validation schema name (e.g., blog_post, email, ad_copy). "
            "Required for the output_structure dimension."
        ),
    )
    parser.add_argument(
        "--evidence",
        type=str,
        default=None,
        help=(
            "Path to evidence file for claim verification. "
            "Required for the claim_verification dimension."
        ),
    )
    parser.add_argument(
        "--content-type",
        type=str,
        default=None,
        help=(
            "Content categorization for per-type threshold lookups "
            "(e.g., blog_post, email, ad_copy, social_post, landing_page)."
        ),
    )
    parser.add_argument(
        "--log",
        action="store_true",
        default=False,
        help="Auto-log eval results via quality-tracker.py (default: false).",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

ACTION_DISPATCH = {
    "run-full":       action_run_full,
    "run-quick":      action_run_quick,
    "run-compliance": action_run_compliance,
}


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.brand:
        args.brand = _common.slugify_brand(args.brand)

    handler = ACTION_DISPATCH.get(args.action)
    if not handler:
        print(json.dumps({
            "error": f"Unknown action: {args.action}",
            "valid_actions": list(ACTION_DISPATCH.keys()),
        }, indent=2))
        sys.exit(1)

    try:
        if getattr(args, "schema", None):
            listed = _check_schema(args.schema)
            if listed is not None:  # --schema list
                print(json.dumps(listed, indent=2, ensure_ascii=False))
                sys.exit(0)
        result = handler(args)
    except InputError as exc:
        print(json.dumps({"error": str(exc), **exc.extra}, indent=2, ensure_ascii=False))
        sys.exit(2)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Exit with non-zero if there was a top-level error, and 3 when the content must not ship
    if "error" in result:
        sys.exit(1)
    sys.exit(EXIT_BLOCKED if result.get("decision") == "BLOCKED" else 0)


def _check_schema(name):
    """--schema list returns output-validator's schema list; an unknown name raises InputError."""
    ok, data, err = _run_script("output-validator.py", ["--action", "list-schemas"])
    schemas = (data or {}).get("schemas") if ok else None
    if not isinstance(schemas, dict):
        raise InputError(f"could not list the output schemas: {err}")
    if name == "list":
        return {"schemas": schemas}
    if name not in schemas:
        raise InputError(f"unknown --schema {name!r}", valid_schemas=sorted(schemas))
    return None


if __name__ == "__main__":
    main()
