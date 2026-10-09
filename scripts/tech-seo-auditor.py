#!/usr/bin/env python3
"""Technical SEO URL auditing tool.

Uses Python's stdlib urllib.request to perform HTTP checks on URLs. Evaluates
status codes, redirect chains, meta tags, HTTP headers, security posture, and
speed hints. Returns a per-URL score (0-100) with categorized issues and an
aggregate summary.

Dependencies: none (stdlib only)

Usage:
    python tech-seo-auditor.py --url "https://example.com"
    python tech-seo-auditor.py --urls '["https://example.com", "https://example.org"]'
    python tech-seo-auditor.py --file urls.txt --checks status,meta,security --timeout 15
"""

import argparse
import gzip
import json
import sys
import time
import zlib
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALL_CHECKS = {"status", "redirects", "meta", "headers", "security", "speed_hints"}
MAX_REDIRECTS = 10
USER_AGENT = "TechSEOAuditor/1.0 (+https://github.com/indranilbanerjee/digital-marketing-pro)"


# ---------------------------------------------------------------------------
# Lightweight HTML meta-tag parser
# ---------------------------------------------------------------------------

class MetaParser(HTMLParser):
    """Extract title, meta description, canonical, viewport, and robots tags."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self.description = ""
        self.canonical = ""
        self.viewport = ""
        self.robots = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = {k.lower(): v for k, v in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = attrs_dict.get("name", "").lower()
            content = attrs_dict.get("content", "")
            if name == "description":
                self.description = content
            elif name == "viewport":
                self.viewport = content
            elif name == "robots":
                self.robots = content
        elif tag == "link":
            rel = attrs_dict.get("rel", "").lower()
            href = attrs_dict.get("href", "")
            if rel == "canonical":
                self.canonical = href

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _build_request(url):
    """Build a urllib Request with standard headers."""
    return Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})


def _decompress_body(body, headers):
    """Decompress gzip/deflate body if Content-Encoding indicates compression."""
    encoding = headers.get("content-encoding", "").lower()
    if "gzip" in encoding:
        try:
            return gzip.decompress(body)
        except Exception:
            return body
    if "deflate" in encoding:
        try:
            return zlib.decompress(body)
        except Exception:
            try:
                # Some servers send raw deflate streams without zlib headers
                return zlib.decompress(body, -zlib.MAX_WBITS)
            except Exception:
                return body
    return body


def follow_redirects(url, timeout):
    """Manually follow redirects, recording each hop.

    Returns (final_url, status_code, hops_list, response_headers, body, ttfb_ms, error).
    """
    hops = []
    current_url = url
    visited = set()

    for _ in range(MAX_REDIRECTS):
        if current_url in visited:
            return current_url, None, hops, {}, b"", 0, "Redirect loop detected"
        visited.add(current_url)

        # Every hop: http/https only, public addresses only (Hermes review).
        unsafe = _common.public_url_error(current_url)
        if unsafe:
            return current_url, None, hops, {}, b"", 0, unsafe

        req = _build_request(current_url)
        try:
            # Use a custom opener that does NOT auto-follow redirects
            import urllib.request as _ur
            class NoRedirectHandler(_ur.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None
            opener = _ur.build_opener(NoRedirectHandler)
            start = time.monotonic()
            resp = opener.open(req, timeout=timeout)
            ttfb_ms = round((time.monotonic() - start) * 1000)
            status = resp.getcode()
            headers = {k.lower(): v for k, v in resp.getheaders()}
            body = _decompress_body(resp.read(), headers)
            return current_url, status, hops, headers, body, ttfb_ms, None

        except HTTPError as exc:
            ttfb_ms = 0
            status = exc.code
            headers = {k.lower(): v for k, v in exc.headers.items()}
            if status in (301, 302, 303, 307, 308):
                location = headers.get("location", "")
                if not location:
                    return current_url, status, hops, headers, b"", ttfb_ms, "Redirect without Location header"
                # Resolve relative redirects (checked as the next hop)
                location = urljoin(current_url, location)
                hops.append({"from": current_url, "to": location, "status": status})
                current_url = location
                continue
            else:
                raw = exc.read() if hasattr(exc, "read") else b""
                body = _decompress_body(raw, headers)
                return current_url, status, hops, headers, body, ttfb_ms, None

        except URLError as exc:
            reason = str(exc.reason) if hasattr(exc, "reason") else str(exc)
            return current_url, None, hops, {}, b"", 0, reason

        except Exception as exc:
            return current_url, None, hops, {}, b"", 0, str(exc)

    return current_url, None, hops, {}, b"", 0, f"Too many redirects (>{MAX_REDIRECTS})"


def fetch_url(url, timeout):
    """Fetch a URL with redirect tracking and return all audit data."""
    # First pass: follow redirects manually
    final_url, status, hops, headers, body, ttfb_ms, error = follow_redirects(url, timeout)
    if error and status is None:
        return {
            "final_url": final_url,
            "status_code": None,
            "hops": hops,
            "headers": headers,
            "body": body,
            "ttfb_ms": ttfb_ms,
            "error": error,
        }
    return {
        "final_url": final_url,
        "status_code": status,
        "hops": hops,
        "headers": headers,
        "body": body,
        "ttfb_ms": ttfb_ms,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------

def check_status(data, issues):
    """Check HTTP status code."""
    status = data["status_code"]
    if status is None:
        issues.append({"severity": "critical", "category": "status", "message": f"URL unreachable: {data.get('error', 'unknown error')}"})
        return -20
    if status != 200:
        issues.append({"severity": "critical", "category": "status", "message": f"Non-200 status code: {status}"})
        return -20
    return 0


def check_redirects(data, issues):
    """Check redirect chain."""
    hops = data["hops"]
    count = len(hops)
    deduction = 0
    if count > 2:
        issues.append({"severity": "high", "category": "redirects", "message": f"Long redirect chain ({count} hops). Recommend 1-2 max."})
        deduction = -10
    return deduction, count


def check_meta(data, url, issues):
    """Parse HTML and check meta tags."""
    result = {
        "title": None, "title_length": 0, "title_status": "missing",
        "description": None, "description_length": 0, "description_status": "missing",
        "canonical": None, "canonical_match": False,
        "viewport": None, "robots": None,
        "noindex": False, "nofollow": False,
    }
    deduction = 0
    body = data.get("body", b"")
    if not body:
        issues.append({"severity": "medium", "category": "meta", "message": "Empty response body; could not parse meta tags"})
        return result, -8

    # Decode body
    content_type = data["headers"].get("content-type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        issues.append({"severity": "low", "category": "meta", "message": f"Content-Type is '{content_type}', not HTML. Skipping meta parse."})
        return result, 0

    try:
        html_text = body.decode("utf-8", errors="replace")
    except Exception:
        html_text = body.decode("latin-1", errors="replace")

    parser = MetaParser()
    try:
        parser.feed(html_text)
    except Exception:
        issues.append({"severity": "medium", "category": "meta", "message": "HTML parsing failed; meta checks incomplete"})
        return result, -5

    # Title
    title = parser.title.strip()
    result["title"] = title if title else None
    result["title_length"] = len(title)
    if not title:
        result["title_status"] = "missing"
        issues.append({"severity": "medium", "category": "meta", "message": "Missing title tag"})
        deduction -= 5
    elif len(title) < 30:
        result["title_status"] = "too_short"
        issues.append({"severity": "medium", "category": "meta", "message": f"Title tag too short ({len(title)} chars, recommend 30-60)"})
        deduction -= 5
    elif len(title) > 60:
        result["title_status"] = "too_long"
        issues.append({"severity": "medium", "category": "meta", "message": f"Title tag too long ({len(title)} chars, recommend 30-60)"})
        deduction -= 5
    else:
        result["title_status"] = "good"

    # Description
    desc = parser.description.strip()
    result["description"] = desc if desc else None
    result["description_length"] = len(desc)
    if not desc:
        result["description_status"] = "missing"
        issues.append({"severity": "low", "category": "meta", "message": "Missing meta description"})
        deduction -= 3
    elif len(desc) < 120:
        result["description_status"] = "too_short"
        issues.append({"severity": "low", "category": "meta", "message": f"Meta description too short ({len(desc)} chars, recommend 120-160)"})
        deduction -= 3
    elif len(desc) > 160:
        result["description_status"] = "too_long"
        issues.append({"severity": "low", "category": "meta", "message": f"Meta description too long ({len(desc)} chars, recommend 120-160)"})
        deduction -= 3
    else:
        result["description_status"] = "good"

    # Canonical
    canonical = parser.canonical.strip()
    result["canonical"] = canonical if canonical else None
    final_url = data.get("final_url", url)
    if canonical:
        # Normalize for comparison: strip trailing slash
        c_norm = canonical.rstrip("/").lower()
        u_norm = final_url.rstrip("/").lower()
        result["canonical_match"] = c_norm == u_norm
    else:
        issues.append({"severity": "medium", "category": "meta", "message": "Missing canonical tag"})
        deduction -= 8

    # Viewport
    viewport = parser.viewport.strip()
    result["viewport"] = viewport if viewport else None
    if not viewport:
        issues.append({"severity": "high", "category": "meta", "message": "Missing viewport meta tag (poor mobile rendering)"})
        deduction -= 10

    # Robots
    robots = parser.robots.strip().lower()
    result["robots"] = robots if robots else None
    result["noindex"] = "noindex" in robots if robots else False
    result["nofollow"] = "nofollow" in robots if robots else False
    if result["noindex"]:
        issues.append({"severity": "critical", "category": "meta", "message": "Page has noindex directive (will be excluded from search)"})
        deduction -= 15

    return result, deduction


def check_headers(data, issues):
    """Check HTTP headers for SEO-relevant values."""
    h = data["headers"]
    result = {
        "x_robots_tag": h.get("x-robots-tag"),
        "content_type": h.get("content-type"),
        "content_encoding": h.get("content-encoding"),
        "cache_control": h.get("cache-control"),
        "hsts": h.get("strict-transport-security"),
        "csp": h.get("content-security-policy") is not None,
    }
    deduction = 0

    if not h.get("cache-control"):
        issues.append({"severity": "low", "category": "headers", "message": "Missing Cache-Control header"})
        deduction -= 3

    x_robots = h.get("x-robots-tag", "")
    if "noindex" in x_robots.lower():
        issues.append({"severity": "critical", "category": "headers", "message": "X-Robots-Tag contains noindex"})
        deduction -= 15

    return result, deduction


def check_security(data, url, issues):
    """Check security-related aspects."""
    parsed = urlparse(url)
    is_https = parsed.scheme == "https"
    hsts_header = data["headers"].get("strict-transport-security", "")
    has_hsts = bool(hsts_header)
    hsts_max_age = 0

    if hsts_header:
        for part in hsts_header.split(";"):
            part = part.strip().lower()
            if part.startswith("max-age="):
                try:
                    hsts_max_age = int(part.split("=")[1])
                except (ValueError, IndexError):
                    pass

    result = {
        "https": is_https,
        "hsts": has_hsts,
        "hsts_max_age": hsts_max_age,
    }
    deduction = 0

    if not is_https:
        issues.append({"severity": "critical", "category": "security", "message": "URL is not served over HTTPS"})
        deduction -= 15
    if not has_hsts:
        issues.append({"severity": "low", "category": "security", "message": "Missing HSTS header (Strict-Transport-Security)"})
        deduction -= 5

    return result, deduction


def check_speed_hints(data, issues):
    """Evaluate speed-related signals."""
    ttfb = data["ttfb_ms"]
    content_encoding = data["headers"].get("content-encoding", "")
    compressed = any(enc in content_encoding.lower() for enc in ("gzip", "br", "deflate"))
    content_length = data["headers"].get("content-length")
    content_length_bytes = int(content_length) if content_length and content_length.isdigit() else len(data.get("body", b""))

    result = {
        "ttfb_ms": ttfb,
        "content_length_bytes": content_length_bytes,
        "compressed": compressed,
    }
    deduction = 0

    if not compressed:
        issues.append({"severity": "medium", "category": "speed_hints", "message": "Response is not compressed (no gzip/br encoding detected)"})
        deduction -= 5

    if ttfb > 3000:
        issues.append({"severity": "critical", "category": "speed_hints", "message": f"Very slow TTFB ({ttfb}ms). Recommend < 1000ms."})
        deduction -= 15
    elif ttfb > 1000:
        issues.append({"severity": "high", "category": "speed_hints", "message": f"Slow TTFB ({ttfb}ms). Recommend < 1000ms."})
        deduction -= 8

    return result, deduction


# ---------------------------------------------------------------------------
# Main audit logic
# ---------------------------------------------------------------------------

def audit_url(url, checks, timeout):
    """Run all requested checks against a single URL and return the result dict."""
    issues = []
    score = 100

    # Fetch the URL
    data = fetch_url(url, timeout)

    result = {
        "url": url,
        "status_code": data["status_code"],
        "response_time_ms": data["ttfb_ms"],
    }

    # Redirects (always populated for structure even if check not selected)
    result["redirects"] = data["hops"]
    result["redirect_count"] = len(data["hops"])

    # Fatal error short-circuit
    if data["error"] and data["status_code"] is None:
        issues.append({"severity": "critical", "category": "status", "message": f"URL unreachable: {data['error']}"})
        result["meta"] = {}
        result["headers"] = {}
        result["security"] = {}
        result["speed_hints"] = {}
        result["issues"] = issues
        result["score"] = 0
        return result

    # Status check
    if "status" in checks:
        score += check_status(data, issues)

    # Redirects check
    if "redirects" in checks:
        deduction, _ = check_redirects(data, issues)
        score += deduction

    # Meta check
    if "meta" in checks:
        meta_result, deduction = check_meta(data, url, issues)
        result["meta"] = meta_result
        score += deduction
    else:
        result["meta"] = {}

    # Headers check
    if "headers" in checks:
        headers_result, deduction = check_headers(data, issues)
        result["headers"] = headers_result
        score += deduction
    else:
        result["headers"] = {}

    # Security check
    if "security" in checks:
        security_result, deduction = check_security(data, url, issues)
        result["security"] = security_result
        score += deduction
    else:
        result["security"] = {}

    # Speed hints
    if "speed_hints" in checks:
        speed_result, deduction = check_speed_hints(data, issues)
        result["speed_hints"] = speed_result
        score += deduction
    else:
        result["speed_hints"] = {}

    result["issues"] = issues
    result["score"] = max(0, min(100, score))
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Technical SEO URL auditing tool"
    )
    parser.add_argument("--url", default=None,
                        help="Single URL to audit")
    parser.add_argument("--urls", default=None,
                        help="JSON array of URLs to audit")
    parser.add_argument("--file", default=None,
                        help="Path to file containing URLs (one per line)")
    parser.add_argument("--checks", default="all",
                        help="Comma-separated checks to run (default: all). Options: status, redirects, meta, headers, security, speed_hints")
    parser.add_argument("--timeout", type=int, default=10,
                        help="Request timeout in seconds (default: 10)")
    args = parser.parse_args()

    # --- Resolve URL list ---
    urls = []
    if args.url:
        urls.append(args.url.strip())
    if args.urls:
        try:
            parsed = json.loads(args.urls)
            if isinstance(parsed, list):
                urls.extend([u.strip() for u in parsed if isinstance(u, str) and u.strip()])
            else:
                json.dump({"error": "--urls must be a JSON array of strings"}, sys.stdout, indent=2)
                print()
                sys.exit(0)
        except json.JSONDecodeError as exc:
            json.dump({"error": f"Invalid JSON in --urls: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(0)
    if args.file:
        path = Path(args.file)
        if not path.exists():
            json.dump({"error": f"File not found: {args.file}"}, sys.stdout, indent=2)
            print()
            sys.exit(0)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            urls.extend([line.strip() for line in lines if line.strip() and not line.strip().startswith("#")])
        except Exception as exc:
            json.dump({"error": f"Could not read file: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(0)

    if not urls:
        json.dump({"error": "Provide at least one URL via --url, --urls, or --file"}, sys.stdout, indent=2)
        print()
        sys.exit(0)

    # --- Resolve checks ---
    if args.checks.strip().lower() == "all":
        checks = ALL_CHECKS
    else:
        checks = {c.strip().lower() for c in args.checks.split(",") if c.strip()}
        invalid = checks - ALL_CHECKS
        if invalid:
            json.dump({"error": f"Unknown checks: {', '.join(sorted(invalid))}. Valid: {', '.join(sorted(ALL_CHECKS))}"}, sys.stdout, indent=2)
            print()
            sys.exit(0)

    # --- Run audits ---
    results = []
    for url in urls:
        try:
            result = audit_url(url, checks, args.timeout)
        except Exception as exc:
            result = {
                "url": url,
                "status_code": None,
                "response_time_ms": 0,
                "redirects": [],
                "redirect_count": 0,
                "meta": {},
                "headers": {},
                "security": {},
                "speed_hints": {},
                "issues": [{"severity": "critical", "category": "status", "message": f"Unexpected error: {exc}"}],
                "score": 0,
            }
        results.append(result)

    # --- Summary ---
    scores = [r["score"] for r in results]
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for r in results:
        for issue in r.get("issues", []):
            sev = issue.get("severity", "low")
            if sev in severity_counts:
                severity_counts[sev] += 1

    summary = {
        "urls_checked": len(results),
        "average_score": round(sum(scores) / max(len(scores), 1), 1),
        "critical_issues": severity_counts["critical"],
        "high_issues": severity_counts["high"],
        "medium_issues": severity_counts["medium"],
        "low_issues": severity_counts["low"],
    }

    output = {
        "results": results,
        "summary": summary,
    }

    json.dump(output, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
