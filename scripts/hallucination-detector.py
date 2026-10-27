#!/usr/bin/env python3
"""
hallucination-detector.py
=========================
Detect fabricated statistics, fake URLs, unverifiable claims, and made-up
entities in marketing content.

Core evaluation innovation for AI-generated marketing copy. Uses heuristic
pattern matching (zero external dependencies) to flag content that may
contain hallucinated facts, unsubstantiated superlatives, placeholder URLs,
or unsourced statistics.

Dependencies: stdlib only (json, re, sys, argparse, pathlib, datetime, math)

Usage:
    python hallucination-detector.py --action detect --text "Our product boosts ROI by 347%..."
    python hallucination-detector.py --action detect --file draft.md
    python hallucination-detector.py --action check-urls --text "Visit https://example.com/demo"
    python hallucination-detector.py --action check-stats --file campaign.txt
    python hallucination-detector.py --action check-entities --text "A Harvard study found..."

Actions:
    detect           Full hallucination scan (all checks combined)
    check-urls       Check for placeholder or suspicious URLs only
    check-stats      Check for unverified statistics only
    check-entities   Check for unverifiable entity references only

Scoring:
    90-100  Minimal hallucination risk
    75-89   Low hallucination risk
    60-74   Moderate hallucination risk - review recommended
    40-59   High hallucination risk - revision required
    0-39    Critical hallucination risk - do not publish
"""

import argparse
import json
import math
import re
import sys

for _stream in (sys.stdout, sys.stderr):  # UTF-8 output, even where a Windows pipe defaults to cp1252
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from pathlib import Path

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

# Statistics patterns: percentages, dollar amounts, multipliers, ratios
STAT_PATTERNS = [
    (r"\b\d{1,3}(?:\.\d+)?%", "percentage"),
    (r"\$[\d,]+(?:\.\d{1,2})?(?:\s*(?:million|billion|trillion|M|B|K|k))?", "dollar_amount"),
    (r"\b\d+(?:\.\d+)?[xX]\b", "multiplier"),
    (r"\b(\d+)\s+out\s+of\s+(\d+)\b", "ratio"),
    (r"\b\d+(?:\.\d+)?\s*(?:million|billion|trillion)\b", "large_number"),
    (r"\b(?:over|more than|nearly|almost|approximately|up to)\s+\d[\d,]*", "qualified_number"),
]

# Citation / source attribution patterns (within 2 sentences)
CITATION_PATTERNS = [
    r"\baccording\s+to\b",
    r"\bper\b\s+(?:a\s+)?(?:\w+\s+){0,3}(?:report|study|survey|analysis|research)",
    r"\bbased\s+on\b",
    r"\bsource[ds]?\s*:",
    r"\b(?:20[12]\d|19\d{2})\b",  # year reference
    r"https?://",                   # hyperlink nearby
    r"\bcited\s+(?:by|in|from)\b",
    r"\breported\s+(?:by|in)\b",
    r"\bpublished\s+(?:by|in)\b",
    r"\b(?:research|data|findings)\s+from\b",
    r"\b(?:Gartner|Forrester|McKinsey|Deloitte|Statista|eMarketer|HubSpot|Salesforce)\b",
]

# Placeholder URL patterns
PLACEHOLDER_URL_PATTERNS = [
    r"example\.com",
    r"placeholder",
    r"your-?(?:site|domain|brand|company|url|website)",
    r"test\.(?:com|org|net)",
    r"(?:www\.)?(?:brand|company|site|domain)\.com",
    r"lorem",
    r"sample\.(?:com|org|net)",
    r"demo\.(?:com|org|net)",
    r"foo\.(?:com|org|net)",
    r"bar\.(?:com|org|net)",
    r"xxx",
]

# Placeholder text patterns (inline brackets)
PLACEHOLDER_TEXT_PATTERNS = [
    r"\[link\]",
    r"\[url\]",
    r"\[source\]",
    r"\[insert\s+\w+\]",
    r"\[your\s+\w+\]",
    r"\[add\s+\w+\]",
    r"\[TBD\]",
    r"\[TODO\]",
    r"\[placeholder\]",
    r"\[LINK\]",
    r"\[URL\]",
    r"\[SOURCE\]",
]

