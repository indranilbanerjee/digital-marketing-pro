# Connectors

## How tool references work

Plugin files use `~~category` as a placeholder for whatever tool the user connects in that category. For example, `~~CRM` might mean HubSpot, Salesforce, or any other CRM with an MCP server.

Plugins are **tool-agnostic** — they describe workflows in terms of categories (SEO, email marketing, CRM, etc.) rather than specific products. No `.mcp.json` ships (it is gitignored) — nothing is pre-configured. You opt into specific MCP servers from `.mcp.json.connectors-reference` (HTTP) or `.mcp.json.example` (npx); any MCP server in that category works.

## Connectors for this plugin

| Category | Placeholder | Included servers | Other options |
|----------|-------------|-----------------|---------------|
| Chat | `~~chat` | Slack | Microsoft Teams |
| Design | `~~design` | Canva, Figma | Adobe Creative Cloud |
| CRM | `~~CRM` | HubSpot (remote MCP, GA) | Salesforce, Pipedrive, Zoho |
| Advertising | `~~advertising` | Meta Ads AI Connectors (read/write), Google Ads MCP (read-only), Amazon Ads MCP (partners) | Unified ads MCPs (below) |
| Product analytics | `~~product analytics` | Amplitude | Mixpanel, Google Analytics |
| Knowledge base | `~~knowledge base` | Notion | Confluence, Guru |
| SEO | `~~SEO` | Ahrefs, Similarweb | Semrush, Moz, DataForSEO |
| Email marketing | `~~email marketing` | Klaviyo | Mailchimp, Brevo, Customer.io, SendGrid |
| Calendar | `~~calendar` | Google Calendar | Outlook Calendar |
| Email | `~~email` | Gmail | Outlook |
| Payments | `~~payments` | Stripe | — |
| Project management | `~~project management` | Asana | Linear, Jira, Monday.com |
| CMS | `~~CMS` | Webflow | WordPress, HubSpot CMS |

## Platform-level integrations

Some services are connected at the **Claude platform level** rather than through MCP. These are managed in Claude Desktop → Settings → Integrations and work automatically in Cowork sessions.

| Service | Platform integration | MCP alternative |
|---------|---------------------|-----------------|
| Google Drive | Yes — connect in Settings → Integrations | Also available via npx (`mcp-google-drive`) |
| Google Docs | Yes — connect in Settings → Integrations | — (no standalone npx server; covered by the Google Drive integration) |

Platform-level integrations work even if they don't appear in the `/digital-marketing-pro:integrations` connector dashboard.

## Categories without HTTP connectors (Claude Code only)

The following categories require local npx/stdio MCP servers. They work in Claude Code but not in Cowork. See `.mcp.json.example` for configuration.

| Category | Available via npx | When HTTP becomes available |
|----------|------------------|---------------------------|
| Productivity | Google Drive, Google Sheets | Google Drive/Docs also available as platform integration |
| Advertising | Google Ads, Meta Ads, LinkedIn Ads, TikTok Ads | **Official servers first** (see "Official ad-platform and CRM MCP servers" below): Meta's hosted server is HTTP today; Google's is read-only and local/self-hosted; Amazon's is partner-only. For LinkedIn/TikTok, or one surface across many platforms, use a unified ads MCP (see "Unified ads MCPs" below). Per-platform OAuth still applies. |
| Analytics | Google Analytics, Google Search Console | Connect via Connectors panel when available |
| Social media | Buffer, Twitter/X, LinkedIn | Connect via Connectors panel when available |
| SMS/Messaging | Twilio | Connect via Connectors panel when available |
| Translation | DeepL, Sarvam AI | Connect via Connectors panel when available |
| Database | Supabase, PostgreSQL | Connect via Connectors panel when available |

## Official ad-platform and CRM MCP servers (checked 2026-10-04)

These servers are published by the platforms themselves. Like everything else here they are **opt-in**: no `.mcp.json` ships, and you copy an entry from `.mcp.json.connectors-reference` yourself.

