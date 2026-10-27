#!/usr/bin/env python3
"""
output-validator.py
===================
Validates marketing outputs match expected structure, format, and completeness.

Checks content against built-in or custom schemas for required sections,
word count bounds, format rules (headings, paragraphs, CTAs), placeholder
text, and basic consistency. Returns a validation score (0-100) with
per-check breakdown and actionable issues list.

Dependencies: stdlib only (json, re, sys, argparse, pathlib)

Usage:
    python output-validator.py --action validate --text "# My Post..." --schema blog_post
    python output-validator.py --action validate --file draft.md --schema email
    python output-validator.py --action validate --file page.md --custom-schema my-schema.json
    python output-validator.py --action list-schemas
    python output-validator.py --action check-format --file draft.md

Actions:
    validate      Validate content against a named or custom schema
    list-schemas  List all built-in schema names with descriptions
    check-format  Check format rules only (headings, paragraphs, placeholders)
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
# Built-in schemas
# ---------------------------------------------------------------------------

SCHEMAS = {
    "blog_post": {
        "required_sections": ["title", "introduction", "body", "conclusion"],
        "min_words": 300,
        "format_rules": ["has_headings", "has_paragraphs"],
        "description": "Blog post with title, intro, body sections, and conclusion",
    },
    "email": {
        "required_sections": ["subject_line", "body", "cta"],
        "min_words": 50,
        "format_rules": ["has_cta", "has_subject"],
        "description": "Marketing email with subject, body, and call-to-action",
    },
    "ad_copy": {
        "required_sections": ["headline", "body", "cta"],
        "min_words": 10,
        "max_words": 150,
        "format_rules": ["has_cta"],
        "description": "Ad copy with headline, body text, and CTA",
    },
    "social_post": {
        "required_sections": ["body"],
        "min_words": 5,
        "max_words": 500,
        "format_rules": [],
        "description": "Social media post",
    },
    "landing_page": {
        "required_sections": ["headline", "value_proposition", "body", "cta"],
        "min_words": 100,
        "format_rules": ["has_headings", "has_cta"],
        "description": "Landing page with headline, value prop, body, and CTA",
    },
    "press_release": {
        "required_sections": ["headline", "dateline", "body", "boilerplate", "contact"],
        "min_words": 200,
        "format_rules": ["has_headings", "has_paragraphs"],
        "description": "Press release with headline, dateline, body, boilerplate, contact",
    },
    "content_brief": {
        "required_sections": ["objective", "target_audience", "key_messages", "outline"],
        "min_words": 100,
        "format_rules": ["has_headings"],
        "description": "Content brief with objective, audience, messages, and outline",
    },
    "campaign_plan": {
        "required_sections": ["objective", "strategy", "channels", "timeline", "budget", "kpis"],
        "min_words": 300,
        "format_rules": ["has_headings", "has_paragraphs"],
        "description": "Campaign plan with objectives, strategy, channels, timeline, budget, KPIs",
    },
}

# ---------------------------------------------------------------------------
# Section aliases for fuzzy matching
# ---------------------------------------------------------------------------

SECTION_ALIASES = {
    "title": ["title", "headline", "heading", "name"],
    "headline": ["headline", "title", "heading", "header"],
    "introduction": ["introduction", "intro", "overview", "summary", "about"],
    "body": ["body", "content", "main", "details", "description", "text", "message"],
    "conclusion": ["conclusion", "closing", "summary", "wrap-up", "wrapup", "final thoughts"],
    "cta": ["cta", "call to action", "call-to-action", "action", "next steps", "next step"],
    "subject_line": ["subject", "subject line", "subject_line", "email subject", "re:"],
    "value_proposition": ["value proposition", "value_proposition", "value prop", "benefits", "why us", "why choose"],
    "dateline": ["dateline", "date", "for immediate release", "press release date"],
    "boilerplate": ["boilerplate", "about us", "about the company", "company info", "about"],
    "contact": ["contact", "contact info", "contact information", "media contact", "press contact", "for more information"],
    "objective": ["objective", "objectives", "goal", "goals", "purpose", "aim"],
    "target_audience": ["target audience", "target_audience", "audience", "who", "persona", "personas"],
    "key_messages": ["key messages", "key_messages", "messages", "messaging", "key points", "talking points"],
    "outline": ["outline", "structure", "sections", "table of contents", "toc", "format"],
    "strategy": ["strategy", "approach", "methodology", "tactics", "strategic approach"],
    "channels": ["channels", "platforms", "media", "distribution", "channel mix", "media mix"],
    "timeline": ["timeline", "schedule", "milestones", "calendar", "dates", "phases"],
    "budget": ["budget", "investment", "cost", "costs", "spend", "funding", "financial"],
    "kpis": ["kpis", "kpi", "metrics", "measurement", "success metrics", "key performance indicators"],
}

# ---------------------------------------------------------------------------
# CTA action words
# ---------------------------------------------------------------------------

CTA_ACTION_WORDS = [
    "click", "sign up", "signup", "get started", "learn more", "buy now",
    "try", "download", "subscribe", "contact", "request", "register",
    "enroll", "apply", "book", "schedule", "claim", "grab", "join",
    "start", "shop", "order", "purchase", "explore", "discover",
    "call now", "act now", "get your", "start your", "begin your",
]

# ---------------------------------------------------------------------------
# Placeholder patterns
# ---------------------------------------------------------------------------

PLACEHOLDER_PATTERNS = [
    r"\[INSERT\]",
    r"\[TBD\]",
    r"\[TODO\]",
    r"\bTBD\b",
    r"\bTODO:",
    r"\bPLACEHOLDER\b",
    r"Lorem ipsum",
    r"your \w+ here",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_words(text: str) -> int:
    """Count words in text (alphabetic tokens)."""
    return len(re.findall(r"[a-zA-Z']+", text))


def _normalize(name: str) -> str:
    """Normalize a section name for comparison."""
    return re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()


def _extract_sections(text: str) -> list:
    """Extract section headers from markdown or bold-label patterns.

    Detects:
        ## Section Name
        # Section Name
        **Section Name**
        **Section Name:**
        SECTION NAME (all caps lines)
    """
    sections = []

    # Markdown headings: # ... or ## ... etc.
    for m in re.finditer(r"^#{1,6}\s+(.+)$", text, re.MULTILINE):
        sections.append(_normalize(m.group(1)))

    # Bold labels: **Label** or **Label:**
    for m in re.finditer(r"\*\*([^*]+?)\*\*\s*:?", text):
        sections.append(_normalize(m.group(1)))

    # ALL-CAPS lines (at least 3 chars, standalone)
    for m in re.finditer(r"^([A-Z][A-Z \-]{2,})$", text, re.MULTILINE):
        sections.append(_normalize(m.group(1)))

    return sections


def _fuzzy_section_match(required: str, found_sections: list) -> bool:
    """Check if a required section is present using alias matching."""
    aliases = SECTION_ALIASES.get(required, [required])
    normalized_aliases = [_normalize(a) for a in aliases]

    for found in found_sections:
        for alias in normalized_aliases:
            # Exact match
            if found == alias:
                return True
            # Substring containment (either direction)
            if alias in found or found in alias:
                return True
    return False


def _check_headings(text: str) -> bool:
    """Return True if text has at least one markdown heading."""
    return bool(re.search(r"^#{1,6}\s+", text, re.MULTILINE))


def _check_paragraphs(text: str) -> bool:
    """Return True if text has at least 2 paragraphs separated by blank lines."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return len(paragraphs) >= 2


