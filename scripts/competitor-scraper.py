#!/usr/bin/env python3
"""Extract public competitor data from URLs with robots.txt respect and rate limiting."""

import argparse
import json
import re
import sys
import time
import random
from urllib.parse import urlparse, urljoin

try:
    import requests
except ImportError:
    print(json.dumps({"error": "Missing dependency: pip install requests"}))
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print(json.dumps({"error": "Missing dependency: pip install beautifulsoup4"}))
    sys.exit(1)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
]

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


def check_robots_txt(url):
    """Check if scraping is allowed by robots.txt. Returns (allowed, message)."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = requests.get(robots_url, timeout=5, headers={"User-Agent": random.choice(USER_AGENTS)})
        if resp.status_code == 200:
            path = parsed.path or "/"
            lines = resp.text.splitlines()
            user_agent_match = False
            for line in lines:
                line = line.strip().lower()
                if line.startswith("user-agent:"):
                    agent = line.split(":", 1)[1].strip()
                    user_agent_match = agent == "*"
                elif user_agent_match and line.startswith("disallow:"):
                    disallowed = line.split(":", 1)[1].strip()
                    if disallowed and path.startswith(disallowed):
                        return False, f"Blocked by robots.txt: {disallowed}"
        return True, "Allowed or no robots.txt restriction found"
    except Exception:
        return True, "Could not fetch robots.txt, proceeding with caution"


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

    headers = {"User-Agent": random.choice(USER_AGENTS)}
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

    result = scrape_url(args.url.strip())
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
