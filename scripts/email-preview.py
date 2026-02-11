#!/usr/bin/env python3
"""Analyze email content for deliverability signals and display issues."""

import argparse
import json
import re
import sys
from pathlib import Path

# Spam trigger words organized by severity
SPAM_TRIGGERS = {
    "high": [
        "act now", "apply now", "buy now", "call now", "click here",
        "click below", "do it today", "don't delete", "don't hesitate",
        "exclusive deal", "expire", "free access", "free gift",
        "free offer", "get it now", "limited time", "no cost",
        "no obligation", "offer expires", "once in a lifetime",
        "order now", "please read", "special promotion", "this isn't spam",
        "urgent", "what are you waiting for", "while supplies last",
        "winner", "you have been selected", "you're a winner",
        "congratulations", "100% free", "risk free", "no risk",
    ],
    "medium": [
        "affordable", "bargain", "billion", "bonus", "cash",
        "cheap", "compare", "credit", "discount", "double your",
        "earn", "extra cash", "fantastic deal", "fortune", "free",
        "guarantee", "incredible deal", "insurance", "investment",
        "loan", "lowest price", "luxury", "million", "money",
        "obligation", "offer", "opportunity", "opt in", "prize",
        "profit", "promise", "purchase", "quote", "rates",
        "refinance", "save big", "sale", "satisfaction", "subscribe",
        "trial", "unlimited", "unsecured", "wealth",
    ],
    "low": [
        "as seen on", "best price", "buy", "check", "clearance",
        "deal", "dear friend", "direct", "giving away", "great",
        "hello", "information", "learn", "message", "new",
        "newsletter", "now", "only", "open", "opt-in",
        "order", "performance", "please", "remove", "report",
        "request", "sample", "save", "solution", "special",
        "success", "today", "top", "visit",
    ],
}

# Email client subject line display limits (approximate character counts)
CLIENT_LIMITS = {
    "gmail_desktop": {"subject": 70, "preview": 90},
    "gmail_mobile": {"subject": 40, "preview": 90},
    "outlook_desktop": {"subject": 73, "preview": 40},
    "outlook_mobile": {"subject": 40, "preview": 40},
    "apple_mail_desktop": {"subject": 78, "preview": 140},
    "apple_mail_mobile": {"subject": 35, "preview": 90},
    "yahoo": {"subject": 46, "preview": 110},
}

GMAIL_CLIP_LIMIT_KB = 102


def detect_spam_words(text):
    """Scan text for spam trigger words, return findings by severity."""
    text_lower = text.lower()
    found = {"high": [], "medium": [], "low": []}
    for severity, words in SPAM_TRIGGERS.items():
        for word in words:
            if word in text_lower:
                found[severity].append(word)
    return found


def analyze_subject_line(subject):
    """Analyze subject line against client display limits."""
    if not subject:
        return {"error": "No subject line provided"}

    char_count = len(subject)
    truncation = {}
    for client, limits in CLIENT_LIMITS.items():
        limit = limits["subject"]
        truncation[client] = {
            "limit": limit,
            "fits": char_count <= limit,
            "display": subject[:limit] + ("..." if char_count > limit else ""),
        }

    warnings = []
    if char_count > 60:
        warnings.append("Subject may be truncated on most mobile clients")
    if char_count < 10:
        warnings.append("Subject line is very short; may lack context")
    if subject.upper() == subject and len(subject) > 3:
        warnings.append("ALL CAPS subject lines often trigger spam filters")
    if re.search(r"[!]{2,}", subject):
        warnings.append("Multiple exclamation marks can trigger spam filters")
    if re.match(r"^re:|^fw:", subject, re.IGNORECASE):
        warnings.append("Fake Re:/Fw: prefixes are a spam signal")

    return {
        "subject": subject,
        "character_count": char_count,
        "client_display": truncation,
        "warnings": warnings,
    }


def analyze_preview_text(preview):
    """Analyze preview/preheader text."""
    if not preview:
        return {"warning": "No preview text provided; email clients will pull from body"}

    char_count = len(preview)
    analysis = {
        "preview_text": preview,
        "character_count": char_count,
        "recommended_length": "40-130 characters",
    }
    if char_count < 40:
        analysis["warning"] = "Preview text is short; consider expanding for more context"
    elif char_count > 130:
        analysis["warning"] = "Preview text may be cut off in some clients"
    return analysis


