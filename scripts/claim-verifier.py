#!/usr/bin/env python3
"""
claim-verifier.py
=================
Cross-check marketing claims against user-provided evidence files.

Extracts verifiable claims (statistics, percentages, specific numbers, awards,
certifications) from marketing content, then fuzzy-matches them against an
evidence file to classify each claim as verified, partially verified,
unverified, evidence_unverified (matched an evidence item whose verified flag
is false), or contradicted (numbers conflict with the evidence).

Dependencies: stdlib only (json, re, sys, argparse, pathlib, difflib)

Usage:
    python claim-verifier.py --action verify --text "50% increase in conversions" --evidence evidence.json
    python claim-verifier.py --action verify --file draft.md --evidence evidence.json
    python claim-verifier.py --action extract-claims --text "We grew revenue by 3x and serve 500+ companies"
    python claim-verifier.py --action match-evidence --claim "50% increase" --evidence evidence.json

Actions:
    verify           Extract claims from content and verify against evidence file
    extract-claims   Extract verifiable claims from content (no evidence needed)
    match-evidence   Match a single claim against evidence items

Evidence file format (JSON):
    {
        "evidence": [
            {
                "claim": "50% increase in conversions",
                "source": "GA4 Q4 2025 report",
                "date": "2025-12-31",
                "verified": true
            }
        ]
    }

Scoring:
    (verified * 100 + partially_verified * 60) / total_claims
    If no verifiable claims found, score = 100 with note.
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
from difflib import SequenceMatcher
from pathlib import Path

# ---------------------------------------------------------------------------
# Claim extraction patterns
# ---------------------------------------------------------------------------

# Patterns that identify verifiable claims in marketing content
CLAIM_PATTERNS = [
    (r"\b\d{1,3}(?:\.\d+)?%\s+(?:increase|decrease|growth|decline|improvement|reduction|boost|drop|rise|gain|lift)\s+in\s+[\w\s]+", "percentage_change"),
    (r"\b(?:increase[ds]?|decrease[ds]?|grew|boost(?:ed)?|improved|reduced|grew)\s+(?:by\s+)?\d{1,3}(?:\.\d+)?%", "percentage_change"),
    # "%" is a non-word char, so a trailing \b here would only match when a word
    # character FOLLOWS the "%" — "98%x" matched while "98% of customers", "98%."
    # and end-of-line never did (GitHub issue #10). (?!\w) expresses the intent:
    # the token ends at "%" unless something word-like is glued on.
    (r"\b\d{1,3}(?:\.\d+)?%(?!\w)", "percentage"),
    (r"\$[\d,]+(?:\.\d{1,2})?(?:\s*(?:million|billion|trillion|M|B|K|k))?", "dollar_amount"),
    (r"\b\d+(?:\.\d+)?[xX]\s+(?:increase|growth|improvement|return|ROI|more|faster|better)", "multiplier"),
    (r"\b(?:over|more than|nearly)\s+[\d,]+\+?\s+(?:companies|customers|clients|users|brands|partners|businesses|teams|organizations)", "customer_count"),
    (r"\b[\d,]+\+?\s+(?:companies|customers|clients|users|brands|partners|businesses|teams|organizations)", "customer_count"),
    (r"\b(?:trusted|used|chosen|preferred)\s+by\s+[\d,]+\+?", "trust_claim"),
    (r"\b(?:award-winning|award winning|certified|accredited|patented)\b", "certification"),
    (r"\b(?:voted|named|ranked|recognized)\s+(?:as\s+)?(?:the\s+)?(?:best|top|#\d+|number\s+\d+)", "ranking"),
    (r"\b(?:ISO|SOC|GDPR|HIPAA|PCI|FedRAMP)\s*[\d-]*\s*(?:certified|compliant|compliance)", "compliance_claim"),
    (r"\b\d+(?:\.\d+)?\s*(?:million|billion|trillion)\s+(?:in\s+)?(?:revenue|sales|ARR|MRR|funding|valuation)", "financial_claim"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_numbers(text):
    """Extract all numeric values from text as floats."""
    numbers = []
    # Match integers, decimals, and comma-separated numbers
    for match in re.finditer(r"[\d,]+(?:\.\d+)?", text):
        try:
            num_str = match.group(0).replace(",", "")
            numbers.append(float(num_str))
        except ValueError:
            continue
    return numbers


def _normalize_text(text):
    """Normalize text for comparison: lowercase, collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s%$.,]", "", text)
    return text


def _number_similarity(nums_a, nums_b, tolerance=0.1):
    """Compare two sets of numbers with tolerance. Returns 0.0-1.0 score."""
    if not nums_a or not nums_b:
        return 0.0

    matches = 0
    total = max(len(nums_a), len(nums_b))

    for a in nums_a:
        for b in nums_b:
            if a == 0 and b == 0:
                matches += 1
                break
            elif a != 0 and b != 0:
                ratio = min(a, b) / max(a, b)
                if ratio >= (1.0 - tolerance):
                    matches += 1
                    break

    return matches / total if total > 0 else 0.0


