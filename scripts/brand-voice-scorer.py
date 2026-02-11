#!/usr/bin/env python3
"""
brand-voice-scorer.py
=====================
Score content against a brand voice profile.

Reads a brand voice profile from ~/.claude-marketing/brands/{slug}/profile.json,
analyzes text content across multiple voice dimensions, and returns a voice
consistency score (0-100) with per-dimension breakdown and specific deviations.

Dependencies: nltk, json, sys, pathlib, argparse

Usage:
    python brand-voice-scorer.py --brand acme --text "Check out our amazing product!"
    python brand-voice-scorer.py --brand acme --file content.txt

Brand Profile JSON Schema (profile.json — from setup.py / brand-setup):
    {
        "brand_name": "Acme Corp",
        "brand_voice": {
            "formality": 7,         // 1 (very casual) to 10 (very formal)
            "energy": 5,            // 1 (calm/reserved) to 10 (high-energy/excited)
            "humor": 2,             // 1 (serious) to 10 (humorous)
            "authority": 8,         // 1 (peer-level) to 10 (authoritative/expert)
            "personality_traits": ["confident", "precise"],
            "tone_keywords": ["innovative", "reliable"],
            "avoid_words": ["cheap", "basically", "honestly"],
            "prefer_words": ["innovative", "reliable", "precision"],
            "this_not_that": [["cheap", "affordable"], ["buy", "invest in"]],
            "sample_content": []
        }
    }

    Also supports legacy direct schema:
    {
        "voice_dimensions": {"formality": 0.7, "energy": 0.5, ...},
        "preferred_words": [...], "avoided_words": [...]
    }
"""

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# NLTK bootstrap — download the required data silently on first run
# ---------------------------------------------------------------------------
try:
    import nltk
except ImportError:
    print(json.dumps({
        "fallback": True,
        "error": "nltk_not_installed",
        "message": "NLTK not installed. Voice scoring requires: pip install nltk",
        "overall_score": None,
        "recommendation": "Install NLTK for automated scoring, or review manually against brand voice guidelines."
    }, indent=2))
    sys.exit(0)

# Ensure tokenizer models are available
for _res in ("punkt", "punkt_tab", "averaged_perceptron_tagger",
             "averaged_perceptron_tagger_eng"):
    try:
        nltk.data.find(f"tokenizers/{_res}" if "punkt" in _res
                       else f"taggers/{_res}")
    except LookupError:
        nltk.download(_res, quiet=True)

from nltk.tokenize import sent_tokenize, word_tokenize

# ---------------------------------------------------------------------------
# Constants & indicator word-lists
# ---------------------------------------------------------------------------

# Words / patterns that signal HIGH formality
FORMAL_INDICATORS = {
    "furthermore", "consequently", "nevertheless", "therefore", "moreover",
    "accordingly", "henceforth", "hereby", "herein", "notwithstanding",
    "pursuant", "regarding", "respectively", "subsequently", "thus",
    "whereas", "whereby", "wherein", "utilise", "utilize", "facilitate",
    "implement", "demonstrate", "constitute", "acknowledge", "endeavor",
    "commence", "terminate", "prior", "subsequent", "sufficient",
    "considerable", "significant", "appropriate", "approximately",
    "establish", "determine", "indicate", "obtain", "provide", "require",
    "shall", "must", "ensure",
}

# Words / patterns that signal LOW formality (casual)
CASUAL_INDICATORS = {
    "hey", "hi", "yo", "gonna", "gotta", "wanna", "kinda", "sorta",
    "yeah", "yep", "nope", "cool", "awesome", "amazing", "literally",
    "basically", "honestly", "totally", "super", "stuff", "thing",
    "things", "lots", "tons", "bunch", "guys", "dude", "lol", "omg",
    "btw", "fyi", "tbh", "imo", "imho", "ok", "okay", "chill",
    "vibe", "vibes", "fam", "bro",
}

# High-energy words
HIGH_ENERGY_WORDS = {
    "exciting", "incredible", "amazing", "fantastic", "extraordinary",
    "revolutionary", "breakthrough", "transformative", "game-changing",
    "explosive", "unstoppable", "phenomenal", "spectacular", "stunning",
    "thrilling", "electrifying", "dynamic", "powerful", "turbocharge",
    "skyrocket", "supercharge", "unleash", "ignite", "amplify", "crush",
    "dominate", "epic", "insane", "wild", "massive", "huge", "unbelievable",
}