def _check_cta(text: str) -> bool:
    """Return True if text contains CTA action words."""
    text_lower = text.lower()
    return any(word in text_lower for word in CTA_ACTION_WORDS)


def _check_subject(text: str) -> bool:
    """Return True if text has a subject line indicator."""
    # Check for explicit subject line patterns
    if re.search(r"(?i)^(subject|subject line|re)\s*:", text, re.MULTILINE):
        return True
    # Check for bold subject label
    if re.search(r"\*\*[Ss]ubject", text):
        return True
    # First non-empty line could be the subject if it's short
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if lines and len(lines[0]) <= 120 and len(lines) > 1:
        return True
    return False


def _find_placeholders(text: str) -> list:
    """Find all placeholder text occurrences."""
    found = []
    for pattern in PLACEHOLDER_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            found.append(m.group(0))
    return found


def _check_consistency(text: str, schema: dict) -> list:
    """Check for basic consistency issues. Returns list of warning strings."""
    warnings = []
    text_lower = text.lower()

    # If CTA is required and content mentions awareness, flag conversion CTAs
    required = schema.get("required_sections", [])
    if "cta" in required:
        awareness_signals = ["brand awareness", "awareness campaign", "awareness objective"]
        conversion_signals = ["buy now", "purchase", "shop now", "order now", "add to cart"]
        has_awareness = any(sig in text_lower for sig in awareness_signals)
        has_conversion_cta = any(sig in text_lower for sig in conversion_signals)
        if has_awareness and has_conversion_cta:
            warnings.append(
                "Content mentions awareness objectives but uses conversion-focused CTAs. "
                "Consider softer CTAs like 'Learn more' or 'Discover' for awareness content."
            )

    return warnings


