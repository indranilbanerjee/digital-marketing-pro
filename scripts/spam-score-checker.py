#!/usr/bin/env python3
"""Check email content for spam risk indicators.

Scans email body and optional subject line for spam triggers across multiple
categories: trigger words (4 severity tiers), excessive punctuation, ALL CAPS
abuse, link density, suspicious phrases, missing unsubscribe links, and
image-to-text ratio. Returns a risk score (0-100, lower is better) with
categorized findings and deliverability recommendations.

Usage:
    python spam-score-checker.py --content "Buy now! 100% free offer!!!"
    python spam-score-checker.py --file email.html --subject "URGENT: Act Now"
    python spam-score-checker.py --content "Hello {first_name}..." --subject "Quick update"
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Spam trigger words organized by severity tier
# ---------------------------------------------------------------------------

SPAM_TIERS = {
    "critical": [
        "act now", "100% free", "click here", "you've been selected",
        "you have been selected", "winner", "congratulations", "this isn't spam",
        "this is not spam", "you're a winner", "act immediately",
        "once in a lifetime", "no catch", "double your income",
        "earn money while you sleep",
    ],
    "high": [
        "free", "urgent", "limited time", "buy now", "no obligation",
        "risk free", "no risk", "call now", "apply now", "order now",
        "don't delete", "don't hesitate", "while supplies last",
        "offer expires", "free access", "free gift", "free offer",
        "get it now", "what are you waiting for", "expire",
    ],
    "medium": [
        "special offer", "save big", "best price", "lowest price",
        "bargain", "incredible deal", "exclusive deal", "amazing deal",
        "fantastic deal", "great offer", "special promotion",
        "compare rates", "consolidate debt", "extra cash",
        "earn extra", "make money", "million dollars",
    ],
    "low": [
        "deal", "discount", "offer", "sale", "bonus", "cash",
        "cheap", "credit", "guarantee", "investment", "loan",
        "luxury", "opportunity", "profit", "quote", "rates",
        "refinance", "subscribe", "trial", "unlimited", "wealth",
    ],
}

TIER_SCORES = {
    "critical": 15,
    "high": 8,
    "medium": 4,
    "low": 2,
}

SUSPICIOUS_PHRASES = [
    "this is not spam",
    "this isn't spam",
    "you've been selected",
    "you have been selected",
    "act immediately",
    "wire transfer",
    "nigerian prince",
    "dear beneficiary",
    "claim your prize",
    "verify your account",
    "confirm your identity",
    "suspended your account",
    "unusual activity",
]


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------

def scan_spam_triggers(text):
    """Scan text for spam trigger words across all tiers."""
    text_lower = text.lower()
    findings = []
    total_penalty = 0

    for tier, phrases in SPAM_TIERS.items():
        for phrase in phrases:
            if phrase in text_lower:
                penalty = TIER_SCORES[tier]
                total_penalty += penalty
                findings.append({
                    "category": "spam_trigger",
                    "severity": tier,
                    "detail": f"'{phrase}' (+{penalty} risk)",
                })

    return total_penalty, findings


def check_punctuation(text):
    """Check for excessive punctuation patterns."""
    findings = []
    penalty = 0

    # Multiple exclamation marks in sequence
    excl_sequences = re.findall(r"!{2,}", text)
    for seq in excl_sequences:
        penalty += 5
        findings.append({
            "category": "excessive_punctuation",
            "severity": "medium",
            "detail": f"Exclamation sequence '{seq}' (+5 risk)",
        })

    # Multiple question marks in sequence
    quest_sequences = re.findall(r"\?{2,}", text)
    for seq in quest_sequences:
        penalty += 5
        findings.append({
            "category": "excessive_punctuation",
            "severity": "medium",
            "detail": f"Question mark sequence '{seq}' (+5 risk)",
        })

    # Dollar signs used excessively
    dollar_count = text.count("$")
    if dollar_count >= 3:
        penalty += 5
        findings.append({
            "category": "excessive_punctuation",
            "severity": "low",
            "detail": f"{dollar_count} dollar signs found (+5 risk)",
        })

    return penalty, findings


def check_caps_ratio(text):
    """Check for ALL CAPS abuse."""
    words = text.split()
    if not words:
        return 0, []

    caps_words = [w for w in words if w.isupper() and len(w) > 2 and w.isalpha()]
    total_alpha = [w for w in words if w.isalpha() and len(w) > 1]

    if not total_alpha:
        return 0, []

    ratio = len(caps_words) / len(total_alpha)
    findings = []
    penalty = 0

    if ratio > 0.40:
        penalty = 20
        findings.append({
            "category": "all_caps",
            "severity": "high",
            "detail": f"{ratio:.0%} of words are ALL CAPS (+20 risk). Significant spam signal.",
        })
    elif ratio > 0.20:
        penalty = 15
        findings.append({
            "category": "all_caps",
            "severity": "medium",
            "detail": f"{ratio:.0%} of words are ALL CAPS (+15 risk)",
        })
    elif ratio > 0.10:
        penalty = 5
        findings.append({
            "category": "all_caps",
            "severity": "low",
            "detail": f"{ratio:.0%} of words are ALL CAPS (+5 risk)",
        })

    return penalty, findings


def check_link_density(text):
    """Check link density (links per 100 words)."""
    # Count URLs and href attributes
    urls = re.findall(r'https?://[^\s<>"\']+', text)
    hrefs = re.findall(r'href\s*=\s*["\']([^"\']+)["\']', text, re.IGNORECASE)
    link_count = len(set(urls + hrefs))

    # Word count (strip HTML for accuracy)
    text_clean = re.sub(r"<[^>]+>", " ", text)
    words = text_clean.split()
    word_count = len(words)

    if word_count == 0:
        return 0, []

    density = (link_count / word_count) * 100
    findings = []
    penalty = 0

    if density > 5:
        penalty = 20
        findings.append({
            "category": "link_density",
            "severity": "high",
            "detail": f"{link_count} links in {word_count} words ({density:.1f} per 100). Very high density (+20 risk).",
        })
    elif density > 3:
        penalty = 10
        findings.append({
            "category": "link_density",
            "severity": "medium",
            "detail": f"{link_count} links in {word_count} words ({density:.1f} per 100). High density (+10 risk).",
        })

    return penalty, findings


def check_suspicious_phrases(text):
    """Check for known suspicious phrases."""
    text_lower = text.lower()
    findings = []
    penalty = 0

    for phrase in SUSPICIOUS_PHRASES:
        if phrase in text_lower:
            penalty += 10
            findings.append({
                "category": "suspicious_phrase",
                "severity": "critical",
                "detail": f"'{phrase}' (+10 risk)",
            })

    return penalty, findings


def check_unsubscribe(text):
    """Check for missing unsubscribe link in longer emails."""
    # Strip HTML tags for word count
    text_clean = re.sub(r"<[^>]+>", " ", text)
    word_count = len(text_clean.split())

    if word_count <= 200:
        return 0, []

    has_unsub = bool(re.search(
        r"unsubscribe|opt[\s-]?out|manage[\s-]?preferences|email[\s-]?preferences",
        text, re.IGNORECASE
    ))

    if not has_unsub:
        return 10, [{
            "category": "missing_unsubscribe",
            "severity": "high",
            "detail": "No unsubscribe/opt-out link detected in a long email (+10 risk). Required by CAN-SPAM/GDPR.",
        }]

    return 0, []


def check_image_ratio(text):
    """Check image-to-text hints in HTML content."""
    img_tags = re.findall(r"<img\b", text, re.IGNORECASE)
    img_count = len(img_tags)

    if img_count == 0:
        return 0, []

    text_clean = re.sub(r"<[^>]+>", " ", text)
    text_clean = re.sub(r"\s+", " ", text_clean).strip()
    text_length = len(text_clean)

    # If heavy images relative to text content
    if img_count >= 3 and text_length < 200:
        return 5, [{
            "category": "image_heavy",
            "severity": "medium",
            "detail": f"{img_count} images with only {text_length} chars of text (+5 risk). Image-heavy emails risk spam filtering.",
        }]
    elif img_count >= 5:
        return 5, [{
            "category": "image_heavy",
            "severity": "low",
            "detail": f"{img_count} images detected (+5 risk). Ensure adequate text content accompanies images.",
        }]

    return 0, []


def classify_risk(score):
    """Classify overall risk score into a named level."""
    if score <= 10:
        return "low"
    elif score <= 30:
        return "medium"
    elif score <= 60:
        return "high"
    else:
        return "critical"


def generate_recommendations(findings, risk_score):
    """Generate actionable recommendations based on findings."""
    recommendations = []
    categories_found = {f["category"] for f in findings}

    if "spam_trigger" in categories_found:
        recommendations.append(
            "Remove or replace spam trigger words. Use conversational "
            "language that delivers value instead of hard-sell phrases."
        )

    if "excessive_punctuation" in categories_found:
        recommendations.append(
            "Reduce exclamation and question mark repetition. "
            "A single punctuation mark is sufficient."
        )

    if "all_caps" in categories_found:
        recommendations.append(
            "Convert ALL CAPS text to sentence case. "
            "Caps-heavy emails are a top spam filter signal."
        )

    if "link_density" in categories_found:
        recommendations.append(
            "Reduce the number of links. Focus on 1-2 primary CTAs "
            "rather than many competing links."
        )

    if "suspicious_phrase" in categories_found:
        recommendations.append(
            "Remove suspicious phrases that are strongly associated "
            "with phishing and scam emails."
        )

    if "missing_unsubscribe" in categories_found:
        recommendations.append(
            "Add an unsubscribe link. It is legally required (CAN-SPAM, GDPR) "
            "and improves sender reputation."
        )

    if "image_heavy" in categories_found:
        recommendations.append(
            "Add more text content alongside images. A healthy text-to-image "
            "ratio improves deliverability."
        )

    if risk_score <= 10:
        recommendations.append(
            "Email looks clean. Continue following best practices for "
            "consistent inbox placement."
        )

    return recommendations


def analyze_email(content, subject=None):
    """Run the full spam risk analysis on email content."""
    # Combine subject and body for unified scanning
    full_text = content
    if subject:
        full_text = subject + " " + content

    all_findings = []
    total_penalty = 0

    # Run all checks
    checks = [
        scan_spam_triggers(full_text),
        check_punctuation(full_text),
        check_caps_ratio(full_text),
        check_link_density(content),
        check_suspicious_phrases(full_text),
        check_unsubscribe(content),
        check_image_ratio(content),
    ]

    for penalty, findings in checks:
        total_penalty += penalty
        all_findings.extend(findings)

    # Clamp score to 0-100
    risk_score = max(0, min(100, total_penalty))
    risk_level = classify_risk(risk_score)
    recommendations = generate_recommendations(all_findings, risk_score)

    result = {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "findings": all_findings,
        "findings_count": len(all_findings),
        "recommendations": recommendations,
    }

    if subject:
        result["subject_analyzed"] = subject

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Check email content for spam risk indicators"
    )
    parser.add_argument(
        "--content", default=None,
        help="Email body text as a string",
    )
    parser.add_argument(
        "--file", default=None,
        help="Path to file containing the email body",
    )
    parser.add_argument(
        "--subject", default=None,
        help="Subject line for combined analysis (optional)",
    )
    args = parser.parse_args()

    if not args.content and not args.file:
        json.dump(
            {"error": "Provide either --content or --file with the email body"},
            sys.stdout, indent=2,
        )
        print()
        sys.exit(1)

    # Resolve content
    content = args.content or ""
    if args.file:
        path = Path(args.file)
        if not path.exists():
            json.dump({"error": f"File not found: {args.file}"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            json.dump({"error": f"Could not read file: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(1)

    if not content.strip():
        json.dump({"error": "Email content is empty"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    result = analyze_email(content, subject=args.subject)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