# Calm / reserved words
CALM_WORDS = {
    "steady", "measured", "considered", "thoughtful", "deliberate",
    "careful", "gradual", "consistent", "reliable", "sustainable",
    "balanced", "moderate", "stable", "calm", "quiet", "gentle",
    "subtle", "understated", "nuanced", "refined",
}

# Humor indicators
HUMOR_INDICATORS = {
    "lol", "haha", "hehe", "rofl", "lmao", "😂", "🤣", "😄", "😆",
    "joke", "jokes", "joking", "kidding", "pun", "puns", "funny",
    "hilarious", "witty", "tongue-in-cheek",
}

# Exclamation marks and emoji also raise energy / humor signals
EXCLAMATION_WEIGHT = 0.02  # per exclamation mark
QUESTION_WEIGHT = 0.005

# Authority indicators
AUTHORITY_INDICATORS = {
    "proven", "research", "data", "evidence", "study", "studies",
    "expert", "expertise", "authority", "definitive", "comprehensive",
    "analysis", "framework", "methodology", "strategy", "strategic",
    "insight", "insights", "benchmark", "best-practice", "best practice",
    "proprietary", "patent", "certified", "decade", "decades", "years",
    "experience", "track record", "industry-leading", "peer-reviewed",
    "published", "demonstrated", "validated", "verified",
}

