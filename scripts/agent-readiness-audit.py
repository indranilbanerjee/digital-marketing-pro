#!/usr/bin/env python3
"""
agent-readiness-audit.py — can AI agents and AI crawlers actually use this site?

Stdlib only. Works fully OFFLINE on files you supply; network fetching is
optional and happens only with --fetch.

Checks (each one runs only when its input is supplied):

  robots_ai_crawlers   robots.txt rules for the major AI crawler tokens, parsed
                       per RFC 9309 (group matching, longest-match, Allow wins
                       ties, * and $ wildcards). Search / user-fetch / ads bots
                       blocked at "/" => fail. Training bots are a POLICY choice:
                       reported as info unless --training-policy says otherwise.
  structured_data      JSON-LD presence (Product, Offer, Organization, FAQPage),
                       @graph aware. Unparseable JSON-LD => fail. Product with no
                       offers => warn (merchant listings require offers).
  no_js_render         Is the main content in the server HTML (no JavaScript
                       run)? SPA shells / tiny visible text / missing --expect
                       phrases => fail.
  accessibility_basics html lang, image alt text, labelled inputs, named
                       buttons/links — proxies for the accessibility tree that
                       browser agents read. Warn-level only.
  merchant_feed        Merchant Center product feed export (TSV/CSV/XML):
                       required attributes, availability values, price format,
                       native_commerce(checkout_eligibility), conversational
                       attributes coverage.
  acp_feed             OPTIONAL agentic-commerce product feed (JSONL OpenAI
                       format, or Google-compatible CSV/TSV): required fields +
                       eligibility flags.
  webmcp               OPTIONAL, EXPERIMENTAL (Chrome origin trial). Declarative
                       form tools / imperative registerTool calls. Never fails.

What this script will never do: recommend llms.txt for Google. Google's AI
optimization guide lists "LLMS.txt files and other 'special' markup" under
"Mythbusting generative AI search" — "Google Search itself doesn't use them."

Sources (all checked 2026-10-04):
  Google AI optimization guide  https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
  OpenAI crawlers               https://developers.openai.com/api/docs/bots
  Anthropic crawlers            https://support.claude.com/en/articles/8896518
  Perplexity crawlers           https://docs.perplexity.ai/guides/bots
  Google-Extended               https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers
  Applebot-Extended             https://support.apple.com/en-us/119829
  RFC 9309 (robots.txt)         https://www.rfc-editor.org/rfc/rfc9309
  Merchant listing markup       https://developers.google.com/search/docs/appearance/structured-data/merchant-listing
  FAQ rich results              https://developers.google.com/search/docs/appearance/structured-data/faqpage
  Product data specification    https://support.google.com/merchants/answer/7052112
  UCP checkout / native_commerce https://support.google.com/merchants/answer/16837055
                                https://developers.google.com/merchant/ucp/guides/merchant-center
  Conversational attributes     https://support.google.com/merchants/answer/17085370
  Agentic-commerce feed         https://developers.openai.com/commerce/specs/file-upload/products
  WebMCP                        https://developer.chrome.com/docs/ai/webmcp

Usage
-----
  # Offline, on exported files
  python scripts/agent-readiness-audit.py --robots robots.txt \\
      --html home.html --html product.html --expect "Acme Anvil" \\
      --feed products.tsv --acp-feed openai-feed.jsonl --webmcp

  # Fetch robots.txt + pages live (opt-in)
  python scripts/agent-readiness-audit.py --site https://example.com --fetch \\
      --page https://example.com/products/anvil

Exit codes
----------
  0 = no check failed (warnings allowed)
  1 = at least one check failed
  2 = bad input (nothing to audit, unreadable/unparseable file, bad flags)
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

TOOL_VERSION = "1.0"
CHECKED = "2026-10-04"
USER_AGENT = "DMP-agent-readiness-audit/1.0 (+https://github.com/indranilbanerjee/digital-marketing-pro)"

# ─────────────────────────────────────────────────────────────────────────────
# AI crawler tokens — names verified on each vendor's page, 2026-10-04.
# role: search | user | ads | training
# ─────────────────────────────────────────────────────────────────────────────
AI_CRAWLERS = [
    {"token": "OAI-SearchBot", "vendor": "OpenAI", "role": "search",
     "purpose": "surfaces websites in ChatGPT search features",
     "source": "https://developers.openai.com/api/docs/bots"},
    {"token": "ChatGPT-User", "vendor": "OpenAI", "role": "user",
     "purpose": "user-initiated visits from ChatGPT and Custom GPTs",
     "robots_note": "OpenAI: for user-initiated requests robots.txt rules may not apply",
     "source": "https://developers.openai.com/api/docs/bots"},
    {"token": "OAI-AdsBot", "vendor": "OpenAI", "role": "ads",
     "purpose": "validates the safety of web pages submitted as ads on ChatGPT",
     "source": "https://developers.openai.com/api/docs/bots"},
    {"token": "GPTBot", "vendor": "OpenAI", "role": "training",
     "purpose": "crawls content that may be used to train OpenAI's foundation models",
     "source": "https://developers.openai.com/api/docs/bots"},
    {"token": "Claude-SearchBot", "vendor": "Anthropic", "role": "search",
     "purpose": "indexes content to improve Claude's search results",
     "source": "https://support.claude.com/en/articles/8896518"},
    {"token": "Claude-User", "vendor": "Anthropic", "role": "user",
     "purpose": "retrieves pages when a Claude user asks a question",
     "source": "https://support.claude.com/en/articles/8896518"},
    {"token": "ClaudeBot", "vendor": "Anthropic", "role": "training",
     "purpose": "collects web content that could contribute to model training",
     "source": "https://support.claude.com/en/articles/8896518"},
    {"token": "PerplexityBot", "vendor": "Perplexity", "role": "search",
     "purpose": "surfaces and links websites in Perplexity search results (not used for foundation-model training)",
     "source": "https://docs.perplexity.ai/guides/bots"},
    {"token": "Perplexity-User", "vendor": "Perplexity", "role": "user",
     "purpose": "visits pages to answer a Perplexity user's question",
     "robots_note": "Perplexity: this fetcher generally ignores robots.txt rules because a user requested the fetch",
     "source": "https://docs.perplexity.ai/guides/bots"},
    {"token": "Google-Extended", "vendor": "Google", "role": "training",
     "purpose": "control token for Gemini model training and grounding; no separate HTTP user agent",
     "robots_note": "Google: Google-Extended does not impact inclusion in Google Search nor is it a Search ranking signal",
     "source": "https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers"},
    {"token": "Applebot-Extended", "vendor": "Apple", "role": "training",
     "purpose": "control token for use of Applebot-crawled content in Apple foundation-model training; does not crawl",
     "robots_note": "Apple: pages that disallow Applebot-Extended can still be included in search results",
     "source": "https://support.apple.com/en-us/119829"},
]
REQUIRED_ROLES = ("search", "user", "ads")

LLMS_TXT_NOTE = ("llms.txt is NOT recommended for Google: Google's AI optimization guide "
                 "lists \"LLMS.txt files and other 'special' markup\" under \"Mythbusting "
                 "generative AI search\" — \"Google Search itself doesn't use them.\" "
                 "(https://developers.google.com/search/docs/fundamentals/ai-optimization-guide, "
                 "checked 2026-10-04)")
STRUCTURED_DATA_NOTE = ("Google: \"Structured data isn't required for generative AI search, and "
                        "there's no special schema.org markup you need to add.\" It still powers "
                        "rich results, which is why it is checked here.")


class BadInput(Exception):
    """Raised for unusable inputs — maps to exit code 2."""


# ─────────────────────────────────────────────────────────────────────────────
# robots.txt (RFC 9309)
# ─────────────────────────────────────────────────────────────────────────────

def parse_robots(text: str) -> list[dict]:
    """Return groups: [{"agents": [lowercased tokens], "rules": [(allow, path)]}].

    Consecutive user-agent lines open one group; a rule line closes the agent
    list, so a later user-agent line starts a new group (RFC 9309 §2.1)."""
    groups: list[dict] = []
    current: dict | None = None
    last_was_agent = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            if current is None or not last_was_agent:
                current = {"agents": [], "rules": []}
                groups.append(current)
            current["agents"].append(value.lower())
            last_was_agent = True
        elif key in ("allow", "disallow"):
            last_was_agent = False
            if current is None:
                continue  # rules before any user-agent line are ignored
            if value == "":
                continue  # empty Disallow = allow everything; empty Allow is a no-op
            current["rules"].append((key == "allow", value))
        else:
            last_was_agent = False  # sitemap, crawl-delay, etc.
    return groups


def _select_groups(groups: list[dict], token: str) -> tuple[list[dict], str]:
    """Groups that apply to `token`: every group naming it (merged), else '*'."""
    t = token.lower()
    named = [g for g in groups if t in g["agents"]]
    if named:
        return named, token
    star = [g for g in groups if "*" in g["agents"]]
    return star, ("*" if star else "")


def _rule_matches(pattern: str, path: str) -> bool:
    regex = ""
    for ch in pattern:
        if ch == "*":
            regex += ".*"
        elif ch == "$":
            regex += "$"
        else:
            regex += re.escape(ch)
    return re.match(regex, path) is not None


def is_allowed(groups: list[dict], token: str, path: str = "/") -> tuple[bool, str, str | None]:
    """(allowed, matched_group_token, deciding_rule) for `token` on `path`.

    Longest matching rule wins; on equal length Allow wins (RFC 9309 §2.2.2)."""
    selected, matched = _select_groups(groups, token)
    best: tuple[int, bool, str] | None = None
    for g in selected:
        for allow, pattern in g["rules"]:
            if _rule_matches(pattern, path):
                length = len(pattern)
                if best is None or length > best[0] or (length == best[0] and allow and not best[1]):
                    best = (length, allow, pattern)
    if best is None:
        return True, matched, None
    return best[1], matched, ("Allow: " if best[1] else "Disallow: ") + best[2]


def check_robots(text: str | None, paths: list[str], training_policy: str,
                 source_label: str) -> dict:
    if text is None:
        return {"id": "robots_ai_crawlers", "status": "skipped",
                "findings": ["no robots.txt supplied (use --robots FILE or --site URL --fetch)"]}
    groups = parse_robots(text)
    bots = []
    findings = []
    status = "pass"
    for bot in AI_CRAWLERS:
        per_path = {}
        for p in paths:
            allowed, matched, rule = is_allowed(groups, bot["token"], p)
            per_path[p] = {"allowed": allowed, "group": matched or "(none)", "rule": rule}
        root_allowed = per_path[paths[0]]["allowed"]
        blocked_paths = [p for p, r in per_path.items() if not r["allowed"]]
        verdict = "allowed" if not blocked_paths else ("blocked" if not root_allowed else "partially_blocked")
        entry = {"token": bot["token"], "vendor": bot["vendor"], "role": bot["role"],
                 "purpose": bot["purpose"], "verdict": verdict, "paths": per_path,
                 "source": bot["source"]}
        if bot.get("robots_note"):
            entry["note"] = bot["robots_note"]
        bots.append(entry)

        if bot["role"] in REQUIRED_ROLES and blocked_paths:
            status = "fail"
            findings.append(f"{bot['token']} ({bot['vendor']}, {bot['role']}) is {verdict.replace('_', ' ')} "
                            f"on {', '.join(blocked_paths)} — {bot['purpose']}")
        elif bot["role"] == "training":
            if training_policy == "block" and verdict != "blocked":
                status = "fail"
                findings.append(f"{bot['token']} is not blocked but --training-policy is 'block'")
            elif training_policy == "allow" and blocked_paths:
                status = "fail"
                findings.append(f"{bot['token']} is {verdict.replace('_', ' ')} but --training-policy is 'allow'")
    if not text.strip():
        findings.append("robots.txt is empty — every crawler is allowed")
    return {"id": "robots_ai_crawlers", "status": status, "source": source_label,
            "training_policy": training_policy, "findings": findings, "crawlers": bots,
            "rule": "RFC 9309: most specific user-agent group, longest matching rule, Allow wins ties"}


# ─────────────────────────────────────────────────────────────────────────────
# HTML parsing (JSON-LD, visible text, a11y basics, WebMCP)
# ─────────────────────────────────────────────────────────────────────────────

_SKIP_TEXT_TAGS = {"script", "style", "noscript", "template", "svg", "head", "title"}
_SPA_ROOT_IDS = {"root", "app", "__next", "__nuxt", "___gatsby", "svelte"}
_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
              "source", "track", "wbr"}


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.jsonld: list[str] = []
        self.inline_scripts: list[str] = []
        self.text_parts: list[str] = []
        self.noscript_text: list[str] = []
        self.script_count = 0
        self._stack: list[str] = []
        self._in_jsonld = False
        self._in_script = False
        self._in_noscript = 0
        self._buf: list[str] = []
        self.html_lang = None
        self.h1_count = 0
        self.has_main = False
        self.imgs_without_alt = 0
        self.img_count = 0
        self.inputs: list[dict] = []
        self.label_for: set[str] = set()
        self._label_depth = 0
        self.unnamed_buttons = 0
        self._button_open: list[dict] = []
        self.spa_roots: list[str] = []
        self.webmcp_forms: list[dict] = []
        self.webmcp_params = 0

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        tag = tag.lower()
        if tag == "html" and a.get("lang"):
            self.html_lang = a["lang"]
        if tag == "script":
            self.script_count += 1
            t = a.get("type", "").lower()
            if t == "application/ld+json":
                self._in_jsonld = True
            else:
                self._in_script = True
            self._buf = []
        if tag == "noscript":
            self._in_noscript += 1
        if tag == "h1":
            self.h1_count += 1
        if tag == "main" or a.get("role") == "main":
            self.has_main = True
        if tag == "img":
            self.img_count += 1
            if "alt" not in a:
                self.imgs_without_alt += 1
        if tag == "label":
            self._label_depth += 1
            if a.get("for"):
                self.label_for.add(a["for"])
        if tag in ("input", "select", "textarea"):
            itype = a.get("type", "text").lower()
            if itype not in ("hidden", "submit", "button", "image", "reset"):
                self.inputs.append({"id": a.get("id"), "aria": bool(a.get("aria-label") or a.get("aria-labelledby")),
                                    "wrapped": self._label_depth > 0, "title": bool(a.get("title"))})
            if "toolparamdescription" in a:
                self.webmcp_params += 1
        if tag == "button":
            self._button_open.append({"named": bool(a.get("aria-label") or a.get("title")), "text": ""})
        if tag == "div" and a.get("id", "").lower() in _SPA_ROOT_IDS:
            self.spa_roots.append(a["id"])
        if "ng-app" in a or "data-reactroot" in a:
            self.spa_roots.append("ng-app" if "ng-app" in a else "data-reactroot")
        if tag == "form" and "toolname" in a:
            self.webmcp_forms.append({"toolname": a.get("toolname"),
                                      "has_description": bool(a.get("tooldescription")),
                                      "autosubmit": "toolautosubmit" in a})
        if tag == "body":
            # Browsers close <head> implicitly when <body> starts.
            self._stack = [t for t in self._stack if t != "head"]
        if tag not in _VOID_TAGS:
            self._stack.append(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "script":
            if self._in_jsonld:
                self.jsonld.append("".join(self._buf))
            elif self._in_script:
                self.inline_scripts.append("".join(self._buf))
            self._in_jsonld = self._in_script = False
            self._buf = []
        if tag == "noscript" and self._in_noscript:
            self._in_noscript -= 1
        if tag == "label" and self._label_depth:
            self._label_depth -= 1
        if tag == "button" and self._button_open:
            b = self._button_open.pop()
            if not b["named"] and not b["text"].strip():
                self.unnamed_buttons += 1
        if tag in self._stack:
            while self._stack:
                if self._stack.pop() == tag:
                    break

    def handle_data(self, data):
        if self._in_jsonld or self._in_script:
            self._buf.append(data)
            return
        if self._in_noscript:
            self.noscript_text.append(data)
            return
        for b in self._button_open:
            b["text"] += data
        if any(t in _SKIP_TEXT_TAGS for t in self._stack):
            return
        self.text_parts.append(data)

    # derived
    def visible_text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.text_parts)).strip()

    def unlabelled_inputs(self) -> int:
        return sum(1 for i in self.inputs
                   if not (i["wrapped"] or i["aria"] or i["title"] or (i["id"] and i["id"] in self.label_for)))


def parse_html(html: str) -> _PageParser:
    p = _PageParser()
    p.feed(html)
    p.close()
    return p


def _walk_types(node, found: list[dict]):
    if isinstance(node, list):
        for n in node:
            _walk_types(n, found)
    elif isinstance(node, dict):
        t = node.get("@type")
        types = t if isinstance(t, list) else ([t] if t else [])
        for ty in types:
            if isinstance(ty, str):
                found.append({"type": ty.split("/")[-1], "node": node})
        for k, v in node.items():
            if k != "@type":
                _walk_types(v, found)


ORG_TYPES = {"Organization", "Corporation", "OnlineStore", "OnlineBusiness", "LocalBusiness",
             "NewsMediaOrganization", "Store"}
OFFER_TYPES = {"Offer", "AggregateOffer"}


def check_structured_data(pages: list[tuple[str, _PageParser]]) -> dict:
    if not pages:
        return {"id": "structured_data", "status": "skipped",
                "findings": ["no HTML supplied (use --html FILE or --fetch)"]}
    status = "pass"
    findings = []
    per_page = []
    seen = set()
    for label, p in pages:
        types: list[dict] = []
        errors = 0
        for block in p.jsonld:
            try:
                _walk_types(json.loads(block), types)
            except json.JSONDecodeError as e:
                errors += 1
                findings.append(f"{label}: unparseable JSON-LD block ({e.msg} at line {e.lineno})")
        names = sorted({t["type"] for t in types})
        seen.update(names)
        products = [t["node"] for t in types if t["type"] == "Product"]
        no_offer = [pr for pr in products if not pr.get("offers")]
        if errors:
            status = "fail"
        if no_offer:
            if status == "pass":
                status = "warn"
            findings.append(f"{label}: Product markup without `offers` — Google's merchant listing "
                            "rich result requires name, image and offers")
        per_page.append({"page": label, "jsonld_blocks": len(p.jsonld), "parse_errors": errors,
                         "types": names})
    summary = {
        "Product": "Product" in seen,
        "Offer": bool(seen & OFFER_TYPES),
        "Organization": bool(seen & ORG_TYPES),
        "FAQPage": "FAQPage" in seen,
    }
    if not summary["Organization"]:
        if status == "pass":
            status = "warn"
        findings.append("no Organization (or subtype) JSON-LD on any supplied page")
    notes = [STRUCTURED_DATA_NOTE]
    if summary["FAQPage"]:
        notes.append("FAQPage found: Google shows FAQ rich results only for well-known, authoritative "
                     "government and health websites — keep it for meaning, don't expect the rich result.")
    return {"id": "structured_data", "status": status, "findings": findings,
            "present": summary, "pages": per_page, "notes": notes}


def check_no_js(pages: list[tuple[str, _PageParser, int]], expect: list[str], min_text: int) -> dict:
    if not pages:
        return {"id": "no_js_render", "status": "skipped",
                "findings": ["no HTML supplied (use --html FILE or --fetch)"]}
    status = "pass"
    findings = []
    per_page = []
    for label, p, size in pages:
        text = p.visible_text()
        missing = [e for e in expect if e.lower() not in text.lower()]
        shell = bool(p.spa_roots) and len(text) < min_text
        page_status = "pass"
        if len(text) < min_text or shell or missing:
            page_status = "fail"
        elif p.h1_count == 0 and not p.has_main:
            page_status = "warn"
        if page_status == "fail":
            status = "fail"
            why = []
            if len(text) < min_text:
                why.append(f"only {len(text)} characters of visible text in the server HTML (min {min_text})")
            if shell:
                why.append(f"client-side app shell detected ({', '.join(sorted(set(p.spa_roots)))})")
            if missing:
                why.append("expected content not in server HTML: " + ", ".join(repr(m) for m in missing))
            findings.append(f"{label}: " + "; ".join(why))
        elif page_status == "warn":
            if status == "pass":
                status = "warn"
            findings.append(f"{label}: no <h1> and no <main> landmark in the server HTML")
        per_page.append({"page": label, "status": page_status, "visible_text_chars": len(text),
                         "html_bytes": size, "scripts": p.script_count, "h1": p.h1_count,
                         "main_landmark": p.has_main, "spa_shell_markers": sorted(set(p.spa_roots)),
                         "missing_expected": missing,
                         "noscript_says_enable_js": "javascript" in " ".join(p.noscript_text).lower()})
    return {"id": "no_js_render", "status": status, "findings": findings, "pages": per_page,
            "why": ("Checks the HTML as served, before any JavaScript runs. Google says it can process "
                    "JavaScript content when it isn't blocked; content already in the server HTML is "
                    "readable by every crawler and agent regardless.")}


def check_a11y(pages: list[tuple[str, _PageParser]]) -> dict:
    if not pages:
        return {"id": "accessibility_basics", "status": "skipped", "findings": []}
    status = "pass"
    findings = []
    per_page = []
    for label, p in pages:
        issues = []
        if not p.html_lang:
            issues.append("no <html lang>")
        if p.imgs_without_alt:
            issues.append(f"{p.imgs_without_alt}/{p.img_count} images without alt")
        if p.unlabelled_inputs():
            issues.append(f"{p.unlabelled_inputs()} form fields without a label")
        if p.unnamed_buttons:
            issues.append(f"{p.unnamed_buttons} buttons without an accessible name")
        if issues:
            status = "warn"
            findings.append(f"{label}: " + "; ".join(issues))
        per_page.append({"page": label, "issues": issues})
    return {"id": "accessibility_basics", "status": status, "findings": findings, "pages": per_page,
            "why": ("Google's AI optimization guide notes browser agents may inspect the DOM and "
                    "interpret the accessibility tree; these are cheap proxies for that tree.")}


def check_webmcp(enabled: bool, pages: list[tuple[str, _PageParser]]) -> dict:
    base = {"id": "webmcp", "experimental": True,
            "status_note": ("EXPERIMENTAL — WebMCP is a Chrome origin trial (from Chrome 149) and "
                            "\"under active discussion and subject to change\". Informational only; "
                            "never affects the verdict. https://developer.chrome.com/docs/ai/webmcp")}
    if not enabled:
        return {**base, "status": "skipped", "findings": ["not requested (use --webmcp)"]}
    if not pages:
        return {**base, "status": "skipped", "findings": ["no HTML supplied"]}
    forms = []
    imperative = 0
    params = 0
    for label, p in pages:
        for f in p.webmcp_forms:
            forms.append({"page": label, **f})
        params += p.webmcp_params
        imperative += sum(len(re.findall(r"modelContext\s*\.\s*registerTool\s*\(", s))
                          for s in p.inline_scripts)
    findings = []
    if forms or imperative:
        findings.append(f"{len(forms)} declarative form tool(s), {imperative} inline registerTool call(s)")
        missing_desc = [f["toolname"] for f in forms if not f["has_description"]]
        if missing_desc:
            findings.append("forms with toolname but no tooldescription: " + ", ".join(missing_desc))
    else:
        findings.append("no WebMCP tools declared — optional; nothing to fix unless you are in the origin trial")
    return {**base, "status": "info", "findings": findings, "declarative_forms": forms,
            "toolparamdescription_fields": params, "imperative_register_calls": imperative}


# ─────────────────────────────────────────────────────────────────────────────
# Feeds
# ─────────────────────────────────────────────────────────────────────────────

MC_REQUIRED = ["id", "title", "description", "link", "image_link", "availability", "price"]
MC_ALTERNATES = {"title": ["structured_title"], "description": ["structured_description"]}
MC_AVAILABILITY = {"in_stock", "out_of_stock", "preorder", "backorder"}
CONVERSATIONAL = ["question_and_answer", "document_link", "related_product", "item_group_title",
                  "variant_option", "popularity_rank"]
PRICE_RE = re.compile(r"^\s*\d[\d.,]*\s+[A-Z]{3}\s*$")

ACP_JSONL_REQUIRED = ["item_id", "title", "description", "url", "brand", "seller_name",
                      "image_url", "availability", "price"]
ACP_CSV_REQUIRED = ["id", "title", "description", "link", "image_link", "availability", "price", "brand"]


def _norm_key(k: str) -> str:
    k = (k or "").strip().lower()
    if k.startswith("g:"):
        k = k[2:]
    return k


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise BadInput(f"file not found: {path}")
    except UnicodeDecodeError:
        raise BadInput(f"not UTF-8 text: {path}")


def _rows_from_delimited(text: str) -> list[dict]:
    first = text.splitlines()[0] if text.strip() else ""
    delim = "\t" if first.count("\t") >= first.count(",") and "\t" in first else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    rows = []
    for r in reader:
        rows.append({_norm_key(k): (v or "").strip() for k, v in r.items() if k is not None})
    return rows


def _rows_from_xml(text: str) -> list[dict]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise BadInput(f"feed XML does not parse: {e}")
    rows = []
    items = [el for el in root.iter() if el.tag.split("}")[-1] in ("item", "entry")]
    for item in items:
        row: dict = {}
        for child in item:
            name = child.tag.split("}")[-1].lower()
            if len(child):
                subs = {g.tag.split("}")[-1].lower(): (g.text or "").strip() for g in child}
                row[name] = subs
            else:
                row[name] = (child.text or "").strip()
        rows.append(row)
    return rows


def load_feed(path: Path) -> tuple[list[dict], str]:
    text = _read_text(path)
    stripped = text.lstrip()
    if not stripped:
        raise BadInput(f"feed is empty: {path}")
    if stripped.startswith("<"):
        return _rows_from_xml(text), "xml"
    if stripped.startswith("{"):
        rows = []
        for n, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise BadInput(f"{path}: line {n} is not JSON ({e.msg})")
            rows.append({_norm_key(k): v for k, v in obj.items()})
        return rows, "jsonl"
    return _rows_from_delimited(text), "delimited"


def _checkout_eligibility(row: dict) -> str | None:
    """Value of native_commerce(checkout_eligibility), however the export spells it."""
    nc = row.get("native_commerce")
    if isinstance(nc, dict):
        v = nc.get("checkout_eligibility")
        return v.strip().upper() if isinstance(v, str) and v.strip() else None
    for key in ("native_commerce(checkout_eligibility)", "checkout_eligibility"):
        v = row.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip().upper()
    if isinstance(nc, str) and nc.strip():
        m = re.search(r"checkout_eligibility\s*[:=]\s*(\w+)", nc, re.I)
        return (m.group(1) if m else nc).strip().upper()
    return None


def _present(row: dict, key: str) -> bool:
    v = row.get(key)
    if isinstance(v, dict):
        return any(str(x).strip() for x in v.values())
    return v is not None and str(v).strip() != ""


def check_merchant_feed(path: Path | None) -> dict:
    if path is None:
        return {"id": "merchant_feed", "status": "skipped",
                "findings": ["no Merchant Center feed export supplied (use --feed FILE)"]}
    rows, fmt = load_feed(path)
    if not rows:
        raise BadInput(f"feed has no product rows: {path}")
    status = "pass"
    findings = []
    missing = {a: 0 for a in MC_REQUIRED}
    bad_availability = 0
    bad_price = 0
    for r in rows:
        for a in MC_REQUIRED:
            if not (_present(r, a) or any(_present(r, alt) for alt in MC_ALTERNATES.get(a, []))):
                missing[a] += 1
        av = str(r.get("availability", "")).strip().lower().replace(" ", "_")
        if av and av not in MC_AVAILABILITY:
            bad_availability += 1
        price = r.get("price")
        if isinstance(price, str) and price.strip() and not PRICE_RE.match(price):
            bad_price += 1
    total = len(rows)
    for a, n in missing.items():
        if n:
            status = "fail"
            findings.append(f"[{a}] missing on {n}/{total} products (required by the product data specification)")
    if bad_availability:
        status = "fail"
        findings.append(f"{bad_availability}/{total} products have an [availability] outside "
                        f"{sorted(MC_AVAILABILITY)}")
    if bad_price:
        if status == "pass":
            status = "warn"
        findings.append(f"{bad_price}/{total} products have a [price] not in 'NUMBER CUR' form (e.g. '15.00 USD')")

    elig = [_checkout_eligibility(r) for r in rows]
    invalid_elig = sum(1 for e in elig if e is not None and e not in ("TRUE", "FALSE"))
    opted_in = sum(1 for e in elig if e == "TRUE")
    if invalid_elig:
        status = "fail"
        findings.append(f"{invalid_elig} products have native_commerce(checkout_eligibility) not TRUE/FALSE")
    native = {
        "products_opted_in": opted_in,
        "products_total": total,
        "attribute": "native_commerce(checkout_eligibility) — boolean, defaults to FALSE",
        "note": ("Only listings with native_commerce(checkout_eligibility)=TRUE show the 'Buy' button "
                 "for checkout on Google; available to select merchants, for products eligible in the "
                 "United States, Canada and Australia. Also verify (not checkable from a feed): "
                 "account-level return policy and customer-support contact; consumer_notice where a "
                 "legal disclaimer / safety warning / Prop 65 notice applies."),
        "sources": ["https://support.google.com/merchants/answer/16837055",
                    "https://developers.google.com/merchant/ucp/guides/merchant-center"],
    }
    if opted_in == 0:
        findings.append("no product opts into checkout on Google (native_commerce) — only needed if the "
                        "brand wants agentic checkout and is eligible")

    conv = {a: sum(1 for r in rows if _present(r, a)) for a in CONVERSATIONAL}
    conv_cov = {a: round(100 * n / total, 1) for a, n in conv.items()}
    if not any(conv.values()):
        findings.append("no conversational attributes (question_and_answer, related_product, "
                        "variant_option, ...) — optional, but they help AI matching")
    return {"id": "merchant_feed", "status": status, "format": fmt, "products": total,
            "findings": findings, "required_missing": missing,
            "native_commerce": native,
            "conversational_attributes_coverage_pct": conv_cov,
            "sources": ["https://support.google.com/merchants/answer/7052112",
                        "https://support.google.com/merchants/answer/17085370"]}


def check_acp_feed(path: Path | None) -> dict:
    if path is None:
        return {"id": "acp_feed", "status": "skipped", "optional": True,
                "findings": ["no agentic-commerce feed supplied — optional (use --acp-feed FILE)"]}
    rows, fmt = load_feed(path)
    if not rows:
        raise BadInput(f"agentic-commerce feed has no rows: {path}")
    required = ACP_JSONL_REQUIRED if fmt == "jsonl" else ACP_CSV_REQUIRED
    missing = {a: sum(1 for r in rows if not _present(r, a)) for a in required}
    status = "pass"
    findings = []
    total = len(rows)
    for a, n in missing.items():
        if n:
            status = "fail"
            findings.append(f"`{a}` missing on {n}/{total} rows")

    def _truthy(v):
        return str(v).strip().lower() in ("true", "1", "yes")
    search = sum(1 for r in rows if _truthy(r.get("is_eligible_search", "")))
    checkout = sum(1 for r in rows if _truthy(r.get("is_eligible_checkout", "")))
    if not any("is_eligible_search" in r for r in rows):
        findings.append("no is_eligible_search flag on any row")
    return {"id": "acp_feed", "status": status, "optional": True, "format": fmt, "rows": total,
            "required_fields": required, "required_missing": missing,
            "eligible_search": search, "eligible_checkout": checkout, "findings": findings,
            "source": "https://developers.openai.com/commerce/specs/file-upload/products"}


# ─────────────────────────────────────────────────────────────────────────────
# Fetching (opt-in)
# ─────────────────────────────────────────────────────────────────────────────

def fetch(url: str, timeout: int = 15) -> tuple[int | None, str, str | None]:
    """(http_status, body, error). Never raises."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.status, resp.read().decode(charset, errors="replace"), None
    except urllib.error.HTTPError as e:
        return e.code, "", f"HTTP {e.code}"
    except Exception as e:  # network, DNS, timeout
        return None, "", f"{type(e).__name__}: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────────────

