#!/usr/bin/env python3
"""
content-repurposer.py
=====================
Content repurposing planner that takes original content metadata and generates
a derivative matrix with platform-specific adaptations, effort estimates, and a
suggested content calendar.

Dependencies: none (stdlib only)

Usage:
    python content-repurposer.py --content-type blog --title "10 Ways to Improve Email Open Rates"
    python content-repurposer.py --content-type webinar --title "Q1 Strategy Deep Dive" --key-points '["Point A","Point B"]'
    python content-repurposer.py --content-type podcast --title "Interview with CEO" --platforms '["twitter","linkedin","youtube"]' --brand acme
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

# ---------------------------------------------------------------------------
# Repurposing matrix — maps source content type to derivative formats
# ---------------------------------------------------------------------------

REPURPOSING_MAP = {
    "blog": [
        {
            "format": "Twitter/X Thread",
            "platform": "twitter",
            "description": "Multi-tweet thread, one key point per tweet with supporting data",
            "effort": "low",
            "estimated_time": "30 min",
            "key_adaptations": ["Shorten to 280 chars per point", "Add relevant hashtags", "End with CTA to full post"],
        },
        {
            "format": "LinkedIn Post",
            "platform": "linkedin",
            "description": "Professional long-form post summarising key insights with personal commentary",
            "effort": "low",
            "estimated_time": "30 min",
            "key_adaptations": ["Open with a hook or bold statement", "Use line breaks for readability", "Add 3-5 relevant hashtags"],
        },
        {
            "format": "Instagram Carousel",
            "platform": "instagram",
            "description": "Visual slide deck (8-10 slides) with one takeaway per slide",
            "effort": "medium",
            "estimated_time": "1.5 hours",
            "key_adaptations": ["Design branded slide templates", "Keep text under 30 words per slide", "Final slide = CTA"],
        },
        {
            "format": "Email Newsletter Excerpt",
            "platform": "email",
            "description": "Newsletter section featuring top 3 takeaways with link to full post",
            "effort": "low",
            "estimated_time": "20 min",
            "key_adaptations": ["Write a compelling subject line", "Excerpt the strongest 3 points", "Include a clear read-more CTA"],
        },
        {
            "format": "Infographic Outline",
            "platform": "general",
            "description": "Visual summary of key data points and takeaways for design team",
            "effort": "medium",
            "estimated_time": "1 hour",
            "key_adaptations": ["Extract all statistics and numbers", "Create a visual hierarchy", "Include source attribution"],
        },
        {
            "format": "Video Script Outline",
            "platform": "youtube",
            "description": "Short-form video script (2-3 min) covering the blog's core message",
            "effort": "medium",
            "estimated_time": "1 hour",
            "key_adaptations": ["Write a hook for the first 5 seconds", "Simplify language for spoken delivery", "Add B-roll suggestions"],
        },
        {
            "format": "Podcast Talking Points",
            "platform": "podcast",
            "description": "Discussion guide with key points, questions, and anecdotes",
            "effort": "low",
            "estimated_time": "30 min",
            "key_adaptations": ["Frame as conversation starters", "Add personal experience angles", "Include listener questions"],
        },
        {
            "format": "Pinterest Pin",
            "platform": "pinterest",
            "description": "Vertical pin graphic with blog title, key stat, and link",
            "effort": "low",
            "estimated_time": "20 min",
            "key_adaptations": ["Use 2:3 aspect ratio", "Bold headline text overlay", "Include blog URL"],
        },
    ],
    "webinar": [
        {
            "format": "Blog Post Series (3-5 posts)",
            "platform": "blog",
            "description": "Break webinar content into 3-5 focused blog posts, one per topic",
            "effort": "high",
            "estimated_time": "4 hours",
            "key_adaptations": ["Expand each section with written context", "Add internal links between posts", "Optimise each post for SEO"],
        },
        {
            "format": "Social Media Clips (5-8)",
            "platform": "multi",
            "description": "Short video clips (30-90 sec) of key moments from the recording",
            "effort": "medium",
            "estimated_time": "2 hours",
            "key_adaptations": ["Add captions/subtitles", "Include speaker name overlay", "End each clip with webinar replay CTA"],
        },
        {
            "format": "Email Follow-Up Sequence",
            "platform": "email",
            "description": "3-email drip: thank-you + replay, key takeaways, related resource",
            "effort": "medium",
            "estimated_time": "1.5 hours",
            "key_adaptations": ["Personalise with attendee name", "Segment by attendee vs. no-show", "Include replay link and slides"],
        },
        {
            "format": "Slide Deck Summary",
            "platform": "slideshare",
            "description": "Condensed version of presentation slides for sharing/download",
            "effort": "low",
            "estimated_time": "45 min",
            "key_adaptations": ["Remove speaker-only slides", "Add context notes to key slides", "Include company branding"],
        },
        {
            "format": "FAQ Document",
            "platform": "general",
            "description": "Compiled Q&A from the webinar session for support/sales use",
            "effort": "low",
            "estimated_time": "30 min",
            "key_adaptations": ["Group questions by theme", "Expand brief answers", "Add links to relevant resources"],
        },
        {
            "format": "Podcast Episode",
            "platform": "podcast",
            "description": "Audio-only version or discussion episode reviewing webinar content",
            "effort": "medium",
            "estimated_time": "1.5 hours",
            "key_adaptations": ["Add intro/outro context", "Remove visual-dependent segments", "Include additional commentary"],
        },
    ],
    "podcast": [
        {
            "format": "Blog Post",
            "platform": "blog",
            "description": "Written article based on episode content with expanded context",
            "effort": "medium",
            "estimated_time": "1.5 hours",
            "key_adaptations": ["Restructure for reading flow", "Add headers and formatting", "Embed audio player"],
        },
        {
            "format": "Social Media Audiograms",
            "platform": "multi",
            "description": "30-60 second audio clips with waveform animation for social sharing",
            "effort": "medium",
            "estimated_time": "1 hour",
            "key_adaptations": ["Select most engaging soundbites", "Add captions overlay", "Include episode info"],
        },
        {
            "format": "Quote Graphics",
            "platform": "instagram",
            "description": "Branded quote cards featuring key statements from the episode",
            "effort": "low",
            "estimated_time": "30 min",
            "key_adaptations": ["Attribute quotes to speaker", "Use brand fonts and colours", "Include episode number"],
        },
        {
            "format": "Newsletter Feature",
            "platform": "email",
            "description": "Episode summary with key takeaways and listen link",
            "effort": "low",
            "estimated_time": "20 min",
            "key_adaptations": ["Write a compelling teaser", "Highlight 3 key moments", "Include direct listen links"],
        },
        {
            "format": "YouTube Video/Clips",
            "platform": "youtube",
            "description": "Full episode with static image or short highlight clips",
            "effort": "medium",
            "estimated_time": "1 hour",
            "key_adaptations": ["Add chapter markers", "Create custom thumbnail", "Write SEO-optimised description"],
        },
    ],
    "video": [
        {
            "format": "Blog Post",
            "platform": "blog",
            "description": "Written article based on video content with embedded video",
            "effort": "medium",
            "estimated_time": "1.5 hours",
            "key_adaptations": ["Transcribe and restructure for reading", "Add screenshots as images", "Embed original video"],
        },
        {
            "format": "Short-Form Clips (Reels/TikTok/Shorts)",
            "platform": "multi",
            "description": "3-5 vertical clips (15-60 sec) of key moments",
            "effort": "medium",
            "estimated_time": "1.5 hours",
            "key_adaptations": ["Crop to 9:16 vertical format", "Add captions", "Hook within first 2 seconds"],
        },
        {
            "format": "Thumbnail + Quote Graphics",
            "platform": "instagram",
            "description": "Eye-catching thumbnail and branded quote cards from the video",
            "effort": "low",
            "estimated_time": "30 min",
            "key_adaptations": ["Use high-contrast text", "Include speaker/brand logo", "Match brand colour palette"],
        },
        {
            "format": "Full Transcription",
            "platform": "general",
            "description": "Complete transcript for accessibility, SEO, and content repurposing",
            "effort": "low",
            "estimated_time": "30 min",
            "key_adaptations": ["Add speaker labels", "Include timestamps", "Clean up filler words"],
        },
        {
            "format": "LinkedIn Post",
            "platform": "linkedin",
            "description": "Professional summary post with video embed or key insight",
            "effort": "low",
            "estimated_time": "20 min",
            "key_adaptations": ["Lead with the key insight", "Tag relevant people/companies", "Add 3-5 hashtags"],
        },
    ],
    "whitepaper": [
        {
            "format": "Blog Series (3-5 posts)",
            "platform": "blog",
            "description": "Break whitepaper into digestible chapter-based blog posts",
            "effort": "high",
            "estimated_time": "4 hours",
            "key_adaptations": ["Simplify academic language", "Add visuals and callout boxes", "Link to full whitepaper download"],
        },
        {
            "format": "Infographic",
            "platform": "general",
            "description": "Visual summary of key findings and statistics",
            "effort": "high",
            "estimated_time": "3 hours",
            "key_adaptations": ["Extract top 5-7 data points", "Design visual flow", "Include source citations"],
        },
        {
            "format": "Webinar Outline",
            "platform": "webinar",
            "description": "Presentation outline for a live discussion of the findings",
            "effort": "medium",
            "estimated_time": "1.5 hours",
            "key_adaptations": ["Create discussion questions", "Design presentation slides", "Plan Q&A section"],
        },
        {
            "format": "Social Proof Snippets",
            "platform": "multi",
            "description": "Data-backed social media posts highlighting key statistics",
            "effort": "low",
            "estimated_time": "30 min",
            "key_adaptations": ["Lead with the statistic", "Add context in 1-2 sentences", "Link to download"],
        },
        {
            "format": "Email Drip Series",
            "platform": "email",
            "description": "3-5 email sequence revealing insights and driving to download",
            "effort": "medium",
            "estimated_time": "2 hours",
            "key_adaptations": ["One key insight per email", "Build curiosity across sequence", "Final email = full download CTA"],
        },
    ],
    "case_study": [
        {
            "format": "Social Proof Posts",
            "platform": "multi",
            "description": "Results-focused posts highlighting metrics and outcomes",
            "effort": "low",
            "estimated_time": "30 min",
            "key_adaptations": ["Lead with the headline result", "Include before/after metrics", "Tag the customer (if permitted)"],
        },
        {
            "format": "Sales Deck Slide",
            "platform": "general",
            "description": "One-slide summary for inclusion in sales presentations",
            "effort": "low",
            "estimated_time": "20 min",
            "key_adaptations": ["Challenge > Solution > Result format", "Include customer logo", "Bold the key metric"],
        },
        {
            "format": "Testimonial Graphics",
            "platform": "instagram",
            "description": "Branded quote cards with customer testimonial and results",
            "effort": "low",
            "estimated_time": "30 min",
            "key_adaptations": ["Use customer photo if available", "Highlight quantified results", "Match brand style"],
        },
        {
            "format": "Blog Post",
            "platform": "blog",
            "description": "Expanded narrative version of the case study",
            "effort": "medium",
            "estimated_time": "1.5 hours",
            "key_adaptations": ["Add storytelling elements", "Include process details", "Optimise for SEO"],
        },
        {
            "format": "Email Snippet",
            "platform": "email",
            "description": "Short case study highlight for newsletter or nurture sequence",
            "effort": "low",
            "estimated_time": "15 min",
            "key_adaptations": ["3-sentence summary", "Include headline metric", "Link to full case study"],
        },
    ],
    "report": [
        {
            "format": "Data Visualization Set",
            "platform": "general",
            "description": "Charts and graphs extracted/recreated for standalone use",
            "effort": "high",
            "estimated_time": "3 hours",
            "key_adaptations": ["Ensure brand-consistent styling", "Add clear labels and legends", "Include source attribution"],
        },
        {
            "format": "Blog Series",
            "platform": "blog",
            "description": "Multi-post series covering report sections individually",
            "effort": "high",
            "estimated_time": "4 hours",
            "key_adaptations": ["Make each post standalone", "Add expert commentary", "Link to full report download"],
        },
        {
            "format": "Social Data Cards",
            "platform": "multi",
            "description": "Shareable graphic cards with one key statistic each",
            "effort": "medium",
            "estimated_time": "1.5 hours",
            "key_adaptations": ["One stat per card", "Bold number + short context", "Consistent card design"],
        },
        {
            "format": "PR Pitch Angles",
            "platform": "general",
            "description": "Press-ready angles and soundbites derived from report findings",
            "effort": "medium",
            "estimated_time": "1 hour",
            "key_adaptations": ["Frame as newsworthy findings", "Prepare spokesperson quotes", "Include supporting data"],
        },
        {
            "format": "Webinar Content",
            "platform": "webinar",
            "description": "Live presentation walking through key findings and implications",
            "effort": "medium",
            "estimated_time": "2 hours",
            "key_adaptations": ["Build narrative around data", "Prepare interactive polls", "Plan Q&A around methodology"],
        },
    ],
    "infographic": [
        {
            "format": "Social Media Segments",
            "platform": "multi",
            "description": "Cropped sections posted as individual social media images",
            "effort": "low",
            "estimated_time": "30 min",
            "key_adaptations": ["Crop to platform-optimal dimensions", "Add individual captions", "Post as a series over several days"],
        },
        {
            "format": "Blog with Expanded Data",
            "platform": "blog",
            "description": "Blog post using the infographic as hero image with written analysis",
            "effort": "medium",
            "estimated_time": "1.5 hours",
            "key_adaptations": ["Expand each data point into paragraphs", "Add context and sources", "Embed the full infographic"],
        },
        {
            "format": "Email Visual",
            "platform": "email",
            "description": "Condensed version or key section for email newsletter",
            "effort": "low",
            "estimated_time": "20 min",
            "key_adaptations": ["Optimise file size for email clients", "Use top section only", "Add alt text"],
        },
        {
            "format": "Presentation Slide",
            "platform": "general",
            "description": "Adapted version for inclusion in slide decks",
            "effort": "low",
            "estimated_time": "20 min",
            "key_adaptations": ["Reformat to 16:9 layout", "Simplify if needed", "Add speaker notes"],
        },
    ],
    "presentation": [
        {
            "format": "Blog Post",
            "platform": "blog",
            "description": "Written article expanding on the presentation content",
            "effort": "medium",
            "estimated_time": "1.5 hours",
            "key_adaptations": ["Add written context for each slide", "Embed key slides as images", "Optimise for SEO"],
        },
        {
            "format": "Social Key Slides",
            "platform": "multi",
            "description": "Most impactful slides shared as individual social posts",
            "effort": "low",
            "estimated_time": "30 min",
            "key_adaptations": ["Select 3-5 most visual slides", "Add contextual captions", "Include link to full deck"],
        },
        {
            "format": "Video Walkthrough",
            "platform": "youtube",
            "description": "Narrated screen recording walking through the presentation",
            "effort": "medium",
            "estimated_time": "1.5 hours",
            "key_adaptations": ["Record voiceover narration", "Add transitions", "Include intro and outro"],
        },
        {
            "format": "Handout/PDF Summary",
            "platform": "general",
            "description": "Condensed PDF with key slides and notes for download",
            "effort": "low",
            "estimated_time": "30 min",
            "key_adaptations": ["Remove animation-dependent slides", "Add written summaries", "Include contact info/CTA"],
        },
    ],
}

VALID_CONTENT_TYPES = set(REPURPOSING_MAP.keys())

# Time string to minutes for aggregation
TIME_TO_MINUTES = {
    "15 min": 15, "20 min": 20, "30 min": 30, "45 min": 45,
    "1 hour": 60, "1.5 hours": 90, "2 hours": 120,
    "3 hours": 180, "4 hours": 240,
}


def minutes_to_display(total_minutes):
    """Convert minutes to a human-readable time string."""
    if total_minutes < 60:
        return f"{total_minutes} min"
    hours = total_minutes / 60.0
    if hours == int(hours):
        return f"{int(hours)} hours"
    return f"{hours:.1f} hours"


# ---------------------------------------------------------------------------
# Plan generation
# ---------------------------------------------------------------------------

def filter_by_platforms(derivatives, platforms):
    """Filter derivative list to only include requested platforms."""
    if not platforms:
        return derivatives
    platform_set = set(platforms)
    # Always include 'general' and 'multi' platform items
    platform_set.add("general")
    platform_set.add("multi")
    return [d for d in derivatives if d["platform"] in platform_set]


def build_calendar(derivatives, content_type, title):
    """Generate a suggested content calendar with staggered release days."""
    calendar = [{"day": 0, "format": f"Original {content_type} published: {title}"}]

    # Sort by effort: low first, then medium, then high
    effort_order = {"low": 0, "medium": 1, "high": 2}
    sorted_derivs = sorted(derivatives, key=lambda d: effort_order.get(d["effort"], 1))

    day = 1
    for deriv in sorted_derivs:
        calendar.append({"day": day, "format": deriv["format"]})
        # Space items based on effort
        if deriv["effort"] == "low":
            day += 1
        elif deriv["effort"] == "medium":
            day += 2
        else:
            day += 3

    return calendar


def generate_plan(content_type, title, key_points, platforms, brand):
    """Build the full repurposing plan output."""
    derivatives = REPURPOSING_MAP.get(content_type, [])
    if not derivatives:
        return {"error": f"No repurposing templates for content type: {content_type}"}

    # Deep copy to avoid mutating the template
    derivatives = [dict(d) for d in derivatives]

    # Filter by platform preference
    filtered = filter_by_platforms(derivatives, platforms)

    # Calculate statistics
    total_pieces = len(filtered)
    total_minutes = sum(TIME_TO_MINUTES.get(d["estimated_time"], 60) for d in filtered)
    # +1 for the original piece itself
    roi_multiplier = f"{total_pieces + 1}x"

    # Build calendar
    calendar = build_calendar(filtered, content_type, title)

    output = {
        "original": {
            "type": content_type,
            "title": title,
        },
        "repurposing_plan": filtered,
        "total_derivatives": total_pieces,
        "content_calendar_suggestion": calendar,
        "key_points_used": key_points if key_points else [],
        "statistics": {
            "total_derivative_pieces": total_pieces,
            "estimated_total_time": minutes_to_display(total_minutes),
            "content_roi_multiplier": roi_multiplier,
        },
    }

    if brand:
        output["brand"] = brand

    if platforms:
        output["target_platforms"] = platforms

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Content repurposing planner and derivative matrix generator"
    )
    parser.add_argument(
        "--content-type", required=True,
        choices=sorted(VALID_CONTENT_TYPES),
        help="Original content type",
    )
    parser.add_argument(
        "--title", required=True,
        help="Content title",
    )
    parser.add_argument(
        "--key-points", default=None,
        help="JSON array of key takeaways/data points from the content",
    )
    parser.add_argument(
        "--platforms", default=None,
        help="JSON array of target platforms (default: all common platforms)",
    )
    parser.add_argument(
        "--brand", type=_common.path_component, default=None,
        help="Brand slug for voice context",
    )
    args = parser.parse_args()

    # --- Parse optional JSON arguments ---
    key_points = None
    if args.key_points:
        try:
            key_points = json.loads(args.key_points)
            if not isinstance(key_points, list):
                json.dump({"error": "key-points must be a JSON array of strings"}, sys.stdout, indent=2)
                print()
                return
        except json.JSONDecodeError as exc:
            json.dump({"error": f"Invalid JSON in --key-points: {exc}"}, sys.stdout, indent=2)
            print()
            return

    platforms = None
    if args.platforms:
        try:
            platforms = json.loads(args.platforms)
            if not isinstance(platforms, list):
                json.dump({"error": "platforms must be a JSON array of strings"}, sys.stdout, indent=2)
                print()
                return
        except json.JSONDecodeError as exc:
            json.dump({"error": f"Invalid JSON in --platforms: {exc}"}, sys.stdout, indent=2)
            print()
            return

    # --- Validate title ---
    if not args.title.strip():
        json.dump({"error": "Title cannot be empty"}, sys.stdout, indent=2)
        print()
        return

    # --- Generate plan ---
    output = generate_plan(args.content_type, args.title.strip(), key_points, platforms, args.brand)

    json.dump(output, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
