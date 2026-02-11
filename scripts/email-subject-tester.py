#!/usr/bin/env python3
"""Score email subject lines for open-rate effectiveness.

Evaluates subject lines across 10 dimensions including length, word count,
spam triggers, personalization, emoji usage, capitalization, power words,
and mobile preview compatibility. Returns per-subject scores (0-100) with
detailed breakdowns, warnings, and actionable recommendations.

Usage:
    python email-subject-tester.py --subjects '["50% Off Today Only!", "Hey {first_name}, quick question"]'
    python email-subject-tester.py --subjects "Your Weekly Digest Is Here"
    python email-subject-tester.py --subjects '["Subject A", "Subject B"]' --brand acme
"""

import argparse
import json
import re
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPAM_TRIGGERS = {
    "act now", "action required", "apply now", "buy now", "buy direct",
    "call now", "click here", "click below", "congratulations", "dear friend",
    "don't delete", "don't hesitate", "double your", "earn extra", "exclusive deal",
    "expire", "extra cash", "free", "free access", "free gift", "free offer",
    "100% free", "get it now", "get paid", "great offer", "guarantee",
    "increase your", "incredible deal", "limited time", "limited offer",
    "lowest price", "make money", "million dollars", "no catch", "no cost",
    "no obligation", "no risk", "not spam", "offer expires", "once in a lifetime",
    "order now", "please read", "prize", "promise you", "risk free",
    "special promotion", "this isn't spam", "urgent", "you've been selected",
    "you're a winner", "winner", "what are you waiting for", "while supplies last",
}

POWER_WORDS = {
    "amazing", "astonishing", "backed", "breakthrough", "captivating",
    "compelling", "confidential", "crush", "cutting-edge", "daring",
    "discover", "dominate", "effortless", "elite", "epic", "essential",
    "exclusive", "extraordinary", "eye-opening", "forbidden", "genius",
    "guaranteed", "hidden", "insider", "instant", "jaw-dropping",
    "legendary", "life-changing", "limited", "massive", "mind-blowing",
    "proven", "rare", "remarkable", "revolutionary", "secret", "sensational",
    "shocking", "skyrocket", "stunning", "supercharge", "surprising",
    "ultimate", "unconventional", "unexpected", "unleash", "unprecedented",
    "unstoppable", "urgent", "vital",
}

PERSONALIZATION_TOKENS = {
    "{first_name}", "{last_name}", "{name}", "{company}", "{city}",
    "{industry}", "{title}", "{job_title}", "{location}",
}

# Regex for common emoji Unicode ranges
EMOJI_PATTERN = re.compile(
    "[\U0001F600-\U0001F64F"   # emoticons
    "\U0001F300-\U0001F5FF"    # symbols & pictographs
    "\U0001F680-\U0001F6FF"    # transport & map
    "\U0001F1E0-\U0001F1FF"    # flags
    "\U00002702-\U000027B0"    # dingbats
    "\U0001F900-\U0001F9FF"    # supplemental symbols
    "\U0001FA00-\U0001FA6F"    # chess symbols
    "\U0001FA70-\U0001FAFF"    # symbols extended-A
    "\U00002600-\U000026FF"    # misc symbols
    "]+", flags=re.UNICODE,
)


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def score_length(subject):
    """Score character length (0-20). Optimal: 30-60 chars."""
    length = len(subject)
    if 30 <= length <= 60:
        return 20
    elif 20 <= length < 30:
        return 15
    elif 60 < length <= 80:
        return 12
    elif 10 <= length < 20:
        return 8
    elif 80 < length <= 100:
        return 6
    else:
        return 2


def score_word_count(subject):
    """Score word count (0-15). Optimal: 4-9 words."""
    words = subject.split()
    count = len(words)
    if 4 <= count <= 9:
        return 15
    elif count == 3 or count == 10:
        return 10
    elif count == 2 or count == 11:
        return 6
    else:
        return 2


def score_spam_triggers(subject):
    """Scan for spam trigger words. Returns penalty (0 to -30) and list found."""
    subject_lower = subject.lower()
    found = []
    for trigger in SPAM_TRIGGERS:
        if trigger in subject_lower:
            found.append(trigger)
    penalty = min(len(found) * 10, 30)
    return -penalty, found