def recommendations_for(checks: list[dict]) -> list[str]:
    recs = []
    by_id = {c["id"]: c for c in checks}
    r = by_id.get("robots_ai_crawlers", {})
    for bot in r.get("crawlers", []):
        if bot["role"] in REQUIRED_ROLES and bot["verdict"] != "allowed":
            recs.append(f"Allow {bot['token']} in robots.txt if the brand wants to appear in "
                        f"{bot['vendor']} answers ({bot['purpose']}).")
    if by_id.get("structured_data", {}).get("status") in ("warn", "fail"):
        recs.append("Fix or add JSON-LD (Organization site-wide; Product with offers on product pages) "
                    "and validate it in Google's Rich Results Test.")
    if by_id.get("no_js_render", {}).get("status") == "fail":
        recs.append("Render the main content (names, prices, key copy) into the server HTML — "
                    "server-side rendering or pre-rendering.")
    if by_id.get("merchant_feed", {}).get("status") == "fail":
        recs.append("Fill the missing required Merchant Center attributes before relying on AI shopping surfaces.")
    if by_id.get("acp_feed", {}).get("status") == "fail":
        recs.append("Complete the required agentic-commerce feed fields.")
    return recs


def run_audit(args) -> dict:
    robots_text = None
    robots_label = None
    html_pages: list[tuple[str, str]] = []
    fetch_log = []

    if args.robots:
        robots_text = _read_text(Path(args.robots))
        robots_label = args.robots
    for h in args.html or []:
        html_pages.append((h, _read_text(Path(h))))

    if args.fetch:
        if not args.site:
            raise BadInput("--fetch needs --site")
        parsed = urlparse(args.site)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise BadInput(f"--site must be an http(s) URL: {args.site}")
        base = f"{parsed.scheme}://{parsed.netloc}"
        if robots_text is None:
            url = urljoin(base, "/robots.txt")
            code, body, err = fetch(url)
            fetch_log.append({"url": url, "status": code, "error": err})
            if code == 200:
                robots_text, robots_label = body, url
            elif code is not None and 400 <= code < 500:
                # RFC 9309 §2.3.1.3: an unavailable robots.txt (4xx) means no restrictions.
                robots_text, robots_label = "", f"{url} (HTTP {code} — treated as allow-all)"
        for url in [args.site] + list(args.page or []):
            code, body, err = fetch(url)
            fetch_log.append({"url": url, "status": code, "error": err})
            if code == 200 and body:
                html_pages.append((url, body))

    if robots_text is None and not html_pages and not args.feed and not args.acp_feed:
        raise BadInput("nothing to audit — supply --robots, --html, --feed, --acp-feed, or --site with --fetch")

    paths = args.path or ["/"]
    if paths[0] != "/":
        paths = ["/"] + [p for p in paths if p != "/"]
    parsed_pages = [(label, parse_html(body), len(body.encode("utf-8"))) for label, body in html_pages]

    checks = [
        check_robots(robots_text, paths, args.training_policy, robots_label or ""),
        check_structured_data([(l, p) for l, p, _ in parsed_pages]),
        check_no_js(parsed_pages, args.expect or [], args.min_text),
        check_a11y([(l, p) for l, p, _ in parsed_pages]),
        check_merchant_feed(Path(args.feed) if args.feed else None),
        check_acp_feed(Path(args.acp_feed) if args.acp_feed else None),
        check_webmcp(args.webmcp, [(l, p) for l, p, _ in parsed_pages]),
    ]
    counts: dict[str, int] = {}
    for c in checks:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    verdict = "not_ready" if counts.get("fail") else ("needs_work" if counts.get("warn") else "ready")
    return {
        "tool": "agent-readiness-audit",
        "version": TOOL_VERSION,
        "sources_checked": CHECKED,
        "site": args.site,
        "fetched": fetch_log,
        "verdict": verdict,
        "summary": counts,
        "checks": checks,
        "recommendations": recommendations_for(checks),
        "notes": [LLMS_TXT_NOTE,
                  "Verdict ignores experimental and skipped checks; training-crawler rules are policy, "
                  "reported as info unless --training-policy is set."],
    }


