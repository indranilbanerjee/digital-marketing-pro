#!/usr/bin/env python3
"""
content-scorer.py
=================
Multi-dimension content quality scoring using a standardized rubric.

Evaluates marketing content across readability, SEO signals, structure,
CTA quality, and spam/filler detection. Returns an overall quality score
(0-100) with weighted dimension breakdown and actionable recommendations.

Dependencies: textstat, nltk, json, re, sys, argparse, pathlib

Usage:
    python content-scorer.py --text "Your content..." --type blog --keyword "AI tools"
    python content-scorer.py --file article.md --type landing_page --keyword "project management"
    python content-scorer.py --file email.txt --type email

Content Types:  blog | email | ad | landing_page | social
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------
try:
    import textstat
except ImportError:
    print(json.dumps({
        "fallback": True,
        "error": "textstat_not_installed",
        "message": "textstat not installed. Content scoring requires: pip install textstat",
        "overall_score": None,
        "recommendation": "Install textstat for automated content scoring, or evaluate manually using skills/context-engine/scoring-rubrics.md"
    }, indent=2))
    sys.exit(0)

try:
    import nltk
except ImportError:
    print(json.dumps({
        "fallback": True,
        "error": "nltk_not_installed",
        "message": "NLTK not installed. Content scoring requires: pip install nltk",
        "overall_score": None,
        "recommendation": "Install NLTK for automated content scoring, or evaluate manually using skills/context-engine/scoring-rubrics.md"
    }, indent=2))
    sys.exit(0)

for _res in ("punkt", "punkt_tab"):
    try:
        nltk.data.find(f"tokenizers/{_res}")
    except LookupError:
        nltk.download(_res, quiet=True)

from nltk.tokenize import sent_tokenize

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONTENT_TYPE_WEIGHTS = {
    "blog": {
        "readability": 0.20,
        "seo": 0.25,
        "structure": 0.20,
        "cta": 0.10,
        "spam_filler": 0.10,
        "length": 0.15,
    },
    "email": {
        "readability": 0.25,
        "seo": 0.05,
        "structure": 0.15,
        "cta": 0.30,
        "spam_filler": 0.15,
        "length": 0.10,
    },
    "ad": {
        "readability": 0.20,
        "seo": 0.10,
        "structure": 0.10,
        "cta": 0.35,
        "spam_filler": 0.15,
        "length": 0.10,
    },
    "landing_page": {
        "readability": 0.15,
        "seo": 0.25,
        "structure": 0.20,
        "cta": 0.25,
        "spam_filler": 0.05,
        "length": 0.10,
    },
    "social": {
        "readability": 0.25,
        "seo": 0.05,
        "structure": 0.10,
        "cta": 0.25,
        "spam_filler": 0.20,
        "length": 0.15,
    },
}

IDEAL_WORD_COUNTS = {
    "blog": (800, 2500),
    "email": (50, 500),
    "ad": (15, 150),
    "landing_page": (300, 1500),
    "social": (10, 280),
}

# Spam / filler words and phrases
SPAM_WORDS = {
    "act now", "buy now", "limited time", "once in a lifetime", "risk-free",
    "no obligation", "free", "100% free", "click here", "click below",
    "congratulations", "winner", "you've been selected", "double your",
    "earn extra cash", "make money", "$$", "!!!",
    "no questions asked", "guaranteed", "no catch", "instant",
    "apply now", "order now",
}

FILLER_WORDS = {
    "very", "really", "just", "actually", "basically", "honestly",
    "literally", "simply", "quite", "rather", "somewhat", "pretty",
    "stuff", "things", "thing", "kind of", "sort of", "a lot",
    "in order to", "due to the fact", "at the end of the day",
    "it goes without saying", "needless to say", "as a matter of fact",
    "for all intents and purposes", "in terms of",
}

# CTA patterns
CTA_PATTERNS = [
    r"\b(sign up|signup)\b",
    r"\b(get started|start now|start today)\b",
    r"\b(learn more|read more|find out more)\b",
    r"\b(download|download now|get your copy)\b",
    r"\b(subscribe|join now|join us|join today)\b",
    r"\b(buy now|shop now|order now|purchase)\b",
    r"\b(try (it )?free|free trial|start free)\b",
    r"\b(book (a )?demo|schedule (a )?call|request (a )?demo)\b",
    r"\b(contact us|reach out|get in touch)\b",
    r"\b(claim (your )?offer|grab (your )?spot)\b",
    r"\b(register|enroll|apply)\b",
    r"\b(explore|discover)\b",
]

CTA_STRONG_VERBS = {
    "sign up", "signup", "get started", "start now", "start today",
    "download", "subscribe", "join", "buy", "shop", "order", "purchase",
    "try", "book", "schedule", "request", "claim", "grab", "register",
    "enroll", "apply",
}

CTA_WEAK_VERBS = {
    "learn more", "read more", "find out", "explore", "discover",
    "contact", "reach out", "click here",
}

# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def _split_words(text: str) -> list[str]:
    """Extract alphabetic tokens from text."""
    return [w for w in re.findall(r"[a-zA-Z']+", text) if len(w) > 0]


def score_readability(text: str, content_type: str) -> dict:
    """Score readability 0-100 using Flesch Reading Ease as primary metric."""
    ease = textstat.flesch_reading_ease(text)
    grade = textstat.flesch_kincaid_grade(text)

    # Target reading ease ranges per content type
    targets = {
        "blog": (50, 70),
        "email": (55, 75),
        "ad": (60, 80),
        "landing_page": (50, 70),
        "social": (65, 85),
    }
    lo, hi = targets.get(content_type, (50, 70))
    mid = (lo + hi) / 2

    # Score: 100 if within range, decays linearly outside
    if lo <= ease <= hi:
        score = 100.0
    elif ease < lo:
        score = max(0, 100 - (lo - ease) * 2.5)
    else:
        score = max(0, 100 - (ease - hi) * 2.0)

    recommendations = []
    if ease < lo:
        recommendations.append(
            f"Content is harder to read than ideal for {content_type} "
            f"(Reading Ease: {ease:.1f}, target: {lo}-{hi}). "
            "Simplify sentences and use shorter words."
        )
    elif ease > hi:
        recommendations.append(
            f"Content may be too simplistic for {content_type} "
            f"(Reading Ease: {ease:.1f}, target: {lo}-{hi}). "
            "Consider adding more substantive detail."
        )

    return {
        "score": round(min(max(score, 0), 100), 2),
        "flesch_reading_ease": round(ease, 2),
        "flesch_kincaid_grade": round(grade, 2),
        "target_ease_range": [lo, hi],
        "recommendations": recommendations,
    }


def score_seo(text: str, keyword: str | None, content_type: str) -> dict:
    """Score SEO signals 0-100."""
    score = 0.0
    max_possible = 0.0
    details = {}
    recommendations = []

    text_lower = text.lower()
    words = _split_words(text)
    word_count = len(words)

    # --- Keyword checks (50 points possible) ---
    if keyword:
        kw_lower = keyword.lower()
        max_possible += 50

        # Keyword in first 100 words
        first_100 = " ".join(words[:100]).lower()
        kw_in_first_100 = kw_lower in first_100
        if kw_in_first_100:
            score += 15
        else:
            recommendations.append(
                f"Primary keyword '{keyword}' not found in the first 100 words. "
                "Move it earlier in the content for better SEO."
            )
        details["keyword_in_first_100_words"] = kw_in_first_100

        # Keyword density (ideal: 1-3%)
        kw_words = kw_lower.split()
        if len(kw_words) == 1:
            kw_count = text_lower.split().count(kw_lower)
        else:
            kw_count = text_lower.count(kw_lower)
        density = (kw_count / max(word_count, 1)) * 100 if word_count else 0
        details["keyword_density_pct"] = round(density, 2)
        details["keyword_count"] = kw_count

        if 0.8 <= density <= 3.0:
            score += 20
        elif 0.3 <= density < 0.8:
            score += 10
            recommendations.append(
                f"Keyword density ({density:.1f}%) is slightly low. "
                "Aim for 1-3% for optimal SEO."
            )
        elif density > 3.0:
            score += 5
            recommendations.append(
                f"Keyword density ({density:.1f}%) is too high. "
                "This may be flagged as keyword stuffing. Aim for 1-3%."
            )
        else:
            recommendations.append(
                f"Keyword '{keyword}' barely appears (density: {density:.1f}%). "
                "Use it more naturally throughout the content."
            )

        # Keyword in headings
        headings = re.findall(r"^#+\s+(.+)$", text, re.MULTILINE)
        headings += re.findall(r"<h[1-6][^>]*>(.+?)</h[1-6]>", text, re.IGNORECASE)
        kw_in_heading = any(kw_lower in h.lower() for h in headings)
        details["keyword_in_heading"] = kw_in_heading
        if kw_in_heading:
            score += 15
        elif headings:
            recommendations.append(
                f"Primary keyword '{keyword}' not found in any heading. "
                "Include it in at least one H2 or H3."
            )
    else:
        details["keyword"] = "No keyword provided — SEO keyword checks skipped."

    # --- Heading structure (25 points) ---
    max_possible += 25
    heading_md = re.findall(r"^(#{1,6})\s+", text, re.MULTILINE)
    heading_html = re.findall(r"<h([1-6])", text, re.IGNORECASE)
    heading_count = len(heading_md) + len(heading_html)
    details["heading_count"] = heading_count

    if content_type in ("blog", "landing_page"):
        if heading_count >= 3:
            score += 25
        elif heading_count >= 1:
            score += 15
            recommendations.append(
                f"Only {heading_count} heading(s) found. Use more subheadings "
                "(H2, H3) to improve scannability and SEO."
            )
        else:
            recommendations.append(
                "No headings found. Add H2/H3 subheadings for structure and SEO."
            )
    else:
        # For emails, ads, social: headings less critical
        score += 20 if heading_count >= 1 else 15

    # --- Meta description length proxy (25 points) ---
    # Check if there's a meta description in front-matter or first paragraph
    max_possible += 25
    meta_match = re.search(r"meta[_-]?description[:\s]+[\"']?(.+?)[\"']?\s*$",
                           text, re.MULTILINE | re.IGNORECASE)
    first_para = text.strip().split("\n\n")[0] if text.strip() else ""
    first_para_len = len(first_para)

    if meta_match:
        meta_len = len(meta_match.group(1).strip())
        details["meta_description_length"] = meta_len
        if 120 <= meta_len <= 160:
            score += 25
        elif 80 <= meta_len <= 200:
            score += 15
            recommendations.append(
                f"Meta description is {meta_len} chars. "
                "Ideal is 120-160 characters."
            )
        else:
            score += 5
            recommendations.append(
                f"Meta description is {meta_len} chars — "
                "outside the recommended 120-160 range."
            )
    else:
        details["meta_description"] = "Not found"
        if content_type in ("blog", "landing_page"):
            # Use first paragraph as proxy
            if 120 <= first_para_len <= 200:
                score += 15
                details["first_paragraph_length"] = first_para_len
            else:
                score += 5
                recommendations.append(
                    "No meta description found. Add one (120-160 chars) for "
                    "search engine snippets."
                )
        else:
            score += 20  # Less relevant for non-web content

    # Normalize to 0-100
    final_score = (score / max(max_possible, 1)) * 100 if max_possible else 50

    return {
        "score": round(min(max(final_score, 0), 100), 2),
        "details": details,
        "recommendations": recommendations,
    }


def score_structure(text: str, content_type: str) -> dict:
    """Score content structure 0-100 (paragraphs, headings, lists)."""
    score = 0.0
    recommendations = []

    # Paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    para_count = len(paragraphs)

    # Headings
    headings = re.findall(r"^#{1,6}\s+", text, re.MULTILINE)
    html_headings = re.findall(r"<h[1-6]", text, re.IGNORECASE)
    heading_count = len(headings) + len(html_headings)

    # Lists (markdown or HTML)
    md_list_items = re.findall(r"^[\s]*[-*+]\s+", text, re.MULTILINE)
    md_numbered_items = re.findall(r"^[\s]*\d+[.)]\s+", text, re.MULTILINE)
    html_list_items = re.findall(r"<li", text, re.IGNORECASE)
    list_item_count = len(md_list_items) + len(md_numbered_items) + len(html_list_items)

    # Bold/emphasis usage
    bold_count = len(re.findall(r"\*\*[^*]+\*\*", text))
    bold_count += len(re.findall(r"__[^_]+__", text))
    bold_count += len(re.findall(r"<strong>", text, re.IGNORECASE))
    bold_count += len(re.findall(r"<b>", text, re.IGNORECASE))

    details = {
        "paragraph_count": para_count,
        "heading_count": heading_count,
        "list_item_count": list_item_count,
        "bold_emphasis_count": bold_count,
    }

    # --- Scoring logic varies by content type ---
    if content_type == "blog":
        # Paragraphs: expect multiple, short-ish paragraphs
        if para_count >= 5:
            score += 25
        elif para_count >= 3:
            score += 15
        else:
            score += 5
            recommendations.append(
                "Blog has very few paragraphs. Break content into more "
                "paragraphs for easier scanning."
            )

        # Check for wall-of-text paragraphs
        long_paras = [p for p in paragraphs if len(_split_words(p)) > 100]
        if long_paras:
            score -= 5
            recommendations.append(
                f"{len(long_paras)} paragraph(s) exceed 100 words. "
                "Break these up for better readability."
            )

        # Headings
        if heading_count >= 3:
            score += 25
        elif heading_count >= 1:
            score += 15
            recommendations.append("Add more subheadings to improve scannability.")
        else:
            recommendations.append("No headings found. Add H2/H3 subheadings.")

        # Lists
        if list_item_count >= 3:
            score += 25
        elif list_item_count >= 1:
            score += 15
        else:
            score += 5
            recommendations.append(
                "Consider adding bullet points or numbered lists to "
                "highlight key information."
            )

        # Emphasis
        if bold_count >= 2:
            score += 25
        elif bold_count >= 1:
            score += 15
        else:
            score += 5
            recommendations.append(
                "Use bold text to highlight key phrases and improve scannability."
            )

    elif content_type == "email":
        if para_count >= 2:
            score += 30
        else:
            score += 15
        if list_item_count >= 1:
            score += 25
        else:
            score += 15
        # Emails don't need many headings
        score += 25
        if bold_count >= 1:
            score += 20
        else:
            score += 10
            recommendations.append("Bold key phrases to draw the reader's eye.")

    elif content_type == "ad":
        # Ads are short — less structure needed
        if para_count >= 1:
            score += 30
        score += 30  # Headings/lists less relevant
        if bold_count >= 1:
            score += 20
        score += 20

    elif content_type == "landing_page":
        if para_count >= 3:
            score += 20
        else:
            score += 10
            recommendations.append("Add more content sections to the landing page.")
        if heading_count >= 3:
            score += 25
        elif heading_count >= 1:
            score += 15
            recommendations.append(
                "Landing pages benefit from multiple headings. Add more H2s."
            )
        else:
            recommendations.append("Add headings to structure the landing page.")
        if list_item_count >= 2:
            score += 25
        else:
            score += 10
            recommendations.append(
                "Add feature lists or benefit bullets to the landing page."
            )
        if bold_count >= 2:
            score += 30
        elif bold_count >= 1:
            score += 20
        else:
            score += 5
            recommendations.append("Use bold for key value propositions.")

    elif content_type == "social":
        if para_count >= 1:
            score += 40
        score += 30  # Structure is minimal for social
        if list_item_count >= 1 or bold_count >= 1:
            score += 30
        else:
            score += 20

    return {
        "score": round(min(max(score, 0), 100), 2),
        "details": details,
        "recommendations": recommendations,
    }


def score_cta(text: str, content_type: str) -> dict:
    """Score CTA (Call to Action) quality 0-100."""
    text_lower = text.lower()
    recommendations = []

    # Find all CTAs
    ctas_found = []
    for pattern in CTA_PATTERNS:
        matches = re.finditer(pattern, text_lower)
        for m in matches:
            ctas_found.append(m.group(0))
    ctas_found = list(set(ctas_found))  # deduplicate

    cta_count = len(ctas_found)

    # Classify CTAs as strong or weak
    strong = [c for c in ctas_found
              if any(sv in c for sv in CTA_STRONG_VERBS)]
    weak = [c for c in ctas_found if c not in strong]

    details = {
        "ctas_found": ctas_found,
        "cta_count": cta_count,
        "strong_ctas": strong,
        "weak_ctas": weak,
    }

    # --- Scoring ---
    score = 0.0

    # Ideal CTA count depends on content type
    ideal_cta = {
        "blog": (1, 3),
        "email": (1, 2),
        "ad": (1, 2),
        "landing_page": (2, 5),
        "social": (1, 1),
    }
    lo, hi = ideal_cta.get(content_type, (1, 3))

    if cta_count == 0:
        score = 0
        recommendations.append(
            "No call to action found. Every piece of marketing content "
            "should include at least one clear CTA."
        )
    elif lo <= cta_count <= hi:
        score += 50
    elif cta_count < lo:
        score += 25
        recommendations.append(
            f"Only {cta_count} CTA found. Consider adding "
            f"{'another' if cta_count == 1 else 'more'} for a {content_type}."
        )
    else:
        score += 30
        recommendations.append(
            f"{cta_count} CTAs detected — may be too many for {content_type}. "
            f"Ideal is {lo}-{hi}. Too many CTAs can dilute impact."
        )

    # Strong vs weak
    if strong:
        score += 30
    elif weak:
        score += 15
        recommendations.append(
            "CTAs use weak verbs (e.g., 'learn more'). "
            "Consider stronger action verbs like 'Get started', 'Download', 'Sign up'."
        )

    # CTA placement: check if CTA appears near end of content
    if ctas_found:
        # Check last 20% of text for a CTA
        cutoff = int(len(text_lower) * 0.8)
        last_portion = text_lower[cutoff:]
        cta_near_end = any(c in last_portion for c in ctas_found)
        details["cta_near_end"] = cta_near_end
        if cta_near_end:
            score += 20
        else:
            score += 5
            recommendations.append(
                "No CTA found near the end of the content. "
                "Place your primary CTA where readers finish reading."
            )
    else:
        details["cta_near_end"] = False

    return {
        "score": round(min(max(score, 0), 100), 2),
        "details": details,
        "recommendations": recommendations,
    }


def score_spam_filler(text: str) -> dict:
    """Score content for spam/filler word usage. Higher = cleaner."""
    text_lower = text.lower()
    words = _split_words(text)
    word_count = len(words)
    recommendations = []

    # Spam word detection
    spam_found = []
    for phrase in SPAM_WORDS:
        if phrase in text_lower:
            spam_found.append(phrase)
    # Check for excessive exclamation marks
    excl_count = text.count("!")
    excl_sequences = len(re.findall(r"!{2,}", text))

    # Filler word detection
    filler_found = []
    for phrase in FILLER_WORDS:
        if " " in phrase:
            count = text_lower.count(phrase)
            if count > 0:
                filler_found.append({"phrase": phrase, "count": count})
        else:
            tokens_lower = [w.lower() for w in words]
            count = tokens_lower.count(phrase)
            if count > 0:
                filler_found.append({"phrase": phrase, "count": count})

    total_filler_count = sum(f["count"] for f in filler_found)
    filler_pct = round((total_filler_count / max(word_count, 1)) * 100, 2)

    # ALL CAPS words (shouting)
    caps_words = [w for w in text.split() if w.isupper() and len(w) > 2
                  and w.isalpha()]

    details = {
        "spam_phrases_found": spam_found,
        "spam_count": len(spam_found),
        "filler_words_found": sorted(filler_found, key=lambda x: x["count"],
                                     reverse=True)[:10],
        "filler_word_pct": filler_pct,
        "exclamation_marks": excl_count,
        "consecutive_exclamation_sequences": excl_sequences,
        "all_caps_words": caps_words[:10],
        "all_caps_count": len(caps_words),
    }

    # --- Scoring (start at 100, subtract) ---
    score = 100.0

    # Spam penalties
    score -= len(spam_found) * 8
    if spam_found:
        recommendations.append(
            f"Spam trigger words detected: {', '.join(spam_found[:5])}. "
            "These can hurt email deliverability and ad approval."
        )

    # Filler penalties
    if filler_pct > 8:
        score -= 20
        recommendations.append(
            f"High filler word usage ({filler_pct}%). "
            "Remove unnecessary qualifiers like 'very', 'really', 'just'."
        )
    elif filler_pct > 4:
        score -= 10
        recommendations.append(
            f"Moderate filler word usage ({filler_pct}%). "
            "Consider tightening the prose."
        )

    # Exclamation penalties
    if excl_sequences > 0:
        score -= excl_sequences * 5
        recommendations.append(
            "Multiple consecutive exclamation marks detected. "
            "Use a single exclamation mark at most."
        )
    if excl_count > 3:
        score -= (excl_count - 3) * 2
        recommendations.append(
            f"{excl_count} exclamation marks found. "
            "Excessive exclamation reduces credibility."
        )

    # ALL CAPS penalties
    if len(caps_words) > 2:
        score -= len(caps_words) * 3
        recommendations.append(
            f"{len(caps_words)} ALL CAPS words found. "
            "Avoid shouting — it looks spammy."
        )

    if not recommendations:
        recommendations.append("Content is clean — no significant spam or filler detected.")

    return {
        "score": round(min(max(score, 0), 100), 2),
        "details": details,
        "recommendations": recommendations,
    }


def score_length(text: str, content_type: str) -> dict:
    """Score content length appropriateness 0-100."""
    words = _split_words(text)
    word_count = len(words)
    recommendations = []

    lo, hi = IDEAL_WORD_COUNTS.get(content_type, (100, 1500))

    details = {
        "word_count": word_count,
        "ideal_range": [lo, hi],
    }

    if lo <= word_count <= hi:
        score = 100.0
    elif word_count < lo:
        ratio = word_count / max(lo, 1)
        score = max(ratio * 100, 0)
        recommendations.append(
            f"Content is too short ({word_count} words) for {content_type}. "
            f"Ideal range is {lo}-{hi} words."
        )
    else:
        # Over the max — gentle penalty
        overage_ratio = (word_count - hi) / max(hi, 1)
        score = max(100 - overage_ratio * 80, 20)
        recommendations.append(
            f"Content is long ({word_count} words) for {content_type}. "
            f"Ideal range is {lo}-{hi} words. Consider trimming."
        )

    return {
        "score": round(min(max(score, 0), 100), 2),
        "details": details,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Main scoring pipeline
# ---------------------------------------------------------------------------

def score_content(text: str, content_type: str, keyword: str | None) -> dict:
    """Run the full multi-dimension scoring pipeline."""
    if not text or not text.strip():
        return {
            "error": "Empty text provided. Please supply content to analyze.",
            "overall_score": 0,
        }

    if content_type not in CONTENT_TYPE_WEIGHTS:
        return {
            "error": f"Unknown content type: '{content_type}'",
            "valid_types": list(CONTENT_TYPE_WEIGHTS.keys()),
        }

    weights = CONTENT_TYPE_WEIGHTS[content_type]

    # Run each dimension scorer
    readability = score_readability(text, content_type)
    seo = score_seo(text, keyword, content_type)
    structure = score_structure(text, content_type)
    cta = score_cta(text, content_type)
    spam_filler = score_spam_filler(text)
    length = score_length(text, content_type)

    dimensions = {
        "readability": readability,
        "seo": seo,
        "structure": structure,
        "cta": cta,
        "spam_filler": spam_filler,
        "length": length,
    }

    # Calculate weighted overall score
    overall = 0.0
    for dim_name, dim_result in dimensions.items():
        w = weights.get(dim_name, 0)
        overall += dim_result["score"] * w

    overall = round(min(max(overall, 0), 100), 2)

    # Collect all recommendations sorted by dimension weight (most impactful first)
    all_recommendations = []
    for dim_name in sorted(weights, key=weights.get, reverse=True):
        dim = dimensions[dim_name]
        for rec in dim.get("recommendations", []):
            all_recommendations.append({
                "dimension": dim_name,
                "weight": weights[dim_name],
                "recommendation": rec,
            })

    # Summary statistics
    sentences = sent_tokenize(text)
    words = _split_words(text)
    stats = {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "avg_sentence_length": (
            round(len(words) / len(sentences), 1) if sentences else 0
        ),
        "content_type": content_type,
        "keyword": keyword or "N/A",
    }

    return {
        "overall_score": overall,
        "interpretation": _interpret_score(overall),
        "weights_used": weights,
        "dimension_scores": {
            name: {
                "score": dim["score"],
                "weight": weights.get(name, 0),
                "weighted_contribution": round(
                    dim["score"] * weights.get(name, 0), 2
                ),
            }
            for name, dim in dimensions.items()
        },
        "dimension_details": dimensions,
        "top_recommendations": all_recommendations[:10],
        "stats": stats,
    }


def _interpret_score(score: float) -> str:
    """Return a human-readable interpretation of the overall score."""
    if score >= 90:
        return "Excellent — publish-ready content"
    elif score >= 75:
        return "Good — minor improvements recommended"
    elif score >= 60:
        return "Fair — several areas need attention"
    elif score >= 40:
        return "Poor — significant revision needed"
    else:
        return "Critical — major rewrite recommended"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Multi-dimension content quality scoring.",
        epilog=(
            "Content types: blog, email, ad, landing_page, social\n\n"
            "Example:\n"
            '  python content-scorer.py --file post.md --type blog --keyword "AI tools"'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        "--type", dest="content_type", required=True,
        choices=list(CONTENT_TYPE_WEIGHTS.keys()),
        help="Type of marketing content.",
    )
    parser.add_argument(
        "--keyword", type=str, default=None,
        help="Primary SEO keyword to check for (optional).",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Resolve input text
    if args.text:
        text = args.text
    else:
        file_path = Path(args.file)
        if not file_path.exists():
            print(json.dumps({
                "error": f"File not found: {file_path}",
            }, indent=2))
            sys.exit(1)
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception as exc:
            print(json.dumps({
                "error": f"Could not read file: {exc}",
            }, indent=2))
            sys.exit(1)

    # Score
    result = score_content(text, args.content_type, args.keyword)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
