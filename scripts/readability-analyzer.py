#!/usr/bin/env python3
"""
readability-analyzer.py
=======================
Multi-metric readability analysis for marketing content.

Computes Flesch-Kincaid Grade Level, Flesch Reading Ease, Gunning Fog Index,
average sentence/word length, complex-word percentage, and provides
target-audience comparison with concrete improvement suggestions.

Dependencies: textstat, sys, argparse, json

Usage:
    python readability-analyzer.py --text "Your marketing copy here."
    python readability-analyzer.py --file draft.txt --target b2c_general
    python readability-analyzer.py --file article.md --target b2b_technical
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import textstat
except ImportError:
    print(json.dumps({
        "error": "Missing dependency: textstat. Install with: pip install textstat"
    }))
    sys.exit(1)

# ---------------------------------------------------------------------------
# Audience profiles — ideal readability ranges
# ---------------------------------------------------------------------------
AUDIENCE_PROFILES = {
    "b2c_general": {
        "label": "B2C General Consumer",
        "grade_level_range": (5, 8),
        "reading_ease_range": (60, 80),
        "fog_range": (6, 10),
        "avg_sentence_length_range": (10, 18),
        "complex_word_pct_range": (0, 12),
        "description": (
            "Everyday consumers. Content should be conversational, easy to "
            "scan, and free of jargon. Aim for a 6th-8th grade reading level."
        ),
    },
    "b2b_professional": {
        "label": "B2B Professional",
        "grade_level_range": (8, 12),
        "reading_ease_range": (45, 65),
        "fog_range": (10, 14),
        "avg_sentence_length_range": (14, 22),
        "complex_word_pct_range": (8, 20),
        "description": (
            "Business decision-makers. Content can use industry terms but "
            "should remain clear and scannable. Aim for 8th-12th grade level."
        ),
    },
    "b2b_technical": {
        "label": "B2B Technical",
        "grade_level_range": (10, 16),
        "reading_ease_range": (30, 55),
        "fog_range": (12, 18),
        "avg_sentence_length_range": (16, 25),
        "complex_word_pct_range": (12, 30),
        "description": (
            "Engineers, developers, technical buyers. Precision matters more "
            "than simplicity, but unnecessary complexity should still be avoided."
        ),
    },
    "children": {
        "label": "Children (ages 8-12)",
        "grade_level_range": (2, 5),
        "reading_ease_range": (80, 100),
        "fog_range": (3, 7),
        "avg_sentence_length_range": (6, 12),
        "complex_word_pct_range": (0, 5),
        "description": (
            "Young readers. Use short sentences, common words, and an "
            "energetic tone. Aim for 2nd-5th grade reading level."
        ),
    },
    "academic": {
        "label": "Academic / Research",
        "grade_level_range": (12, 20),
        "reading_ease_range": (15, 45),
        "fog_range": (14, 20),
        "avg_sentence_length_range": (18, 30),
        "complex_word_pct_range": (15, 35),
        "description": (
            "Researchers and scholars. Formal register is expected, but "
            "clarity is still valued. Avoid unnecessary verbosity."
        ),
    },
}

# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def _count_syllables(word: str) -> int:
    """Estimate syllable count for a single word using a simple heuristic."""
    word = word.lower().strip()
    if not word:
        return 0
    # Use textstat's built-in if available
    try:
        return textstat.syllable_count(word)
    except Exception:
        pass
    # Fallback heuristic
    count = 0
    vowels = "aeiouy"
    if word[0] in vowels:
        count += 1
    for i in range(1, len(word)):
        if word[i] in vowels and word[i - 1] not in vowels:
            count += 1
    if word.endswith("e"):
        count -= 1
    return max(count, 1)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    # Use a simple regex that handles common abbreviations reasonably
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s for s in sentences if s.strip()]


def _split_words(text: str) -> list[str]:
    """Extract words (alpha tokens) from text."""
    return [w for w in re.findall(r"[a-zA-Z']+", text) if len(w) > 0]


def compute_metrics(text: str) -> dict:
    """Compute all readability metrics for the given text."""
    if not text or not text.strip():
        return {"error": "Empty text provided. Please supply content to analyze."}

    # Core textstat metrics
    fk_grade = textstat.flesch_kincaid_grade(text)
    reading_ease = textstat.flesch_reading_ease(text)
    gunning_fog = textstat.gunning_fog(text)

    # Manual calculations for detail
    sentences = _split_sentences(text)
    words = _split_words(text)

    sentence_count = max(len(sentences), 1)
    word_count = len(words)

    avg_sentence_length = round(word_count / sentence_count, 2) if sentence_count else 0

    # Average word length in characters
    avg_word_length = (
        round(sum(len(w) for w in words) / word_count, 2) if word_count else 0
    )

    # Complex words (3+ syllables)
    complex_words = [w for w in words if _count_syllables(w) >= 3]
    complex_word_pct = (
        round(len(complex_words) / word_count * 100, 2) if word_count else 0
    )

    # Identify longest sentences (potential candidates for splitting)
    sentence_lengths = []
    for s in sentences:
        s_words = _split_words(s)
        sentence_lengths.append({
            "sentence": s[:120] + ("..." if len(s) > 120 else ""),
            "word_count": len(s_words),
        })
    sentence_lengths.sort(key=lambda x: x["word_count"], reverse=True)

    # Identify most complex words
    word_syllables = {}
    for w in words:
        wl = w.lower()
        if wl not in word_syllables:
            word_syllables[wl] = _count_syllables(w)
    top_complex = sorted(
        [(w, s) for w, s in word_syllables.items() if s >= 3],
        key=lambda x: x[1],
        reverse=True,
    )[:15]

    return {
        "flesch_kincaid_grade": round(fk_grade, 2),
        "flesch_reading_ease": round(reading_ease, 2),
        "gunning_fog_index": round(gunning_fog, 2),
        "avg_sentence_length": avg_sentence_length,
        "avg_word_length_chars": avg_word_length,
        "complex_word_pct": complex_word_pct,
        "stats": {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "complex_word_count": len(complex_words),
        },
        "longest_sentences": sentence_lengths[:5],
        "most_complex_words": [
            {"word": w, "syllables": s} for w, s in top_complex
        ],
    }


def recommend_audience(metrics: dict) -> dict:
    """Based on the metrics, recommend which audience the content suits."""
    grade = metrics.get("flesch_kincaid_grade", 8)
    best_fit = None
    best_distance = float("inf")

    fits = {}
    for key, profile in AUDIENCE_PROFILES.items():
        lo, hi = profile["grade_level_range"]
        mid = (lo + hi) / 2
        distance = abs(grade - mid)
        within = lo <= grade <= hi
        fits[key] = {
            "label": profile["label"],
            "grade_range": f"{lo}-{hi}",
            "within_range": within,
            "distance_from_midpoint": round(distance, 2),
        }
        if distance < best_distance:
            best_distance = distance
            best_fit = key

    return {
        "best_fit_audience": best_fit,
        "best_fit_label": AUDIENCE_PROFILES[best_fit]["label"],
        "audience_breakdown": fits,
    }


def compare_to_target(metrics: dict, target: str) -> dict:
    """Compare metrics against a specific target audience profile."""
    if target not in AUDIENCE_PROFILES:
        return {
            "error": f"Unknown target audience: '{target}'",
            "valid_targets": list(AUDIENCE_PROFILES.keys()),
        }

    profile = AUDIENCE_PROFILES[target]
    comparisons = {}

    mapping = [
        ("flesch_kincaid_grade", "grade_level_range", "Grade Level", False),
        ("flesch_reading_ease", "reading_ease_range", "Reading Ease", True),
        ("gunning_fog_index", "fog_range", "Gunning Fog", False),
        ("avg_sentence_length", "avg_sentence_length_range", "Avg Sentence Length", False),
        ("complex_word_pct", "complex_word_pct_range", "Complex Word %", False),
    ]

    for metric_key, range_key, label, higher_is_easier in mapping:
        val = metrics.get(metric_key, 0)
        lo, hi = profile[range_key]
        if val < lo:
            status = "below_range"
        elif val > hi:
            status = "above_range"
        else:
            status = "within_range"
        comparisons[metric_key] = {
            "label": label,
            "value": val,
            "target_range": [lo, hi],
            "status": status,
        }

    return {
        "target_audience": target,
        "target_label": profile["label"],
        "target_description": profile["description"],
        "comparisons": comparisons,
    }


def generate_suggestions(metrics: dict, target: str | None) -> list[dict]:
    """Generate actionable improvement suggestions."""
    suggestions = []
    profile = AUDIENCE_PROFILES.get(target, AUDIENCE_PROFILES["b2c_general"]) if target else None

    # --- Sentence length ---
    avg_sl = metrics.get("avg_sentence_length", 0)
    if profile:
        lo, hi = profile["avg_sentence_length_range"]
        if avg_sl > hi:
            suggestions.append({
                "category": "sentence_length",
                "priority": "high",
                "message": (
                    f"Average sentence length ({avg_sl} words) exceeds the "
                    f"target range ({lo}-{hi}) for {profile['label']}. "
                    "Break long sentences into shorter ones."
                ),
            })
        elif avg_sl < lo:
            suggestions.append({
                "category": "sentence_length",
                "priority": "medium",
                "message": (
                    f"Average sentence length ({avg_sl} words) is below the "
                    f"target range ({lo}-{hi}) for {profile['label']}. "
                    "Combine choppy sentences for better flow."
                ),
            })
    else:
        if avg_sl > 25:
            suggestions.append({
                "category": "sentence_length",
                "priority": "high",
                "message": (
                    f"Average sentence length is {avg_sl} words. "
                    "Sentences over 25 words are harder to read. "
                    "Consider splitting complex sentences."
                ),
            })

    # --- Complex words ---
    complex_pct = metrics.get("complex_word_pct", 0)
    if profile:
        lo, hi = profile["complex_word_pct_range"]
        if complex_pct > hi:
            top_complex = metrics.get("most_complex_words", [])[:5]
            examples = ", ".join(w["word"] for w in top_complex)
            suggestions.append({
                "category": "complex_words",
                "priority": "high",
                "message": (
                    f"Complex word percentage ({complex_pct}%) exceeds "
                    f"the target ({lo}-{hi}%) for {profile['label']}. "
                    f"Consider simpler alternatives for: {examples}"
                ),
            })
    else:
        if complex_pct > 20:
            suggestions.append({
                "category": "complex_words",
                "priority": "medium",
                "message": (
                    f"{complex_pct}% of words have 3+ syllables. "
                    "Consider replacing some with simpler alternatives."
                ),
            })

    # --- Reading ease ---
    ease = metrics.get("flesch_reading_ease", 50)
    if ease < 30:
        suggestions.append({
            "category": "readability",
            "priority": "high",
            "message": (
                f"Flesch Reading Ease score is {ease} (very difficult). "
                "Unless writing for an academic audience, simplify language."
            ),
        })
    elif ease < 50:
        suggestions.append({
            "category": "readability",
            "priority": "medium",
            "message": (
                f"Flesch Reading Ease score is {ease} (difficult). "
                "Consider using shorter words and sentences for broader reach."
            ),
        })

    # --- Longest sentences ---
    longest = metrics.get("longest_sentences", [])
    flagged_sentences = [s for s in longest if s["word_count"] > 35]
    if flagged_sentences:
        suggestions.append({
            "category": "long_sentences",
            "priority": "high",
            "message": (
                f"Found {len(flagged_sentences)} sentence(s) over 35 words. "
                "These are very difficult to parse. Consider breaking them up."
            ),
            "examples": [s["sentence"] for s in flagged_sentences[:3]],
        })

    # --- Grade level ---
    grade = metrics.get("flesch_kincaid_grade", 8)
    if grade > 16:
        suggestions.append({
            "category": "grade_level",
            "priority": "medium",
            "message": (
                f"Grade level is {grade} (post-graduate). "
                "This limits your audience significantly. Consider simplifying "
                "unless targeting academic/technical readers."
            ),
        })

    if not suggestions:
        suggestions.append({
            "category": "general",
            "priority": "info",
            "message": "Content readability looks good for the target audience.",
        })

    return suggestions


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Multi-metric readability analysis for marketing content.",
        epilog=(
            "Targets: b2c_general, b2b_professional, b2b_technical, children, academic\n\n"
            "Example:\n"
            '  python readability-analyzer.py --text "Short punchy copy." --target b2c_general'
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
        help="Path to a text file containing content to analyze.",
    )
    parser.add_argument(
        "--target", type=str, default=None,
        choices=list(AUDIENCE_PROFILES.keys()),
        help="Target audience for comparison (default: auto-detect best fit).",
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

    # Compute metrics
    metrics = compute_metrics(text)
    if "error" in metrics:
        print(json.dumps(metrics, indent=2))
        sys.exit(1)

    # Audience recommendation
    audience_rec = recommend_audience(metrics)

    # Target comparison
    target = args.target
    target_comparison = compare_to_target(metrics, target) if target else None

    # Suggestions
    suggestions = generate_suggestions(metrics, target or audience_rec["best_fit_audience"])

    # Assemble output
    output = {
        "metrics": metrics,
        "audience_recommendation": audience_rec,
        "suggestions": suggestions,
    }
    if target_comparison:
        output["target_comparison"] = target_comparison

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