# Peer-level / humble indicators
PEER_INDICATORS = {
    "we think", "in our opinion", "we believe", "maybe", "perhaps",
    "might", "could", "possibly", "it seems", "from our perspective",
    "we feel", "just", "simply", "honestly", "in our experience",
    "we've found", "we've noticed",
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def normalize_profile(profile: dict) -> dict:
    """Normalize brand profile to the scorer's internal format.

    Handles both:
    - Full profile schema (from setup.py / brand-setup) with brand_voice nested object
      and 1-10 integer scales
    - Legacy direct schema with voice_dimensions (0.0-1.0 floats) at root level
    """
    normalized = dict(profile)

    brand_voice = profile.get("brand_voice", {})
    if brand_voice and "voice_dimensions" not in profile:
        # Convert setup.py's 1-10 int scale to 0.0-1.0 float scale
        normalized["voice_dimensions"] = {
            "formality": brand_voice.get("formality", 5) / 10.0,
            "energy": brand_voice.get("energy", 5) / 10.0,
            "humor": brand_voice.get("humor", 3) / 10.0,
            "authority": brand_voice.get("authority", 5) / 10.0,
        }
        # Map field names: prefer_words → preferred_words, avoid_words → avoided_words
        if "preferred_words" not in normalized:
            normalized["preferred_words"] = brand_voice.get("prefer_words", [])
        if "avoided_words" not in normalized:
            normalized["avoided_words"] = brand_voice.get("avoid_words", [])
        # Carry over tone keywords as notes context
        tone = brand_voice.get("tone_keywords", [])
        if tone and "notes" not in normalized:
            normalized["notes"] = f"Tone keywords: {', '.join(tone)}"

    return normalized


def load_brand_profile(slug: str) -> dict:
    """Load a brand voice profile JSON from the standard location."""
    profile_path = Path.home() / ".claude-marketing" / "brands" / slug / "profile.json"
    if not profile_path.exists():
        return {
            "error": f"Brand profile not found at {profile_path}",
            "hint": (
                "Create a profile.json at the path above. "
                "Run /dm:brand-setup to create one interactively."
            ),
        }
    try:
        with open(profile_path, "r", encoding="utf-8") as fh:
            profile = json.load(fh)
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid JSON in {profile_path}: {exc}"}
    return normalize_profile(profile)


def _count_matches(tokens_lower: list[str], word_set: set[str]) -> int:
    """Count how many tokens appear in the given set."""
    return sum(1 for t in tokens_lower if t in word_set)


def _bigram_matches(text_lower: str, phrase_set: set[str]) -> int:
    """Count phrase-level matches that may contain spaces."""
    return sum(1 for phrase in phrase_set if " " in phrase and phrase in text_lower)


def analyze_formality(tokens_lower: list[str], text_lower: str) -> float:
    """Return a formality score between 0.0 (casual) and 1.0 (formal)."""
    if not tokens_lower:
        return 0.5
    formal_hits = _count_matches(tokens_lower, FORMAL_INDICATORS)
    casual_hits = _count_matches(tokens_lower, CASUAL_INDICATORS)
    total = formal_hits + casual_hits
    if total == 0:
        return 0.5  # neutral
    return round(formal_hits / total, 4)


def analyze_energy(tokens_lower: list[str], text: str) -> float:
    """Return an energy score between 0.0 (calm) and 1.0 (high-energy)."""
    if not tokens_lower:
        return 0.5
    high_hits = _count_matches(tokens_lower, HIGH_ENERGY_WORDS)
    calm_hits = _count_matches(tokens_lower, CALM_WORDS)
    exclamation_boost = text.count("!") * EXCLAMATION_WEIGHT
    caps_words = sum(1 for t in text.split() if t.isupper() and len(t) > 1)
    caps_boost = min(caps_words * 0.01, 0.15)
    total = high_hits + calm_hits
    if total == 0:
        base = 0.5
    else:
        base = high_hits / total
    score = base + exclamation_boost + caps_boost
    return round(min(max(score, 0.0), 1.0), 4)


def analyze_humor(tokens_lower: list[str], text_lower: str) -> float:
    """Return a humor score between 0.0 (serious) and 1.0 (humorous)."""
    if not tokens_lower:
        return 0.0
    humor_hits = _count_matches(tokens_lower, HUMOR_INDICATORS)
    # Also check for multi-word humor indicators
    humor_hits += _bigram_matches(text_lower, HUMOR_INDICATORS)
    # Normalize: even a few humor markers in short text is notable
    ratio = humor_hits / max(len(tokens_lower), 1)
    # Scale so that ~5% humor words => score of ~1.0
    score = min(ratio * 20, 1.0)
    return round(score, 4)


def analyze_authority(tokens_lower: list[str], text_lower: str) -> float:
    """Return an authority score between 0.0 (peer) and 1.0 (authoritative)."""
    if not tokens_lower:
        return 0.5
    auth_hits = _count_matches(tokens_lower, AUTHORITY_INDICATORS)
    auth_hits += _bigram_matches(text_lower, AUTHORITY_INDICATORS)
    peer_hits = _bigram_matches(text_lower, PEER_INDICATORS)
    peer_hits += _count_matches(tokens_lower, PEER_INDICATORS)
    total = auth_hits + peer_hits
    if total == 0:
        return 0.5
    return round(auth_hits / total, 4)


def check_word_lists(tokens_lower: list[str], preferred: list[str],
                     avoided: list[str]) -> dict:
    """Check for preferred and avoided word usage."""
    preferred_lower = {w.lower() for w in preferred}
    avoided_lower = {w.lower() for w in avoided}

    preferred_found = sorted(preferred_lower & set(tokens_lower))
    preferred_missing = sorted(preferred_lower - set(tokens_lower))
    avoided_found = sorted(avoided_lower & set(tokens_lower))

    return {
        "preferred_found": preferred_found,
        "preferred_missing": preferred_missing,
        "avoided_found": avoided_found,
        "preferred_usage_ratio": (
            round(len(preferred_found) / len(preferred_lower), 4)
            if preferred_lower else 1.0
        ),
        "avoided_violation_count": len(avoided_found),
    }


def dimension_distance(actual: float, target: float) -> float:
    """Absolute distance between actual and target (both 0-1)."""
    return abs(actual - target)


def score_from_distance(distance: float) -> float:
    """Convert a 0-1 distance to a 0-100 score (closer = higher)."""
    return round((1.0 - distance) * 100, 2)


def generate_deviations(dimension_scores: dict, profile: dict) -> list[dict]:
    """Generate human-readable deviation descriptions."""
    deviations = []
    targets = profile.get("voice_dimensions", {})

    labels = {
        "formality": ("casual", "formal"),
        "energy": ("calm/reserved", "high-energy/excited"),
        "humor": ("serious", "humorous"),
        "authority": ("peer-level", "authoritative/expert"),
    }

    for dim, info in dimension_scores.items():
        dist = info["distance"]
        if dist > 0.15:  # threshold for flagging
            target = targets.get(dim, 0.5)
            actual = info["actual"]
            low_label, high_label = labels.get(dim, ("low", "high"))
            direction = high_label if actual > target else low_label
            target_dir = high_label if target > 0.5 else low_label
            deviations.append({
                "dimension": dim,
                "severity": "high" if dist > 0.35 else "medium",
                "message": (
                    f"Content reads as too {direction} "
                    f"(actual={actual:.2f}, target={target:.2f}). "
                    f"Brand voice calls for more {target_dir} tone."
                ),
            })
    return deviations


# ---------------------------------------------------------------------------
# Main scoring pipeline
# ---------------------------------------------------------------------------

def score_content(text: str, profile: dict) -> dict:
    """Run the full brand-voice scoring pipeline and return results dict."""
    if not text or not text.strip():
        return {
            "error": "Empty text provided. Please supply content to analyze.",
            "score": 0,
        }

    targets = profile.get("voice_dimensions", {
        "formality": 0.5,
        "energy": 0.5,
        "humor": 0.0,
        "authority": 0.5,
    })

    # Tokenize
    sentences = sent_tokenize(text)
    tokens = word_tokenize(text)
    tokens_lower = [t.lower() for t in tokens if t.isalpha()]
    text_lower = text.lower()

    # Dimension analysis
    actual = {
        "formality": analyze_formality(tokens_lower, text_lower),
        "energy": analyze_energy(tokens_lower, text),
        "humor": analyze_humor(tokens_lower, text_lower),
        "authority": analyze_authority(tokens_lower, text_lower),
    }

    dimension_results = {}
    weighted_score_sum = 0.0
    weight_total = 0.0

    # Weights for overall score (configurable in profile, with defaults)
    weights = profile.get("dimension_weights", {
        "formality": 1.0,
        "energy": 1.0,
        "humor": 0.8,
        "authority": 1.0,
    })

    for dim in ("formality", "energy", "humor", "authority"):
        target_val = targets.get(dim, 0.5)
        dist = dimension_distance(actual[dim], target_val)
        dim_score = score_from_distance(dist)
        w = weights.get(dim, 1.0)
        weighted_score_sum += dim_score * w
        weight_total += w
        dimension_results[dim] = {
            "actual": round(actual[dim], 4),
            "target": target_val,
            "distance": round(dist, 4),
            "score": dim_score,
        }

    # Word-list checks
    preferred = profile.get("preferred_words", [])
    avoided = profile.get("avoided_words", [])
    word_check = check_word_lists(tokens_lower, preferred, avoided)

    # Word-list contribution to overall score
    word_list_score = 100.0
    if preferred:
        word_list_score -= (1.0 - word_check["preferred_usage_ratio"]) * 30
    if avoided:
        penalty = min(word_check["avoided_violation_count"] * 10, 40)
        word_list_score -= penalty
    word_list_score = max(word_list_score, 0.0)

    # Combine dimension score and word-list score
    dimension_avg = (weighted_score_sum / weight_total) if weight_total else 50.0
    overall_score = round(dimension_avg * 0.7 + word_list_score * 0.3, 2)
    overall_score = max(0.0, min(100.0, overall_score))

    # Deviations
    deviations = generate_deviations(dimension_results, profile)

    # Sentence length check
    avg_sentence_len = (
        round(len(tokens) / len(sentences), 1) if sentences else 0
    )
    target_sentence_len = profile.get("target_sentence_length", None)
    if target_sentence_len and abs(avg_sentence_len - target_sentence_len) > 8:
        deviations.append({
            "dimension": "sentence_length",
            "severity": "medium",
            "message": (
                f"Average sentence length is {avg_sentence_len} words "
                f"(target: ~{target_sentence_len}). Consider adjusting."
            ),
        })

    return {
        "brand": profile.get("brand_name", "Unknown"),
        "overall_score": overall_score,
        "interpretation": _interpret_score(overall_score),
        "dimension_scores": dimension_results,
        "word_list_analysis": word_check,
        "word_list_score": round(word_list_score, 2),
        "deviations": deviations,
        "stats": {
            "word_count": len(tokens_lower),
            "sentence_count": len(sentences),
            "avg_sentence_length": avg_sentence_len,
        },
    }


def _interpret_score(score: float) -> str:
    """Return a human-readable interpretation of the overall score."""
    if score >= 90:
        return "Excellent — closely aligned with brand voice"
    elif score >= 75:
        return "Good — mostly on-brand with minor deviations"
    elif score >= 60:
        return "Fair — noticeable deviations from brand voice"
    elif score >= 40:
        return "Poor — significant misalignment with brand voice"
    else:
        return "Critical — content does not match brand voice"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score content against a brand voice profile.",
        epilog=(
            "Example:\n"
            '  python brand-voice-scorer.py --brand acme --text "Our product is great!"'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--brand", required=True,
        help="Brand slug (matches folder name under ~/.claude-marketing/brands/)",
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
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Load brand profile
    profile = load_brand_profile(args.brand)
    if "error" in profile:
        print(json.dumps(profile, indent=2))
        sys.exit(1)

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
    result = score_content(text, profile)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