def score_personalization(subject):
    """Detect personalization tokens (0 or 10 bonus)."""
    subject_lower = subject.lower()
    found = [t for t in PERSONALIZATION_TOKENS if t in subject_lower]
    return (10 if found else 0), found


def score_emoji(subject):
    """Score emoji usage (0-10). 1 emoji = good, 3+ = penalty."""
    emojis = EMOJI_PATTERN.findall(subject)
    # Each match can contain multiple emoji chars
    emoji_count = sum(len(e) for e in emojis)
    if emoji_count == 1:
        return 10
    elif emoji_count == 2:
        return 6
    elif emoji_count == 0:
        return 4
    else:
        return 0  # 3+ emoji is a penalty zone


def score_question(subject):
    """Score question detection (0 or 5)."""
    return 5 if "?" in subject else 0


def score_caps_ratio(subject):
    """Score ALL CAPS ratio (0-10). >30% caps = penalty."""
    alpha_chars = [c for c in subject if c.isalpha()]
    if not alpha_chars:
        return 5
    upper_count = sum(1 for c in alpha_chars if c.isupper())
    ratio = upper_count / len(alpha_chars)
    if ratio <= 0.15:
        return 10
    elif ratio <= 0.30:
        return 7
    elif ratio <= 0.50:
        return 3
    else:
        return 0


def score_numbers(subject):
    """Score number usage (0 or 5). Numbers in subjects boost opens."""
    return 5 if re.search(r"\d", subject) else 0


def score_power_words(subject):
    """Score power word usage (0-15)."""
    words = re.findall(r"[a-zA-Z'-]+", subject.lower())
    found = [w for w in words if w in POWER_WORDS]
    unique_found = list(set(found))
    count = len(unique_found)
    if count >= 3:
        return 15, unique_found
    elif count == 2:
        return 12, unique_found
    elif count == 1:
        return 8, unique_found
    else:
        return 0, unique_found


def score_preview_compat(subject):
    """Score preview text compatibility (0-10). Under 90 chars is good for mobile."""
    length = len(subject)
    if length <= 50:
        return 10
    elif length <= 70:
        return 8
    elif length <= 90:
        return 5
    else:
        return 2


def generate_recommendations(breakdown, spam_found, power_found, subject):
    """Generate actionable recommendations based on scoring breakdown."""
    recs = []
    length = len(subject)

    if breakdown["length_score"] < 15:
        if length < 30:
            recs.append("Subject is too short. Aim for 30-60 characters for optimal open rates.")
        elif length > 60:
            recs.append(f"Subject is {length} chars. Trim to 30-60 characters to avoid truncation on mobile.")

    if breakdown["word_count_score"] < 10:
        recs.append("Adjust word count to 4-9 words for the best engagement.")

    if breakdown["spam_trigger_penalty"] < 0:
        recs.append(f"Remove spam triggers ({', '.join(spam_found[:3])}). These hurt deliverability.")

    if breakdown["power_word_score"] == 0:
        recs.append("Add a power word (e.g., 'exclusive', 'proven', 'secret') to boost curiosity.")

    if breakdown["emoji_score"] == 0:
        recs.append("Too many emojis. Limit to 1 emoji per subject line.")
    elif breakdown["emoji_score"] == 4:
        recs.append("Consider adding a single relevant emoji to stand out in the inbox.")

    if breakdown["question_score"] == 0:
        recs.append("Try phrasing as a question to increase curiosity and open rates.")

    if breakdown["caps_ratio_score"] < 5:
        recs.append("Reduce ALL CAPS usage. It triggers spam filters and feels aggressive.")

    if breakdown["number_score"] == 0:
        recs.append("Including a number (e.g., '5 tips', '30% off') can improve open rates.")

    if breakdown["personalization_bonus"] == 0:
        recs.append("Add a personalization token like {first_name} to boost open rates by 10-20%.")

    if breakdown["preview_compat_score"] < 5:
        recs.append("Subject is too long for mobile preview. Keep under 50 chars for best display.")

    return recs