# ---------------------------------------------------------------------------
# Format rule dispatcher
# ---------------------------------------------------------------------------

FORMAT_CHECKERS = {
    "has_headings": _check_headings,
    "has_paragraphs": _check_paragraphs,
    "has_cta": _check_cta,
    "has_subject": _check_subject,
}


# ---------------------------------------------------------------------------
# Scoring interpretation
# ---------------------------------------------------------------------------

def _interpret_score(score: int) -> str:
    """Return human-readable interpretation of the validation score."""
    if score >= 90:
        return "Excellent — content meets all requirements"
    elif score >= 75:
        return "Good — minor issues found"
    elif score >= 60:
        return "Fair — several issues need attention"
    elif score >= 40:
        return "Poor — significant gaps in required structure"
    else:
        return "Critical — major structural problems detected"


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------

def validate_content(text: str, schema: dict, schema_name: str = "custom") -> dict:
    """Validate content against a schema and return detailed results.

    Scoring: start at 100.
        -20 per missing required section
        -15 for word count violation
        -10 per format rule violation
        -10 per placeholder found
         -5 per consistency warning
    Floor at 0.
    """
    if not text or not text.strip():
        return {
            "validation_score": 0,
            "interpretation": "Critical — no content provided",
            "schema": schema_name,
            "checks": {},
            "issues": ["No content provided for validation."],
            "passed": False,
        }

    score = 100
    issues = []
    word_count = _count_words(text)

    # ------------------------------------------------------------------
    # 1. Required sections
    # ------------------------------------------------------------------
    required = schema.get("required_sections", [])
    found_sections = _extract_sections(text)
    sections_found = []
    sections_missing = []

    for req in required:
        if _fuzzy_section_match(req, found_sections):
            sections_found.append(req)
        else:
            # Fallback: check if the section name appears anywhere in the text
            aliases = SECTION_ALIASES.get(req, [req])
            text_lower = text.lower()
            if any(a.lower() in text_lower for a in aliases):
                sections_found.append(req)
            else:
                sections_missing.append(req)
                score -= 20
                issues.append(f"Missing required section: '{req}'")

    sections_status = "pass" if not sections_missing else "fail"

    # ------------------------------------------------------------------
    # 2. Word count
    # ------------------------------------------------------------------
    min_words = schema.get("min_words")
    max_words = schema.get("max_words")
    word_count_status = "pass"

    if min_words and word_count < min_words:
        word_count_status = "fail"
        score -= 15
        issues.append(f"Word count ({word_count}) below minimum ({min_words})")
    elif max_words and word_count > max_words:
        word_count_status = "fail"
        score -= 15
        issues.append(f"Word count ({word_count}) exceeds maximum ({max_words})")

    # ------------------------------------------------------------------
    # 3. Format rules
    # ------------------------------------------------------------------
    format_rules = schema.get("format_rules", [])
    format_details = {}

    for rule in format_rules:
        checker = FORMAT_CHECKERS.get(rule)
        if checker:
            passed = checker(text)
            format_details[rule] = passed
            if not passed:
                score -= 10
                issues.append(f"Format rule failed: '{rule}'")
        else:
            format_details[rule] = None  # unknown rule

    format_status = "pass" if all(v is True for v in format_details.values() if v is not None) else "fail"
    if not format_rules:
        format_status = "pass"

    # ------------------------------------------------------------------
    # 4. Placeholder detection
    # ------------------------------------------------------------------
    placeholders = _find_placeholders(text)
    # Deduplicate while preserving order
    seen = set()
    unique_placeholders = []
    for p in placeholders:
        if p not in seen:
            seen.add(p)
            unique_placeholders.append(p)

    for p in unique_placeholders:
        score -= 10
        issues.append(f"Placeholder text found: '{p}'")

    placeholder_status = "pass" if not unique_placeholders else "fail"

    # ------------------------------------------------------------------
    # 5. Consistency
    # ------------------------------------------------------------------
    consistency_warnings = _check_consistency(text, schema)
    for w in consistency_warnings:
        score -= 5
        issues.append(f"Consistency warning: {w}")

    consistency_status = "pass" if not consistency_warnings else "warn"

    # ------------------------------------------------------------------
    # Final score
    # ------------------------------------------------------------------
    score = max(score, 0)
    passed = score >= 50 and not sections_missing

    return {
        "validation_score": score,
        "interpretation": _interpret_score(score),
        "schema": schema_name,
        "checks": {
            "sections": {
                "status": sections_status,
                "found": sections_found,
                "missing": sections_missing,
            },
            "word_count": {
                "status": word_count_status,
                "count": word_count,
                "min": min_words,
                "max": max_words,
            },
            "format": {
                "status": format_status,
                "details": format_details,
            },
            "placeholders": {
                "status": placeholder_status,
                "found": unique_placeholders,
            },
            "consistency": {
                "status": consistency_status,
                "warnings": consistency_warnings,
            },
        },
        "issues": issues,
        "passed": passed,
    }


