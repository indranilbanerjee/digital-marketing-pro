#!/usr/bin/env python3
"""Generate structured review response drafts with tone templates.

Analyzes customer reviews for sentiment, key issues, and positive mentions,
then generates contextually appropriate response drafts with primary and
alternative versions. Supports multiple platforms and tone presets. Flags
escalation triggers such as health/safety concerns, legal threats, or profanity.

Usage:
    python review-response-drafter.py --review "Great food but slow service" --rating 3
    python review-response-drafter.py --review "Absolutely loved it!" --rating 5 --tone warm --reviewer "Sarah"
    python review-response-drafter.py --review "Terrible experience" --rating 1 --platform google --brand acme
"""

import argparse
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

POSITIVE_KEYWORDS = [
    "good", "great", "excellent", "amazing", "fantastic", "wonderful",
    "outstanding", "perfect", "love", "loved", "best", "awesome",
    "delicious", "friendly", "helpful", "clean", "fast", "quick",
    "professional", "beautiful", "recommend", "impressive", "quality",
    "pleasant", "attentive", "superb", "exceptional", "brilliant",
    "top-notch", "stellar", "remarkable", "fabulous", "comfortable",
]

NEGATIVE_KEYWORDS = [
    "bad", "terrible", "awful", "horrible", "worst", "slow", "rude",
    "dirty", "cold", "stale", "overpriced", "expensive", "disappointing",
    "mediocre", "poor", "unfriendly", "unprofessional", "broken",
    "disgusting", "unacceptable", "incompetent", "neglected", "ignored",
    "waited", "waiting", "wrong", "mistake", "never again", "waste",
    "bland", "tasteless", "noisy", "cramped", "understaffed",
]

ESCALATION_TRIGGERS = {
    "health_safety": [
        "food poisoning", "sick", "ill", "hospital", "allergic reaction",
        "cockroach", "rat", "insect", "mold", "contaminated", "injury",
        "injured", "hazard", "unsafe", "health department", "bacteria",
    ],
    "legal": [
        "lawyer", "attorney", "lawsuit", "sue", "legal action", "court",
        "class action", "fraud", "scam", "report to", "bbb",
        "consumer protection", "ftc",
    ],
    "profanity": [
        "fuck", "shit", "damn", "ass", "bitch", "crap", "hell",
        "bastard", "piss",
    ],
    "discrimination": [
        "racist", "racism", "sexist", "discrimination", "discriminated",
        "homophobic", "bigot", "harassment", "harassed",
    ],
}

PLATFORM_WORD_RECOMMENDATIONS = {
    "google": 150,
    "yelp": 200,
    "g2": 200,
    "capterra": 200,
    "trustpilot": 150,
}


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------

def extract_mentions(review_lower, keywords):
    """Extract keyword matches found in the review text."""
    found = []
    for kw in keywords:
        if kw in review_lower:
            found.append(kw)
    return found


def detect_escalation(review_lower):
    """Detect escalation triggers in the review text."""
    triggers = []
    for category, phrases in ESCALATION_TRIGGERS.items():
        for phrase in phrases:
            if phrase in review_lower:
                triggers.append({"category": category, "trigger": phrase})
                break  # one trigger per category is enough
    return triggers


def classify_sentiment(rating, positive_count, negative_count):
    """Classify overall sentiment based on rating and keyword counts."""
    if rating >= 4 and positive_count > negative_count:
        return "positive"
    elif rating <= 2 and negative_count > positive_count:
        return "negative"
    elif rating == 3 or (positive_count > 0 and negative_count > 0):
        return "mixed"
    elif rating >= 4:
        return "positive"
    elif rating <= 2:
        return "negative"
    return "neutral"


# ---------------------------------------------------------------------------
# Response generation
# ---------------------------------------------------------------------------