# Superlative / unsubstantiated claim patterns
SUPERLATIVE_PATTERNS = [
    (r"\b(?:the\s+)?(?:best|#1|number\s+one|number\s+1)\b", "superlative"),
    (r"\b(?:the\s+)?(?:first|only|fastest|slowest|largest|biggest)\b", "exclusive_claim"),
    (r"\b(?:leading|top-rated|award-winning|world-class|industry-leading)\b", "unqualified_title"),
    (r"\b(?:most\s+(?:popular|trusted|reliable|advanced|innovative))\b", "superlative"),
    (r"\b(?:unmatched|unrivaled|unparalleled|unsurpassed|peerless)\b", "superlative"),
    (r"\b(?:guaranteed|100%\s+guaranteed)\b", "guarantee_claim"),
]

# Substantiation patterns (nearby context that supports a superlative)
SUBSTANTIATION_PATTERNS = [
    r"\bcertified\s+by\b",
    r"\branked\s+(?:by|#?\d)\b",
    r"\bawarded?\s+(?:by|the)\b",
    r"\brated\s+(?:by|#?\d)\b",
    r"\brecognized\s+(?:by|as)\b",
    r"\baccording\s+to\b",
    r"\bG2\b|\bCapterra\b|\bTrustpilot\b|\bForrester\b|\bGartner\b",
    r"\bverified\s+by\b",
    r"\bindependently\s+(?:tested|verified|audited)\b",
]

# Entity patterns: quoted org names, study citations, person-as-citation
ENTITY_PATTERNS = [
    (r"(?:a|the)\s+((?:Harvard|Stanford|MIT|Oxford|Yale|Princeton|Cambridge)\s+(?:study|research|report|survey|analysis))", "academic_citation"),
    (r"(?:a|the)\s+((?:recent|new|latest|landmark|groundbreaking)\s+(?:study|research|report|survey))", "vague_study"),
    (r'"([A-Z][A-Za-z\s&,.-]+(?:Inc|Corp|LLC|Ltd|Co|Group|Foundation|Institute|Association)\.?)"', "quoted_organization"),
    (r"\b(Dr\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:says?|found|reported|confirmed|noted|stated|argues?)", "person_citation"),
    (r"\b(Professor\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:says?|found|reported|noted)", "person_citation"),
]

# Missing hedging: definitive forward-looking claims
DEFINITIVE_CLAIM_PATTERNS = [
    (r"\bwill\s+(?:increase|decrease|boost|improve|grow|double|triple|reduce|eliminate|transform|revolutionize)\b", "definitive_future"),
    (r"\bguarantees?\s+(?:that|a|an|the|you|your|results?|success)\b", "guarantee"),
    (r"\bensures?\s+(?:that|a|an|the|you|your|results?|success)\b", "guarantee_soft"),
    (r"\b(?:always|never)\s+(?:works?|fails?|delivers?|produces?|results?)\b", "absolute_claim"),
    (r"\bproven\s+to\b", "proven_claim"),
]

# Hedged equivalents (if nearby, the definitive claim is acceptable)
HEDGING_PATTERNS = [
    r"\bcan\b",
    r"\bmay\b",
    r"\bmight\b",
    r"\bcould\b",
    r"\btends?\s+to\b",
    r"\btypically\b",
    r"\bgenerally\b",
    r"\boften\b",
    r"\bin\s+(?:many|most|some)\s+cases\b",
    r"\bhas\s+(?:been\s+)?shown\s+to\b",
    r"\bdesigned\s+to\b",
    r"\bhelps?\b",
    r"\baims?\s+to\b",
]

# Headline / CTA detection (for severity escalation)
HEADLINE_CTA_PATTERNS = [
    r"^#{1,6}\s+",                      # markdown heading
    r"^<h[1-6]",                        # html heading
    r"\b(?:sign up|get started|buy now|order now|download|subscribe|join)\b",
    r"\b(?:free trial|limited time|act now|don't miss)\b",
]

