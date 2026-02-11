#!/usr/bin/env python3
"""Format content for specific social media platforms with character limits and rules."""

import argparse
import json
import re
import sys

# Platform specifications: character limits, hashtag limits, and content types
PLATFORM_SPECS = {
    "twitter": {
        "name": "Twitter / X",
        "limits": {
            "post": {"chars": 280, "hashtags": 5, "links": 1},
            "thread": {"chars": 280, "note": "Per tweet in thread; split at sentence boundaries"},
        },
        "mention_format": "@username",
        "features": ["polls", "spaces", "communities"],
    },
    "instagram": {
        "name": "Instagram",
        "limits": {
            "post": {"chars": 2200, "hashtags": 30, "display_chars": 125},
            "reel": {"chars": 2200, "hashtags": 30, "display_chars": 55},
            "story": {"chars": 250, "hashtags": 10},
        },
        "mention_format": "@username",
        "features": ["carousel", "reels", "stories", "guides"],
        "notes": ["First 125 chars show before 'more' on feed posts", "Hashtags can go in first comment"],
    },
    "linkedin": {
        "name": "LinkedIn",
        "limits": {
            "post": {"chars": 3000, "hashtags": 5, "display_chars": 140},
            "article": {"chars": 120000, "hashtags": 5},
        },
        "mention_format": "@Name",
        "features": ["articles", "newsletters", "polls", "documents"],
        "notes": ["First 140 chars show before 'see more'", "3-5 hashtags recommended"],
    },
    "facebook": {
        "name": "Facebook",
        "limits": {
            "post": {"chars": 63206, "hashtags": 5, "display_chars": 477},
            "story": {"chars": 250, "hashtags": 5},
        },
        "mention_format": "@Page or @Person",
        "features": ["reels", "stories", "groups", "events"],
        "notes": ["Posts over 477 chars get truncated with 'See more'"],
    },
    "tiktok": {
        "name": "TikTok",
        "limits": {
            "post": {"chars": 4000, "hashtags": 5},
            "reel": {"chars": 4000, "hashtags": 5},
        },
        "mention_format": "@username",
        "features": ["duets", "stitches", "live"],
        "notes": ["Shorter captions tend to perform better", "Hashtags count toward char limit"],
    },
    "threads": {
        "name": "Threads",
        "limits": {
            "post": {"chars": 500, "hashtags": 5, "links": 1},
        },
        "mention_format": "@username",
        "features": ["polls", "carousel"],
        "notes": ["500 character limit per post", "Supports up to 10 images per carousel"],
    },
    "bluesky": {
        "name": "Bluesky",
        "limits": {
            "post": {"chars": 300, "hashtags": 0, "links": 1},
        },
        "mention_format": "@handle.bsky.social",
        "features": ["custom feeds", "starter packs"],
        "notes": ["300 character limit", "No native hashtag support — uses facets for links/mentions"],
    },
    "pinterest": {
        "name": "Pinterest",
        "limits": {
            "post": {"chars": 500, "hashtags": 20, "title_chars": 100},
        },
        "mention_format": "@username",
        "features": ["idea pins", "boards", "sections"],
        "notes": ["First 50 chars of description show in feed"],
    },
    "youtube": {
        "name": "YouTube",
        "limits": {
            "post": {"chars": 5000, "hashtags": 15, "title_chars": 100},
            "story": {"chars": 200, "hashtags": 5},
        },
        "mention_format": "@channel",
        "features": ["shorts", "community posts", "live"],
        "notes": ["First 100 chars of description visible without expand", "Max 15 hashtags in description"],
    },
}


def count_hashtags(text):
    """Count hashtags in text."""
    return len(re.findall(r"#\w+", text))


def extract_hashtags(text):
    """Extract hashtags from text."""
    return re.findall(r"#\w+", text)


def count_mentions(text):
    """Count mentions in text."""
    return len(re.findall(r"@\w+", text))


def count_links(text):
    """Count URLs in text."""
    return len(re.findall(r"https?://\S+", text))


def truncate_text(text, limit):
    """Truncate text at a word boundary with ellipsis."""
    if len(text) <= limit:
        return text
    truncated = text[: limit - 3]
    # Try to break at last space
    last_space = truncated.rfind(" ")
    if last_space > limit * 0.5:
        truncated = truncated[:last_space]
    return truncated.rstrip() + "..."


