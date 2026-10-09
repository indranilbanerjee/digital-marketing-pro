---
description: "Execute an audit or launch action against its real API; writes need --confirm. \"actually fire this action\""
argument-hint: "--action <id> [--brand <slug>] [--execute] [--confirm] [--channel <name>] [--data <json>]"
allowed-tools: Bash Read
disable-model-invocation: false
---

# /digital-marketing-pro:execute-action — Fire an Action Against Real API

Resolves an action via `connector_resolver` and (optionally) executes it via `connector_executor` using stdlib `urllib.request`. No third-party deps, no OAuth flow — credentials read from env vars only.

## Three modes of operation

| Flag combo | What happens |
|------------|-------------|
| no flags | Dry-run: returns the resolved manifest (same as `/digital-marketing-pro:doctor --action <id>`) — no HTTP call |
| `--execute` only | Read ops fire immediately. Write ops are BLOCKED with `execute_blocked_reason`. |
| `--execute --confirm` | Write ops also fire. Execution is logged to `~/.claude-marketing/brands/{brand}/executions/`. |

## Which connectors execute end-to-end via Python

These execute against the real API when the named env var is set (10 actions, 8 connectors):

| Connector | Env var | Auth | Verified endpoint |
|-----------|---------|------|---------------------|
| Slack | `SLACK_BOT_TOKEN` | Bearer xoxb- | `POST chat.postMessage` |
| HubSpot | `HUBSPOT_PRIVATE_APP_TOKEN` | Bearer | `GET /automation/v4/flows`, `POST /marketing/v3/campaigns` |
| Klaviyo | `KLAVIYO_PRIVATE_KEY` | `Klaviyo-API-Key`, revision 2026-04-15 | `GET /api/flows`, `PATCH /api/flows/{id}` (vnd.api+json) |
| SendGrid | `SENDGRID_API_KEY` | Bearer SG. | `POST /v3/mail/send` (202) |
| Brevo | `BREVO_API_KEY` | `api-key:` header (NOT Bearer) | `POST /v3/smtp/email` |
| Customer.io | `CUSTOMERIO_APP_API_KEY` | Bearer (App API key, not Site/Track) | `POST /v1/send/email` |
| Mailchimp | `MAILCHIMP_API_KEY` | Basic auth, dc from key suffix | `GET /3.0/automations` |
| Ahrefs | `AHREFS_API_KEY` | Bearer | `GET /v3/site-explorer/metrics` |

## Which connectors REQUIRE the MCP path (cannot execute from Python)

OAuth-only connectors return `execute_blocked_reason: "use MCP path"`. Use Claude with the connector's MCP installed instead:

Google Ads, Meta Marketing, LinkedIn Marketing, LinkedIn Publishing, TikTok Ads, Twitter/X (OAuth 1.0a), Gmail, Google Calendar, Google Analytics, Google Search Console, Meta Graph (organic), Salesforce, Pipedrive, Zoho CRM, Buffer, Hootsuite, Cision, Muckrack, Amplitude, Similarweb, SEMrush, Moz, Intercom, Canva, Figma, and the official ad-platform MCP servers: Meta Ads AI Connectors (`meta-ads`), Google Ads MCP (`google-ads-mcp`, read-only, so it is never chosen for a write), and Amazon Ads MCP (`amazon-ads-mcp`). For these three the manifest carries an `mcp_tool_hint` instead of an HTTP request, and any new ad object is created PAUSED.

For all of these, the **`manifest_ready`** response includes the exact HTTP request shape Claude's MCP tool will send — so even though Python can't fire it directly, you can see what would go out.

## Quick examples

```
# Dry-run: see the manifest for HubSpot list-workflows
/digital-marketing-pro:execute-action --action audit-workflows --brand acme

# Read op: fire HubSpot list-workflows (read-only, no --confirm needed)
HUBSPOT_PRIVATE_APP_TOKEN=pat-na1-xxx \
/digital-marketing-pro:execute-action --action audit-workflows --brand acme --execute

# Write op: post Slack kickoff message (requires --confirm)
SLACK_BOT_TOKEN=xoxb-xxx \
/digital-marketing-pro:execute-action --action internal-kickoff --brand acme \
  --data '{"plan": {"slack_channel": "#launches", "kickoff_message": "Launch day!"}}' \
  --execute --confirm

# Write op without --confirm: BLOCKED
/digital-marketing-pro:execute-action --action create-campaign --brand acme --execute
# -> execute_blocked_reason: "action create-campaign is a write op; --confirm flag is required"
```

## Safety gates summary

1. **No --execute** -> no HTTP call ever fires
2. **Write op without --confirm** -> blocked with reason
3. **OAuth-only connector** -> blocked with alternative pointing to MCP path
4. **Missing env var** -> blocked with `setup_hint_credential` naming the var
5. **Unconfigured connector** -> blocked at resolver level (mode=stub_unconfigured)
6. **Unresolved placeholder** -> request NEVER sent (would have leaked literal `{VAR}` text)
7. **Every fired call** -> logged to `~/.claude-marketing/brands/{brand}/executions/exec-{connector}-{action}-{ts}.json`

## See also

- [scripts/connector_executor.py](../scripts/connector_executor.py) — the underlying executor
- [scripts/connector_resolver.py](../scripts/connector_resolver.py) — the resolver
- [scripts/action-doctor.py](../scripts/action-doctor.py) — readiness diagnostic (no execution)
- [/digital-marketing-pro:doctor](doctor.md) — per-action readiness map

## Run

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/connector_executor.py" "$@"
```
