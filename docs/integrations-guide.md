# Integrations & CRM Guide

> **Digital Marketing Pro** v1.2.0 | For marketing operations managers
>
> This guide covers all 12 MCP integrations available in the plugin, how to configure them, how to manage credentials across multiple clients, and what the plugin can do with or without live connections.

---

## Table of Contents

1. [How MCP Integrations Work](#1-how-mcp-integrations-work)
2. [Setting Up Your First Integration](#2-setting-up-your-first-integration)
3. [Integration-by-Integration Setup](#3-integration-by-integration-setup)
   - [Analytics & Measurement](#analytics--measurement)
   - [Advertising Platforms](#advertising-platforms)
   - [CRM & Customer Data](#crm--customer-data)
   - [Email Marketing](#email-marketing)
   - [Commerce](#commerce)
   - [SEO & Competitive Intelligence](#seo--competitive-intelligence)
   - [Productivity & Reporting](#productivity--reporting)
4. [Multi-CRM Setup for Agencies](#4-multi-crm-setup-for-agencies)
5. [What Works Without Integrations](#5-what-works-without-integrations)
6. [Data Privacy & Security](#6-data-privacy--security)

---

## 1. How MCP Integrations Work

### What Is MCP?

MCP stands for **Model Context Protocol**. It is the standard that allows Claude to connect to external data sources and services during a session. When an MCP server is configured, Claude can read from and write to that service on your behalf, using your credentials, in real time.

In practical terms: instead of you manually pulling a GA4 report, pasting it into the conversation, and asking Claude to analyze it, the GA4 MCP server lets Claude pull that data directly. You ask a question, Claude fetches the numbers, and you get an answer grounded in your real data.

### How the Plugin Uses MCP

The plugin ships with a `.mcp.json` configuration file that defines 12 MCP server connections. Each one maps to a marketing platform or productivity tool. None of them are active by default. They activate only when you set the required environment variables for that service.

This is the key design principle: **the plugin works fully without any integrations enabled.** All 13 skill modules, 86 reference knowledge files, scoring scripts, brand voice analysis, compliance checking, and campaign planning features operate entirely offline using built-in benchmarks and reference data. MCP integrations layer real data on top of that foundation.

### What Happens Under the Hood

1. When Claude Code starts a session, it reads `.mcp.json` and attempts to start each configured MCP server.
2. If the required environment variables for a server are set, the server starts and Claude gains access to that platform's data.
3. If the variables are missing, the server silently skips. No errors, no broken functionality.
4. During the session, when a module needs data (for example, the `analytics-insights` module building a performance report), it checks whether the relevant MCP connection is available. If it is, it pulls real data. If not, it falls back to industry benchmarks from `industry-profiles.md`.

### Where Credentials Live

All API keys and credentials are stored exclusively in **environment variables** on your machine. Nothing is hardcoded in the plugin. Nothing is written to plugin data files. The `.mcp.json` file references variables using `${VARIABLE_NAME}` syntax, and those values are resolved from your environment at runtime.

No data is sent to third parties beyond the direct MCP server connections you configure. Each MCP server runs locally on your machine and connects directly to the service API.

---

## 2. Setting Up Your First Integration

The following walkthrough uses Google Analytics 4 as a worked example. The same pattern applies to every integration in the plugin.

### Step 1: Get Your Credentials

You need two things for GA4:

- **GA4 Property ID**: Found in Google Analytics under Admin > Property Settings. It is a numeric ID (e.g., `123456789`).
- **Google Application Credentials**: A service account JSON key file from Google Cloud Console. Go to APIs & Services > Credentials > Create Credentials > Service Account. Generate a JSON key and download it. Then grant this service account "Viewer" access to your GA4 property.

### Step 2: Set Environment Variables

Set these before launching Claude Code. How you do this depends on your operating system.

**macOS / Linux (terminal)**

```bash
export GA_PROPERTY_ID="123456789"
export GOOGLE_APPLICATION_CREDENTIALS="/Users/you/keys/ga4-service-account.json"
```

To make these persist across sessions, add them to your `~/.bashrc`, `~/.zshrc`, or `~/.bash_profile`.

**Windows (Command Prompt)**

```cmd
set GA_PROPERTY_ID=123456789
set GOOGLE_APPLICATION_CREDENTIALS=C:\Users\you\keys\ga4-service-account.json
```

**Windows (PowerShell)**

```powershell
$env:GA_PROPERTY_ID = "123456789"
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\Users\you\keys\ga4-service-account.json"
```

To make these persist on Windows, set them as System or User environment variables via System Properties > Environment Variables.

### Step 3: Verify the Connection

Start Claude Code and ask something that would require GA4 data:

```
You: Pull my website traffic data for the last 30 days
```

- **If GA4 MCP is configured:** Claude pulls real sessions, pageviews, conversion data, and traffic sources directly from your property.
- **If GA4 MCP is not configured:** Claude tells you the integration is not available and uses industry benchmarks from `industry-profiles.md` (covering 22 industries) to provide estimated ranges instead.

### Step 4: What Changes When the Integration Is Active

With GA4 connected, the following plugin capabilities upgrade from benchmark-based to data-driven:

| Capability | Without GA4 | With GA4 |
|---|---|---|
| Performance reports | Industry benchmark ranges | Your actual traffic and conversion numbers |
| Anomaly detection | Not available | Flags unusual spikes or drops in your metrics |
| Campaign post-mortems | Generic framework | References your real conversion data and attribution |
| KPI tracking | Suggested targets based on industry | Tracks against your actual historical performance |
| Audience intelligence | Persona-based assumptions | Real demographic and behavioral data from your visitors |

---

## 3. Integration-by-Integration Setup

### Analytics & Measurement

#### Google Analytics 4

**What it enables:** Real-time access to your website traffic, conversion funnels, audience demographics, event tracking, and engagement metrics. Powers the `analytics-insights` and `performance-report` modules with actual data instead of benchmarks.

**Required environment variables:**

| Variable | Description |
|---|---|
| `GA_PROPERTY_ID` | Your GA4 property ID (numeric) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to a Google Cloud service account JSON key file |

**Where to get credentials:**
1. GA4 Property ID: Google Analytics > Admin > Property Settings
2. Service account: Google Cloud Console > APIs & Services > Credentials > Create Service Account > Generate JSON key
3. Grant the service account "Viewer" role on your GA4 property in the GA4 admin panel under Property Access Management

**Example usage:**
```
You: Show me my top 10 landing pages by conversion rate this month
```

---

#### Google Search Console

**What it enables:** Search ranking data, click-through rates by query, index coverage status, Core Web Vitals scores, and crawl statistics. Powers the `seo-audit` and `aeo-audit` modules with real search performance data.

**Required environment variables:**

| Variable | Description |
|---|---|
| `GSC_SITE_URL` | Your verified site URL (e.g., `https://example.com` or `sc-domain:example.com`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to a Google Cloud service account JSON key file (same file used for GA4) |

**Where to get credentials:**
1. Site URL: Google Search Console > Settings > Property selector
2. Service account: Same as GA4 above. Add the service account email as a user in Search Console with "Full" permission.

**Example usage:**
```
You: Which queries have high impressions but low CTR? I want to optimize those pages.
```

---

### Advertising Platforms

#### Google Ads

**What it enables:** Campaign performance data, keyword-level metrics, Quality Scores, bid recommendations, ad group structure analysis, and budget pacing. Powers the `paid-advertising` and `ad-creative` modules with live campaign data.

**Required environment variables:**

| Variable | Description |
|---|---|
| `GOOGLE_ADS_CUSTOMER_ID` | Your Google Ads customer ID (format: `123-456-7890`, without dashes in the env var) |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Developer token from Google Ads API Center |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to a Google Cloud service account JSON key file |

**Where to get credentials:**
1. Customer ID: Google Ads > top-right corner (the 10-digit number)
2. Developer token: Google Ads > Tools & Settings > API Center. Apply for a developer token if you do not have one. Basic access is sufficient for read-only operations.
3. Service account: Same Google Cloud setup. Enable the Google Ads API in your GCP project and link the service account.

**Example usage:**
```
You: Which of my Google Ads campaigns have the highest CPA this quarter? Suggest optimizations.
```

---

#### Meta Business Suite (Facebook & Instagram)

**What it enables:** Ad campaign performance across Facebook and Instagram, audience insights, creative performance analytics, spend tracking, and ROAS calculations. Powers the `paid-advertising` module for Meta platforms.

**Required environment variables:**

| Variable | Description |
|---|---|
| `META_ACCESS_TOKEN` | A long-lived user or system access token from Meta |
| `META_AD_ACCOUNT_ID` | Your ad account ID (format: `act_123456789`) |

**Where to get credentials:**
1. Access token: Meta Business Suite > Business Settings > System Users > Generate Token. Select the `ads_read` and `ads_management` permissions. Convert to a long-lived token (60-day expiry) or use a system user token for permanent access.
2. Ad account ID: Meta Business Suite > Business Settings > Ad Accounts. The ID starts with `act_`.

**Example usage:**
```
You: Compare performance across my active Meta ad sets and flag any with a frequency above 3.
```

---

#### LinkedIn Marketing

**What it enables:** LinkedIn ad campaign performance, audience demographics, engagement metrics on sponsored content, company page analytics, and lead gen form data. Powers the `paid-advertising` module for LinkedIn campaigns.

**Required environment variables:**

| Variable | Description |
|---|---|
| `LINKEDIN_ACCESS_TOKEN` | OAuth 2.0 access token with Marketing API scope |
| `LINKEDIN_AD_ACCOUNT_ID` | Your LinkedIn ad account ID (numeric) |

**Where to get credentials:**
1. Access token: Create an app in the LinkedIn Developer Portal. Request the `r_ads`, `r_ads_reporting`, and `r_organization_social` scopes. Generate an OAuth 2.0 token through the token flow or the Developer Portal token tool.
2. Ad account ID: LinkedIn Campaign Manager > Account Settings. The numeric ID is in the URL.

**Example usage:**
```
You: What is my LinkedIn CPL trend over the last 90 days? How does it compare to industry benchmarks?
```

---

### CRM & Customer Data

#### HubSpot CRM

**What it enables:** Contact and company records, deal pipeline data, email engagement metrics, lifecycle stage distribution, lead scoring data, and marketing attribution. Powers the `audience-intelligence` and `funnel-architect` modules with real customer data.

**Required environment variables:**

| Variable | Description |
|---|---|
| `HUBSPOT_ACCESS_TOKEN` | A private app access token from HubSpot |

**Where to get credentials:**
1. Go to HubSpot > Settings > Integrations > Private Apps
2. Create a new private app
3. Under Scopes, enable: `crm.objects.contacts.read`, `crm.objects.deals.read`, `crm.objects.companies.read`, `content`, and `e-commerce` as needed
4. Copy the generated access token

**Example usage:**
```
You: Pull my deal pipeline and identify which stages have the highest drop-off rates.
```

---

### Email Marketing

#### Mailchimp

**What it enables:** Email campaign analytics (open rates, click rates, bounce rates), list health metrics, automation workflow performance, A/B test results, and subscriber segmentation data. Powers the `email-sequence` module with real engagement data.

**Required environment variables:**

| Variable | Description |
|---|---|
| `MAILCHIMP_API_KEY` | Your Mailchimp API key |

**Where to get credentials:**
1. Go to Mailchimp > Account & Billing > Extras > API Keys
2. Create a new API key
3. The key format is `xxxxxxxxxx-usXX` where `usXX` is your data center

**Example usage:**
```
You: Analyze my last 10 email campaigns and identify which subject line patterns get the highest open rates.
```

---

### Commerce

#### Stripe

**What it enables:** Revenue data, payment conversion rates, subscription metrics, churn rates, average order value, lifetime value calculations, and refund tracking. Powers the `analytics-insights` module with real commerce data for revenue attribution.

**Required environment variables:**

| Variable | Description |
|---|---|
| `STRIPE_API_KEY` | Your Stripe secret key (use a restricted read-only key for safety) |

**Where to get credentials:**
1. Go to Stripe Dashboard > Developers > API Keys
2. Recommended: Create a restricted key with read-only permissions for the data types you want to analyze (Charges, Customers, Subscriptions, Invoices)
3. Do not use your full secret key. A restricted read-only key limits exposure.

**Example usage:**
```
You: What is my monthly recurring revenue trend and churn rate over the last 6 months?
```

---

### SEO & Competitive Intelligence

#### SEMrush

**What it enables:** Keyword research with search volume and difficulty scores, competitor domain analysis, backlink data, site audit findings, position tracking, and advertising research. Powers the `seo-audit`, `competitor-analysis`, and `content-brief` modules with competitive intelligence.

**Required environment variables:**

| Variable | Description |
|---|---|
| `SEMRUSH_API_KEY` | Your SEMrush API key |

**Where to get credentials:**
1. Go to SEMrush > Subscription Info > API Units (or SEMrush > Settings > API)
2. Your API key is displayed on the API access page
3. Note: API calls consume API units from your SEMrush plan. Monitor usage.

**Example usage:**
```
You: Find keyword gaps between my domain and our top 3 competitors.
```

---

#### Ahrefs

**What it enables:** Backlink profile analysis, keyword explorer with click data, content gap analysis, rank tracking, referring domain quality assessment, and broken link detection. Powers the `seo-audit`, `digital-pr`, and `competitor-analysis` modules.

**Required environment variables:**

| Variable | Description |
|---|---|
| `AHREFS_API_KEY` | Your Ahrefs API key |

**Where to get credentials:**
1. Go to Ahrefs > Account Settings > API
2. Generate an API key (requires an active Ahrefs subscription)
3. API access and rate limits depend on your subscription tier

**Example usage:**
```
You: Audit my backlink profile and flag any toxic or low-quality referring domains.
```

---

### Productivity & Reporting

#### Google Sheets

**What it enables:** Export reports, campaign data, content calendars, and KPI dashboards directly to Google Sheets. Allows the `performance-report` and `content-calendar` modules to write structured outputs to spreadsheets you can share with stakeholders.

**Required environment variables:**

| Variable | Description |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to a Google Cloud service account JSON key file (same as GA4/GSC) |

**Where to get credentials:**
1. Same service account JSON used for GA4 and GSC
2. Enable the Google Sheets API in your GCP project
3. Share the target spreadsheet with the service account email address (the `client_email` field in the JSON key file)

**Example usage:**
```
You: Export this month's performance report to Google Sheets.
```

---

#### Slack

**What it enables:** Send marketing reports, campaign alerts, weekly performance digests, and team notifications to Slack channels. Useful for automated reporting workflows and keeping stakeholders informed without leaving Claude Code.

**Required environment variables:**

| Variable | Description |
|---|---|
| `SLACK_BOT_TOKEN` | A Slack bot token starting with `xoxb-` |

**Where to get credentials:**
1. Go to api.slack.com > Your Apps > Create New App (From Scratch)
2. Under OAuth & Permissions, add the scopes: `chat:write`, `channels:read`, and `files:write`
3. Install the app to your workspace
4. Copy the Bot User OAuth Token (`xoxb-...`)
5. Invite the bot to any channels where you want it to post (`/invite @YourBotName`)

**Example usage:**
```
You: Post this week's campaign summary to the #marketing-reports Slack channel.
```

---

## 4. Multi-CRM Setup for Agencies

### The Challenge

The `.mcp.json` file supports a single set of credentials per MCP server. If you manage one brand, this is straightforward. But agencies managing multiple clients -- each with their own HubSpot portal, their own GA4 property, their own Meta ad account -- run into a credential management challenge.

### Current Limitation (Stated Honestly)

There is no built-in per-brand MCP credential switching in v1.2.0. When you switch brands with `/dm:switch-brand`, the brand profile, voice settings, compliance rules, and campaign history all switch. But the MCP credentials do not automatically change. The environment variables remain whatever was set when the session started.

This is a known gap. Below are four workaround patterns, ordered from simplest to most robust.

---

### Pattern A: Environment Variable Swapping

The simplest approach. Manually change the environment variables before starting work on a different client.

```bash
# Working on Client A (their GA4 property, their HubSpot portal)
export GA_PROPERTY_ID="111111111"
export HUBSPOT_ACCESS_TOKEN="pat-na1-client-a-token"

# Switching to Client B
export GA_PROPERTY_ID="222222222"
export HUBSPOT_ACCESS_TOKEN="pat-na1-client-b-token"
```

**Best for:** Agencies with 2-3 clients on the same platforms. Quick to execute, nothing to maintain beyond the credential values themselves.

**Limitation:** Requires restarting Claude Code after changing environment variables for MCP servers to pick up the new values.

---

### Pattern B: Multiple .mcp.json Files

Maintain separate MCP configuration files per client and swap the active one.

```bash
# One-time setup: create per-client configs
cp .mcp.json .mcp-acme-corp.json      # Edit with Acme Corp's credentials
cp .mcp.json .mcp-techflow.json        # Edit with TechFlow's credentials
cp .mcp.json .mcp-greenleaf.json       # Edit with GreenLeaf's credentials

# Before starting a session for Acme Corp
cp .mcp-acme-corp.json .mcp.json

# Before starting a session for TechFlow
cp .mcp-techflow.json .mcp.json
```

**Best for:** Agencies with clients on different platform combinations. One client might use GA4 + HubSpot + Mailchimp while another uses GA4 + Stripe + Slack. Each `.mcp.json` file can have a different set of servers enabled.

**Limitation:** Requires file swap and Claude Code restart between clients.

---

### Pattern C: CRM-Agnostic Workflow (No Live Connection)

Skip MCP entirely for CRM data. Export from whatever CRM the client uses and bring the data into the session manually.

```
You: Here is our client's pipeline data exported from Salesforce:

Stage            | Count | Avg Value | Avg Days
Qualification    | 45    | $12,000   | 8
Proposal         | 23    | $18,500   | 14
Negotiation      | 11    | $25,000   | 22
Closed Won       | 8     | $27,000   | 31

Analyze this pipeline and create a nurture campaign targeting deals stuck in Negotiation for more than 20 days.
```

**Best for:** Clients on CRMs that do not have MCP server support (Salesforce, Pipedrive, Zoho, Close, Monday CRM, etc.). Also useful when a client is unwilling to provide API credentials and prefers to share exports.

**Trade-off:** You lose the real-time query capability (Claude cannot pull fresh data mid-conversation), but all analysis, planning, and content creation modules work the same way once the data is in the session.

---

### Pattern D: Per-Session Configuration

Create shell scripts that set all environment variables for a specific client, then launch Claude Code.

```bash
# File: clients/acme-corp/env.sh
export GA_PROPERTY_ID="111111111"
export GSC_SITE_URL="https://acmecorp.com"
export GOOGLE_APPLICATION_CREDENTIALS="/keys/acme-corp-sa.json"
export HUBSPOT_ACCESS_TOKEN="pat-na1-acme-token"
export MAILCHIMP_API_KEY="abc123def456-us14"
export SLACK_BOT_TOKEN="xoxb-acme-slack-token"

# File: clients/techflow/env.sh
export GA_PROPERTY_ID="222222222"
export GSC_SITE_URL="https://techflow.io"
export GOOGLE_APPLICATION_CREDENTIALS="/keys/techflow-sa.json"
export META_ACCESS_TOKEN="EAAxxxxxxxx"
export META_AD_ACCOUNT_ID="act_987654321"
export STRIPE_API_KEY="rk_live_techflow_restricted_key"
```

Usage:

```bash
# Start a session for Acme Corp
source ./clients/acme-corp/env.sh && claude

# Start a session for TechFlow
source ./clients/techflow/env.sh && claude
```

**Best for:** Agencies that want clean, repeatable separation between client sessions. Each session starts with a known-good credential set. Combine this with `/dm:switch-brand` at session start to load the matching brand profile.

**Security note:** Store these env files outside of version control. Add `clients/*/env.sh` to your `.gitignore`.

---

### Future Roadmap

Per-brand MCP configuration -- where switching brands with `/dm:switch-brand` would automatically swap the active MCP credentials -- is a potential enhancement for a future plugin version. This would eliminate the manual credential management described above.

---

## 5. What Works Without Integrations

The plugin is designed to be fully functional with zero MCP connections enabled. Here is what the offline baseline includes:

### Always Available (No Integrations Required)

| Capability | What Powers It |
|---|---|
| Content creation (briefs, calendars, social posts, email sequences) | 13 skill modules + `platform-specs.md` (format specs for 15+ platforms) |
| Brand voice scoring | `brand-voice-scorer.py` + local brand profile |
| Content quality scoring | `content-scorer.py` + `scoring-rubrics.md` |
| Campaign planning and strategy | Skill modules + `industry-profiles.md` (22 industries) |
| Compliance checking | `compliance-rules.md` (16 jurisdictions including GDPR, CCPA, CAN-SPAM, CASL) |
| AEO/GEO optimization | `aeo-audit` and `aeo-geo` modules with built-in optimization frameworks |
| Competitor analysis frameworks | `competitor-analysis` module (manual input of competitor data) |
| Crisis communication | `crisis-response` module with response templates and escalation frameworks |
| Funnel architecture and audits | `funnel-architect` and `funnel-audit` modules |
| Landing page audits | `landing-page-audit` module with CRO heuristics |
| Influencer briefs | `influencer-brief` and `influencer-creator` modules |
| Brand setup and switching | `brand-setup` and `switch-brand` skills |
| Campaign memory and tracking | `campaign-tracker.py` (local persistent storage) |

### Significantly Enhanced by Integrations

These capabilities work offline but deliver substantially more value with live data:

| Capability | Without Integration | With Integration |
|---|---|---|
| **Performance reports** | Framework with industry benchmarks | Real metrics from GA4, GSC, ad platforms |
| **Anomaly detection** | Not possible (no data to monitor) | Flags unusual changes in traffic, conversions, spend |
| **Competitive keyword intelligence** | Manual input only | SEMrush/Ahrefs pull live keyword and backlink data |
| **CRM-driven campaigns** | You provide pipeline data manually | HubSpot feeds real contact and deal data |
| **Revenue attribution** | Estimated based on industry benchmarks | Stripe provides actual revenue and conversion data |
| **Automated reporting** | Reports generated in-session | Sheets export + Slack delivery to stakeholders |
| **Email performance optimization** | Best practices and frameworks | Mailchimp provides real open/click/bounce data |
| **Ad platform optimization** | General recommendations | Platform-specific data from Google Ads, Meta, LinkedIn |

### Recommended Starting Configuration

If you are setting up integrations for the first time, this priority order gives you the most value per effort:

1. **Google Analytics 4** -- Unlocks real performance data across almost every module
2. **Google Search Console** -- Pairs with GA4 for complete organic search visibility
3. **Your primary ad platform** (Google Ads, Meta, or LinkedIn) -- Whichever you spend the most on
4. **Your CRM** (HubSpot) -- Connects campaign planning to real pipeline data
5. **Google Sheets** -- Enables export and sharing of reports with stakeholders
6. **Everything else** -- Add as needed based on your workflow

---

## 6. Data Privacy & Security

### Credential Storage

- All API keys and credentials are stored exclusively in **environment variables** on your local machine
- The `.mcp.json` file contains only variable references (`${VARIABLE_NAME}`), never actual credential values
- No credentials are stored in plugin code, plugin data files, brand profiles, or campaign tracking data
- The plugin never writes credentials to disk, logs, or temporary files

### Data Flow

- Each MCP server runs as a local process on your machine
- Data flows directly from your machine to the service API (e.g., your machine to Google Analytics API)
- Data is not routed through Anthropic's servers, the plugin author's servers, or any third party
- Query results are used within your Claude Code session and are subject to Claude Code's standard data handling

### Client Data Isolation

- Each brand's data is stored in its own directory under `~/.claude-marketing/brands/`
- Brand profiles, campaign history, and scoring data are fully isolated at the file system level
- There is no cross-client data leakage through the plugin
- The `switch-brand` skill loads only the selected brand's data into the session context

### Agency Security Recommendations

For agencies managing multiple client accounts:

1. **Use restricted/read-only API keys wherever possible.** Stripe, Google Ads, and most platforms support restricted keys with specific permission scopes. Only grant the access the plugin actually needs.

2. **Use separate environment variable files per client** (Pattern D from Section 4). Never store multiple clients' credentials in the same shell profile.

3. **Add credential files to .gitignore.** If you version-control your agency configuration, ensure env files and service account JSON keys are excluded.

4. **Rotate credentials on a schedule.** When an analyst leaves the team or a client relationship ends, rotate the affected API keys.

5. **Audit which integrations are active.** Not every client engagement needs every integration. Enable only what each project requires.

6. **Keep service account JSON files in a secure location.** Use a dedicated directory with restricted file permissions, not your Downloads folder or Desktop.

### Compliance Considerations

When connecting MCP integrations that access personal data (especially GA4, HubSpot, Meta, and Mailchimp), ensure that:

- Your use of Claude Code with these data sources is covered by your organization's data processing agreements
- You have appropriate consent or legal basis for processing the personal data accessed through these integrations
- The data handling aligns with the compliance rules applicable to your clients' jurisdictions (see `compliance-rules.md` for rules covering 16 jurisdictions including GDPR, CCPA, LGPD, PIPEDA, and more)
- You maintain records of which integrations are enabled and what data they access, per your internal data governance policies

---

## Quick Reference: All Environment Variables

| Integration | Variables | Shared Credential |
|---|---|---|
| Google Analytics 4 | `GA_PROPERTY_ID`, `GOOGLE_APPLICATION_CREDENTIALS` | GCP service account |
| Google Search Console | `GSC_SITE_URL`, `GOOGLE_APPLICATION_CREDENTIALS` | GCP service account |
| Google Ads | `GOOGLE_ADS_CUSTOMER_ID`, `GOOGLE_ADS_DEVELOPER_TOKEN`, `GOOGLE_APPLICATION_CREDENTIALS` | GCP service account |
| Meta Business Suite | `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID` | -- |
| HubSpot CRM | `HUBSPOT_ACCESS_TOKEN` | -- |
| Mailchimp | `MAILCHIMP_API_KEY` | -- |
| LinkedIn Marketing | `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AD_ACCOUNT_ID` | -- |
| SEMrush | `SEMRUSH_API_KEY` | -- |
| Ahrefs | `AHREFS_API_KEY` | -- |
| Stripe | `STRIPE_API_KEY` | -- |
| Google Sheets | `GOOGLE_APPLICATION_CREDENTIALS` | GCP service account |
| Slack | `SLACK_BOT_TOKEN` | -- |

**Total unique variables:** 17 (because `GOOGLE_APPLICATION_CREDENTIALS` is shared across GA4, GSC, Google Ads, and Sheets).

**Minimum setup for maximum coverage:** A single GCP service account JSON file + your GA4 Property ID + GSC Site URL gives you three integrations (GA4, GSC, Sheets) from two environment variables.

---

*Digital Marketing Pro v1.2.0 -- Integrations & CRM Guide*