TONE_OPENERS = {
    "professional": {
        5: "Thank you for your excellent review",
        4: "Thank you for your positive feedback",
        3: "Thank you for sharing your experience",
        2: "We sincerely appreciate you taking the time to share your feedback",
        1: "We are truly sorry to hear about your experience",
    },
    "warm": {
        5: "We're so thrilled to hear this",
        4: "Thanks so much for the kind words",
        3: "We really appreciate you sharing your thoughts with us",
        2: "We're sorry to hear things didn't go as expected",
        1: "We're deeply sorry about what happened",
    },
    "empathetic": {
        5: "It truly means the world to us to hear this",
        4: "We understand how much a great experience matters, and we're glad we delivered",
        3: "We hear you, and we appreciate your honest feedback",
        2: "We understand your frustration and we're sorry we fell short",
        1: "We can only imagine how disappointing this must have been",
    },
    "enthusiastic": {
        5: "Wow, thank you SO much for this amazing review",
        4: "This is wonderful to hear! Thank you",
        3: "Thank you for your honest feedback — we're always looking to improve",
        2: "We appreciate you sharing this with us",
        1: "We appreciate you letting us know about this",
    },
}


def build_response(rating, reviewer, tone, positive_mentions, negative_mentions,
                   platform, brand):
    """Build primary and alternative response drafts."""
    name = reviewer if reviewer else "[Name]"
    opener = TONE_OPENERS.get(tone, TONE_OPENERS["professional"]).get(rating, "Thank you for your feedback")

    # Build body based on rating tier
    if rating == 5:
        body = _response_5_star(name, opener, tone, positive_mentions, brand)
    elif rating == 4:
        body = _response_4_star(name, opener, tone, positive_mentions, negative_mentions, brand)
    elif rating == 3:
        body = _response_3_star(name, opener, tone, positive_mentions, negative_mentions, brand)
    elif rating == 2:
        body = _response_2_star(name, opener, tone, negative_mentions, brand)
    else:
        body = _response_1_star(name, opener, tone, negative_mentions, brand)

    primary = body["primary"]
    alt_formal = body["alternative_formal"]
    alt_casual = body["alternative_casual"]

    return {
        "primary": primary,
        "alternative_formal": alt_formal,
        "alternative_casual": alt_casual,
    }


def _mention_text(mentions, prefix=""):
    """Format a list of mentions into readable text."""
    if not mentions:
        return ""
    if len(mentions) == 1:
        return f"{prefix}{mentions[0]}"
    return f"{prefix}{', '.join(mentions[:-1])} and {mentions[-1]}"


def _brand_sign(brand):
    """Generate sign-off with brand context."""
    if brand:
        return f"— The {brand.replace('-', ' ').title()} Team"
    return "— The Team"


def _response_5_star(name, opener, tone, positives, brand):
    pos_text = _mention_text(positives, "especially the ")
    sign = _brand_sign(brand)

    primary = (
        f"{opener}, {name}! "
        f"{'We are delighted' if tone == 'professional' else 'We are so happy'} "
        f"to hear you had such a great experience"
        f"{', ' + pos_text if pos_text else ''}. "
        f"Your kind words mean a lot to our team. "
        f"If you enjoyed your experience, we'd love it if you shared it with friends and family. "
        f"We look forward to welcoming you back! {sign}"
    )
    alt_formal = (
        f"Dear {name}, Thank you for taking the time to leave such a wonderful review. "
        f"We are grateful for your patronage"
        f"{' and pleased you appreciated the ' + ', '.join(positives) if positives else ''}. "
        f"We would be honored to serve you again. {sign}"
    )
    alt_casual = (
        f"Hey {name}! Thanks for the awesome review — you just made our day! "
        f"{'So glad you loved the ' + ', '.join(positives) + '! ' if positives else ''}"
        f"Hope to see you again soon! {sign}"
    )
    return {"primary": primary, "alternative_formal": alt_formal, "alternative_casual": alt_casual}