def split_thread(text, char_limit=280):
    """Split text into thread-sized chunks at sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    tweets = []
    current = ""

    for sentence in sentences:
        if not sentence.strip():
            continue
        test = (current + " " + sentence).strip() if current else sentence
        if len(test) <= char_limit:
            current = test
        else:
            if current:
                tweets.append(current)
            if len(sentence) <= char_limit:
                current = sentence
            else:
                # Force-split long sentences
                while len(sentence) > char_limit:
                    tweets.append(truncate_text(sentence, char_limit))
                    sentence = sentence[char_limit - 3:].lstrip()
                current = sentence

    if current:
        tweets.append(current)

    return tweets


def format_for_platform(text, platform, content_type="post"):
    """Format text for a specific platform and return analysis."""
    if not text or not text.strip():
        return {"error": "Empty text provided"}

    platform = platform.lower()
    if platform not in PLATFORM_SPECS:
        return {
            "error": f"Unknown platform: {platform}",
            "supported_platforms": list(PLATFORM_SPECS.keys()),
        }

    spec = PLATFORM_SPECS[platform]
    type_limits = spec["limits"].get(content_type)
    if not type_limits:
        available = list(spec["limits"].keys())
        return {
            "error": f"Content type '{content_type}' not supported for {spec['name']}",
            "available_types": available,
        }

    char_limit = type_limits["chars"]
    hashtag_limit = type_limits.get("hashtags", 30)
    display_chars = type_limits.get("display_chars")
    link_limit = type_limits.get("links")

    # Analysis
    char_count = len(text)
    hashtag_count = count_hashtags(text)
    mention_count = count_mentions(text)
    link_count = count_links(text)
    hashtags_found = extract_hashtags(text)

    warnings = []

    # Character limit check
    is_over_limit = char_count > char_limit
    if is_over_limit:
        warnings.append(f"Text exceeds {spec['name']} limit by {char_count - char_limit} characters")

    # Hashtag limit check
    if hashtag_count > hashtag_limit:
        warnings.append(f"Too many hashtags ({hashtag_count}/{hashtag_limit})")

    # Link limit check
    if link_limit and link_count > link_limit:
        warnings.append(f"Too many links ({link_count}/{link_limit})")

    # Display truncation warning
    if display_chars and char_count > display_chars:
        warnings.append(f"Text will be truncated after {display_chars} chars in feed view")

    # Format the text
    formatted_text = text.strip()
    thread_parts = None

    if is_over_limit:
        if content_type == "thread" or platform == "twitter":
            thread_parts = split_thread(formatted_text, char_limit)
            formatted_text = thread_parts[0] if thread_parts else truncate_text(formatted_text, char_limit)
        else:
            formatted_text = truncate_text(formatted_text, char_limit)

    result = {
        "platform": spec["name"],
        "content_type": content_type,
        "original_length": char_count,
        "character_limit": char_limit,
        "formatted_text": formatted_text,
        "formatted_length": len(formatted_text),
        "within_limit": not is_over_limit,
        "hashtags": {
            "count": hashtag_count,
            "limit": hashtag_limit,
            "found": hashtags_found,
        },
        "mentions_count": mention_count,
        "link_count": link_count,
        "mention_format": spec["mention_format"],
    }

    if display_chars:
        preview = text[:display_chars]
        result["feed_preview"] = preview + ("..." if char_count > display_chars else "")

    if thread_parts and len(thread_parts) > 1:
        result["thread"] = {
            "total_parts": len(thread_parts),
            "parts": [{"part": i + 1, "text": part, "chars": len(part)} for i, part in enumerate(thread_parts)],
        }

    if warnings:
        result["warnings"] = warnings

    if spec.get("notes"):
        result["platform_tips"] = spec["notes"]

    return result


def main():
    parser = argparse.ArgumentParser(description="Format content for social media platforms")
    parser.add_argument("--text", required=True, help="Content text to format")
    parser.add_argument("--platform", required=True,
                        choices=list(PLATFORM_SPECS.keys()),
                        help="Target social media platform")
    parser.add_argument("--type", dest="content_type", default="post",
                        choices=["post", "reel", "story", "thread", "article"],
                        help="Content type (default: post)")
    args = parser.parse_args()

    if not args.text.strip():
        print(json.dumps({"error": "Text cannot be empty"}))
        sys.exit(1)

    result = format_for_platform(args.text, args.platform, args.content_type)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