def generate_warnings(breakdown, spam_found, subject):
    """Generate warnings for critical issues."""
    warnings = []
    if spam_found:
        warnings.append(f"Spam triggers detected: {', '.join(spam_found)}")
    if breakdown["caps_ratio_score"] == 0:
        warnings.append("Excessive ALL CAPS — high risk of spam filtering")
    if len(subject) > 100:
        warnings.append("Subject exceeds 100 characters — will be heavily truncated on most clients")
    if breakdown["emoji_score"] == 0:
        warnings.append("Emoji overuse (3+) can hurt deliverability")
    if subject.strip().startswith("RE:") or subject.strip().startswith("FW:"):
        warnings.append("Fake RE:/FW: prefix is a known spam signal")
    return warnings


def analyze_subject(subject, brand=None):
    """Analyze a single subject line and return full scoring result."""
    if not subject or not subject.strip():
        return {"error": "Empty subject line provided"}

    subject = subject.strip()

    # Calculate all dimension scores
    length_sc = score_length(subject)
    word_sc = score_word_count(subject)
    spam_penalty, spam_found = score_spam_triggers(subject)
    personal_sc, personal_tokens = score_personalization(subject)
    emoji_sc = score_emoji(subject)
    question_sc = score_question(subject)
    caps_sc = score_caps_ratio(subject)
    number_sc = score_numbers(subject)
    power_sc, power_found = score_power_words(subject)
    preview_sc = score_preview_compat(subject)

    breakdown = {
        "length_score": length_sc,
        "word_count_score": word_sc,
        "spam_trigger_penalty": spam_penalty,
        "personalization_bonus": personal_sc,
        "emoji_score": emoji_sc,
        "question_score": question_sc,
        "caps_ratio_score": caps_sc,
        "number_score": number_sc,
        "power_word_score": power_sc,
        "preview_compat_score": preview_sc,
    }

    # Total score: sum of positives + penalties + bonuses, clamped to 0-100
    raw_score = (
        length_sc + word_sc + spam_penalty + personal_sc +
        emoji_sc + question_sc + caps_sc + number_sc +
        power_sc + preview_sc
    )
    total_score = max(0, min(100, raw_score))

    warnings = generate_warnings(breakdown, spam_found, subject)
    recommendations = generate_recommendations(breakdown, spam_found, power_found, subject)

    result = {
        "subject": subject,
        "score": total_score,
        "breakdown": breakdown,
        "spam_triggers_found": spam_found,
        "power_words_found": power_found,
        "personalization_tokens_found": personal_tokens,
        "warnings": warnings,
        "recommendations": recommendations,
    }

    if brand:
        result["brand"] = brand

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Score email subject lines for open-rate effectiveness"
    )
    parser.add_argument(
        "--subjects", required=True,
        help='JSON array of subject lines OR a single subject string',
    )
    parser.add_argument(
        "--brand", default=None,
        help="Brand slug for context (optional)",
    )
    args = parser.parse_args()

    # Parse input: try JSON array first, fall back to single string
    raw = args.subjects.strip()
    try:
        subjects = json.loads(raw)
        if isinstance(subjects, str):
            subjects = [subjects]
        elif not isinstance(subjects, list):
            json.dump({"error": "Subjects must be a JSON array or a single string"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
    except json.JSONDecodeError:
        subjects = [raw]

    if not subjects:
        json.dump({"error": "No subject lines provided"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    results = [analyze_subject(s, brand=args.brand) for s in subjects]

    if len(results) == 1:
        output = results[0]
    else:
        valid = [r for r in results if "error" not in r]
        scores = [r["score"] for r in valid]
        avg = round(sum(scores) / max(len(scores), 1), 1)
        best = max(valid, key=lambda r: r["score"]) if valid else None
        worst = min(valid, key=lambda r: r["score"]) if valid else None
        output = {
            "total_subjects": len(results),
            "average_score": avg,
            "best_subject": best["subject"] if best else None,
            "worst_subject": worst["subject"] if worst else None,
            "results": results,
        }

    json.dump(output, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