| Entry | Endpoint | Access | Status | Source |
|---|---|---|---|---|
| `meta-ads` — Meta Ads AI Connectors | `https://mcp.facebook.com/ads` (Meta-hosted) | **Read + write**: reporting, create/edit campaigns, ad sets and ads, catalogs, signals | Open beta (announced 29 Apr 2026); business-authenticated login | [Meta announcement](https://www.facebook.com/business/news/meta-ads-ai-connectors) · [developer docs](https://developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-mcp-server/ads-mcp-server-overview) |
| `google-ads-mcp` — Google Ads MCP | Local stdio via `pipx run --spec google-ads-mcp==<version> google-ads-mcp` (Claude Code only), or self-hosted Streamable HTTP behind its OAuth proxy | **Read-only**: `search` (GAQL), `list_accessible_customers`, `get_resource_metadata`. Google: "strictly read-only. It cannot modify bids, pause campaigns, or create new assets." | Open source (Apache-2.0) | [GitHub](https://github.com/googleads/google-ads-mcp) · [Google guide](https://developers.google.com/google-ads/api/docs/developer-toolkit/mcp-server) |
| `amazon-ads-mcp` — Amazon Ads MCP Server | Not published on the announcement page; take it from your Amazon Ads API onboarding | **Read + write**, including create/update/delete campaigns, reporting, account settings, billing data | Open beta since 2 Feb 2026, for Amazon Ads partners with active API credentials | [Amazon Ads news](https://advertising.amazon.com/library/news/amazon-ads-mcp-server-open-beta) |
| `hubspot` — remote HubSpot MCP | `https://mcp.hubspot.com` (Streamable HTTP; OAuth 2.1 + PKCE) | **Read + write**: create/update contacts, companies, deals, tickets, line items, products, activities | Generally available since 13 Apr 2026 | [HubSpot changelog](https://developers.hubspot.com/changelog/remote-hubspot-mcp-server-is-now-generally-available) |

**How DMP uses the write-capable ones**
- Writes run only through the **typed approval gate** in `/digital-marketing-pro:launch-ad-campaign`: Execution Summary → the user types `yes` → `approval-manager.py` records the approval → execute → mark executed.
- Every **new** campaign, ad set/ad group and ad is **created PAUSED**, with the status set explicitly in the tool call. Going live is a separate, separately approved write.
- DMP never runs delete operations through these servers.
- The action resolver (`scripts/connector_resolver.py`) never picks a read-only server such as `google-ads-mcp` for a write action.

**Transport check (2026-10-04).** MCP spec revision 2026-07-28 classifies the old HTTP+SSE transport as **Deprecated** and eligible for removal ([spec](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)). Catalog changes:
- Asana moved to its V2 Streamable HTTP endpoint (`https://mcp.asana.com/v2/mcp`). Asana shut down the V1 `/sse` server on 11 May 2026 ([Asana docs](https://developers.asana.com/docs/using-asanas-mcp-server)).
- Webflow moved to `https://mcp.webflow.com/mcp` ([Webflow changelog](https://developers.webflow.com/home/changelog/2025/11/24)).
- Make.com moved to its stateless Streamable HTTP URL ([Make docs](https://developers.make.com/mcp-server)).
- Replicate is **flagged**: its setup page still lists only an `/sse` URL.

## Unified ads MCPs (added v3.4, corrected v3.4.1)

As of May 2026, three options exist for unifying multiple ad-platform connectors. Pick ONE — overlap creates duplicate tools. Configuration lives in `.mcp.json.connectors-reference` under `_section_unified_ads_mcps`; copy the entry you want into `.mcp.json` to activate. **All endpoint URLs and platform-coverage claims below were verified May 2026 — re-verify before production use as these are early-stage services and endpoints may move.**

| Option | Platforms covered | Auth | Source | When to pick |
|---|---|---|---|---|
| **synter-media-ai** | 7 platforms — Google, Meta, LinkedIn, Microsoft, Reddit, TikTok, X | `X-Synter-Key` header | [github.com/Synter-Media-AI/mcp-server](https://github.com/Synter-Media-AI/mcp-server) | Agencies running 3+ of these platforms |
| **ryze-ai-google-ads** | Google Ads (primary); separate per-platform connectors for Meta + GA4 via app.get-ryze.ai/mcp-connector | OAuth on first connect (managed service) | [get-ryze.ai](https://www.get-ryze.ai) | Google-Ads-heavy teams that want a vendor-managed connector |
| **northbeam-mcp-selfhosted** | Google + Meta + LinkedIn + TikTok | BYO per-platform OAuth or API keys (self-hosted) | [github.com/mattcoatsworth/Northbeam-MCP-Server](https://github.com/mattcoatsworth/Northbeam-MCP-Server) (community-maintained) | Org policy forbids sending OAuth tokens to a third-party SaaS |

All three are HTTP — fully Cowork-compatible. They replace the per-platform stdio servers in `.mcp.json.example` for teams who want one ads tool surface instead of one per platform.

## Managing connectors

Use these skills to discover and manage your integrations:

| Skill | What it does |
|-------|-------------|
| `/digital-marketing-pro:integrations` | Status dashboard — see what's connected, what's available, which skills each connector unlocks |
| `/digital-marketing-pro:connect <name>` | Guided setup — step-by-step instructions for connecting a specific service (e.g., `/digital-marketing-pro:connect google-ads`) |
| `/digital-marketing-pro:add-integration` | Custom setup — add any MCP server not in the registry (npm packages or custom APIs) |
| `/digital-marketing-pro:credential-switch` | Agency mode — switch active credentials when managing multiple client accounts |

## Advanced configuration (Claude Code)

For Claude Code CLI users who want the full 68-server configuration with npx/stdio transports, rename the example file:

```bash
cp .mcp.json.example .mcp.json
```

This replaces the HTTP-only configuration with the full set of local MCP servers. Requires Node.js, npx, and the appropriate API keys configured as environment variables.