def check_format_only(text: str) -> dict:
    """Check format rules without schema validation."""
    if not text or not text.strip():
        return {
            "error": "No content provided for format check.",
            "checks": {},
        }

    word_count = _count_words(text)
    has_headings = _check_headings(text)
    has_paragraphs = _check_paragraphs(text)
    has_cta = _check_cta(text)
    placeholders = _find_placeholders(text)

    seen = set()
    unique_placeholders = []
    for p in placeholders:
        if p not in seen:
            seen.add(p)
            unique_placeholders.append(p)

    issues = []
    if not has_headings:
        issues.append("No markdown headings found. Add # or ## headings for structure.")
    if not has_paragraphs:
        issues.append("Fewer than 2 paragraphs detected. Break content into paragraphs with blank lines.")
    if unique_placeholders:
        issues.append(f"Placeholder text found: {', '.join(unique_placeholders)}")

    return {
        "format_check": True,
        "word_count": word_count,
        "has_headings": has_headings,
        "has_paragraphs": has_paragraphs,
        "has_cta": has_cta,
        "placeholders_found": unique_placeholders,
        "issues": issues,
        "clean": len(issues) == 0,
    }


def list_schemas() -> dict:
    """Return all built-in schemas with descriptions."""
    schemas = {}
    for name, schema in SCHEMAS.items():
        schemas[name] = {
            "description": schema["description"],
            "required_sections": schema["required_sections"],
            "min_words": schema.get("min_words"),
            "max_words": schema.get("max_words"),
            "format_rules": schema.get("format_rules", []),
        }
    return {"schemas": schemas, "count": len(schemas)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate marketing outputs against expected structure and format.",
        epilog=(
            "Actions:\n"
            "  validate      Validate content against a schema (built-in or custom)\n"
            "  list-schemas  List all built-in schema names and descriptions\n"
            "  check-format  Check format rules only (headings, paragraphs, placeholders)\n\n"
            "Built-in schemas: "
            + ", ".join(sorted(SCHEMAS.keys()))
            + "\n\n"
            "Examples:\n"
            '  python output-validator.py --action validate --text "# My Blog Post..." --schema blog_post\n'
            "  python output-validator.py --action validate --file draft.md --schema email\n"
            "  python output-validator.py --action validate --file page.md --custom-schema my-schema.json\n"
            "  python output-validator.py --action list-schemas\n"
            "  python output-validator.py --action check-format --file draft.md"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=["validate", "list-schemas", "check-format"],
        help="Action to perform.",
    )
    parser.add_argument(
        "--text",
        type=str,
        default=None,
        help="Content text to validate (inline).",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to a file containing content to validate.",
    )
    parser.add_argument(
        "--schema",
        type=str,
        default=None,
        help="Built-in schema name (e.g., blog_post, email, ad_copy).",
    )
    parser.add_argument(
        "--custom-schema",
        type=str,
        default=None,
        help="Path to a custom schema JSON file with the same structure as built-in schemas.",
    )
    return parser


def _resolve_text(args) -> str:
    """Resolve content text from --text or --file."""
    if args.text:
        return args.text
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(json.dumps({"error": f"File not found: {file_path}"}, indent=2))
            sys.exit(1)
        try:
            return file_path.read_text(encoding="utf-8-sig")
        except Exception as exc:
            print(json.dumps({"error": f"Could not read file: {exc}"}, indent=2))
            sys.exit(1)
    return ""


def _resolve_schema(args) -> tuple:
    """Resolve schema from --schema or --custom-schema. Returns (schema_dict, schema_name)."""
    if args.custom_schema:
        custom_path = Path(args.custom_schema)
        if not custom_path.exists():
            print(json.dumps({"error": f"Custom schema file not found: {custom_path}"}, indent=2))
            sys.exit(1)
        try:
            schema = json.loads(custom_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            print(json.dumps({"error": f"Invalid JSON in custom schema: {exc}"}, indent=2))
            sys.exit(1)
        return schema, custom_path.stem

    if args.schema:
        if args.schema not in SCHEMAS:
            print(json.dumps({
                "error": f"Unknown schema: '{args.schema}'",
                "available_schemas": sorted(SCHEMAS.keys()),
            }, indent=2))
            sys.exit(1)
        return SCHEMAS[args.schema], args.schema

    print(json.dumps({
        "error": "No schema specified. Provide --schema or --custom-schema.",
        "available_schemas": sorted(SCHEMAS.keys()),
    }, indent=2))
    sys.exit(1)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # --- list-schemas ---
    if args.action == "list-schemas":
        print(json.dumps(list_schemas(), indent=2))
        return

    # --- check-format ---
    if args.action == "check-format":
        if not args.text and not args.file:
            print(json.dumps({"error": "Provide --text or --file for format check."}, indent=2))
            sys.exit(1)
        text = _resolve_text(args)
        result = check_format_only(text)
        print(json.dumps(result, indent=2))
        sys.exit(1 if isinstance(result, dict) and "error" in result else 0)

    # --- validate ---
    if args.action == "validate":
        if not args.text and not args.file:
            print(json.dumps({"error": "Provide --text or --file for validation."}, indent=2))
            sys.exit(1)
        text = _resolve_text(args)
        schema, schema_name = _resolve_schema(args)
        result = validate_content(text, schema, schema_name)
        print(json.dumps(result, indent=2))
        sys.exit(1 if isinstance(result, dict) and "error" in result else 0)


if __name__ == "__main__":
    main()
