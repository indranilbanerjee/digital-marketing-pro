#!/usr/bin/env python3
"""
form-analyzer.py
================
Analyze web forms for conversion rate optimization. Scores forms (0-100)
based on field count, friction, required ratio, high-friction penalties,
mobile-friendliness, and progressive disclosure opportunities.

Dependencies: none (stdlib only)

Usage:
    python form-analyzer.py --fields '[{"name":"email","type":"email","required":true}]'
    python form-analyzer.py --file form-fields.json --form-type signup
    python form-analyzer.py --fields '[{"name":"email","type":"email","required":true},{"name":"phone","type":"tel","required":false}]' --form-type lead_gen
"""

import argparse
import json
import sys
from pathlib import Path

# Friction scores per field type (higher = more friction for the user)
FIELD_FRICTION = {
    "text": 1.0, "email": 1.5, "tel": 3.0, "phone": 3.0,
    "address": 3.5, "dropdown": 1.2, "select": 1.2,
    "checkbox": 0.5, "radio": 0.8, "textarea": 2.0,
    "password": 2.5, "date": 1.5, "file": 4.0, "number": 1.0,
    "url": 2.0, "hidden": 0.0,
}

# Optimal visible field counts (min, max) per form type
OPTIMAL_FIELD_COUNTS = {
    "lead_gen": (3, 5),
    "signup": (2, 4),
    "contact": (3, 6),
    "checkout": (5, 10),
    "application": (8, 15),
}

# Fields that trigger correct mobile keyboards (bonus)
MOBILE_FRIENDLY_TYPES = {"email", "tel", "phone", "number", "url", "date"}

# High-friction field types that hurt non-checkout forms
HIGH_FRICTION_TYPES = {"tel", "phone", "address", "file"}


def parse_fields(fields_json):
    """Parse and validate the fields JSON input.

    Returns:
        list of field dicts, or raises ValueError
    """
    if isinstance(fields_json, str):
        try:
            fields = json.loads(fields_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}")
    else:
        fields = fields_json

    if not isinstance(fields, list):
        raise ValueError("Fields must be a JSON array")

    if len(fields) == 0:
        raise ValueError("Fields array is empty")

    validated = []
    for i, field in enumerate(fields):
        if not isinstance(field, dict):
            raise ValueError(f"Field at index {i} must be an object")
        name = field.get("name", f"field_{i}")
        ftype = field.get("type", "text").lower()
        required = bool(field.get("required", False))
        placeholder = field.get("placeholder", "")
        validated.append({
            "name": name,
            "type": ftype,
            "required": required,
            "placeholder": placeholder,
        })

    return validated


def analyze_fields(fields):
    """Analyze individual fields for friction and notes.

    Returns:
        list of field analysis dicts
    """
    analysis = []
    for field in fields:
        ftype = field["type"]
        friction = FIELD_FRICTION.get(ftype, 1.5)
        notes = []

        if ftype in MOBILE_FRIENDLY_TYPES:
            notes.append(f"Triggers optimized mobile keyboard for {ftype}")
        if ftype == "textarea":
            notes.append("Open-ended fields increase cognitive load")
        if ftype == "file":
            notes.append("File uploads have the highest abandonment friction")
        if ftype == "password":
            notes.append("Consider showing password strength indicator")
        if ftype == "hidden":
            notes.append("Hidden field — no user friction")
        if field["required"] and ftype in HIGH_FRICTION_TYPES:
            notes.append(f"Required high-friction field ({ftype}) — consider making optional")
        if not field["placeholder"] and ftype not in ("checkbox", "radio", "hidden", "file"):
            notes.append("Missing placeholder text — add a hint to reduce hesitation")

        analysis.append({
            "name": field["name"],
            "type": ftype,
            "required": field["required"],
            "friction": friction,
            "notes": notes,
        })

    return analysis