# ---------------------------------------------------------------------------
# Severity weights for scoring
# ---------------------------------------------------------------------------
SEVERITY_DEDUCTIONS = {
    "critical": 15,
    "high": 8,
    "medium": 4,
    "low": 2,
}


# ---------------------------------------------------------------------------
# Helper: split text into sentences (stdlib-only)
# ---------------------------------------------------------------------------
def _split_sentences(text):
    """Split text into rough sentences using regex."""
    # Split on sentence-ending punctuation followed by space and uppercase letter
    # This avoids splitting on abbreviations like Dr., Inc., U.S., e.g., etc.
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def _get_sentence_window(sentences, idx, window=2):
    """Return text from sentences within +/- window of idx."""
    start = max(0, idx - window)
    end = min(len(sentences), idx + window + 1)
    return " ".join(sentences[start:end])


def _is_in_headline_or_cta(sentence):
    """Check if a sentence appears to be a headline or CTA."""
    for pattern in HEADLINE_CTA_PATTERNS:
        if re.search(pattern, sentence, re.IGNORECASE):
            return True
    return False


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

def check_stats(text):
    """Detect statistics without source attribution."""
    flags = []
    sentences = _split_sentences(text)

    for sent_idx, sentence in enumerate(sentences):
        for pattern, stat_type in STAT_PATTERNS:
            for match in re.finditer(pattern, sentence, re.IGNORECASE):
                stat_text = match.group(0)
                # Check for citation in a 2-sentence window
                window = _get_sentence_window(sentences, sent_idx, window=2)
                has_citation = any(
                    re.search(cp, window, re.IGNORECASE)
                    for cp in CITATION_PATTERNS
                )

                if not has_citation:
                    in_headline = _is_in_headline_or_cta(sentence)
                    severity = "high" if in_headline else "medium"
                    flags.append({
                        "type": "unverified_statistic",
                        "value": stat_text,
                        "stat_type": stat_type,
                        "context": sentence.strip()[:200],
                        "severity": severity,
                        "reason": (
                            "Statistic lacks source attribution. No citation, "
                            "source reference, date, or hyperlink found within "
                            "surrounding context."
                        ),
                    })

    return flags


def check_urls(text, brand_domain=None):
    """Detect placeholder or suspicious URLs."""
    flags = []

    # Check inline placeholder patterns (e.g. [link], [URL])
    for pattern in PLACEHOLDER_TEXT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            context = text[max(0, match.start() - 40):match.end() + 40].strip()
            # Placeholder in a CTA/link context is the worst case: the reader
            # is being asked to act on a link that does not exist.
            severity = "critical" if _is_in_headline_or_cta(context) else "high"
            flags.append({
                "type": "placeholder_text",
                "value": match.group(0),
                "context": context,
                "severity": severity,
                "reason": "Placeholder text found that should be replaced with actual content.",
            })

    # Extract URLs and check for placeholder patterns
    url_pattern = r'https?://[^\s<>\[\]"\')\}]+'
    for match in re.finditer(url_pattern, text):
        url = match.group(0).rstrip(".,;:!?)")
        url_lower = url.lower()

        # Skip if it matches the brand's own domain
        if brand_domain and brand_domain.lower() in url_lower:
            continue

        for placeholder_pat in PLACEHOLDER_URL_PATTERNS:
            if re.search(placeholder_pat, url_lower):
                context = text[max(0, match.start() - 40):match.end() + 40].strip()
                # A placeholder URL inside a CTA/link context is critical:
                # publishing it ships a broken call to action.
                severity = "critical" if _is_in_headline_or_cta(context) else "high"
                flags.append({
                    "type": "suspicious_url",
                    "value": url,
                    "context": context,
                    "severity": severity,
                    "reason": (
                        f"URL matches placeholder pattern. Replace with "
                        f"a real, verified link before publishing."
                    ),
                })
                break  # one flag per URL is sufficient

    return flags