def _response_4_star(name, opener, tone, positives, negatives, brand):
    sign = _brand_sign(brand)
    concern = negatives[0] if negatives else None

    primary = (
        f"{opener}, {name}. "
        f"{'We are glad' if tone == 'professional' else 'So glad'} to hear "
        f"{'you enjoyed the ' + ', '.join(positives) if positives else 'you had a positive experience'}. "
        f"{'We noticed you mentioned the ' + concern + ' — we are always looking to improve in that area. ' if concern else ''}"
        f"We hope to welcome you back and earn that fifth star! {sign}"
    )
    alt_formal = (
        f"Dear {name}, Thank you for your thoughtful feedback. "
        f"We appreciate your recognition"
        f"{' of the ' + ', '.join(positives) if positives else ''}. "
        f"{'We have noted your concern regarding ' + concern + ' and will address it with our team. ' if concern else ''}"
        f"We value your patronage and look forward to your next visit. {sign}"
    )
    alt_casual = (
        f"Hey {name}! Thanks for the great review! "
        f"{'Love that you enjoyed the ' + ', '.join(positives) + '! ' if positives else ''}"
        f"{'We hear you on the ' + concern + ' — working on it! ' if concern else ''}"
        f"See you next time! {sign}"
    )
    return {"primary": primary, "alternative_formal": alt_formal, "alternative_casual": alt_casual}


def _response_3_star(name, opener, tone, positives, negatives, brand):
    sign = _brand_sign(brand)
    concern_text = ", ".join(negatives[:2]) if negatives else "your concerns"

    primary = (
        f"{opener}, {name}. We appreciate your honest feedback. "
        f"{'We are glad you found the ' + ', '.join(positives) + ' satisfactory. ' if positives else ''}"
        f"We are sorry to hear about {concern_text}. "
        f"We take this feedback seriously and would love the chance to make it right. "
        f"Please reach out to us directly so we can address your concerns. {sign}"
    )
    alt_formal = (
        f"Dear {name}, Thank you for your candid review. "
        f"We acknowledge your mixed experience and take your concerns regarding "
        f"{concern_text} very seriously. "
        f"We would welcome the opportunity to discuss this further. "
        f"Please contact us at your convenience. {sign}"
    )
    alt_casual = (
        f"Hey {name}! Thanks for keeping it real with us. "
        f"{'Glad the ' + ', '.join(positives) + ' hit the mark! ' if positives else ''}"
        f"Sorry about the {concern_text} though — that's not the experience we aim for. "
        f"Drop us a line and we'll make it up to you! {sign}"
    )
    return {"primary": primary, "alternative_formal": alt_formal, "alternative_casual": alt_casual}


def _response_2_star(name, opener, tone, negatives, brand):
    sign = _brand_sign(brand)
    issues = ", ".join(negatives[:2]) if negatives else "the issues you experienced"

    primary = (
        f"{opener}, {name}. We sincerely apologize for {issues}. "
        f"This does not reflect the standard we hold ourselves to. "
        f"We would like to offer a concrete resolution and make this right. "
        f"Please contact us directly so we can address your experience personally. {sign}"
    )
    alt_formal = (
        f"Dear {name}, We are deeply sorry that your experience did not meet expectations. "
        f"The concerns you raised regarding {issues} have been shared with our management team. "
        f"We would like the opportunity to resolve this matter. "
        f"Please reach out to us at your earliest convenience. {sign}"
    )
    alt_casual = (
        f"Hey {name}, we're really sorry about this. "
        f"{'The ' + issues + ' — ' if negatives else 'What happened — '}"
        f"that's not okay and we want to fix it. "
        f"Can you reach out to us? We'd love to make things right. {sign}"
    )
    return {"primary": primary, "alternative_formal": alt_formal, "alternative_casual": alt_casual}