def score_form(fields, field_analysis, form_type):
    """Score the form on a 0-100 scale across multiple dimensions.

    Dimensions:
        1. Field count vs optimal     (25 pts)
        2. Required ratio              (15 pts)
        3. Friction score              (20 pts)
        4. High-friction penalty       (15 pts)
        5. Mobile-friendliness         (15 pts)
        6. Progressive disclosure      (10 pts)
    """
    visible_fields = [f for f in fields if f["type"] != "hidden"]
    visible_count = len(visible_fields)
    total_count = len(fields)

    optimal_min, optimal_max = OPTIMAL_FIELD_COUNTS.get(form_type, (3, 6))

    # --- 1. Field count score (max 25) ---
    if optimal_min <= visible_count <= optimal_max:
        field_count_score = 25
    elif visible_count < optimal_min:
        deficit = optimal_min - visible_count
        field_count_score = max(0, 25 - deficit * 8)
    else:
        excess = visible_count - optimal_max
        field_count_score = max(0, 25 - excess * 5)

    # --- 2. Required ratio score (max 15) ---
    required_count = sum(1 for f in visible_fields if f["required"])
    required_ratio = required_count / max(visible_count, 1)

    if required_ratio <= 0.5:
        required_ratio_score = 15
    elif required_ratio <= 0.7:
        required_ratio_score = 12
    elif required_ratio <= 0.85:
        required_ratio_score = 8
    else:
        required_ratio_score = 4

    # --- 3. Friction score (max 20) ---
    total_friction = sum(fa["friction"] for fa in field_analysis)
    # Normalize: 0 friction = 20pts, friction >= visible_count * 3.0 = 0pts
    max_expected_friction = max(visible_count * 3.0, 1)
    friction_normalized = min(total_friction / max_expected_friction, 1.0)
    friction_score = round(20 * (1.0 - friction_normalized))

    # --- 4. High-friction field penalty (max 15, penalty subtracts) ---
    high_friction_fields = [f for f in visible_fields if f["type"] in HIGH_FRICTION_TYPES]
    hf_count = len(high_friction_fields)

    if form_type == "checkout":
        # Checkout forms legitimately need address/phone
        high_friction_penalty = min(hf_count * 2, 10)
    else:
        high_friction_penalty = min(hf_count * 5, 15)

    high_friction_score = 15 - high_friction_penalty

    # --- 5. Mobile-friendliness score (max 15) ---
    mobile_optimized = sum(1 for f in visible_fields if f["type"] in MOBILE_FRIENDLY_TYPES)
    textarea_count = sum(1 for f in visible_fields if f["type"] == "textarea")

    mobile_ratio = mobile_optimized / max(visible_count, 1)
    mobile_score = round(10 * min(mobile_ratio * 2, 1.0))  # up to 10 pts for mobile types
    mobile_score -= min(textarea_count * 3, 6)  # penalty for textareas on mobile
    mobile_score = max(0, min(15, mobile_score))

    # Bonus for having at least one mobile-optimized input type
    if mobile_optimized > 0 and mobile_score < 15:
        mobile_score = min(15, mobile_score + 3)

    # --- 6. Progressive disclosure opportunity (max 10) ---
    if visible_count <= 5:
        progressive_score = 10  # no need for progressive disclosure
    elif visible_count <= 8:
        progressive_score = 6  # could benefit from splitting
    else:
        progressive_score = 2  # strongly recommend multi-step

    # --- Total ---
    total_score = max(0, min(100,
        field_count_score + required_ratio_score + friction_score +
        high_friction_score + mobile_score + progressive_score
    ))

    breakdown = {
        "field_count_score": field_count_score,
        "required_ratio_score": required_ratio_score,
        "friction_score": friction_score,
        "high_friction_penalty": -high_friction_penalty,
        "mobile_score": mobile_score,
        "progressive_disclosure_score": progressive_score,
    }

    return total_score, breakdown, total_friction, required_ratio


