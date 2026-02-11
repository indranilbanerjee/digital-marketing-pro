#!/usr/bin/env python3
"""Batch UTM parameter generation with GA4 channel grouping validation."""

import argparse
import csv
import json
import re
import sys
import io
import base64
from pathlib import Path
from urllib.parse import urlencode, urlparse

# GA4 default channel groupings and their expected source/medium patterns
GA4_CHANNEL_RULES = {
    "Organic Search": {"medium": ["organic"]},
    "Paid Search": {"medium": ["cpc", "ppc", "paid_search"]},
    "Display": {"medium": ["display", "banner", "cpm"]},
    "Paid Social": {"medium": ["paid_social", "paidsocial"], "source": ["facebook", "instagram", "linkedin", "twitter", "tiktok", "pinterest"]},
    "Organic Social": {"medium": ["social", "organic_social"], "source": ["facebook", "instagram", "linkedin", "twitter", "tiktok", "pinterest"]},
    "Email": {"medium": ["email"]},
    "Affiliates": {"medium": ["affiliate"]},
    "Referral": {"medium": ["referral"]},
    "SMS": {"medium": ["sms"]},
    "Video": {"medium": ["video"]},
    "Audio": {"medium": ["audio", "podcast"]},
}


def sanitize_param(value):
    """Lowercase, replace spaces with underscores, strip non-URL-safe chars."""
    if not value:
        return ""
    value = value.strip().lower()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^a-z0-9_\-.]", "", value)
    return value


def validate_base_url(url):
    """Check that a URL has a scheme and netloc."""
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
        parsed = urlparse(url)
    if not parsed.netloc:
        return None, "Invalid URL: no domain found"
    return url, None


def detect_ga4_channel(source, medium):
    """Return the likely GA4 default channel grouping."""
    for channel, rules in GA4_CHANNEL_RULES.items():
        medium_match = medium in rules.get("medium", [])
        source_list = rules.get("source", [])
        if medium_match:
            if source_list and source not in source_list:
                continue
            return channel
    return "Unassigned"


def generate_qr(url):
    """Return a base64-encoded PNG QR code or None if library unavailable."""
    try:
        import qrcode
        from io import BytesIO
        qr = qrcode.make(url)
        buf = BytesIO()
        qr.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except ImportError:
        return None


def build_utm_url(base_url, source, medium, campaign, content="", term="", with_qr=False):
    """Build a single UTM-tagged URL and return a result dict."""
    base_url, err = validate_base_url(base_url)
    if err:
        return {"error": err, "base_url": base_url}

    params = {}
    source = sanitize_param(source)
    medium = sanitize_param(medium)
    campaign = sanitize_param(campaign)
    content = sanitize_param(content)
    term = sanitize_param(term)

    warnings = []
    if not source:
        warnings.append("utm_source is empty")
    if not medium:
        warnings.append("utm_medium is empty")
    if not campaign:
        warnings.append("utm_campaign is empty")

    if source:
        params["utm_source"] = source
    if medium:
        params["utm_medium"] = medium
    if campaign:
        params["utm_campaign"] = campaign
    if content:
        params["utm_content"] = content
    if term:
        params["utm_term"] = term

    separator = "&" if "?" in base_url else "?"
    tagged_url = base_url + separator + urlencode(params) if params else base_url

    channel = detect_ga4_channel(source, medium)

    result = {
        "base_url": base_url,
        "tagged_url": tagged_url,
        "params": params,
        "ga4_channel_grouping": channel,
    }
    if warnings:
        result["warnings"] = warnings
    if with_qr:
        qr_data = generate_qr(tagged_url)
        if qr_data:
            result["qr_code_base64_png"] = qr_data
        else:
            result["qr_code_note"] = "Install 'qrcode' and 'Pillow' packages for QR generation"
    return result


def process_csv(filepath, with_qr=False):
    """Read a CSV with columns: base_url, source, medium, campaign, content, term."""
    path = Path(filepath)
    if not path.exists():
        return {"error": f"File not found: {filepath}"}
    results = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                r = build_utm_url(
                    base_url=row.get("base_url", row.get("url", "")),
                    source=row.get("source", row.get("utm_source", "")),
                    medium=row.get("medium", row.get("utm_medium", "")),
                    campaign=row.get("campaign", row.get("utm_campaign", "")),
                    content=row.get("content", row.get("utm_content", "")),
                    term=row.get("term", row.get("utm_term", "")),
                    with_qr=with_qr,
                )
                r["row"] = i + 1
                results.append(r)
    except Exception as e:
        return {"error": f"CSV parsing failed: {str(e)}"}
    return results


def main():
    parser = argparse.ArgumentParser(description="Batch UTM parameter generation with GA4 validation")
    parser.add_argument("--base-url", help="Base URL to tag")
    parser.add_argument("--campaign", default="", help="Campaign name")
    parser.add_argument("--source", default="", help="Traffic source")
    parser.add_argument("--medium", default="", help="Traffic medium")
    parser.add_argument("--content", default="", help="Ad content identifier")
    parser.add_argument("--term", default="", help="Paid keyword term")
    parser.add_argument("--csv", dest="csv_file", help="CSV file for batch mode")
    parser.add_argument("--qr", action="store_true", help="Generate QR codes")
    args = parser.parse_args()

    if not args.base_url and not args.csv_file:
        parser.error("Provide --base-url or --csv")

    if args.csv_file:
        output = {"mode": "batch", "results": process_csv(args.csv_file, with_qr=args.qr)}
    else:
        result = build_utm_url(
            base_url=args.base_url,
            source=args.source,
            medium=args.medium,
            campaign=args.campaign,
            content=args.content,
            term=args.term,
            with_qr=args.qr,
        )
        output = {"mode": "single", "result": result}

    json.dump(output, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
