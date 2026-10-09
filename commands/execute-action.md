---
description: "Execute an audit or launch action against its real API; writes need an approval record. \"actually fire this action\""
argument-hint: "--action <id> [--brand <slug>] [--execute] [--approval-id <id>] [--channel <name>] [--data <json>]"
allowed-tools: Bash Read
disable-model-invocation: false
---

# /digital-marketing-pro:execute-action — Fire an Action Against Real API

> **Script location.** If your host does not set `${CLAUDE_PLUGIN_ROOT}`, the scripts are in this plugin's `scripts/` folder, next to `skills/`.

Resolves an action via `connector_resolver` and (optionally) executes it via `connector_executor` using stdlib `urllib.request`. No third-party deps, no OAuth flow — credentials read from env vars only.

## How a write fires: three steps

| Step | Command | What happens |
|------|---------|-------------|
| 1. Prepare | `--execute` (no `--approval-id`) | Builds the exact request (data substituted, credential named but never shown), writes a **pending** approval record holding its sha256 and a script-rendered `preview`, sends nothing, exits 2. |
| 2. Approve | `approval-manager.py --action approve --id <id>` | Run this **only after the user reads the preview and types `yes`**. Pending records expire after 30 minutes unreviewed. |
| 3. Fire | `--execute --approval-id <id>` | Rebuilds the request; it fires only if the hash matches, the record is approved, inside its 15-minute fire window, and unused. The record is consumed once the request is sent (any HTTP status) and released if nothing was sent (for example a DNS failure). |

Read operations fire on `--execute` alone. With no flags it is a dry run: the resolved manifest, no HTTP call, no record. `--confirm` is accepted for old scripts but adds nothing.

Show the user the `preview` exactly as printed: it is the request that will be sent, so never paraphrase it. If any step errors, stop and report it; never work around the gate with another tool.

**Batches.** `--prepare-batch plan.json` (a JSON list of `{"action", "data", "channel"}` items) writes ONE record with an itemised preview. After one `approve`, fire each item with the same `--approval-id`; each item is consumed on its own and a changed item fails alone.

**Standing approvals.** For routine low-risk writes (for example launch-day Slack pings), `approval-manager.py --action create-standing --data '{"kind": "executor", "connector": "slack", "actions": ["internal-kickoff"], "max_uses_per_day": 5, "days": 7, "summary": "..."}'` creates a bounded rule: scoped to one connector and the listed actions, a daily cap, at most 7 days, every use logged. It must be approved like any record.

## What this proves, and what it does not

- It proves the approval step ran for this exact request, once, inside its window. It cannot prove who typed `yes`: the model runs every command, including `approve`, and a process running as you can edit the record files. Every fire is logged with a full copy of the record, so a forged record is visible afterwards.
- **The one check the model cannot fake is your host's permission prompt.** Keep `connector_executor.py --execute` out of your host's command allowlist so the host asks you every time. Bypass or auto-approve modes remove that check.
- **Writes through MCP server tools are outside this code check.** Google Ads, Meta, LinkedIn, TikTok, Amazon and the other OAuth connectors below are called by the model directly through their MCP tools; they rely on the skill's typed `yes` and your host's permission prompt for that tool.

## Which connectors execute end-to-end via Python

These execute against the real API when the named env var is set (8 connectors). Only each connector's own environment variables (same vendor prefix) are ever substituted into a request.

| Connector | Env var | Auth | Endpoints the executor builds |
|-----------|---------|------|---------------------|
| Slack | `SLACK_BOT_TOKEN` | Bearer xoxb- | `POST chat.postMessage` |
| HubSpot | `HUBSPOT_PRIVATE_APP_TOKEN` | Bearer | `GET /automation/v4/flows`, `POST /marketing/v3/campaigns`, `PUT /automation/v4/flows/{id}/enroll` |
| Klaviyo | `KLAVIYO_PRIVATE_KEY` | `Klaviyo-API-Key`, revision 2026-04-15 | `GET /api/flows`, `PATCH /api/flows/{id}` (vnd.api+json) |
| SendGrid | `SENDGRID_API_KEY` | Bearer SG. | `GET /v3/marketing/automations`, `POST /v3/mail/send` (202) |
| Brevo | `BREVO_API_KEY` | `api-key:` header (NOT Bearer) | `GET /v3/emailCampaigns` (read only; sends go through the Brevo MCP) |
| Customer.io | `CUSTOMERIO_APP_API_KEY` | Bearer (App API key, not Site/Track) | `GET /v1/campaigns` (read only; sends go through the Customer.io MCP) |
| Mailchimp | `MAILCHIMP_API_KEY` | Basic auth, dc from key suffix | `GET /3.0/automations` |
| Ahrefs | `AHREFS_API_KEY` | Bearer | `GET /v3/site-explorer/metrics` |