def build_recommendations(fields, field_analysis, form_type, breakdown, total_friction, required_ratio):
    """Generate actionable CRO recommendations."""
    recs = []
    visible_fields = [f for f in fields if f["type"] != "hidden"]
    visible_count = len(visible_fields)
    optimal_min, optimal_max = OPTIMAL_FIELD_COUNTS.get(form_type, (3, 6))

    if visible_count > optimal_max:
        recs.append(
            f"Form has {visible_count} visible fields but optimal for {form_type} is "
            f"{optimal_min}-{optimal_max}. Remove low-value fields or move them to a "
            f"follow-up step."
        )

    high_friction = [fa for fa in field_analysis if fa["type"] in HIGH_FRICTION_TYPES and fa["type"] != "hidden"]
    if high_friction and form_type not in ("checkout", "application"):
        names = ", ".join(fa["name"] for fa in high_friction)
        recs.append(
            f"Consider removing or making optional the high-friction field(s): {names}. "
            f"Phone and address fields significantly increase form abandonment."
        )

    missing_placeholder = [fa for fa in field_analysis
                           if not fields[field_analysis.index(fa)].get("placeholder", "")
                           and fa["type"] not in ("checkbox", "radio", "hidden", "file")]
    if missing_placeholder:
        names = ", ".join(fa["name"] for fa in missing_placeholder[:3])
        recs.append(
            f"Add placeholder text to: {names}. Placeholders reduce hesitation "
            f"and clarify expected input format."
        )

    if required_ratio > 0.85:
        recs.append(
            f"Required ratio is {required_ratio:.0%} — nearly all fields are mandatory. "
            f"Making some fields optional can reduce perceived effort and increase submissions."
        )

    if visible_count > 5:
        recs.append(
            f"With {visible_count} fields, consider progressive disclosure: split the "
            f"form into 2-3 steps to reduce visual complexity and improve completion rates."
        )

    textarea_fields = [fa for fa in field_analysis if fa["type"] == "textarea"]
    if textarea_fields:
        recs.append(
            "Textarea fields add significant friction on mobile. Consider replacing with "
            "structured inputs (dropdowns, checkboxes) or making them optional."
        )

    if not any(fa["type"] in MOBILE_FRIENDLY_TYPES for fa in field_analysis):
        recs.append(
            "No fields use mobile-optimized input types. Use type='email' for email "
            "fields and type='tel' for phone fields to trigger the correct mobile keyboard."
        )

    if not recs:
        recs.append(
            "Form structure looks good. Consider A/B testing button copy, form placement, "
            "and surrounding trust signals (testimonials, security badges) for further gains."
        )

    return recs


def main():
    parser = argparse.ArgumentParser(
        description="Analyze web forms for conversion rate optimization"
    )
    parser.add_argument("--fields", type=str, default=None,
                        help='JSON array of field objects, e.g. \'[{"name":"email","type":"email","required":true}]\'')
    parser.add_argument("--file", type=str, default=None,
                        help="Path to JSON file containing fields array")
    parser.add_argument("--form-type", type=str, default="lead_gen",
                        choices=["lead_gen", "signup", "contact", "checkout", "application"],
                        help="Form type for benchmarking (default: lead_gen)")
    args = parser.parse_args()

    # --- Input validation ---
    if not args.fields and not args.file:
        json.dump({"error": "Provide either --fields or --file"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    raw_fields = None
    if args.file:
        path = Path(args.file)
        if not path.exists():
            json.dump({"error": f"File not found: {args.file}"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
        try:
            raw_fields = path.read_text(encoding="utf-8")
        except Exception as exc:
            json.dump({"error": f"Failed to read file: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
    else:
        raw_fields = args.fields

    try:
        fields = parse_fields(raw_fields)
    except ValueError as exc:
        json.dump({"error": str(exc)}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    # --- Analysis ---
    field_analysis = analyze_fields(fields)
    total_score, breakdown, total_friction, required_ratio = score_form(
        fields, field_analysis, args.form_type
    )
    recommendations = build_recommendations(
        fields, field_analysis, args.form_type, breakdown, total_friction, required_ratio
    )

    # --- Warnings ---
    warnings = []
    visible_count = sum(1 for f in fields if f["type"] != "hidden")
    if visible_count > 15:
        warnings.append("Extremely long form (>15 fields). Expect high abandonment rates.")
    if visible_count == 1:
        warnings.append("Single-field form. Ensure it captures enough data for your goal.")
    if all(f["required"] for f in fields if f["type"] != "hidden"):
        warnings.append("Every visible field is required. This maximizes perceived effort.")

    # --- Output ---
    output = {
        "form_type": args.form_type,
        "field_count": len(fields),
        "visible_field_count": visible_count,
        "score": total_score,
        "breakdown": breakdown,
        "field_analysis": field_analysis,
        "total_friction": round(total_friction, 1),
        "required_ratio": f"{required_ratio:.0%}",
        "recommendations": recommendations,
        "warnings": warnings,
    }

    json.dump(output, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
