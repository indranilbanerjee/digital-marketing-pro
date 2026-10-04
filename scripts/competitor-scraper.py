#!/usr/bin/env python3
"""Extract public competitor data from URLs with robots.txt respect and rate limiting."""

import argparse
import json
import re
import sys
import time
import random
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# The scraper names itself. Site owners can see who fetched their pages and
# write robots.txt rules for this token; rotating browser user-agents would
# hide the scraper from exactly those rules.
ROBOTS_TOKEN = "DigitalMarketingPro-CompetitorScraper"
USER_AGENT = f"{ROBOTS_TOKEN}/1.0 (+https://github.com/indranilbanerjee/digital-marketing-pro)"

SOCIAL_DOMAINS = {
    "facebook.com": "Facebook", "fb.com": "Facebook",
    "twitter.com": "Twitter", "x.com": "Twitter",
    "linkedin.com": "LinkedIn",
    "instagram.com": "Instagram",
    "youtube.com": "YouTube", "youtu.be": "YouTube",
    "tiktok.com": "TikTok",
    "pinterest.com": "Pinterest",
    "github.com": "GitHub",
}

TECH_SIGNALS = {
    "wp-content": "WordPress", "wp-includes": "WordPress",
    "shopify": "Shopify", "cdn.shopify.com": "Shopify",
    "squarespace": "Squarespace",
    "wix.com": "Wix",
    "hubspot": "HubSpot", "hs-scripts.com": "HubSpot",
    "google-analytics.com": "Google Analytics", "gtag": "Google Analytics",
    "googletagmanager.com": "Google Tag Manager",
    "fbevents.js": "Facebook Pixel", "connect.facebook.net": "Facebook Pixel",
    "hotjar.com": "Hotjar",
    "cloudflare": "Cloudflare",
    "react": "React", "_next": "Next.js",
    "bootstrap": "Bootstrap", "tailwind": "Tailwind CSS",
}


def robots_verdict(status_code, robots_text, url, agent=ROBOTS_TOKEN):
    """Decide from a robots.txt response whether `agent` may fetch `url`.

    RFC 9309 section 2.3.1: a 4xx robots.txt means no restrictions; a 5xx or an
    unreachable one means the crawler must assume complete disallow. A rule
    group for this scraper's own token wins over the `*` group, and Allow
    lines count.
    """
    if status_code is None or status_code >= 500:
        return False, "robots.txt unreachable; treated as disallow (RFC 9309)"
    if 400 <= status_code < 500:
        return True, f"robots.txt returned {status_code}; no restrictions (RFC 9309)"
    rp = RobotFileParser()
    rp.parse((robots_text or "").splitlines())
    if rp.can_fetch(agent, url):
        return True, "Allowed by robots.txt"
    return False, f"Blocked by robots.txt for {agent}"


def check_robots_txt(url):
    """Check if scraping is allowed by robots.txt. Returns (allowed, message)."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = requests.get(robots_url, timeout=5, headers={"User-Agent": USER_AGENT})
    except requests.RequestException:
        return robots_verdict(None, "", url)
    return robots_verdict(resp.status_code, resp.text, url)


def extract_headings(soup):
    """Extract H1-H3 headings."""
    headings = {}
    for level in ["h1", "h2", "h3"]:
        tags = soup.find_all(level)
        if tags:
            headings[level] = [tag.get_text(strip=True) for tag in tags]
    return headings


def extract_social_links(soup, base_url):
    """Find social media links."""
    social = []
    seen = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        parsed = urlparse(href)
        domain = parsed.netloc.replace("www.", "")
        for social_domain, platform in SOCIAL_DOMAINS.items():
            if social_domain in domain and href not in seen:
                social.append({"platform": platform, "url": href})
                seen.add(href)
                break
    return social


def detect_schema_types(soup):
    """Find JSON-LD and microdata schema types."""
    schemas = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                for item in data:
                    if "@type" in item:
                        schemas.append(item["@type"])
            elif "@type" in data:
                schemas.append(data["@type"])
        except (json.JSONDecodeError, TypeError):
            pass
    for tag in soup.find_all(attrs={"itemtype": True}):
        schema_url = tag.get("itemtype", "")
        schema_type = schema_url.split("/")[-1] if "/" in schema_url else schema_url
        if schema_type:
            schemas.append(schema_type)
    return list(set(schemas))


def detect_technologies(html_text):
    """Detect technologies from page source."""
    found = set()
    html_lower = html_text.lower()
    for signal, tech in TECH_SIGNALS.items():
        if signal.lower() in html_lower:
            found.add(tech)
    return sorted(found)


def scrape_url(url):
    """Main scraping function."""
    if not url.startswith("http"):
        url = "https://" + url

    allowed, robots_msg = check_robots_txt(url)
    if not allowed:
        return {"error": robots_msg, "url": url}

    # Rate limiting: small delay
    time.sleep(random.uniform(0.5, 1.5))

    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, timeout=15, headers=headers, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException as e:
        return {"error": f"Request failed: {str(e)}", "url": url}

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_kw_tag = soup.find("meta", attrs={"name": "keywords"})
    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    og_title = soup.find("meta", attrs={"property": "og:title"})
    og_desc = soup.find("meta", attrs={"property": "og:description"})

    result = {
        "url": url,
        "final_url": resp.url,
        "status_code": resp.status_code,
        "title": title_tag.get_text(strip=True) if title_tag else None,
        "meta_description": meta_desc_tag.get("content", "").strip() if meta_desc_tag else None,
        "meta_keywords": meta_kw_tag.get("content", "").strip() if meta_kw_tag else None,
        "canonical": canonical_tag.get("href", "").strip() if canonical_tag else None,
        "og_title": og_title.get("content", "").strip() if og_title else None,
        "og_description": og_desc.get("content", "").strip() if og_desc else None,
        "headings": extract_headings(soup),
        "social_links": extract_social_links(soup, url),
        "schema_types": detect_schema_types(soup),
        "technologies_detected": detect_technologies(html),
        "robots_txt": robots_msg,
        "user_agent": USER_AGENT,
        "legal_disclaimer": (
            "This data was collected from publicly accessible web pages. "
            "No login-protected or paywalled content was accessed. "
            "Use responsibly and in compliance with applicable laws and terms of service."
        ),
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Extract public competitor data from URLs")
    parser.add_argument("--url", required=True, help="Competitor URL to analyze")
    parser.add_argument("--output", default="json", help="Output format (json)")
    args = parser.parse_args()

    if not args.url.strip():
        print(json.dumps({"error": "URL cannot be empty"}))
        sys.exit(1)

    missing = [name for name, mod in (("requests", requests), ("beautifulsoup4", BeautifulSoup)) if mod is None]
    if missing:
        print(json.dumps({
            "fallback": True,
            "error": f"{missing[0]}_not_installed",
            "message": "Competitor scraping requires: pip install " + " ".join(missing),
            "recommendation": "Install dependencies for automated scraping, or analyze competitor pages manually."
        }))
        sys.exit(0)

    result = scrape_url(args.url.strip())
    _common.finish(result)


if __name__ == "__main__":
    main()
