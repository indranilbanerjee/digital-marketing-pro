#!/usr/bin/env python3
"""
connector_resolver.py
=====================
The action-resolution layer that sits between the 12 campaign-audit /
launch-campaign actions and the connector registry.

Every action resolves to one of three modes:

  1. real                  — Connector is configured AND the call is safe to
                             execute locally. The action runs end-to-end.
                             Examples: arm-watchdog (writes local config),
                             slack-incoming-webhook posts.

  2. manifest_ready        — Connector is configured but the call is a
                             write/launch/send op that requires user approval
                             or MCP-mediated execution. Returns the exact HTTP
                             request manifest (method, URL, headers, body
                             template, auth_pattern) so the orchestrator
                             (Claude with MCP tool) can execute it.

  3. stub_unconfigured     — No matching connector configured. Returns the
                             original instructive stub PLUS copy-paste setup
                             instructions: which connectors unlock the action,
                             which env vars to set, and a one-line .mcp.json
                             snippet ready to paste.

This module is imported by:
  - performance-monitor.py (inventory, automations, cadence, diagnostic, arm-watchdog)
  - crm-sync.py            (audit-workflows, create-campaign)
  - execution-tracker.py   (enable-automation, schedule-posts, notify-influencers,
                            pr-send, internal-kickoff, launch-ads)
  - seo-executor.py        (audit-current)
  - action-doctor.py       (the /digital-marketing-pro:doctor command)
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from _connector_registry import (
    _load_mcp_json,
    find_connector,
    is_connector_configured,
    is_read_only,
)

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

BRANDS_DIR = _common.brands_root()


# ─────────────────────────────────────────────────────────────────────────────
# ACTION_SPECS — the canonical map of action_id → connector requirements
# ─────────────────────────────────────────────────────────────────────────────
#
# Schema:
#   "action_id": {
#       "purpose":               human-readable one-liner
#       "operation":             "read" | "write" | "local"
#       "candidate_connectors":  callable(kwargs) → list[connector_name]
#                                in priority order; first configured one wins
#       "manual_fallback":       human steps if no connector is configured
#       "fields_returned":       list of fields the implemented call returns
#       "manifest_builder":      callable(connector_name, brand, kwargs) → dict
#                                produces the manifest_ready response
#       "local_executor":        callable(brand, kwargs) → dict
#                                ONLY for operation=="local" actions
#   }
#
# Channel routing: many actions (inventory / automations / cadence) take a
# --channel flag that decides which connector applies. The candidate_connectors
# callable handles that mapping.


CHANNEL_TO_AD_CONNECTOR = {
    "google_ads": "google-ads",
    "meta_ads": "meta-marketing",
    "linkedin_ads": "linkedin-marketing",
    "tiktok_ads": "tiktok-ads",
    "twitter_ads": "twitter-x",
}

# Official, platform-published ad MCP servers (checked 2026-10-04). Tried AFTER
# the per-platform connector for the same channel. Their registry `access`
# field decides whether they can serve write actions (google-ads-mcp cannot).
OFFICIAL_AD_MCP_BY_CHANNEL = {
    "google_ads": ["google-ads-mcp"],
    "meta_ads": ["meta-ads"],
    "amazon_ads": ["amazon-ads-mcp"],
}

# Connectors reached only through an MCP tool — there is no REST manifest to
# hand back, so manifests carry an `mcp_tool_hint` instead of `http_request`.
MCP_TOOL_ONLY_CONNECTORS = {"meta-ads", "google-ads-mcp", "amazon-ads-mcp"}

# Every NEW ad object (campaign / ad set / ad group / ad) is created with this
# status; going live is a separate, separately approved write (launch-ads).
AD_OBJECT_CREATE_STATUS = "PAUSED"

CHANNEL_TO_AUTOMATION_CONNECTOR = {
    "email": ["klaviyo", "hubspot", "mailchimp", "brevo", "customer-io", "sendgrid"],
    "crm":   ["hubspot", "salesforce", "pipedrive", "zoho-crm"],
    "sms":   ["klaviyo", "brevo"],
}

CHANNEL_TO_ORGANIC_SOCIAL_CONNECTOR = {
    "facebook":  ["meta-graph", "buffer", "hootsuite"],
    "instagram": ["meta-graph", "buffer", "hootsuite"],
    "linkedin":  ["linkedin-publishing", "buffer", "hootsuite"],
    "twitter":   ["twitter-x", "buffer", "hootsuite"],
    "tiktok":    ["buffer", "hootsuite"],
}

CRM_CONNECTORS_PRIORITY = ["hubspot", "salesforce", "pipedrive", "zoho-crm"]


def _ad_connector_for_channel(channel):
    """Resolve channel name to ad-platform connector list."""
    if not channel:
        official = [n for names in OFFICIAL_AD_MCP_BY_CHANNEL.values() for n in names]
        return list(CHANNEL_TO_AD_CONNECTOR.values()) + official  # all
    c = channel.lower().replace("-", "_")
    mapped = CHANNEL_TO_AD_CONNECTOR.get(c)
    return ([mapped] if mapped else []) + list(OFFICIAL_AD_MCP_BY_CHANNEL.get(c, []))


def _automation_connector_for_channel(channel):
    """Resolve channel name to automation connector list."""
    if not channel:
        return ["klaviyo", "hubspot"]
    return CHANNEL_TO_AUTOMATION_CONNECTOR.get(channel.lower(), [])


def _organic_connector_for_channel(channel):
    """Resolve channel name to organic-social connector list."""
    if not channel:
        return ["meta-graph", "linkedin-publishing", "buffer"]
    return CHANNEL_TO_ORGANIC_SOCIAL_CONNECTOR.get(channel.lower(), [])


# ─────────────────────────────────────────────────────────────────────────────
# Manifest builders — one per action. Returns the HTTP request shape that
# the orchestrator (Claude via MCP) would execute.
# ─────────────────────────────────────────────────────────────────────────────

def _manifest_inventory(connector_name, brand, kwargs):
    channel = kwargs.get("channel") or "unknown"
    endpoints = {
        "google-ads": {
            "method": "POST",
            "url": "https://googleads.googleapis.com/v24/customers/{customer_id}/googleAds:search",
            "headers": {
                "Authorization": "Bearer {GOOGLE_ADS_OAUTH_TOKEN}",
                "developer-token": "{GOOGLE_ADS_DEVELOPER_TOKEN}",
                "login-customer-id": "{GOOGLE_ADS_CUSTOMER_ID}",
            },
            "body_template": {
                "query": "SELECT campaign.id, campaign.name, campaign.status, campaign_budget.amount_micros, metrics.cost_micros, metrics.conversions FROM campaign WHERE segments.date DURING LAST_30_DAYS"
            },
            "auth_pattern": "OAuth2 + developer-token header",
        },
        "meta-marketing": {
            "method": "GET",
            "url": "https://graph.facebook.com/v24.0/act_{META_AD_ACCOUNT_ID}/campaigns",
            "params": {
                "fields": "id,name,status,daily_budget,updated_time,insights{spend,actions}",
                "date_preset": "last_30d",
                "access_token": "{META_ACCESS_TOKEN}",
            },
            "auth_pattern": "Long-lived access token in query param",
        },
        "linkedin-marketing": {
            "method": "GET",
            "url": "https://api.linkedin.com/rest/adCampaignsV2",
            "headers": {
                "Authorization": "Bearer {LINKEDIN_ACCESS_TOKEN}",
                "LinkedIn-Version": "202606",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            "params": {"q": "search", "search.account.values[0]": "urn:li:sponsoredAccount:{LINKEDIN_AD_ACCOUNT_ID}"},
            "auth_pattern": "OAuth2 Bearer + LinkedIn-Version header",
        },
        "tiktok-ads": {
            "method": "GET",
            "url": "https://business-api.tiktok.com/open_api/v1.3/campaign/get/",
            "headers": {"Access-Token": "{TIKTOK_ACCESS_TOKEN}"},
            "params": {"advertiser_id": "{TIKTOK_ADVERTISER_ID}"},
            "auth_pattern": "Access-Token header",
        },
        "twitter-x": {
            "method": "GET",
            "url": "https://ads-api.twitter.com/12/accounts/{account_id}/campaigns",
            "headers": {"Authorization": "OAuth1.0a {TWITTER_OAUTH_HEADER}"},
            "auth_pattern": "OAuth 1.0a user context",
        },
    }
    spec = endpoints.get(connector_name)
    manifest = {
        "connector": connector_name,
        "channel": channel,
        "operation": "read",
        "http_request": spec,
        "mcp_invocation_hint": f"If the {connector_name} MCP is connected, ask Claude to "
                               f"'list active campaigns' on the {channel} ad account and it will "
                               f"call the MCP tool that wraps this endpoint.",
    }
    if connector_name in MCP_TOOL_ONLY_CONNECTORS:
        manifest["http_request"] = None
        manifest["mcp_tool_hint"] = {
            "google-ads-mcp": ("Call the server's `search` tool with this GAQL: "
                               + endpoints["google-ads"]["body_template"]["query"]
                               + " (use `list_accessible_customers` first to get the customer id)."),
            "meta-ads": ("Use the Meta Ads MCP reporting tools to list campaigns with id, name, "
                         "status, daily budget and last-30-day spend/actions for the ad account."),
            "amazon-ads-mcp": ("Use the Amazon Ads MCP reporting tools to list active campaigns "
                               "with budget, status and last-30-day spend for the advertiser profile."),
        }[connector_name]
    return manifest


def _manifest_automations(connector_name, brand, kwargs):
    channel = kwargs.get("channel") or "email"
    endpoints = {
        "klaviyo": {
            "method": "GET",
            "url": "https://a.klaviyo.com/api/flows/",
            "headers": {
                "Authorization": "Klaviyo-API-Key {KLAVIYO_PRIVATE_KEY}",
                "revision": "2026-04-15",
                "accept": "application/json",
            },
            "params": {"filter": "equals(status,'live')", "page[size]": "100"},
            "auth_pattern": "Klaviyo private API key in Authorization header",
        },
        "hubspot": {
            "method": "GET",
            "url": "https://api.hubapi.com/automation/v4/flows",
            "headers": {"Authorization": "Bearer {HUBSPOT_PRIVATE_APP_TOKEN}"},
            "params": {"limit": "100", "archived": "false"},
            "auth_pattern": "HubSpot Private App OAuth token",
        },
        "mailchimp": {
            "method": "GET",
            "url": "https://{MAILCHIMP_DC}.api.mailchimp.com/3.0/automations",
            "headers": {"Authorization": "Basic {base64(anystring:MAILCHIMP_API_KEY)}"},
            "auth_pattern": "Basic auth, key suffix is data-center",
        },
        "brevo": {
            "method": "GET",
            "url": "https://api.brevo.com/v3/emailCampaigns",
            "headers": {"api-key": "{BREVO_API_KEY}", "accept": "application/json"},
            "params": {"status": "queued", "limit": "100"},
            "auth_pattern": "Brevo custom api-key header (lowercase, NOT Authorization Bearer)",
        },
        "customer-io": {
            "method": "GET",
            "url": "https://api.customer.io/v1/campaigns",
            "headers": {"Authorization": "Bearer {CUSTOMERIO_APP_API_KEY}"},
            "auth_pattern": "Bearer token (App API key, not site/track key)",
        },
        "sendgrid": {
            "method": "GET",
            "url": "https://api.sendgrid.com/v3/marketing/automations",
            "headers": {"Authorization": "Bearer {SENDGRID_API_KEY}"},
            "auth_pattern": "Bearer token",
        },
    }
    spec = endpoints.get(connector_name)
    return {
        "connector": connector_name,
        "channel": channel,
        "operation": "read",
        "http_request": spec,
        "mcp_invocation_hint": f"If {connector_name} MCP is connected, ask 'list active "
                               f"automations / flows' on the brand's account.",
    }


def _manifest_cadence(connector_name, brand, kwargs):
    channel = kwargs.get("channel") or "all"
    endpoints = {
        "meta-graph": {
            "method": "GET",
            "url": "https://graph.facebook.com/v24.0/{META_PAGE_ID}/posts",
            "params": {
                "fields": "id,created_time,message,insights.metric(post_engaged_users,post_impressions)",
                "since": "{90_days_ago_unix}",
                "access_token": "{META_PAGE_ACCESS_TOKEN}",
                "limit": "100",
            },
            "auth_pattern": "Page-scoped access token",
        },
        "linkedin-publishing": {
            "method": "GET",
            "url": "https://api.linkedin.com/rest/posts",
            "headers": {
                "Authorization": "Bearer {LINKEDIN_ACCESS_TOKEN}",
                "LinkedIn-Version": "202606",
            },
            "params": {"q": "author", "author": "urn:li:organization:{LINKEDIN_COMPANY_ID}",
                       "count": "100"},
            "auth_pattern": "OAuth2 Bearer + LinkedIn-Version header",
        },
        "twitter-x": {
            "method": "GET",
            "url": "https://api.twitter.com/2/users/{user_id}/tweets",
            "params": {"max_results": "100", "tweet.fields": "created_at,public_metrics"},
            "headers": {"Authorization": "Bearer {TWITTER_BEARER_TOKEN}"},
            "auth_pattern": "OAuth2 App-only Bearer",
        },
        "buffer": {
            "method": "GET",
            "url": "https://api.bufferapp.com/1/profiles/{profile_id}/updates/sent.json",
            "params": {"access_token": "{BUFFER_ACCESS_TOKEN}", "count": "100"},
            "auth_pattern": "OAuth access_token in query",
        },
        "hootsuite": {
            "method": "GET",
            "url": "https://platform.hootsuite.com/v1/messages",
            "headers": {"Authorization": "Bearer {HOOTSUITE_ACCESS_TOKEN}"},
            "params": {"state": "SENT", "limit": "100"},
            "auth_pattern": "OAuth2 Bearer",
        },
    }
    spec = endpoints.get(connector_name)
    return {
        "connector": connector_name,
        "channel": channel,
        "operation": "read",
        "http_request": spec,
        "mcp_invocation_hint": f"If {connector_name} MCP is connected, ask 'pull last 90 days "
                               f"of organic posts with engagement metrics'.",
    }


def _manifest_diagnostic(connector_name, brand, kwargs):
    endpoints = {
        "google-analytics": {
            "method": "POST",
            "url": "https://analyticsadmin.googleapis.com/v1beta/properties/{GA_PROPERTY_ID}:dataStreams",
            "headers": {"Authorization": "Bearer {GA_OAUTH_TOKEN}"},
            "auth_pattern": "OAuth2 Bearer, scope analytics.readonly",
        },
        "google-search-console": {
            "method": "POST",
            "url": "https://searchconsole.googleapis.com/v1/sites/{GSC_SITE_URL}/searchAnalytics/query",
            "headers": {"Authorization": "Bearer {GSC_OAUTH_TOKEN}"},
            "body_template": {
                "startDate": "{30_days_ago}",
                "endDate": "{today}",
                "dimensions": ["query"],
                "rowLimit": 100,
            },
            "auth_pattern": "OAuth2 Bearer, scope webmasters.readonly",
        },
    }
    spec = endpoints.get(connector_name)
    return {
        "connector": connector_name,
        "operation": "read",
        "http_request": spec,
        "mcp_invocation_hint": f"If {connector_name} MCP is connected, ask 'check tag-firing "
                               f"health and conversion events on the configured property'.",
    }


def _manifest_audit_workflows(connector_name, brand, kwargs):
    endpoints = {
        "hubspot": {
            "method": "GET",
            "url": "https://api.hubapi.com/automation/v4/flows",
            "headers": {"Authorization": "Bearer {HUBSPOT_PRIVATE_APP_TOKEN}"},
            "params": {"limit": "200"},
            "auth_pattern": "HubSpot Private App OAuth token",
        },
        "salesforce": {
            "method": "GET",
            "url": "{SALESFORCE_INSTANCE_URL}/services/data/v60.0/tooling/query/",
            "headers": {"Authorization": "Bearer {SALESFORCE_ACCESS_TOKEN}"},
            "params": {"q": "SELECT Id, MasterLabel, Status, LastModifiedDate FROM Flow"},
            "auth_pattern": "OAuth2 Bearer with Tooling API scope",
        },
        "pipedrive": {
            "method": "GET",
            "url": "https://{PIPEDRIVE_COMPANY_DOMAIN}.pipedrive.com/api/v1/workflows",
            "params": {"api_token": "{PIPEDRIVE_API_TOKEN}"},
            "auth_pattern": "api_token in query string",
        },
        "zoho-crm": {
            "method": "GET",
            "url": "https://www.zohoapis.com/crm/v5/settings/workflow_rules",
            "headers": {"Authorization": "Zoho-oauthtoken {ZOHO_ACCESS_TOKEN}"},
            "auth_pattern": "Zoho OAuth refresh-token flow",
        },
    }
    spec = endpoints.get(connector_name)
    return {
        "connector": connector_name,
        "operation": "read",
        "http_request": spec,
        "mcp_invocation_hint": f"Ask the {connector_name} MCP to 'list all active workflows / "
                               f"flows / automations and flag any that have not executed in 60 days'.",
    }


def _manifest_create_campaign(connector_name, brand, kwargs):
    plan_path = kwargs.get("plan_path")
    endpoints = {
        "hubspot": {
            "method": "POST",
            "url": "https://api.hubapi.com/marketing/v3/campaigns",
            "headers": {
                "Authorization": "Bearer {HUBSPOT_PRIVATE_APP_TOKEN}",
                "Content-Type": "application/json",
            },
            "body_template": {
                "properties": {
                    "hs_name": "{plan.campaign_name}",
                    "hs_start_date": "{plan.start_date}",
                    "hs_end_date": "{plan.end_date}",
                    "hs_goal": "{plan.objective}",
                    "hs_owner": "{plan.owner_email}",
                }
            },
            "auth_pattern": "HubSpot Private App OAuth token",
        },
        "salesforce": {
            "method": "POST",
            "url": "{SALESFORCE_INSTANCE_URL}/services/data/v60.0/sobjects/Campaign/",
            "headers": {
                "Authorization": "Bearer {SALESFORCE_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            "body_template": {
                "Name": "{plan.campaign_name}",
                "StartDate": "{plan.start_date}",
                "EndDate": "{plan.end_date}",
                "Type": "{plan.objective}",
                "OwnerId": "{plan.owner_sf_id}",
            },
            "auth_pattern": "OAuth2 Bearer with API scope",
        },
    }
    spec = endpoints.get(connector_name)
    return {
        "connector": connector_name,
        "operation": "write",
        "approval_required": True,
        "http_request": spec,
        "plan_path": plan_path,
        "mcp_invocation_hint": f"Load {plan_path} → ask {connector_name} MCP to 'create a "
                               f"campaign with these fields'. The MCP will prompt for confirmation "
                               f"before POST.",
    }


def _manifest_enable_automation(connector_name, brand, kwargs):
    automation_id = kwargs.get("automation_id")
    endpoints = {
        "klaviyo": {
            "method": "PATCH",
            "url": f"https://a.klaviyo.com/api/flows/{automation_id}",
            "headers": {
                "Authorization": "Klaviyo-API-Key {KLAVIYO_PRIVATE_KEY}",
                "revision": "2026-04-15",
                "Content-Type": "application/vnd.api+json",
            },
            "body_template": {"data": {"type": "flow", "id": automation_id,
                                       "attributes": {"status": "live"}}},
            "auth_pattern": "Klaviyo private API key (PATCH requires application/vnd.api+json)",
        },
        "hubspot": {
            "method": "PUT",
            "url": f"https://api.hubapi.com/automation/v4/flows/{automation_id}/enroll",
            "headers": {"Authorization": "Bearer {HUBSPOT_PRIVATE_APP_TOKEN}"},
            "auth_pattern": "HubSpot Private App token",
        },
    }
    spec = endpoints.get(connector_name)
    return {
        "connector": connector_name,
        "operation": "write",
        "approval_required": True,
        "automation_id": automation_id,
        "http_request": spec,
        "idempotency_note": "Re-running on an already-enabled flow is a no-op on Klaviyo "
                            "and HubSpot (both return 200 with current state).",
    }


def _manifest_schedule_posts(connector_name, brand, kwargs):
    plan_path = kwargs.get("plan_path")
    endpoints = {
        "meta-graph": {
            "method": "POST",
            "url": "https://graph.facebook.com/v24.0/{META_PAGE_ID}/feed",
            "params": {"access_token": "{META_PAGE_ACCESS_TOKEN}"},
            "body_template": {"message": "{post.copy}", "published": "false",
                              "scheduled_publish_time": "{post.scheduled_unix}"},
        },
        "linkedin-publishing": {
            "method": "POST",
            "url": "https://api.linkedin.com/rest/posts",
            "headers": {"Authorization": "Bearer {LINKEDIN_ACCESS_TOKEN}",
                        "LinkedIn-Version": "202606",
                        "Content-Type": "application/json"},
            "body_template": {"author": "urn:li:organization:{LINKEDIN_COMPANY_ID}",
                              "commentary": "{post.copy}",
                              "visibility": "PUBLIC",
                              "lifecycleState": "DRAFT"},
        },
        "twitter-x": {
            "method": "POST",
            "url": "https://api.twitter.com/2/tweets",
            "headers": {"Authorization": "Bearer {TWITTER_USER_BEARER}"},
            "body_template": {"text": "{post.copy}"},
            "note": "Twitter API v2 does not support scheduling natively; use Buffer/Hootsuite for that.",
        },
        "buffer": {
            "method": "POST",
            "url": "https://api.bufferapp.com/1/updates/create.json",
            "body_template": {"profile_ids[]": "{profile_id}",
                              "text": "{post.copy}",
                              "scheduled_at": "{post.scheduled_iso}",
                              "access_token": "{BUFFER_ACCESS_TOKEN}"},
        },
        "hootsuite": {
            "method": "POST",
            "url": "https://platform.hootsuite.com/v1/messages",
            "headers": {"Authorization": "Bearer {HOOTSUITE_ACCESS_TOKEN}",
                        "Content-Type": "application/json"},
            "body_template": {"text": "{post.copy}",
                              "socialProfileIds": ["{profile_id}"],
                              "scheduledSendTime": "{post.scheduled_iso}"},
        },
    }
    spec = endpoints.get(connector_name)
    return {
        "connector": connector_name,
        "operation": "write",
        "approval_required": True,
        "plan_path": plan_path,
        "http_request": spec,
        "batch_note": "Schedule one post per call. Iterate over plan.posts[]. Verify timezone "
                      "alignment with brand.market before scheduling.",
    }


def _manifest_notify_influencers(connector_name, brand, kwargs):
    plan_path = kwargs.get("plan_path")
    endpoints = {
        "gmail": {
            "method": "POST",
            "url": "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            "headers": {"Authorization": "Bearer {GMAIL_OAUTH_TOKEN}",
                        "Content-Type": "application/json"},
            "body_template": {"raw": "{base64url(MIME message with attachment)}"},
            "auth_pattern": "OAuth2 Bearer, scope gmail.send",
        },
        "sendgrid": {
            "method": "POST",
            "url": "https://api.sendgrid.com/v3/mail/send",
            "headers": {"Authorization": "Bearer {SENDGRID_API_KEY}",
                        "Content-Type": "application/json"},
            "body_template": {
                "personalizations": [{"to": [{"email": "{creator.email}"}]}],
                "from": {"email": "{brand.from_email}"},
                "subject": "{brief.subject}",
                "content": [{"type": "text/html", "value": "{brief.html_body}"}],
                "attachments": [{"content": "{base64(brief.pdf)}",
                                 "filename": "creator-brief.pdf",
                                 "type": "application/pdf"}],
            },
            "auth_pattern": "Bearer API key",
        },
    }
    spec = endpoints.get(connector_name)
    return {
        "connector": connector_name,
        "operation": "write",
        "approval_required": True,
        "plan_path": plan_path,
        "http_request": spec,
        "batch_note": "One send per creator. Log delivery_id back into the plan JSON.",
    }


def _manifest_pr_send(connector_name, brand, kwargs):
    plan_path = kwargs.get("plan_path")
    endpoints = {
        "cision": {
            "method": "POST",
            "url": "https://api.cision.com/v1/press-releases",
            "headers": {"Authorization": "Bearer {CISION_API_KEY}",
                        "Content-Type": "application/json"},
            "body_template": {"title": "{press.title}", "body_html": "{press.html}",
                              "distribution_list_id": "{press.list_id}",
                              "send_at": "{press.send_iso}"},
        },
        "muckrack": {
            "method": "POST",
            "url": "https://muckrack.com/api/v3/pitches",
            "headers": {"Authorization": "Token {MUCKRACK_API_KEY}"},
            "body_template": {"subject": "{press.title}", "body": "{press.html}",
                              "journalist_ids": "{press.journalist_ids}"},
        },
        "gmail": {
            "method": "POST",
            "url": "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            "headers": {"Authorization": "Bearer {GMAIL_OAUTH_TOKEN}"},
            "body_template": {"raw": "{base64url(MIME mail-merge per journalist)}"},
            "auth_pattern": "OAuth2 Bearer + manual mail-merge",
        },
    }
    spec = endpoints.get(connector_name)
    return {
        "connector": connector_name,
        "operation": "write",
        "approval_required": True,
        "plan_path": plan_path,
        "http_request": spec,
        "delivery_note": "PR distribution is regulated under FTC endorsement guidelines — "
                         "ensure disclosure language is in the press release before send.",
    }


def _manifest_internal_kickoff(connector_name, brand, kwargs):
    plan_path = kwargs.get("plan_path")
    endpoints = {
        "slack": {
            "method": "POST",
            "url": "https://slack.com/api/chat.postMessage",
            "headers": {"Authorization": "Bearer {SLACK_BOT_TOKEN}",
                        "Content-Type": "application/json; charset=utf-8"},
            "body_template": {"channel": "{plan.slack_channel}",
                              "text": "{plan.kickoff_message}",
                              "blocks": "{plan.kickoff_blocks}"},
            "auth_pattern": "Bot user OAuth token (chat:write scope)",
        },
        "gmail": {
            "method": "POST",
            "url": "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            "headers": {"Authorization": "Bearer {GMAIL_OAUTH_TOKEN}"},
            "body_template": {"raw": "{base64url(internal email)}"},
        },
        "google-calendar": {
            "method": "POST",
            "url": "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            "headers": {"Authorization": "Bearer {GCAL_OAUTH_TOKEN}",
                        "Content-Type": "application/json"},
            "body_template": {"summary": "{plan.event_title}",
                              "start": {"dateTime": "{plan.start_iso}",
                                        "timeZone": "{plan.timezone}"},
                              "end":   {"dateTime": "{plan.end_iso}",
                                        "timeZone": "{plan.timezone}"},
                              "attendees": "{plan.attendees}"},
        },
    }
    spec = endpoints.get(connector_name)
    return {
        "connector": connector_name,
        "operation": "write",
        "approval_required": True,
        "plan_path": plan_path,
        "http_request": spec,
        "multi_channel_note": "Full internal-kickoff posts to all three: Slack message + email "
                              "+ calendar invite. Run this action three times (once per connector) "
                              "for full coverage.",
    }


def _manifest_launch_ads(connector_name, brand, kwargs):
    plan_path = kwargs.get("plan_path")
    endpoints = {
        "google-ads": {
            "method": "POST",
            "url": "https://googleads.googleapis.com/v24/customers/{customer_id}/campaigns:mutate",
            "headers": {"Authorization": "Bearer {GOOGLE_ADS_OAUTH_TOKEN}",
                        "developer-token": "{GOOGLE_ADS_DEVELOPER_TOKEN}"},
            "body_template": {"operations": [{"update": {"resourceName": "{campaign_resource}",
                                                          "status": "ENABLED"},
                                              "updateMask": "status"}]},
        },
        "meta-marketing": {
            "method": "POST",
            "url": "https://graph.facebook.com/v24.0/{campaign_id}",
            "params": {"access_token": "{META_ACCESS_TOKEN}", "status": "ACTIVE"},
        },
        "linkedin-marketing": {
            "method": "POST",
            "url": "https://api.linkedin.com/rest/adCampaignsV2/{campaign_id}",
            "headers": {"Authorization": "Bearer {LINKEDIN_ACCESS_TOKEN}",
                        "X-RestLi-Method": "PARTIAL_UPDATE",
                        "LinkedIn-Version": "202606"},
            "body_template": {"patch": {"$set": {"status": "ACTIVE"}}},
        },
        "tiktok-ads": {
            "method": "POST",
            "url": "https://business-api.tiktok.com/open_api/v1.3/campaign/status/update/",
            "headers": {"Access-Token": "{TIKTOK_ACCESS_TOKEN}",
                        "Content-Type": "application/json"},
            "body_template": {"advertiser_id": "{TIKTOK_ADVERTISER_ID}",
                              "campaign_ids": "{plan.campaign_ids}",
                              "operation_status": "ENABLE"},
        },
    }
    spec = endpoints.get(connector_name)
    manifest = {
        "connector": connector_name,
        "operation": "write",
        "approval_required": True,
        "approval_gate": ("typed yes on the Execution Summary, recorded with approval-manager.py "
                          "create-approval BEFORE this call and mark-executed after the platform "
                          "confirms (see /digital-marketing-pro:launch-ad-campaign)"),
        "create_status": AD_OBJECT_CREATE_STATUS,
        "create_status_note": ("Campaigns, ad sets/ad groups and ads are created "
                               f"{AD_OBJECT_CREATE_STATUS}; this action is the separate, "
                               "separately approved activation."),
        "plan_path": plan_path,
        "http_request": spec,
        "launch_order_note": "Launch ads in dependency order from plan.launch_sequence "
                             "(typically Google Ads → Meta → LinkedIn → TikTok). Capture "
                             "activated_at per platform for the launch-record.",
    }
    if connector_name in MCP_TOOL_ONLY_CONNECTORS:
        manifest["http_request"] = None
        manifest["mcp_tool_hint"] = (
            f"Through the {connector_name} MCP server's campaign-management tools, set status "
            "ACTIVE only on plan.campaign_ids that exist and are currently PAUSED — never create "
            "and activate in one call, never delete.")
    return manifest


def _manifest_audit_current_seo(connector_name, brand, kwargs):
    endpoints = {
        "google-search-console": {
            "method": "POST",
            "url": "https://searchconsole.googleapis.com/v1/sites/{GSC_SITE_URL}/searchAnalytics/query",
            "headers": {"Authorization": "Bearer {GSC_OAUTH_TOKEN}"},
            "body_template": {"startDate": "{90_days_ago}", "endDate": "{today}",
                              "dimensions": ["query", "page"], "rowLimit": 1000},
        },
        "ahrefs": {
            "method": "GET",
            "url": "https://api.ahrefs.com/v3/site-explorer/metrics",
            "headers": {"Authorization": "Bearer {AHREFS_API_KEY}", "Accept": "application/json"},
            "params": {"target": "{brand.domain}", "mode": "domain", "date": "{today}"},
            "auth_pattern": "Bearer token (Ahrefs site-explorer endpoint is /metrics not /overview)",
        },
        "similarweb": {
            "method": "GET",
            "url": "https://api.similarweb.com/v1/website/{brand.domain}/total-traffic-and-engagement/visits",
            "params": {"api_key": "{SIMILARWEB_API_KEY}",
                       "start_date": "{90_days_ago}", "end_date": "{today}",
                       "granularity": "monthly"},
        },
        "semrush": {
            "method": "GET",
            "url": "https://api.semrush.com/",
            "params": {"type": "domain_organic", "key": "{SEMRUSH_API_KEY}",
                       "domain": "{brand.domain}",
                       "export_columns": "Ph,Po,Nq,Cp,Co", "display_limit": "50"},
        },
    }
    spec = endpoints.get(connector_name)
    return {
        "connector": connector_name,
        "operation": "read",
        "http_request": spec,
        "mcp_invocation_hint": f"Ask {connector_name} MCP to 'audit current SEO state: ranking "
                               f"keywords, page indexation, schema markup health'.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Local executors — actions that genuinely need no remote API
# ─────────────────────────────────────────────────────────────────────────────

def _execute_arm_watchdog(brand, kwargs):
    """Activate a day-1 KPI watchdog. Writes a watchdog config locally that
    the orchestrator (or a scheduled cron) can read to know what to monitor."""
    brand_dir = BRANDS_DIR / brand
    if not brand_dir.exists():
        return {
            "status": "error",
            "error": f"Brand '{brand}' not found. Run /digital-marketing-pro:brand-setup first.",
        }

    watchdog_dir = brand_dir / "watchdogs"
    watchdog_dir.mkdir(exist_ok=True)

    campaign_id = kwargs.get("campaign_id") or "unspecified"
    kpis = kwargs.get("kpis") or []
    if isinstance(kpis, str):
        kpis = [k.strip() for k in kpis.split(",") if k.strip()]

    if not kpis:
        kpis = ["cpc", "conversion_volume", "ctr", "deliverability_rate", "error_rate"]

    deviation_pct = kwargs.get("deviation_pct", 20)

    watchdog_id = f"wd-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    config = {
        "watchdog_id": watchdog_id,
        "brand": brand,
        "campaign_id": campaign_id,
        "kpis_monitored": kpis,
        "alert_thresholds": {
            k: {"deviation_pct": deviation_pct, "direction": "either"}
            for k in kpis
        },
        "armed_at": datetime.now().isoformat(),
        "next_check_at": None,
        "status": "armed",
        "last_check_at": None,
        "check_interval_hours": kwargs.get("check_interval_hours", 6),
        "alert_channels": kwargs.get("alert_channels", ["local-log"]),
        "notes": "This watchdog config is read by performance-monitor's detect-anomalies "
                 "step. To enable Slack/email alerts, configure the slack or gmail connector "
                 "and re-arm with --alert-channels slack,email.",
    }

    path = watchdog_dir / f"{watchdog_id}.json"
    path.write_text(json.dumps(config, indent=2))

    return {
        "status": "armed",
        "watchdog_id": watchdog_id,
        "path": str(path),
        "campaign_id": campaign_id,
        "kpis_monitored": kpis,
        "alert_thresholds_pct": deviation_pct,
        "check_interval_hours": config["check_interval_hours"],
        "next_action": f"performance-monitor detects metric anomalies against this watchdog's "
                       f"thresholds. Run /digital-marketing-pro:status to see active watchdogs.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# ACTION_SPECS table
# ─────────────────────────────────────────────────────────────────────────────

ACTION_SPECS: dict[str, dict[str, Any]] = {
    "inventory": {
        "script": "performance-monitor",
        "purpose": "List active campaigns / ad groups / keywords / audiences / creatives for the channel.",
        "operation": "read",
        "candidate_connectors": lambda kw: _ad_connector_for_channel(kw.get("channel")),
        "manual_fallback": "Open the channel's native UI and export the active-campaigns list.",
        "fields_returned": ["campaign_id", "campaign_name", "status", "daily_budget",
                            "last_modified", "spend_30d", "conversions_30d"],
        "manifest_builder": _manifest_inventory,
    },
    "automations": {
        "script": "performance-monitor",
        "purpose": "List active automations / flows / journeys with last-execution and per-step health.",
        "operation": "read",
        "candidate_connectors": lambda kw: _automation_connector_for_channel(kw.get("channel", "email")),
        "manual_fallback": "Open the email/CRM platform; list active automations; export to JSON.",
        "fields_returned": ["automation_id", "name", "trigger", "last_execution",
                            "active_subscribers", "deliverability_30d"],
        "manifest_builder": _manifest_automations,
    },
    "cadence": {
        "script": "performance-monitor",
        "purpose": "Report posting cadence per platform over the last 90 days.",
        "operation": "read",
        "candidate_connectors": lambda kw: _organic_connector_for_channel(kw.get("channel")),
        "manual_fallback": "Pull from each platform's native analytics or your scheduler tool.",
        "fields_returned": ["platform", "post_count_90d", "engagement_rate", "follower_trend"],
        "manifest_builder": _manifest_cadence,
    },
    "diagnostic": {
        "script": "performance-monitor",
        "purpose": "Diagnose tag-firing, conversion tracking, consent-mode, event naming on GA4/GSC.",
        "operation": "read",
        "candidate_connectors": lambda kw: ["google-analytics", "google-search-console"],
        "manual_fallback": "Open GA4 DebugView; check Tag Assistant; verify GSC ownership.",
        "fields_returned": ["ga4_property_id", "events_firing_24h", "conversion_events_configured",
                            "consent_mode_state", "gsc_property_ownership"],
        "manifest_builder": _manifest_diagnostic,
    },
    "arm-watchdog": {
        "script": "performance-monitor",
        "purpose": "Activate day-1 monitoring on a launched campaign.",
        "operation": "local",
        "candidate_connectors": lambda kw: [],
        "manual_fallback": "Build a Looker Studio / GA4 dashboard and schedule a 24-hour manual review.",
        "fields_returned": ["watchdog_id", "campaign_id", "kpis_monitored",
                            "alert_thresholds", "next_check_at"],
        "local_executor": _execute_arm_watchdog,
    },
    "audit-workflows": {
        "script": "crm-sync",
        "purpose": "List every active workflow in the configured CRM; report orphaned workflows.",
        "operation": "read",
        "candidate_connectors": lambda kw: CRM_CONNECTORS_PRIORITY,
        "manual_fallback": "Open CRM > Workflows / Automation tab. Sort by last-execution-date.",
        "fields_returned": ["workflow_id", "name", "trigger", "last_execution_at",
                            "execution_count_30d", "broken_links", "owner"],
        "manifest_builder": _manifest_audit_workflows,
    },
    "create-campaign": {
        "script": "crm-sync",
        "purpose": "Create a Campaign object in the configured CRM from the approved plan JSON.",
        "operation": "write",
        "candidate_connectors": lambda kw: CRM_CONNECTORS_PRIORITY,
        "manual_fallback": "Open CRM > Campaigns > New Campaign; copy fields from plan JSON.",
        "fields_returned": ["crm_platform", "campaign_id", "campaign_name", "owner", "created_at"],
        "manifest_builder": _manifest_create_campaign,
    },
    "enable-automation": {
        "script": "execution-tracker",
        "purpose": "Enable an automation / journey / sequence in the email or CRM platform.",
        "operation": "write",
        "candidate_connectors": lambda kw: ["klaviyo", "hubspot", "mailchimp", "brevo", "customer-io"],
        "manual_fallback": "Open the email platform > Flows; find automation_id; toggle Active = ON.",
        "fields_returned": ["platform", "automation_id", "previous_state", "new_state", "enabled_at"],
        "manifest_builder": _manifest_enable_automation,
    },
    "schedule-posts": {
        "script": "execution-tracker",
        "purpose": "Schedule organic-social posts defined in the campaign plan.",
        "operation": "write",
        "candidate_connectors": lambda kw: ["buffer", "hootsuite", "meta-graph",
                                            "linkedin-publishing", "twitter-x"],
        "manual_fallback": "Open scheduler; paste each post's copy + asset + schedule from plan JSON.",
        "fields_returned": ["scheduler", "scheduled_post_ids", "platform_count",
                            "first_post_at", "last_post_at"],
        "manifest_builder": _manifest_schedule_posts,
    },
    "notify-influencers": {
        "script": "execution-tracker",
        "purpose": "Send campaign-specific creator brief to each contracted influencer in the plan.",
        "operation": "write",
        "candidate_connectors": lambda kw: ["gmail", "sendgrid"],
        "manual_fallback": "Open brief PDF for each creator; email from brand's account manager.",
        "fields_returned": ["delivery_channel", "creator_count", "delivered_ids",
                            "failed_ids", "sent_at"],
        "manifest_builder": _manifest_notify_influencers,
    },
    "pr-send": {
        "script": "execution-tracker",
        "purpose": "Distribute the launch press release to the configured press contact list.",
        "operation": "write",
        "candidate_connectors": lambda kw: ["cision", "muckrack", "gmail"],
        "manual_fallback": "Send press release as mail-merge from brand's PR account; track opens.",
        "fields_returned": ["distribution_tool", "press_contact_count", "sent_at", "tracking_id"],
        "manifest_builder": _manifest_pr_send,
    },
    "internal-kickoff": {
        "script": "execution-tracker",
        "purpose": "Send internal kickoff: Slack message + email + calendar invite for launch day.",
        "operation": "write",
        "candidate_connectors": lambda kw: ["slack", "gmail", "google-calendar"],
        "manual_fallback": "Post in Slack; email distribution_list; create launch-day calendar event.",
        "fields_returned": ["slack_message_url", "email_message_id", "calendar_event_id",
                            "recipients_count"],
        "manifest_builder": _manifest_internal_kickoff,
    },
    "launch-ads": {
        "script": "execution-tracker",
        "purpose": "Activate paid-ads across Google / Meta / LinkedIn / TikTok / Amazon in dependency order.",
        "operation": "write",
        "candidate_connectors": lambda kw: ["google-ads", "meta-marketing", "meta-ads",
                                            "linkedin-marketing", "tiktok-ads",
                                            "amazon-ads-mcp"],
        "manual_fallback": "Open each ad platform UI; activate campaigns matching plan.campaign_ids.",
        "fields_returned": ["platforms_activated", "campaign_ids_per_platform",
                            "total_daily_budget", "activated_at"],
        "manifest_builder": _manifest_launch_ads,
    },
    "audit-current": {
        "script": "seo-executor",
        "purpose": "Audit current SEO state for the brand.",
        "operation": "read",
        "candidate_connectors": lambda kw: ["google-search-console", "ahrefs",
                                            "similarweb", "semrush"],
        "manual_fallback": "Pull from GSC, Lighthouse, rich-results.test.google.com.",
        "fields_returned": ["pages_published_90d", "ranking_keywords_top_50",
                            "schema_state_per_page", "internal_link_density",
                            "indexation_health", "core_web_vitals", "ai_overview_citation_rate"],
        "manifest_builder": _manifest_audit_current_seo,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def resolve_action(action_id: str, brand: str, **kwargs) -> dict:
    """Resolve an action_id into one of three modes: real / manifest_ready /
    stub_unconfigured. Caller is responsible for invoking the right backing
    script with the manifest if needed."""
    spec = ACTION_SPECS.get(action_id)
    if not spec:
        return {
            "status": "unknown_action",
            "action": action_id,
            "known_actions": sorted(ACTION_SPECS.keys()),
        }

    # 1. Local execution — runs end-to-end with no connector needed
    if spec["operation"] == "local":
        executor = spec.get("local_executor")
        if executor is None:
            return {"status": "error", "error": f"local action {action_id} has no executor"}
        result = executor(brand, kwargs)
        result.setdefault("mode", "real")
        result.setdefault("action", action_id)
        return result

    # 2. Find a configured connector from the candidate list
    candidates = spec["candidate_connectors"](kwargs) or []
    active_servers = _load_mcp_json()
    configured = []
    candidate_status = []
    for c_name in candidates:
        info = find_connector(c_name)
        if info is None:
            candidate_status.append({"connector": c_name, "status": "unknown_connector"})
            continue
        if spec["operation"] == "write" and is_read_only(c_name):
            # A read-only server can never execute a write; picking it would
            # return a manifest that cannot run (e.g. google-ads-mcp).
            candidate_status.append({"connector": c_name, "status": "skipped_read_only",
                                     "transport": info["transport"]})
            continue
        is_cfg, evidence = is_connector_configured(c_name, info, active_servers)
        candidate_status.append({
            "connector": c_name,
            "configured": is_cfg,
            "transport": info["transport"],
            "evidence": evidence,
        })
        if is_cfg:
            configured.append(c_name)

    if not configured:
        # stub_unconfigured response
        return {
            "status": "stub_unconfigured",
            "mode": "stub_unconfigured",
            "action": action_id,
            "script": spec["script"],
            "brand": brand,
            "purpose": spec["purpose"],
            "operation": spec["operation"],
            "manual_fallback": spec["manual_fallback"],
            "fields_returned_when_implemented": spec["fields_returned"],
            "candidate_connectors": candidates,
            "candidate_status": candidate_status,
            "setup_hint": _build_setup_hint(candidates),
            "note": (f"No matching connector is configured. The action contract is stable — "
                     f"once you configure any of {candidates}, this same call returns a "
                     f"manifest_ready response with the exact HTTP request to make."),
        }

    # 3. manifest_ready — connector is configured; return the request manifest
    chosen = configured[0]
    builder = spec.get("manifest_builder")
    manifest = builder(chosen, brand, kwargs) if builder else {"connector": chosen}
    return {
        "status": "manifest_ready",
        "mode": "manifest_ready",
        "action": action_id,
        "script": spec["script"],
        "brand": brand,
        "purpose": spec["purpose"],
        "operation": spec["operation"],
        "chosen_connector": chosen,
        "other_configured_connectors": configured[1:],
        "manifest": manifest,
        "fields_returned_when_implemented": spec["fields_returned"],
        "execution_note": (
            "Execute via the connector's MCP tool (preferred) — Claude will route the request "
            "through OAuth/auth automatically. For approval-required write ops, the MCP will "
            "prompt before sending. To execute outside Claude, use the manifest.http_request "
            "shape directly."),
    }


def _build_setup_hint(candidates: list[str]) -> dict:
    """Build copy-pasteable setup hints for a list of candidate connectors."""
    hints = []
    for c_name in candidates:
        info = find_connector(c_name)
        if info is None:
            continue
        if info["transport"] == "http":
            hint = {
                "connector": c_name,
                "transport": "http",
                "one_step_setup": f"Add this entry to .mcp.json under mcpServers:",
                "mcp_json_snippet": {c_name: {"type": "http", "url": info.get("url", "")}},
                "auth_flow": "OAuth on first use — no env vars needed.",
                "platforms": "Works in Claude Code CLI + IDE + Anthropic Cowork (HTTP transport).",
            }
            if info.get("setup_note"):
                hint["auth_flow"] = info["setup_note"]
            if info.get("access"):
                hint["access"] = info["access"]
            if "<" in info.get("url", ""):
                hint["url_placeholder"] = ("Replace the <...> part of the URL with your own "
                                           "endpoint before adding it.")
            hints.append(hint)
        elif info.get("package_status") == "no-known-npm-package" or not info.get("package"):
            hints.append({
                "connector": c_name,
                "transport": "unavailable",
                "package_status": "no-known-npm-package",
                "note": info.get(
                    "note",
                    "No verified MCP package on npm — use /digital-marketing-pro:add-integration "
                    "to wire a custom server. npx runs remote code; verify any package before use."),
            })
        else:
            hints.append({
                "connector": c_name,
                "transport": "npx",
                "step_1_set_env_vars": info.get("env_vars", []),
                "step_2_mcp_json_snippet": {
                    c_name: {
                        "command": "npx",
                        "args": ["-y", info.get("package", "")],
                        "env": {v: f"${{{v}}}" for v in info.get("env_vars", [])},
                    }
                },
                "platforms_warning": "npx connectors run in Claude Code CLI/IDE ONLY. "
                                     "Anthropic Cowork cannot run stdio MCPs — use an aggregator "
                                     "(pipedream / composio / zapier) for Cowork instead.",
            })
    return {"setup_options": hints, "note": "Pick the connector that matches your team's existing stack."}


def all_action_ids():
    """Flat list of every action_id this resolver handles."""
    return sorted(ACTION_SPECS.keys())


def action_spec(action_id):
    """Return the spec for a single action (without invoking it)."""
    return ACTION_SPECS.get(action_id)


if __name__ == "__main__":
    # Self-test mode
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "self-test":
        print(f"connector_resolver has {len(ACTION_SPECS)} actions registered:")
        for aid, spec in sorted(ACTION_SPECS.items()):
            print(f"  {aid:22s}  op={spec['operation']:<6s}  script={spec['script']}")
        print("\nTesting resolve_action('audit-workflows', 'test-brand'):")
        r = resolve_action("audit-workflows", "test-brand")
        print(json.dumps(r, indent=2)[:600])
        sys.exit(0)
    print("Usage: python connector_resolver.py self-test")