def render_text(report: dict) -> str:
    lines = [f"Agent readiness: {report['verdict'].upper()}  ({report['summary']})"]
    for c in report["checks"]:
        lines.append(f"- {c['id']}: {c['status']}")
        for f in c.get("findings", []):
            lines.append(f"    · {f}")
    if report["recommendations"]:
        lines.append("Recommendations:")
        lines += [f"  {i}. {r}" for i, r in enumerate(report["recommendations"], 1)]
    lines.append("Note: " + report["notes"][0])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Check whether AI agents and AI crawlers can use a site.")
    ap.add_argument("--site", help="Site base URL (used with --fetch, and as a label)")
    ap.add_argument("--fetch", action="store_true",
                    help="Fetch robots.txt and pages over the network (off by default)")
    ap.add_argument("--page", action="append", help="Extra page URL to fetch (repeatable; needs --fetch)")
    ap.add_argument("--robots", help="Path to a robots.txt file")
    ap.add_argument("--path", action="append",
                    help="URL path to test robots rules against (repeatable; '/' is always tested)")
    ap.add_argument("--training-policy", choices=["either", "allow", "block"], default="either",
                    help="Brand policy for training crawlers (default: either = report only)")
    ap.add_argument("--html", action="append", help="Path to a server-HTML file (repeatable)")
    ap.add_argument("--expect", action="append",
                    help="Text that must appear in the server HTML, e.g. a product name (repeatable)")
    ap.add_argument("--min-text", type=int, default=250,
                    help="Minimum visible-text characters in server HTML (default 250)")
    ap.add_argument("--feed", help="Merchant Center product feed export (TSV/CSV/XML)")
    ap.add_argument("--acp-feed", help="Optional agentic-commerce product feed (JSONL or CSV/TSV)")
    ap.add_argument("--webmcp", action="store_true",
                    help="Include the EXPERIMENTAL WebMCP check (informational only)")
    ap.add_argument("--format", choices=["json", "text"], default="json")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        report = run_audit(args)
    except BadInput as e:
        print(json.dumps({"error": str(e), "exit_code": 2}))
        return 2
    if args.format == "text":
        print(render_text(report))
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report["summary"].get("fail") else 0


if __name__ == "__main__":
    sys.exit(main())