def check_claims(text):
    """Detect unsubstantiated superlative and exclusive claims."""
    flags = []
    sentences = _split_sentences(text)

    for sent_idx, sentence in enumerate(sentences):
        for pattern, claim_type in SUPERLATIVE_PATTERNS:
            for match in re.finditer(pattern, sentence, re.IGNORECASE):
                claim_text = match.group(0)
                window = _get_sentence_window(sentences, sent_idx, window=2)
                has_substantiation = any(
                    re.search(sp, window, re.IGNORECASE)
                    for sp in SUBSTANTIATION_PATTERNS
                )

                if not has_substantiation:
                    in_headline = _is_in_headline_or_cta(sentence)
                    severity = "high" if in_headline else "medium"
                    flags.append({
                        "type": "unsubstantiated_claim",
                        "claim_type": claim_type,
                        "value": claim_text,
                        "context": sentence.strip()[:200],
                        "severity": severity,
                        "reason": (
                            "Superlative or exclusive claim lacks substantiation. "
                            "Add a certification, ranking source, or qualifying "
                            "context."
                        ),
                    })

    return flags


def check_entities(text):
    """Detect potentially fabricated entity references."""
    flags = []

    for pattern, entity_type in ENTITY_PATTERNS:
        for match in re.finditer(pattern, text):
            entity_name = match.group(1) if match.lastindex else match.group(0)
            # Get surrounding context
            start = max(0, match.start() - 60)
            end = min(len(text), match.end() + 60)
            context = text[start:end].strip()

            severity = "medium" if entity_type == "academic_citation" else "low"
            flags.append({
                "type": "entity_to_verify",
                "entity_type": entity_type,
                "value": entity_name.strip(),
                "context": context[:200],
                "severity": severity,
                "status": "requires_verification",
                "reason": (
                    "Entity reference should be independently verified. "
                    "AI models can fabricate study names, organizations, "
                    "and expert citations."
                ),
            })

    return flags


def check_hedging(text):
    """Detect definitive forward-looking claims that lack hedging."""
    flags = []
    sentences = _split_sentences(text)

    for sent_idx, sentence in enumerate(sentences):
        for pattern, claim_type in DEFINITIVE_CLAIM_PATTERNS:
            for match in re.finditer(pattern, sentence, re.IGNORECASE):
                claim_text = match.group(0)
                # Check if the same sentence has hedging language
                has_hedging = any(
                    re.search(hp, sentence, re.IGNORECASE)
                    for hp in HEDGING_PATTERNS
                )

                if not has_hedging:
                    severity = "medium" if claim_type in ("definitive_future", "guarantee") else "low"
                    flags.append({
                        "type": "missing_hedging",
                        "claim_type": claim_type,
                        "value": claim_text,
                        "context": sentence.strip()[:200],
                        "severity": severity,
                        "reason": (
                            "Definitive claim without hedging language. "
                            "Consider softer phrasing (e.g., 'can increase' "
                            "instead of 'will increase', 'may help' instead "
                            "of 'guarantees')."
                        ),
                    })

    return flags


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def compute_score(all_flags):
    """Compute hallucination score from flags. Start at 100, subtract per flag."""
    score = 100
    critical_count = 0

    for flag in all_flags:
        severity = flag.get("severity", "low")
        deduction = SEVERITY_DEDUCTIONS.get(severity, 2)
        score -= deduction
        if severity == "critical":
            critical_count += 1

    score = max(0, score)
    return score, critical_count


def interpret_score(score):
    """Return human-readable interpretation of the hallucination score."""
    if score >= 90:
        return "Minimal hallucination risk"
    elif score >= 75:
        return "Low hallucination risk"
    elif score >= 60:
        return "Moderate hallucination risk - review recommended"
    elif score >= 40:
        return "High hallucination risk - revision required"
    else:
        return "Critical hallucination risk - do not publish"


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

