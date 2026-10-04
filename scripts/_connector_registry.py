#!/usr/bin/env python3
"""
_connector_registry.py
======================
Single source of truth for the Digital Marketing Pro connector registry.

Both `connector-status.py` (user-facing CLI) and `connector_resolver.py`
(the action-resolution layer used by performance-monitor / crm-sync /
execution-tracker / seo-executor) import from here. Centralising the
registry means a connector added in one place is automatically discoverable
by every action that needs it.

Three responsibilities:
  1. CONNECTOR_REGISTRY — the full catalog grouped by category
  2. _load_mcp_json + is_connector_configured — probe whether a connector is reachable
  3. redact_secrets — credential-safe response filter

No network calls happen here. All probes are local (env vars + .mcp.json).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# Plugin root = parent of scripts/
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
MCP_JSON = PLUGIN_ROOT / ".mcp.json"


CONNECTOR_REGISTRY = {
    "chat": {
        "description": "Team messaging and notifications",
        "connectors": {
            "slack": {
                "transport": "http",
                "url": "https://mcp.slack.com/mcp",
                "description": "Slack — send reports, alerts, team notifications",
                "env_vars": [],
                "skills_unlocked": [
                    "send-notification", "send-report", "campaign-status"
                ],
            },
            "intercom": {
                "transport": "npx",
                "package": None,
                "package_status": "no-known-npm-package",
                "note": "No verified MCP package on npm — use /digital-marketing-pro:add-integration to wire a custom server. npx runs remote code; verify any package before use.",
                "description": "Intercom — customer messaging, churn detection",
                "env_vars": ["INTERCOM_ACCESS_TOKEN"],
                "skills_unlocked": ["send-notification"],
            },
        },
    },
    "design": {
        "description": "Visual design and creative assets",
        "connectors": {
            "canva": {
                "transport": "http",
                "url": "https://mcp.canva.com/mcp",
                "description": "Canva — design creation, brand kit, templates",
                "env_vars": [],
                "skills_unlocked": ["ad-creative", "social-strategy"],
            },
            "figma": {
                "transport": "http",
                "url": "https://mcp.figma.com/mcp",
                "description": "Figma — design files, prototypes, components",
                "env_vars": [],
                "skills_unlocked": ["ad-creative", "landing-page-audit"],
            },
        },
    },
    "crm": {
        "description": "Customer relationship management",
        "connectors": {
            "hubspot": {
                "transport": "http",
                # GA remote server (13 Apr 2026); OAuth 2.1 + PKCE. Checked 2026-10-04:
                # developers.hubspot.com/changelog/remote-hubspot-mcp-server-is-now-generally-available
                "url": "https://mcp.hubspot.com",
                "access": "read-write",
                "setup_note": ("OAuth 2.1 with PKCE is required; have your connector app's client ID, "
                               "client secret and redirect URL ready. CRM writes run only behind the "
                               "calling skill's approval gate."),
                "description": "HubSpot — contacts, deals, email, pipeline",
                "env_vars": [],
                "skills_unlocked": [
                    "crm-sync", "lead-import", "pipeline-update",
                    "segment-audience", "client-report",
                ],
            },
            "salesforce": {
                "transport": "npx",
                "package": None,
                "package_status": "no-known-npm-package",
                "note": "No verified MCP package on npm — use /digital-marketing-pro:add-integration to wire a custom server. npx runs remote code; verify any package before use.",
                "description": "Salesforce — CRM pipeline, leads, accounts",
                "env_vars": ["SALESFORCE_INSTANCE_URL", "SALESFORCE_ACCESS_TOKEN"],
                "skills_unlocked": [
                    "crm-sync", "lead-import", "pipeline-update", "segment-audience",
                ],
            },
            "pipedrive": {
                "transport": "npx",
                "package": "mcp-pipedrive",
                "description": "Pipedrive — deal pipeline, contacts, activities",
                "env_vars": ["PIPEDRIVE_API_TOKEN"],
                "skills_unlocked": [
                    "crm-sync", "lead-import", "pipeline-update",
                ],
            },
            "zoho-crm": {
                "transport": "npx",
                "package": "mcp-zoho-crm",
                "description": "Zoho CRM — leads, contacts, deals, campaigns",
                "env_vars": ["ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN"],
                "skills_unlocked": [
                    "crm-sync", "lead-import", "pipeline-update",
                ],
            },
        },
    },
    "seo": {
        "description": "Search engine optimization and analysis",
        "connectors": {
            "ahrefs": {
                "transport": "http",
                "url": "https://api.ahrefs.com/mcp/mcp",
                "description": "Ahrefs — backlinks, keywords, content gaps",
                "env_vars": [],
                "skills_unlocked": [
                    "seo-audit", "keyword-research", "competitor-analysis",
                    "tech-seo-audit", "content-decay-scan",
                ],
            },
            "similarweb": {
                "transport": "http",
                "url": "https://mcp.similarweb.com",
                "endpoint_status": "unverified — confirm this MCP endpoint exists before relying on it",
                "description": "Similarweb — traffic analysis, competitor benchmarks",
                "env_vars": [],
                "skills_unlocked": ["competitor-analysis", "share-of-voice"],
            },
            "semrush": {
                "transport": "npx",
                "package": None,
                "package_status": "no-known-npm-package",
                "note": "No verified MCP package on npm — use /digital-marketing-pro:add-integration to wire a custom server. npx runs remote code; verify any package before use.",
                "description": "SEMrush — keyword research, site audit, backlinks",
                "env_vars": ["SEMRUSH_API_KEY"],
                "skills_unlocked": ["seo-audit", "keyword-research", "competitor-analysis"],
            },
            "moz": {
                "transport": "npx",
                "package": "mcp-moz",
                "description": "Moz — domain authority, rank tracking, SERP",
                "env_vars": ["MOZ_ACCESS_ID", "MOZ_SECRET_KEY"],
                "skills_unlocked": ["seo-audit", "keyword-research"],
            },
        },
    },
    "email-marketing": {
        "description": "Email campaigns and automation",
        "connectors": {
            "klaviyo": {
                "transport": "http",
                "url": "https://mcp.klaviyo.com/mcp",
                "endpoint_status": "unverified — confirm this MCP endpoint exists before relying on it",
                "description": "Klaviyo — email/SMS campaigns, flows, segmentation",
                "env_vars": [],
                "skills_unlocked": [
                    "send-email-campaign", "email-sequence", "segment-audience",
                ],
            },
            "mailchimp": {
                "transport": "npx",
                "package": "mcp-mailchimp",
                "description": "Mailchimp — email campaigns, lists, automation",
                "env_vars": ["MAILCHIMP_API_KEY"],
                "skills_unlocked": ["send-email-campaign", "email-sequence"],
            },
            "sendgrid": {
                "transport": "npx",
                "package": "mcp-sendgrid",
                "description": "SendGrid — transactional + marketing email",
                "env_vars": ["SENDGRID_API_KEY"],
                "skills_unlocked": ["send-email-campaign"],
            },
            "brevo": {
                "transport": "npx",
                "package": "mcp-brevo",
                "description": "Brevo — email/SMS/WhatsApp, automation, CRM",
                "env_vars": ["BREVO_API_KEY"],
                "skills_unlocked": ["send-email-campaign", "send-sms"],
            },
            "customer-io": {
                "transport": "npx",
                "package": "mcp-customer-io",
                "description": "Customer.io — behavioral email/SMS, segments",
                "env_vars": ["CUSTOMERIO_API_KEY"],
                "skills_unlocked": ["send-email-campaign", "email-sequence"],
            },
        },
    },
    "advertising": {
        "description": "Paid ad platforms",
        "connectors": {
            "google-ads": {
                "transport": "npx",
                "package": "mcp-google-ads",
                "description": "Google Ads — campaigns, keywords, bid optimization",
                "env_vars": [
                    "GOOGLE_ADS_CUSTOMER_ID", "GOOGLE_ADS_DEVELOPER_TOKEN",
                    "GOOGLE_APPLICATION_CREDENTIALS",
                ],
                "skills_unlocked": [
                    "launch-ad-campaign", "performance-check",
                    "budget-tracker", "media-plan",
                ],
            },
            "meta-marketing": {
                "transport": "npx",
                "package": None,
                "package_status": "no-known-npm-package",
                "note": "No verified MCP package on npm — use /digital-marketing-pro:add-integration to wire a custom server. npx runs remote code; verify any package before use.",
                "description": "Meta — Facebook/Instagram ads, audiences",
                "env_vars": ["META_ACCESS_TOKEN", "META_AD_ACCOUNT_ID"],
                "skills_unlocked": [
                    "launch-ad-campaign", "performance-check",
                    "budget-tracker", "media-plan",
                ],
            },
            "linkedin-marketing": {
                "transport": "npx",
                "package": "mcp-linkedin-marketing",
                "description": "LinkedIn Ads — B2B targeting, company pages",
                "env_vars": ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AD_ACCOUNT_ID"],
                "skills_unlocked": [
                    "launch-ad-campaign", "performance-check", "media-plan",
                ],
            },
            "tiktok-ads": {
                "transport": "npx",
                "package": "mcp-tiktok-ads",
                "description": "TikTok Ads — campaigns, creative insights",
                "env_vars": ["TIKTOK_ACCESS_TOKEN", "TIKTOK_ADVERTISER_ID"],
                "skills_unlocked": [
                    "launch-ad-campaign", "performance-check", "media-plan",
                ],
            },
            # ── Official ad-platform MCP servers (checked 2026-10-04) ──────────
            # `access` is load-bearing: connector_resolver never picks a
            # "read-only" connector for a write action. Writes through a
            # "read-write" one run only behind launch-ad-campaign's typed
            # approval gate, and new ad objects are created PAUSED.
            "meta-ads": {
                "transport": "http",
                "url": "https://mcp.facebook.com/ads",
                "access": "read-write",
                "status": "open beta (announced 29 Apr 2026)",
                "setup_note": ("Business-authenticated Meta login on first connect; write tools need an "
                               "ad-account role that can manage ads. Writes only behind the typed "
                               "approval gate; create new campaigns/ad sets/ads with status PAUSED."),
                "source": "https://www.facebook.com/business/news/meta-ads-ai-connectors",
                "description": "Meta Ads AI Connectors — official hosted MCP: reporting, campaign/ad set/ad create+edit, catalogs, signals",
                "env_vars": [],
                "skills_unlocked": [
                    "launch-ad-campaign", "performance-check", "budget-tracker", "media-plan",
                ],
            },
            "google-ads-mcp": {
                "transport": "http",
                "url": "https://<your-self-hosted-host>/mcp",
                "access": "read-only",
                "setup_note": ("Google's open-source server: runs locally over stdio by default "
                               "(pipx run --spec google-ads-mcp==<version> google-ads-mcp — Claude Code only), "
                               "or self-hosted over Streamable HTTP behind its OAuth proxy. Needs OAuth "
                               "(adwords scope) and, for production, a developer token. Strictly READ-ONLY: "
                               "search (GAQL), list_accessible_customers, get_resource_metadata."),
                "source": "https://github.com/googleads/google-ads-mcp",
                "description": "Google Ads MCP (official, open source, READ-ONLY) — GAQL reporting and account metadata",
                "env_vars": [],
                "skills_unlocked": [
                    "performance-check", "budget-tracker", "media-plan", "campaign-audit",
                ],
            },
            "amazon-ads-mcp": {
                "transport": "http",
                "url": "<endpoint-from-your-Amazon-Ads-API-partner-onboarding>",
                "access": "read-write",
                "status": "open beta since 2 Feb 2026 — Amazon Ads partners with active API credentials",
                "setup_note": ("Requires active Amazon Ads API credentials; Amazon's announcement publishes "
                               "no endpoint URL — take it from your API onboarding. Writes only behind the "
                               "typed approval gate, new campaigns PAUSED; DMP never runs delete operations."),
                "source": "https://advertising.amazon.com/library/news/amazon-ads-mcp-server-open-beta",
                "description": "Amazon Ads MCP Server — campaigns, reporting, account settings (partners, open beta)",
                "env_vars": [],
                "skills_unlocked": [
                    "launch-ad-campaign", "performance-check", "budget-tracker", "media-plan",
                ],
            },
        },
    },
    "analytics": {
        "description": "Website and product analytics",
        "connectors": {
            "amplitude": {
                "transport": "http",
                "url": "https://mcp.amplitude.com/mcp",
                "endpoint_status": "unverified — confirm this MCP endpoint exists before relying on it",
                "description": "Amplitude — behavioral analytics, experiments",
                "env_vars": [],
                "skills_unlocked": [
                    "performance-check", "cohort-analysis", "funnel-audit",
                ],
            },
            "google-analytics": {
                "transport": "npx",
                "package": None,
                "package_status": "no-known-npm-package",
                "note": "No verified MCP package on npm — use /digital-marketing-pro:add-integration to wire a custom server. npx runs remote code; verify any package before use.",
                "description": "Google Analytics 4 — traffic, conversions, audiences",
                "env_vars": ["GA_PROPERTY_ID", "GOOGLE_APPLICATION_CREDENTIALS"],
                "skills_unlocked": [
                    "performance-check", "seo-audit",
                    "funnel-audit", "attribution-report",
                ],
            },
            "google-search-console": {
                "transport": "npx",
                "package": "@anthropic/mcp-google-search-console",
                "description": "Google Search Console — rankings, queries, CTR",
                "env_vars": ["GSC_SITE_URL", "GOOGLE_APPLICATION_CREDENTIALS"],
                "skills_unlocked": [
                    "seo-audit", "keyword-research", "content-decay-scan",
                ],
            },
        },
    },
    "social-media": {
        "description": "Social media publishing and management",
        "connectors": {
            "meta-graph": {
                "transport": "npx",
                "package": "mcp-meta-graph",
                "description": "Meta Graph API — Facebook/Instagram organic posting",
                "env_vars": ["META_PAGE_ACCESS_TOKEN", "META_PAGE_ID"],
                "skills_unlocked": ["schedule-social", "social-strategy"],
            },
            "linkedin-publishing": {
                "transport": "npx",
                "package": "mcp-linkedin-publishing",
                "description": "LinkedIn — company page posts, analytics",
                "env_vars": ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_COMPANY_ID"],
                "skills_unlocked": ["schedule-social", "social-strategy"],
            },
            "twitter-x": {
                "transport": "npx",
                "package": "mcp-twitter-x",
                "description": "Twitter/X — tweet scheduling, analytics",
                "env_vars": ["TWITTER_API_KEY", "TWITTER_API_SECRET",
                             "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"],
                "skills_unlocked": ["schedule-social", "social-strategy"],
            },
            "buffer": {
                "transport": "npx",
                "package": "mcp-buffer",
                "description": "Buffer — cross-platform scheduling, analytics",
                "env_vars": ["BUFFER_ACCESS_TOKEN"],
                "skills_unlocked": ["schedule-social", "social-strategy"],
            },
            "hootsuite": {
                "transport": "npx",
                "package": "mcp-hootsuite",
                "description": "Hootsuite — multi-platform scheduling",
                "env_vars": ["HOOTSUITE_ACCESS_TOKEN"],
                "skills_unlocked": ["schedule-social", "social-strategy"],
            },
        },
    },
    "calendar": {
        "description": "Calendar and scheduling",
        "connectors": {
            "google-calendar": {
                "transport": "http",
                "url": "https://calendarmcp.googleapis.com/mcp/v1",
                "description": "Google Calendar — schedule events, deadlines, launches",
                "env_vars": [],
                "skills_unlocked": ["campaign-plan", "launch-plan"],
            },
        },
    },
    "email": {
        "description": "Transactional email (send-from-account)",
        "connectors": {
            "gmail": {
                "transport": "http",
                "url": "https://gmailmcp.googleapis.com/mcp/v1",
                "description": "Gmail — send approval reminders, distribute reports",
                "env_vars": [],
                "skills_unlocked": ["send-notification", "send-report"],
            },
        },
    },
    "pr": {
        "description": "Public relations distribution",
        "connectors": {
            "cision": {
                "transport": "npx",
                "package": None,
                "package_status": "no-known-npm-package",
                "note": "No verified MCP package on npm — use /digital-marketing-pro:add-integration to wire a custom server. npx runs remote code; verify any package before use.",
                "description": "Cision — press release distribution, journalist database",
                "env_vars": ["CISION_API_KEY"],
                "skills_unlocked": ["pr-pitch", "digital-pr"],
            },
            "muckrack": {
                "transport": "npx",
                "package": "mcp-muckrack",
                "description": "Muck Rack — journalist database, pitch tracking",
                "env_vars": ["MUCKRACK_API_KEY"],
                "skills_unlocked": ["pr-pitch", "digital-pr"],
            },
        },
    },
}


def _load_mcp_json():
    """Load the active .mcp.json and return configured server names → entries."""
    if not MCP_JSON.exists():
        return {}
    try:
        data = json.loads(MCP_JSON.read_text(encoding="utf-8"))
        return data.get("mcpServers", {})
    except (json.JSONDecodeError, KeyError, OSError):
        return {}


def is_connector_configured(name, info=None, active_servers=None):
    """Probe whether a single connector is configured RIGHT NOW.

    HTTP connector: counts as configured if its name appears in .mcp.json
                    under mcpServers. (OAuth happens at first use; we can't
                    probe OAuth state without a network call.)

    npx connector:  counts as configured if every env var in its env_vars
                    list is set on the current process. (.mcp.json membership
                    is necessary too, but the env vars are the real gate.)

    Returns (configured: bool, evidence: dict-or-None).
    """
    if info is None:
        info = find_connector(name)
        if info is None:
            return False, None
    if active_servers is None:
        active_servers = _load_mcp_json()

    in_mcp_json = name in active_servers
    transport = info.get("transport")

    if transport == "http":
        return in_mcp_json, {"in_mcp_json": in_mcp_json, "transport": "http"}

    if transport == "npx":
        env_vars = info.get("env_vars", []) or []
        env_status = {v: bool(os.environ.get(v)) for v in env_vars}
        all_set = all(env_status.values()) if env_vars else False
        return (in_mcp_json and all_set), {
            "in_mcp_json": in_mcp_json,
            "transport": "npx",
            "env_vars_set": env_status,
        }

    return False, {"reason": f"unknown transport: {transport}"}


def find_connector(name):
    """Return the connector info dict for a given name, or None."""
    for cat in CONNECTOR_REGISTRY.values():
        if name in cat["connectors"]:
            return cat["connectors"][name]
    return None


def is_read_only(name):
    """True when the registry marks a connector `access: read-only`.

    The resolver uses this to keep read-only servers (e.g. Google's
    google-ads-mcp, which "cannot modify bids, pause campaigns, or create new
    assets") out of every write action's candidate list — choosing one would
    hand the user a manifest the server can never execute."""
    info = find_connector(name)
    return bool(info) and info.get("access") == "read-only"


def find_connector_category(name):
    """Return the category key for a given connector name, or None."""
    for cat_key, cat in CONNECTOR_REGISTRY.items():
        if name in cat["connectors"]:
            return cat_key
    return None


def list_all_connector_names():
    """Flat list of every connector name across all categories."""
    names = []
    for cat in CONNECTOR_REGISTRY.values():
        names.extend(cat["connectors"].keys())
    return names


_SECRET_NEEDLES = (
    "token", "secret", "password", "api_key", "apikey",
    "auth", "credential", "private_key", "client_secret",
    "access_token", "refresh_token",
)


def redact_secrets(obj):
    """Walk a dict/list and redact anything that looks like a credential value.
    Idempotent — safe to call multiple times on the same object."""
    if isinstance(obj, dict):
        redacted = {}
        for k, v in obj.items():
            kl = str(k).lower()
            if any(needle in kl for needle in _SECRET_NEEDLES):
                redacted[k] = "[REDACTED]" if v else None
            else:
                redacted[k] = redact_secrets(v)
        return redacted
    if isinstance(obj, list):
        return [redact_secrets(x) for x in obj]
    return obj


if __name__ == "__main__":
    # Self-test when invoked directly
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "self-test":
        all_names = list_all_connector_names()
        print(f"Registry has {len(all_names)} connectors across "
              f"{len(CONNECTOR_REGISTRY)} categories.")
        print(f"Connectors: {', '.join(sorted(all_names))}")
        # Probe Slack as a sanity check
        configured, evidence = is_connector_configured("slack")
        print(f"\nSlack probe: configured={configured}, evidence={evidence}")
        sys.exit(0)
    print("Usage: python _connector_registry.py self-test")