def _text_similarity(text_a, text_b):
    """Compute text similarity using SequenceMatcher. Returns 0.0-1.0."""
    norm_a = _normalize_text(text_a)
    norm_b = _normalize_text(text_b)
    return SequenceMatcher(None, norm_a, norm_b).ratio()


def _match_score(claim_text, evidence_item):
    """Compute overall match score between a claim and an evidence item."""
    evidence_claim = evidence_item.get("claim", "")

    # Text similarity (keyword overlap)
    text_sim = _text_similarity(claim_text, evidence_claim)

    # Number comparison
    claim_nums = _extract_numbers(claim_text)
    evidence_nums = _extract_numbers(evidence_claim)
    num_sim = _number_similarity(claim_nums, evidence_nums)

    # Combined score: weight text similarity and number similarity
    if claim_nums and evidence_nums:
        # When both have numbers, numbers are important
        combined = text_sim * 0.5 + num_sim * 0.5
    elif claim_nums or evidence_nums:
        # One has numbers, the other doesn't - lower match
        combined = text_sim * 0.7 + num_sim * 0.3
    else:
        # No numbers in either - pure text match
        combined = text_sim

    return round(combined, 4)


def _numbers_contradict(claim_text, evidence_claim):
    """Check if numbers in claim and evidence contradict each other."""
    claim_nums = _extract_numbers(claim_text)
    evidence_nums = _extract_numbers(evidence_claim)

    if not claim_nums or not evidence_nums:
        return False

    # If the primary numbers differ significantly, it's a contradiction
    for a in claim_nums:
        for b in evidence_nums:
            if a == 0 or b == 0:
                continue
            ratio = min(a, b) / max(a, b)
            if ratio < 0.5:  # numbers differ by more than 50%
                return True

    return False


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def extract_claims(text):
    """Extract verifiable claims from marketing content."""
    claims = []
    seen_spans = set()

    for pattern, claim_type in CLAIM_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            span = (match.start(), match.end())
            # Skip overlapping matches
            overlap = False
            for seen_start, seen_end in seen_spans:
                if not (span[1] <= seen_start or span[0] >= seen_end):
                    overlap = True
                    break
            if overlap:
                continue

            claim_text = match.group(0).strip()
            if len(claim_text) < 3:
                continue

            seen_spans.add(span)
            claims.append({
                "text": claim_text,
                "type": claim_type,
                "position": span[0],
            })

    # Sort by position in text
    claims.sort(key=lambda c: c["position"])

    # Remove position from output (internal use only)
    for claim in claims:
        del claim["position"]

    return claims


def verify_claims(text, evidence_data):
    """Extract claims and verify against evidence."""
    claims = extract_claims(text)
    evidence_items = evidence_data.get("evidence", [])

    if not claims:
        return {
            "verification_score": 100,
            "interpretation": "No verifiable claims found in content",
            "claims": [],
            "summary": {
                "verified": 0,
                "partially_verified": 0,
                "unverified": 0,
                "evidence_unverified": 0,
                "contradicted": 0,
                "total": 0,
            },
        }

    verified_claims = []
    summary = {
        "verified": 0,
        "partially_verified": 0,
        "unverified": 0,
        "evidence_unverified": 0,
        "contradicted": 0,
        "total": len(claims),
    }

    for claim in claims:
        claim_text = claim["text"]
        best_match = None
        best_score = 0.0
        best_evidence = None

        for ev in evidence_items:
            score = _match_score(claim_text, ev)
            if score > best_score:
                best_score = score
                best_match = ev.get("claim", "")
                best_evidence = ev

        # Classify the claim
        if best_score >= 0.6 and best_evidence is not None:
            # Check for contradiction (numeric conflict with the evidence)
            ev_claim = best_evidence.get("claim", "")
            ev_verified = best_evidence.get("verified", False)

            if _numbers_contradict(claim_text, ev_claim):
                status = "contradicted"
                summary["contradicted"] += 1
            elif not ev_verified:
                # Evidence item matched but its verified flag is false —
                # the claim rests on unverified evidence, not a contradiction.
                status = "evidence_unverified"
                summary["evidence_unverified"] += 1
            elif best_score >= 0.8:
                status = "verified"
                summary["verified"] += 1
            else:
                status = "partially_verified"
                summary["partially_verified"] += 1

            verified_claims.append({
                "text": claim_text,
                "claim_type": claim.get("type", "unknown"),
                "status": status,
                "evidence_match": best_match,
                "source": best_evidence.get("source"),
                "confidence": best_score,
            })
        else:
            summary["unverified"] += 1
            verified_claims.append({
                "text": claim_text,
                "claim_type": claim.get("type", "unknown"),
                "status": "unverified",
                "evidence_match": None,
                "source": None,
                "confidence": round(best_score, 4) if best_score > 0 else 0.0,
            })

    # Compute verification score
    total = summary["total"]
    if total > 0:
        score_raw = (
            (summary["verified"] * 100 + summary["partially_verified"] * 60)
            / total
        )
        verification_score = max(0, min(100, round(score_raw, 1)))
    else:
        verification_score = 100

    # Interpretation
    if verification_score >= 90:
        interpretation = "Well-verified - claims are strongly supported by evidence"
    elif verification_score >= 70:
        interpretation = "Partially verified - some claims need evidence"
    elif verification_score >= 50:
        interpretation = "Weakly verified - many claims lack evidence"
    elif verification_score >= 25:
        interpretation = "Poorly verified - most claims are unsubstantiated"
    else:
        interpretation = "Unverified - claims are not supported by provided evidence"

    return {
        "verification_score": verification_score,
        "interpretation": interpretation,
        "claims": verified_claims,
        "summary": summary,
    }