## Which connectors REQUIRE the MCP path (cannot execute from Python)

OAuth-only connectors return `execute_blocked_reason: "use MCP path"`. Use your host with the connector's MCP installed instead:

Google Ads, Meta Marketing, LinkedIn Marketing, LinkedIn Publishing, TikTok Ads, Twitter/X (OAuth 1.0a), Gmail, Google Calendar, Google Analytics, Google Search Console, Meta Graph (organic), Salesforce, Pipedrive, Zoho CRM, Buffer, Hootsuite, Cision, Muckrack, Amplitude, Similarweb, SEMrush, Moz, Intercom, Canva, Figma, and the official ad-platform MCP servers: Meta Ads AI Connectors (`meta-ads`), Google Ads MCP (`google-ads-mcp`, read-only, so it is never chosen for a write), and Amazon Ads MCP (`amazon-ads-mcp`). For these three the manifest carries an `mcp_tool_hint` instead of an HTTP request, and any new ad object is created PAUSED.

For all of these, the **`manifest_ready`** response shows the request shape the MCP tool will send. These writes are outside the approval-record check (see above).

## Quick examples

```
# Dry-run: see the manifest for HubSpot list-workflows
/digital-marketing-pro:execute-action --action audit-workflows --brand acme

# Read op: fire HubSpot list-workflows (no approval needed)
HUBSPOT_PRIVATE_APP_TOKEN=pat-na1-xxx \
/digital-marketing-pro:execute-action --action audit-workflows --brand acme --execute

# Write op, step 1: prepare (sends nothing, prints preview + approval_id, exit 2)
SLACK_BOT_TOKEN=xoxb-xxx \
/digital-marketing-pro:execute-action --action internal-kickoff --brand acme \
  --data '{"plan": {"slack_channel": "#launches", "kickoff_message": "Launch day!", "kickoff_blocks": "none"}}' \
  --execute

# Step 2, only after the user types yes:
python "${CLAUDE_PLUGIN_ROOT}/scripts/approval-manager.py" --brand acme --action approve --id <approval_id>

# Step 3: fire the identical command with the id (any change to --data is refused)
SLACK_BOT_TOKEN=xoxb-xxx \
/digital-marketing-pro:execute-action --action internal-kickoff --brand acme \
  --data '{"plan": {"slack_channel": "#launches", "kickoff_message": "Launch day!", "kickoff_blocks": "none"}}' \
  --execute --approval-id <approval_id>
```

## Safety gates summary

1. **No --execute** -> no HTTP call ever fires, and resolving has no side effects
2. **Write op without a matching approved record** -> nothing is sent (exit 2, with the next step)
3. **Changed request, reused, expired or other-brand record** -> refused before anything is sent
4. **OAuth-only connector** -> blocked with alternative pointing to the MCP path (outside the record check)
5. **Missing env var** -> blocked with `setup_hint_credential` naming the var
6. **Unconfigured connector** -> blocked at resolver level (mode=stub_unconfigured)
7. **Unresolved placeholder** -> request NEVER sent (would have leaked literal `{VAR}` text)
8. **Every fired call** -> logged to `brands/{brand}/executions/exec-{connector}-{action}-{ts}.json`, writes with a full copy of the approval record

## See also

- [scripts/connector_executor.py](../scripts/connector_executor.py) — the underlying executor
- [scripts/approval-manager.py](../scripts/approval-manager.py) — approve, standing approvals, history
- [scripts/connector_resolver.py](../scripts/connector_resolver.py) — the resolver
- [scripts/action-doctor.py](../scripts/action-doctor.py) — readiness diagnostic (no execution)
- [/digital-marketing-pro:doctor](doctor.md) — per-action readiness map

## Run

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/connector_executor.py" "$@"
```