def analyze_body(body):
    """Analyze the email body for deliverability signals."""
    if not body:
        return {"warning": "No body content provided"}

    size_bytes = len(body.encode("utf-8"))
    size_kb = round(size_bytes / 1024, 1)

    # Link count
    links = re.findall(r'(?:href=["\']([^"\']+)["\'])|(?:https?://[^\s<>"]+)', body)
    link_count = len(links)

    # Image detection
    images = re.findall(r"<img\b", body, re.IGNORECASE)
    image_count = len(images)

    # Text extraction (strip HTML tags)
    text_only = re.sub(r"<[^>]+>", " ", body)
    text_only = re.sub(r"\s+", " ", text_only).strip()
    text_length = len(text_only)

    # Text-to-image ratio
    if image_count > 0 and text_length > 0:
        text_image_ratio = f"{round(text_length / max(image_count, 1))}:1 (chars per image)"
    elif image_count == 0:
        text_image_ratio = "No images detected"
    else:
        text_image_ratio = "Image-only email (high spam risk)"

    # CTA detection
    cta_patterns = [
        r"(?:click|tap|learn more|get started|sign up|subscribe|download|register|join|shop now|buy now|order|book|try)",
    ]
    cta_count = 0
    for pattern in cta_patterns:
        cta_count += len(re.findall(pattern, body, re.IGNORECASE))

    # Unsubscribe link check
    has_unsubscribe = bool(re.search(r"unsubscribe|opt.?out|manage.*preferences", body, re.IGNORECASE))

    warnings = []
    if size_kb > GMAIL_CLIP_LIMIT_KB:
        warnings.append(f"Email exceeds Gmail clipping limit ({GMAIL_CLIP_LIMIT_KB}KB). Current: {size_kb}KB")
    if size_kb > 80:
        warnings.append(f"Email is {size_kb}KB; approaching Gmail's {GMAIL_CLIP_LIMIT_KB}KB clipping threshold")
    if link_count > 20:
        warnings.append("High link count (>20) may trigger spam filters")
    if image_count > 0 and text_length < 100:
        warnings.append("Very low text-to-image ratio; may be flagged as spam")
    if not has_unsubscribe:
        warnings.append("No unsubscribe/opt-out link detected (required by CAN-SPAM/GDPR)")
    if cta_count == 0:
        warnings.append("No clear call-to-action detected")
    if cta_count > 5:
        warnings.append("Multiple CTAs detected; consider focusing on a primary action")

    return {
        "size_kb": size_kb,
        "gmail_clipping_risk": size_kb > GMAIL_CLIP_LIMIT_KB,
        "link_count": link_count,
        "image_count": image_count,
        "text_length_chars": text_length,
        "text_to_image_ratio": text_image_ratio,
        "cta_count": cta_count,
        "has_unsubscribe_link": has_unsubscribe,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze email content for deliverability and display")
    parser.add_argument("--subject", help="Email subject line")
    parser.add_argument("--preview", help="Preview/preheader text")
    parser.add_argument("--body", help="Email body (HTML or plain text)")
    parser.add_argument("--file", help="Path to an HTML email file")
    args = parser.parse_args()

    if not any([args.subject, args.preview, args.body, args.file]):
        parser.error("Provide at least one of: --subject, --preview, --body, --file")

    body = args.body or ""
    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(json.dumps({"error": f"File not found: {args.file}"}))
            sys.exit(1)
        body = path.read_text(encoding="utf-8")

    full_text = " ".join(filter(None, [args.subject, args.preview, body]))
    spam_analysis = detect_spam_words(full_text)
    total_spam_words = sum(len(v) for v in spam_analysis.values())

    result = {
        "subject_analysis": analyze_subject_line(args.subject) if args.subject else None,
        "preview_analysis": analyze_preview_text(args.preview),
        "body_analysis": analyze_body(body) if body else None,
        "spam_word_scan": {
            "total_triggers_found": total_spam_words,
            "high_severity": spam_analysis["high"],
            "medium_severity": spam_analysis["medium"],
            "low_severity": spam_analysis["low"],
            "risk_level": "high" if spam_analysis["high"] else ("medium" if spam_analysis["medium"] else "low"),
        },
        "inbox_placement_signals": {
            "spam_word_risk": "high" if total_spam_words > 5 else ("medium" if total_spam_words > 2 else "low"),
            "note": "Actual inbox placement depends on sender reputation, authentication (SPF/DKIM/DMARC), and engagement history.",
        },
    }

    # Remove None entries
    result = {k: v for k, v in result.items() if v is not None}

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