def match_single_claim(claim_text, evidence_data):
    """Match a single claim against evidence items and return matches."""
    evidence_items = evidence_data.get("evidence", [])
    matches = []

    for ev in evidence_items:
        score = _match_score(claim_text, ev)
        if score >= 0.3:  # include lower-confidence matches for visibility
            matches.append({
                "evidence_claim": ev.get("claim", ""),
                "source": ev.get("source"),
                "date": ev.get("date"),
                "verified": ev.get("verified", False),
                "match_score": score,
            })

    matches.sort(key=lambda m: m["match_score"], reverse=True)

    return {
        "input_claim": claim_text,
        "matches_found": len(matches),
        "matches": matches,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Cross-check marketing claims against user-provided evidence files."
        ),
        epilog=(
            "Actions:\n"
            "  verify           Extract claims and verify against evidence file\n"
            "  extract-claims   Extract verifiable claims from content\n"
            "  match-evidence   Match a single claim against evidence items\n"
            "\n"
            "Evidence file format (JSON):\n"
            '  {"evidence": [{"claim": "...", "source": "...", "date": "...", "verified": true}]}\n'
            "\n"
            "Examples:\n"
            '  python claim-verifier.py --action verify --text "50% boost" --evidence evidence.json\n'
            '  python claim-verifier.py --action verify --file draft.md --evidence evidence.json\n'
            '  python claim-verifier.py --action extract-claims --text "We grew revenue by 3x"\n'
            '  python claim-verifier.py --action match-evidence --claim "50% increase" --evidence evidence.json\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--action", required=True,
        choices=["verify", "extract-claims", "match-evidence"],
        help="Which verification action to run.",
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--text", type=str,
        help="Content text to analyze (inline).",
    )
    input_group.add_argument(
        "--file", type=str,
        help="Path to a file containing content to analyze.",
    )
    parser.add_argument(
        "--claim", type=str,
        help="Single claim text for match-evidence action.",
    )
    parser.add_argument(
        "--evidence", type=str,
        help="Path to evidence JSON file.",
    )
    return parser


def _load_evidence(filepath):
    """Load and validate an evidence JSON file."""
    path = Path(filepath)
    if not path.exists():
        return None, f"Evidence file not found: {filepath}"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON in evidence file: {exc}"

    if "evidence" not in data or not isinstance(data["evidence"], list):
        return None, (
            "Evidence file must contain an 'evidence' key with a list of items. "
            'Expected format: {"evidence": [{"claim": "...", "source": "...", "verified": true}]}'
        )

    return data, None


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Resolve input text (for verify and extract-claims)
    text = None
    if args.text:
        text = args.text
    elif args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(json.dumps({"error": f"File not found: {args.file}"}))
            sys.exit(1)
        try:
            text = file_path.read_text(encoding="utf-8-sig")
        except Exception as exc:
            print(json.dumps({"error": f"Could not read file: {exc}"}))
            sys.exit(1)

    # Dispatch action
    if args.action == "verify":
        if not text:
            print(json.dumps({"error": "Provide --text or --file for verify action."}))
            sys.exit(1)
        if not args.evidence:
            print(json.dumps({"error": "Provide --evidence for verify action."}))
            sys.exit(1)
        evidence_data, err = _load_evidence(args.evidence)
        if err:
            print(json.dumps({"error": err}))
            sys.exit(1)
        result = verify_claims(text, evidence_data)

    elif args.action == "extract-claims":
        if not text:
            print(json.dumps({"error": "Provide --text or --file for extract-claims action."}))
            sys.exit(1)
        claims = extract_claims(text)
        result = {
            "claims": claims,
            "total_claims": len(claims),
        }

    elif args.action == "match-evidence":
        if not args.claim:
            print(json.dumps({"error": "Provide --claim for match-evidence action."}))
            sys.exit(1)
        if not args.evidence:
            print(json.dumps({"error": "Provide --evidence for match-evidence action."}))
            sys.exit(1)
        evidence_data, err = _load_evidence(args.evidence)
        if err:
            print(json.dumps({"error": err}))
            sys.exit(1)
        result = match_single_claim(args.claim, evidence_data)

    else:
        result = {"error": f"Unknown action: {args.action}"}

    print(json.dumps(result, indent=2))
    sys.exit(1 if isinstance(result, dict) and "error" in result else 0)  # $? must say it failed


if __name__ == "__main__":
    main()