def _response_1_star(name, opener, tone, negatives, brand):
    sign = _brand_sign(brand)
    issues = ", ".join(negatives[:3]) if negatives else "the issues you described"

    primary = (
        f"{opener}, {name}. We understand how frustrating this must have been. "
        f"We sincerely apologize for {issues}. "
        f"This is not the experience we want anyone to have. "
        f"We would like to resolve this personally. "
        f"Please contact our manager directly so we can address every concern "
        f"and work toward earning back your trust. {sign}"
    )
    alt_formal = (
        f"Dear {name}, Please accept our sincere apologies. "
        f"Your feedback regarding {issues} has been escalated to our management. "
        f"We take these matters extremely seriously and want to ensure your concerns "
        f"are fully resolved. Please contact our manager at your earliest convenience "
        f"so we may discuss this further. {sign}"
    )
    alt_casual = (
        f"Hey {name}, we're really, truly sorry. "
        f"{'Hearing about the ' + issues + ' is hard to read' if negatives else 'Reading this is hard'} "
        f"because it's not who we are. "
        f"We want to make this right — please reach out to us directly "
        f"and we'll do everything we can. {sign}"
    )
    return {"primary": primary, "alternative_formal": alt_formal, "alternative_casual": alt_casual}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def analyze_review(review, rating, platform, reviewer, tone, brand):
    """Full review analysis and response generation."""
    review_lower = review.lower()

    # Extract mentions
    positive_mentions = extract_mentions(review_lower, POSITIVE_KEYWORDS)
    negative_mentions = extract_mentions(review_lower, NEGATIVE_KEYWORDS)

    # Sentiment classification
    sentiment = classify_sentiment(rating, len(positive_mentions), len(negative_mentions))

    # Key issues = negatives for low ratings, positives for high ratings
    key_issues = []
    if negative_mentions:
        key_issues.extend(negative_mentions)
    if positive_mentions:
        key_issues.extend(positive_mentions)

    # Escalation detection
    escalation_triggers = detect_escalation(review_lower)
    escalation_needed = len(escalation_triggers) > 0
    escalation_reason = (
        "; ".join(f"{t['category']}: '{t['trigger']}'" for t in escalation_triggers)
        if escalation_needed else None
    )

    # Tone validation: enthusiastic only appropriate for positive reviews
    effective_tone = tone
    if tone == "enthusiastic" and rating <= 2:
        effective_tone = "empathetic"

    # Generate responses
    response = build_response(
        rating, reviewer, effective_tone,
        positive_mentions, negative_mentions,
        platform, brand,
    )

    # Platform-specific guidelines
    rec_words = PLATFORM_WORD_RECOMMENDATIONS.get(platform, 150)
    max_len_note = f"{rec_words} words recommended"
    if platform:
        max_len_note += f" for {platform.title()}"

    output = {
        "review_analysis": {
            "rating": rating,
            "sentiment": sentiment,
            "key_issues": key_issues,
            "positive_mentions": positive_mentions,
            "negative_mentions": negative_mentions,
        },
        "response": response,
        "response_guidelines": {
            "max_length": max_len_note,
            "include_keywords": rating <= 3,
            "mention_business_name": True,
            "avoid": ["defensive language", "excuses", "generic responses"],
        },
        "escalation": {
            "needed": escalation_needed,
            "reason": escalation_reason,
        },
    }

    if effective_tone != tone:
        output["tone_override"] = {
            "requested": tone,
            "applied": effective_tone,
            "reason": "Enthusiastic tone is not appropriate for low-rating reviews",
        }

    if brand:
        output["brand"] = brand

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate structured review response drafts with tone templates"
    )
    parser.add_argument(
        "--review", required=True,
        help="The review text to respond to",
    )
    parser.add_argument(
        "--rating", required=True, type=int, choices=[1, 2, 3, 4, 5],
        help="Star rating (1-5)",
    )
    parser.add_argument(
        "--platform", default=None,
        help="Platform name (google, yelp, g2, capterra, trustpilot)",
    )
    parser.add_argument(
        "--reviewer", default=None,
        help="Reviewer name for personalized response",
    )
    parser.add_argument(
        "--tone", default="professional",
        choices=["professional", "warm", "empathetic", "enthusiastic"],
        help="Response tone (default: professional)",
    )
    parser.add_argument(
        "--brand", type=_common.path_component, default=None,
        help="Brand slug for context (optional)",
    )
    args = parser.parse_args()

    # Validation
    if not args.review.strip():
        json.dump({"error": "Review text cannot be empty"}, sys.stdout, indent=2)
        print()
        sys.exit(0)

    platform = args.platform.lower().strip() if args.platform else None

    try:
        result = analyze_review(
            review=args.review,
            rating=args.rating,
            platform=platform,
            reviewer=args.reviewer,
            tone=args.tone,
            brand=args.brand,
        )
        _common.finish(result)
    except Exception as exc:
        json.dump({"error": f"Analysis failed: {exc}"}, sys.stdout, indent=2)
        print()


if __name__ == "__main__":
    main()