def action_detect(text, brand_domain=None):
    """Run all hallucination checks and return combined results."""
    stat_flags = check_stats(text)
    url_flags = check_urls(text, brand_domain)
    claim_flags = check_claims(text)
    entity_flags = check_entities(text)
    hedging_flags = check_hedging(text)

    all_flags = stat_flags + url_flags + claim_flags + entity_flags + hedging_flags
    score, critical_count = compute_score(all_flags)

    return {
        "hallucination_score": score,
        "interpretation": interpret_score(score),
        "checks": {
            "unverified_statistics": stat_flags,
            "suspicious_urls": url_flags,
            "unsubstantiated_claims": claim_flags,
            "entities_to_verify": entity_flags,
            "missing_hedging": hedging_flags,
        },
        "total_flags": len(all_flags),
        "critical_flags": critical_count,
    }


def action_check_urls(text, brand_domain=None):
    """Run URL checks only."""
    flags = check_urls(text, brand_domain)
    return {
        "suspicious_urls": flags,
        "total_flags": len(flags),
    }


def action_check_stats(text):
    """Run statistics checks only."""
    flags = check_stats(text)
    return {
        "unverified_statistics": flags,
        "total_flags": len(flags),
    }


def action_check_entities(text):
    """Run entity checks only."""
    flags = check_entities(text)
    return {
        "entities_to_verify": flags,
        "total_flags": len(flags),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Detect fabricated statistics, fake URLs, unverifiable claims, "
            "and made-up entities in marketing content."
        ),
        epilog=(
            "Actions:\n"
            "  detect           Full hallucination scan (all checks combined)\n"
            "  check-urls       Check for placeholder or suspicious URLs only\n"
            "  check-stats      Check for unverified statistics only\n"
            "  check-entities   Check for unverifiable entity references only\n"
            "\n"
            "Scoring (detect action):\n"
            "  90-100  Minimal hallucination risk\n"
            "  75-89   Low hallucination risk\n"
            "  60-74   Moderate hallucination risk - review recommended\n"
            "  40-59   High hallucination risk - revision required\n"
            "  0-39    Critical hallucination risk - do not publish\n"
            "\n"
            "Examples:\n"
            '  python hallucination-detector.py --action detect --text "Our ROI increased 347%"\n'
            '  python hallucination-detector.py --action detect --file draft.md\n'
            '  python hallucination-detector.py --action check-urls --text "Visit https://example.com"\n'
            '  python hallucination-detector.py --action check-stats --file campaign.txt\n'
            '  python hallucination-detector.py --action check-entities --text "A Harvard study found..."\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--action", required=True,
        choices=["detect", "check-urls", "check-stats", "check-entities"],
        help="Which detection action to run.",
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--text", type=str,
        help="Content text to analyze (inline).",
    )
    input_group.add_argument(
        "--file", type=str,
        help="Path to a file containing content to analyze.",
    )
    parser.add_argument(
        "--brand-domain", type=str, default=None,
        help=(
            "Brand's own domain (e.g., 'acme.com'). URLs matching this domain "
            "will not be flagged as suspicious."
        ),
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Resolve input text
    if args.text:
        text = args.text
    else:
        file_path = Path(args.file)
        if not file_path.exists():
            print(json.dumps({"error": f"File not found: {args.file}"}))
            sys.exit(1)
        try:
            text = file_path.read_text(encoding="utf-8-sig")
        except Exception as exc:
            print(json.dumps({"error": f"Could not read file: {exc}"}))
            sys.exit(1)

    if not text or not text.strip():
        print(json.dumps({"error": "Empty content provided."}))
        sys.exit(1)

    # Dispatch action
    if args.action == "detect":
        result = action_detect(text, brand_domain=args.brand_domain)
    elif args.action == "check-urls":
        result = action_check_urls(text, brand_domain=args.brand_domain)
    elif args.action == "check-stats":
        result = action_check_stats(text)
    elif args.action == "check-entities":
        result = action_check_entities(text)
    else:
        result = {"error": f"Unknown action: {args.action}"}

    print(json.dumps(result, indent=2))
    sys.exit(1 if isinstance(result, dict) and "error" in result else 0)  # $? must say it failed


if __name__ == "__main__":
    main()
