# Integrations & CRM Guide

> **Digital Marketing Pro** | For marketing operations managers
>
> This guide covers the 68-server MCP connector catalog shipped in `.mcp.json.example` (no `.mcp.json` ships — nothing auto-connects), how to configure them, how to manage credentials across multiple clients, and what the plugin can do with or without live connections.

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
   - [Social Media Publishing (v2.0.0)](#social-media-publishing-v200)
   - [Email & Marketing Automation (v2.0.0)](#email--marketing-automation-v200)
   - [CRM Platforms (v2.0.0)](#crm-platforms-v200)
   - [Analytics & Data (v2.0.0)](#analytics--data-v200)
   - [Memory & RAG (v2.0.0)](#memory--rag-v200)
   - [Knowledge Management (v2.0.0)](#knowledge-management-v200)
   - [CMS & Website (v2.0.0)](#cms--website-v200)
   - [Communication (v2.0.0)](#communication-v200)
   - [Project Management & Testing (v2.0.0)](#project-management--testing-v200)
   - [Database (v2.0.0)](#database-v200)
   - [CRM --- New Platforms (v2.1.0)](#crm--new-platforms-v210)
   - [Project Management --- New Platforms (v2.1.0)](#project-management--new-platforms-v210)
   - [Design Tools (v2.1.0)](#design-tools-v210)
   - [SEO & Monitoring (v2.1.0)](#seo--monitoring-v210)
   - [Marketing Automation --- New Platforms (v2.1.0)](#marketing-automation--new-platforms-v210)
   - [Translation Services (v2.2.0)](#translation-services-v220)
4. [Multi-CRM Setup for Agencies](#4-multi-crm-setup-for-agencies)
5. [What Works Without Integrations](#5-what-works-without-integrations)
6. [Data Privacy & Security](#6-data-privacy--security)

---

## 1. How MCP Integrations Work

### What Is MCP?

MCP stands for **Model Context Protocol**. It is the standard that allows Claude to connect to external data sources and services during a session. When an MCP server is configured, Claude can read from and write to that service on your behalf, using your credentials, in real time.

In practical terms: instead of you manually pulling a GA4 report, pasting it into the conversation, and asking Claude to analyze it, the GA4 MCP server lets Claude pull that data directly. You ask a question, Claude fetches the numbers, and you get an answer grounded in your real data.

### How the Plugin Uses MCP

The plugin ships no `.mcp.json` (it is gitignored) — nothing is pre-configured and nothing auto-connects. A catalog of 68 MCP server definitions is provided in `.mcp.json.example` (npx/stdio transports), and an HTTP-connector catalog in `.mcp.json.connectors-reference`. You opt in by copying the entries you want into `.mcp.json` (or renaming the example file). Each one maps to a marketing platform or productivity tool and activates only when you set the required environment variables for that service.

This is the key design principle: **the plugin works fully without any integrations enabled.** All 164 skills, 169 reference knowledge files (including the v3.0 methodology + framework refs), scoring scripts, brand voice analysis, compliance checking, campaign planning features, and the v3.0 12-Part engagement methodology + v3.2 quality gates operate entirely offline using built-in benchmarks and reference data. MCP integrations layer real data on top of that foundation.

### What Happens Under the Hood

1. When Claude Code starts a session, it reads `.mcp.json` and attempts to start each server you have enabled there. The shipped file is empty, so nothing starts until you opt a server in from `.mcp.json.example` or `.mcp.json.connectors-reference`.
2. If the required environment variables for an enabled server are set, the server starts and Claude gains access to that platform's data.
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

### Social Media Publishing (v2.0.0)

v2.0.0 adds direct publishing capabilities to six social platforms. These servers support both reading analytics and writing content. All write operations go through the execution safety gate (see `docs/architecture.md`, Section 13).

#### Twitter/X

**What it enables:** Post tweets, manage threads, search content, and upload media. Powers the `schedule-social` and `send-report` commands with direct publishing to Twitter/X.

**Required environment variables:**

| Variable | Description |
|---|---|
| `TWITTER_API_KEY` | Twitter API key from developer portal |
| `TWITTER_API_SECRET` | Twitter API secret |
| `TWITTER_ACCESS_TOKEN` | User access token |
| `TWITTER_ACCESS_SECRET` | User access secret |

**Where to get credentials:**
1. Go to developer.twitter.com and create a project and app
2. Under Keys and Tokens, generate your API Key and Secret
3. Generate your Access Token and Secret (ensure Read and Write permissions)
4. Elevated access may be required for media uploads

**Example usage:**
```
You: Schedule a tweet announcing our new product launch for tomorrow at 9am EST
```

---

#### Instagram

**What it enables:** Schedule and publish Instagram posts, Stories, and Reels. Access engagement analytics and audience insights. Powers the `schedule-social` command for Instagram content.

**Required environment variables:**

| Variable | Description |
|---|---|
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived Instagram Graph API token |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | Your Instagram Business or Creator account ID |

**Where to get credentials:**
1. Connect your Instagram account to a Facebook Page (required for API access)
2. Create an app in the Meta Developer Portal with Instagram Graph API permissions
3. Generate a long-lived token via the token exchange flow (60-day expiry)
4. Your Business Account ID is available via the Graph API `/me/accounts` endpoint

**Example usage:**
```
You: Publish this carousel post to Instagram with the caption we drafted
```

---

#### LinkedIn Publishing

**What it enables:** Publish posts and articles to LinkedIn company pages, manage content scheduling, and track engagement. Complements the existing LinkedIn Marketing server (which focuses on ads). Powers the `schedule-social` command for LinkedIn organic content.

**Required environment variables:**

| Variable | Description |
|---|---|
| `LINKEDIN_PUBLISHING_TOKEN` | OAuth 2.0 token with publishing scope |
| `LINKEDIN_ORG_ID` | Your LinkedIn organization (company page) ID |

**Where to get credentials:**
1. Use your existing LinkedIn Developer app or create a new one
2. Request the `w_organization_social` scope for company page posting
3. Your Org ID is the numeric ID in your LinkedIn company page URL

**Example usage:**
```
You: Publish our thought leadership article to our LinkedIn company page
```

---

#### TikTok Content

**What it enables:** Publish videos to TikTok, manage captions and hashtags, and access content insights. Complements the existing TikTok Ads server. Powers the `schedule-social` command for TikTok organic content.

**Required environment variables:**

| Variable | Description |
|---|---|
| `TIKTOK_CONTENT_TOKEN` | TikTok Content Posting API access token |

**Where to get credentials:**
1. Apply for TikTok's Content Posting API access via the TikTok Developer Portal
2. Create an app and request the `video.publish` scope
3. Complete the OAuth flow to get your access token

**Example usage:**
```
You: Post our 30-second product demo video to TikTok with trending hashtags
```

---

#### YouTube

**What it enables:** Upload videos, manage video metadata (titles, descriptions, tags, thumbnails), create playlists, and access channel analytics. Powers the `schedule-social` command for YouTube content.

**Required environment variables:**

| Variable | Description |
|---|---|
| `YOUTUBE_API_KEY` | YouTube Data API key |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to Google Cloud service account JSON (same as GA4) |

**Where to get credentials:**
1. Enable the YouTube Data API v3 in your Google Cloud Console
2. Use the same service account JSON used for GA4 and Sheets
3. For uploads, OAuth consent screen approval may be required

**Example usage:**
```
You: Upload our webinar recording to YouTube with SEO-optimized title and description
```

---

#### Pinterest

**What it enables:** Create pins, manage boards, publish rich pins with product metadata, and access pin analytics. Powers the `schedule-social` command for Pinterest content.

**Required environment variables:**

| Variable | Description |
|---|---|
| `PINTEREST_ACCESS_TOKEN` | Pinterest API v5 access token |

**Where to get credentials:**
1. Create an app at developers.pinterest.com
2. Request access to the Pins and Boards scopes
3. Generate an access token through the OAuth flow
4. Business account required for analytics access

**Example usage:**
```
You: Create pins for our top 5 blog posts and add them to the "Marketing Tips" board
```

---

### Email & Marketing Automation (v2.0.0)

These servers extend the plugin's email capabilities beyond Mailchimp and ActiveCampaign with full send capabilities and behavioral messaging.

#### SendGrid

**What it enables:** Send transactional and marketing emails, manage contact lists, create email templates, and track delivery metrics. Powers the `send-email-campaign` command for SendGrid users.

**Required environment variables:**

| Variable | Description |
|---|---|
| `SENDGRID_API_KEY` | SendGrid API key with Mail Send and Marketing permissions |

**Where to get credentials:**
1. Go to SendGrid > Settings > API Keys
2. Create a key with "Mail Send" and "Marketing" permissions
3. Restricted keys are recommended over full access keys

**Example usage:**
```
You: Send our product launch email campaign to the "Active Subscribers" segment via SendGrid
```

---

#### Klaviyo

**What it enables:** eCommerce email and SMS marketing, flow automation, audience segmentation, and predictive analytics. Powers the `send-email-campaign` and `segment-audience` commands for Shopify and eCommerce brands.

**Required environment variables:**

| Variable | Description |
|---|---|
| `KLAVIYO_API_KEY` | Klaviyo private API key |

**Where to get credentials:**
1. Go to Klaviyo > Account > Settings > API Keys
2. Create a private API key
3. Select the scopes needed (Campaigns, Flows, Lists, Profiles)

**Example usage:**
```
You: Create a winback flow in Klaviyo targeting customers who haven't purchased in 90 days
```

---

#### Customer.io

**What it enables:** Behavioral messaging, event-triggered campaigns, newsletters, and in-app messaging. Powers the `send-email-campaign` command with behavioral targeting.

**Required environment variables:**

| Variable | Description |
|---|---|
| `CUSTOMERIO_API_KEY` | Customer.io Track API key |
| `CUSTOMERIO_SITE_ID` | Your Customer.io site ID |

**Where to get credentials:**
1. Go to Customer.io > Settings > API Credentials
2. Copy your Site ID and API Key from the Track API section

**Example usage:**
```
You: Set up a behavioral campaign for users who viewed pricing but didn't sign up
```

---

#### Brevo (formerly Sendinblue)

**What it enables:** Email campaigns, SMS marketing, WhatsApp messages, marketing automation, and transactional messaging. Powers the `send-email-campaign`, `send-sms`, and `segment-audience` commands.

**Required environment variables:**

| Variable | Description |
|---|---|
| `BREVO_API_KEY` | Brevo API v3 key |

**Where to get credentials:**
1. Go to Brevo > Settings > SMTP & API > API Keys
2. Generate a new API key (or use an existing v3 key)

**Example usage:**
```
You: Send a WhatsApp campaign to our loyalty segment via Brevo
```

---

#### Mailgun

**What it enables:** Email delivery, validation, mailing list management, and analytics. Powers the `send-email-campaign` command for Mailgun users.

**Required environment variables:**

| Variable | Description |
|---|---|
| `MAILGUN_API_KEY` | Mailgun API key |
| `MAILGUN_DOMAIN` | Your verified sending domain |

**Where to get credentials:**
1. Go to Mailgun > Settings > API Security
2. Copy your private API key
3. Your sending domain is listed under Sending > Domains

**Example usage:**
```
You: Send our newsletter to the subscriber list via Mailgun
```

---

### CRM Platforms (v2.0.0)

These servers complement the existing HubSpot and Salesforce integrations with additional CRM platforms.

#### Zoho CRM

**What it enables:** Contact management, deal pipeline tracking, campaign data, and workflow automation. Powers the `crm-sync`, `lead-import`, and `pipeline-update` commands for Zoho users.

**Required environment variables:**

| Variable | Description |
|---|---|
| `ZOHO_CLIENT_ID` | Zoho API client ID |
| `ZOHO_CLIENT_SECRET` | Zoho API client secret |
| `ZOHO_REFRESH_TOKEN` | Zoho OAuth refresh token |

**Where to get credentials:**
1. Register a self-client at api-console.zoho.com
2. Generate a refresh token with the scopes: `ZohoCRM.modules.ALL`, `ZohoCRM.settings.ALL`
3. The refresh token does not expire and handles automatic access token renewal

**Example usage:**
```
You: Sync our latest webinar registrants from the CSV into Zoho CRM as leads
```

---

#### Pipedrive

**What it enables:** Deal pipeline management, contact tracking, activity logging, and sales analytics. Powers the `crm-sync`, `pipeline-update`, and `lead-import` commands for Pipedrive users.

**Required environment variables:**

| Variable | Description |
|---|---|
| `PIPEDRIVE_API_TOKEN` | Pipedrive personal API token |

**Where to get credentials:**
1. Go to Pipedrive > Settings > Personal Preferences > API
2. Copy your personal API token

**Example usage:**
```
You: Update all deals in the Negotiation stage that haven't been touched in 14 days
```

---

### Analytics & Data (v2.0.0)

#### Mixpanel

**What it enables:** Product analytics, event tracking, funnel analysis, retention reports, and user segmentation. Powers the `performance-check` and `anomaly-scan` commands with product-level behavioral data.

**Required environment variables:**

| Variable | Description |
|---|---|
| `MIXPANEL_API_SECRET` | Mixpanel project API secret |
| `MIXPANEL_PROJECT_ID` | Your Mixpanel project ID |

**Where to get credentials:**
1. Go to Mixpanel > Settings > Project Settings
2. Copy the API Secret and Project ID

**Example usage:**
```
You: Show me the conversion funnel from signup to first purchase over the last 30 days
```

---

#### Amplitude

**What it enables:** Behavioral analytics, cohort analysis, experiment results, and user journey mapping. Powers the `performance-check` and `anomaly-scan` commands with behavioral analytics.

**Required environment variables:**

| Variable | Description |
|---|---|
| `AMPLITUDE_API_KEY` | Amplitude project API key |
| `AMPLITUDE_SECRET_KEY` | Amplitude project secret key |

**Where to get credentials:**
1. Go to Amplitude > Settings > Projects > select your project
2. Copy the API Key and Secret Key

**Example usage:**
```
You: Analyze user retention cohorts for the last 3 months and identify drop-off patterns
```

---

#### BigQuery

**What it enables:** Run SQL queries against your marketing data warehouse, export data from the plugin, and join datasets across platforms. Powers the `data-export` command for data warehouse operations.

**Required environment variables:**

| Variable | Description |
|---|---|
| `BIGQUERY_PROJECT_ID` | Your Google Cloud project ID |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to Google Cloud service account JSON (same as GA4) |

**Where to get credentials:**
1. Enable the BigQuery API in your Google Cloud Console
2. Use the same service account JSON used for GA4 and Sheets
3. Grant the service account "BigQuery Data Editor" role for write operations

**Example usage:**
```
You: Export this month's campaign performance data to our BigQuery marketing dataset
```

---

### Memory & RAG (v2.0.0)

These servers enable persistent brand knowledge storage and retrieval across sessions. They power the `save-knowledge`, `search-knowledge`, and `sync-memory` commands.

#### Pinecone

**What it enables:** Vector storage and semantic search over brand knowledge archives. Store campaign briefs, content examples, performance insights, and brand guidelines as embeddings for fast retrieval. Ideal for large knowledge bases.

**Required environment variables:**

| Variable | Description |
|---|---|
| `PINECONE_API_KEY` | Pinecone API key |
| `PINECONE_ENVIRONMENT` | Pinecone environment (e.g., `us-east-1-aws`) |
| `PINECONE_INDEX_NAME` | Index name for brand knowledge (defaults to `brand-knowledge`) |

**Where to get credentials:**
1. Sign up at pinecone.io and create an organization
2. Create an index (recommended: 1536 dimensions for OpenAI embeddings, or 768 for other models)
3. Copy your API key from the dashboard

**Example usage:**
```
You: Save our Q4 campaign learnings to the knowledge base for future reference
```

---

#### Qdrant

**What it enables:** Self-hosted or cloud vector search for brand knowledge. Similar to Pinecone but with a self-hosting option for teams that need data residency control. Powers the same RAG features as Pinecone.

**Required environment variables:**

| Variable | Description |
|---|---|
| `QDRANT_URL` | Qdrant server URL (e.g., `https://your-cluster.qdrant.io` or `http://localhost:6333`) |
| `QDRANT_API_KEY` | Qdrant API key (required for cloud, optional for self-hosted) |

**Where to get credentials:**
1. For Qdrant Cloud: sign up at cloud.qdrant.io, create a cluster, and copy your API key
2. For self-hosted: run `docker run -p 6333:6333 qdrant/qdrant` and set the URL to `http://localhost:6333`

**Example usage:**
```
You: Search our knowledge base for everything we know about email subject line performance
```

---

#### Supermemory

**What it enables:** Cross-session shared memory for all agents. Stores agent learnings, brand observations, and strategic insights that persist between sessions and are accessible to all specialist agents.

**Required environment variables:**

| Variable | Description |
|---|---|
| `SUPERMEMORY_API_KEY` | Supermemory API key |

**Where to get credentials:**
1. Sign up at supermemory.ai
2. Create a workspace and generate an API key

**Example usage:**
```
You: Sync everything we learned in this session about our audience to persistent memory
```

---

#### Graphiti

**What it enables:** Temporal knowledge graph for mapping campaign relationships over time. Tracks how campaigns, audiences, content, and channels relate and evolve. Useful for attribution analysis and understanding what worked historically.

**Required environment variables:**

| Variable | Description |
|---|---|
| `GRAPHITI_API_URL` | Graphiti server URL |
| `GRAPHITI_API_KEY` | Graphiti API key |

**Where to get credentials:**
1. Deploy Graphiti (open-source) or use the hosted service
2. Generate an API key from the admin dashboard

**Example usage:**
```
You: Show me how our email campaigns have influenced deal velocity over the last 6 months
```

---

### Knowledge Management (v2.0.0)

#### Notion

**What it enables:** Access and manage team documentation, marketing wikis, content databases, and brand asset inventories stored in Notion. Powers the `save-knowledge` and `search-knowledge` commands with structured team documentation.

**Required environment variables:**

| Variable | Description |
|---|---|
| `NOTION_API_KEY` | Notion internal integration token |

**Where to get credentials:**
1. Go to notion.so/my-integrations and create a new integration
2. Copy the Internal Integration Token
3. Share each Notion database or page you want accessible with the integration (click Share > Invite > select your integration)

**Example usage:**
```
You: Pull our content style guide from Notion and apply it to this blog draft
```

---

#### Google Drive

**What it enables:** Access brand assets, creative files, shared documents, and presentation templates stored in Google Drive. Useful for pulling reference materials into sessions.

**Required environment variables:**

| Variable | Description |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to Google Cloud service account JSON (same as GA4) |

**Where to get credentials:**
1. Enable the Google Drive API in your Google Cloud Console
2. Use the same service account JSON used for other Google integrations
3. Share specific Drive folders with the service account email

**Example usage:**
```
You: Pull our brand asset guide from Google Drive and check this creative against it
```

---

### CMS & Website (v2.0.0)

#### Webflow

**What it enables:** Publish and manage content in Webflow CMS collections, update site pages, and manage SEO metadata. Complements the existing WordPress server. Powers the `publish-blog` command for Webflow sites.

**Required environment variables:**

| Variable | Description |
|---|---|
| `WEBFLOW_API_TOKEN` | Webflow API v2 token |
| `WEBFLOW_SITE_ID` | Your Webflow site ID |

**Where to get credentials:**
1. Go to Webflow > Site Settings > Integrations > API Access
2. Generate a site-level API token
3. Your Site ID is in the URL when viewing your site in the Webflow dashboard

**Example usage:**
```
You: Publish the blog post we drafted to our Webflow CMS with the SEO metadata we defined
```

---

### Communication (v2.0.0)

#### Twilio

**What it enables:** Send SMS and WhatsApp messages for marketing campaigns, appointment reminders, and transactional notifications. Powers the `send-sms` command.

**Required environment variables:**

| Variable | Description |
|---|---|
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | Your Twilio phone number (with country code) |

**Where to get credentials:**
1. Sign up at twilio.com and complete phone verification
2. Your Account SID and Auth Token are on the Console dashboard
3. Buy a phone number or use the trial number for testing
4. For WhatsApp: activate the WhatsApp sandbox or apply for a WhatsApp Business API number

**Example usage:**
```
You: Send an SMS campaign to our VIP customer segment with the flash sale announcement
```

---

#### Intercom

**What it enables:** Customer messaging, support inbox management, article publishing, and user segmentation. Powers the `send-notification` command for customer-facing communications.

**Required environment variables:**

| Variable | Description |
|---|---|
| `INTERCOM_ACCESS_TOKEN` | Intercom API access token |

**Where to get credentials:**
1. Go to Intercom > Settings > Integrations > Developer Hub
2. Create a new app and generate an access token
3. Select the required permissions (Conversations, Users, Articles)

**Example usage:**
```
You: Send an in-app message to users who signed up in the last 7 days about our new feature
```

---

### Project Management & Testing (v2.0.0)

#### Linear

**What it enables:** Create and manage marketing tasks, track sprint progress, and organize campaign workflows in Linear. Powers the `team-assign` command for task management.

**Required environment variables:**

| Variable | Description |
|---|---|
| `LINEAR_API_KEY` | Linear personal API key |

**Where to get credentials:**
1. Go to Linear > Settings > API > Personal API Keys
2. Create a new key with the scopes you need (Issues, Projects, Teams)

**Example usage:**
```
You: Create Linear issues for each task in our product launch campaign plan
```

---

#### Optimizely

**What it enables:** A/B testing, feature flags, and experimentation management. Powers the `ab-test-plan` command with live experiment data and results.

**Required environment variables:**

| Variable | Description |
|---|---|
| `OPTIMIZELY_API_TOKEN` | Optimizely personal access token |
| `OPTIMIZELY_PROJECT_ID` | Your Optimizely project ID |

**Where to get credentials:**
1. Go to Optimizely > Settings > Account Settings > API Access
2. Generate a personal access token
3. Your Project ID is visible in the project settings URL

**Example usage:**
```
You: Pull results from our homepage hero experiment and recommend a winner
```

---

### Database (v2.0.0)

#### Supabase

**What it enables:** PostgreSQL database queries, real-time data subscriptions, and structured data storage. Powers the `data-export` command for teams that use Supabase as their data backend.

**Required environment variables:**

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key (for server-side access) |

**Where to get credentials:**
1. Go to your Supabase project > Settings > API
2. Copy the Project URL and the `service_role` key (not the `anon` key)
3. The service role key bypasses Row Level Security -- use with care

**Example usage:**
```
You: Export our campaign performance table to a CSV and analyze trends
```

---

### CRM -- New Platforms (v2.1.0)

v2.1.0 adds seven additional CRM platforms, expanding the plugin's CRM coverage beyond HubSpot, Salesforce, Zoho, and Pipedrive. These servers power the `crm-sync`, `lead-import`, and `pipeline-update` commands.

#### Odoo

**What it enables:** Full CRM, invoicing, inventory, and project management integration. Ideal for SMBs that use Odoo as their all-in-one business platform. Powers the `crm-sync` and `pipeline-update` commands with Odoo deal and contact data.

**Required environment variables:**

| Variable | Description |
|---|---|
| `ODOO_URL` | Your Odoo instance URL (e.g., `https://yourcompany.odoo.com`) |
| `ODOO_DB` | Odoo database name |
| `ODOO_API_KEY` | Odoo API key or user token |

**Example usage:**
```
You: Sync our latest webinar leads into Odoo CRM and assign them to the sales team
```

---

#### Freshsales

**What it enables:** Lead and deal management, contact scoring, activity tracking, and sales sequences. Powers the `crm-sync`, `lead-import`, and `pipeline-update` commands for Freshsales users.

**Required environment variables:**

| Variable | Description |
|---|---|
| `FRESHSALES_API_KEY` | Freshsales API key |
| `FRESHSALES_DOMAIN` | Your Freshsales domain (e.g., `yourcompany.freshsales.io`) |

**Example usage:**
```
You: Import our trade show leads into Freshsales and create a nurture sequence
```

---

#### Monday CRM

**What it enables:** CRM board management, deal tracking, contact management, and workflow automations within Monday.com. Powers the `crm-sync` and `pipeline-update` commands for Monday CRM users.

**Required environment variables:**

| Variable | Description |
|---|---|
| `MONDAY_API_TOKEN` | Monday.com API v2 token |

**Where to get credentials:**
1. Go to Monday.com > Profile > Developers > My Access Tokens
2. Generate a personal API token

**Example usage:**
```
You: Update all stale deals in our Monday CRM board that haven't been touched in 30 days
```

---

#### Dynamics 365

**What it enables:** Microsoft Dynamics 365 CRM integration for leads, opportunities, accounts, and marketing lists. Powers the `crm-sync`, `lead-import`, and `pipeline-update` commands for enterprise Microsoft environments.

**Required environment variables:**

| Variable | Description |
|---|---|
| `DYNAMICS_365_URL` | Your Dynamics 365 instance URL (e.g., `https://yourorg.crm.dynamics.com`) |
| `DYNAMICS_365_CLIENT_ID` | Azure AD app client ID |
| `DYNAMICS_365_CLIENT_SECRET` | Azure AD app client secret |
| `DYNAMICS_365_TENANT_ID` | Azure AD tenant ID |

**Where to get credentials:**
1. Register an application in Azure Active Directory
2. Grant Dynamics CRM API permissions to the app
3. Generate a client secret under Certificates & Secrets

**Example usage:**
```
You: Pull our Dynamics 365 opportunity pipeline and identify deals at risk of slipping
```

---

#### Copper

**What it enables:** Google Workspace-native CRM integration for contacts, deals, activities, and pipeline management. Powers the `crm-sync` and `pipeline-update` commands for teams that use Copper with Google Workspace.

**Required environment variables:**

| Variable | Description |
|---|---|
| `COPPER_API_KEY` | Copper API key |
| `COPPER_USER_EMAIL` | Email address associated with the Copper account |

**Where to get credentials:**
1. Go to Copper > Settings > Integrations > API Keys
2. Generate a new API key

**Example usage:**
```
You: Sync our Google Workspace contacts from Copper and segment them by deal stage
```

---

#### Close

**What it enables:** Sales CRM with built-in calling, email sequences, and pipeline management. Powers the `crm-sync`, `lead-import`, and `pipeline-update` commands for Close users.

**Required environment variables:**

| Variable | Description |
|---|---|
| `CLOSE_API_KEY` | Close API key |

**Where to get credentials:**
1. Go to Close > Settings > Your API Keys
2. Generate a new API key

**Example usage:**
```
You: Pull our Close CRM call activity data and identify which sequences have the best connect rates
```

---

#### Keap

**What it enables:** Keap (formerly Infusionsoft) contact management, deal tracking, invoicing, and marketing automation. Powers the `crm-sync`, `lead-import`, and `pipeline-update` commands for Keap users.

**Required environment variables:**

| Variable | Description |
|---|---|
| `KEAP_API_KEY` | Keap personal access token |

**Where to get credentials:**
1. Go to Keap Developer Portal > API Settings
2. Generate a personal access token with CRM and marketing scopes

**Example usage:**
```
You: Import our event registrants into Keap and tag them for the post-event follow-up sequence
```

---

### Project Management -- New Platforms (v2.1.0)

v2.1.0 adds three dedicated project management integrations beyond the existing Linear server. These power the `team-assign` command and enable campaign task tracking across popular PM tools.

#### Jira

**What it enables:** Issue creation and management, sprint tracking, board management, and project reporting. Powers the `team-assign` command for teams that use Jira for marketing project management.

**Required environment variables:**

| Variable | Description |
|---|---|
| `JIRA_URL` | Your Jira instance URL (e.g., `https://yourcompany.atlassian.net`) |
| `JIRA_EMAIL` | Email address for Jira authentication |
| `JIRA_API_TOKEN` | Jira API token |

**Where to get credentials:**
1. Go to id.atlassian.com > Security > API Tokens
2. Create a new API token
3. Use your Atlassian email and this token for authentication

**Example usage:**
```
You: Create Jira tickets for each deliverable in our Q2 campaign plan and assign them to the team
```

---

#### Asana

**What it enables:** Task and project management, portfolio tracking, timeline views, and goal tracking. Powers the `team-assign` command for Asana users.

**Required environment variables:**

| Variable | Description |
|---|---|
| `ASANA_ACCESS_TOKEN` | Asana personal access token |

**Where to get credentials:**
1. Go to Asana > My Settings > Apps > Developer Apps
2. Create a personal access token

**Example usage:**
```
You: Create an Asana project for our product launch with tasks for each campaign phase
```

---

#### ClickUp

**What it enables:** Task management, space and folder organization, goal tracking, and time tracking. Powers the `team-assign` command for ClickUp users.

**Required environment variables:**

| Variable | Description |
|---|---|
| `CLICKUP_API_TOKEN` | ClickUp personal API token |

**Where to get credentials:**
1. Go to ClickUp > Settings > Apps > API Token
2. Generate a personal API token

**Example usage:**
```
You: Create ClickUp tasks for our content calendar and set due dates based on the publishing schedule
```

---

### Design Tools (v2.1.0)

v2.1.0 adds design platform integrations for creative workflow management and asset access.

#### Canva

**What it enables:** Design creation from templates, brand kit access, asset management, and export in multiple formats. Powers creative workflows by connecting marketing briefs to design execution.

**Required environment variables:**

| Variable | Description |
|---|---|
| `CANVA_API_KEY` | Canva Connect API key |

**Where to get credentials:**
1. Go to canva.com/developers and create an integration
2. Generate an API key with the required scopes (Design, Brand, Asset)
3. Canva Pro or Enterprise required for full API access

**Example usage:**
```
You: Create social media graphics for our campaign using our Canva brand kit templates
```

---

#### Figma

**What it enables:** Access design files, components, and comments. Export assets and review designs directly from the marketing workflow. Useful for design review and creative feedback loops.

**Required environment variables:**

| Variable | Description |
|---|---|
| `FIGMA_ACCESS_TOKEN` | Figma personal access token |

**Where to get credentials:**
1. Go to Figma > Settings > Account > Personal Access Tokens
2. Generate a new token with File and Comment scopes

**Example usage:**
```
You: Pull the latest ad creative designs from our Figma project and review them against brand guidelines
```

---

### SEO & Monitoring (v2.1.0)

v2.1.0 adds SEO and brand monitoring platforms that complement the existing SEMrush and Ahrefs integrations. v2.6.0 adds DataForSEO for live SERP data, keyword research, backlink analysis, and AI visibility tracking.

#### Moz

**What it enables:** Domain authority scores, keyword research, link analysis, and SERP tracking. Powers the `seo-audit` and `competitor-analysis` modules with Moz domain metrics and link data.

**Required environment variables:**

| Variable | Description |
|---|---|
| `MOZ_ACCESS_ID` | Moz API access ID |
| `MOZ_SECRET_KEY` | Moz API secret key |

**Where to get credentials:**
1. Go to Moz > Account > API Access
2. Copy your Access ID and Secret Key
3. API access requires a Moz Pro subscription

**Example usage:**
```
You: Compare our domain authority against our top 5 competitors using Moz data
```

---

#### Google PageSpeed Insights

**What it enables:** Core Web Vitals scores, performance audits, accessibility scores, and SEO checks for any URL. Powers the `tech-seo-audit` command with real-time performance data.

**Required environment variables:**

| Variable | Description |
|---|---|
| `PAGESPEED_API_KEY` | Google PageSpeed Insights API key |

**Where to get credentials:**
1. Go to Google Cloud Console > APIs & Services > Credentials
2. Enable the PageSpeed Insights API
3. Create an API key (no OAuth required -- API key only)

**Example usage:**
```
You: Run Core Web Vitals checks on our top 20 landing pages and flag any failing thresholds
```

---

#### DataForSEO

**What it enables:** Live SERP data, keyword research with search volume and difficulty, backlink profiles with spam scoring, on-page analysis (Lighthouse + content parsing), content analysis, competitor domain analysis, business listings search, AI visibility checking across ChatGPT and other LLMs, and LLM mention tracking. Powers the `seo-audit`, `keyword-research`, `competitor-analysis`, `page-analysis`, `rank-monitor`, `competitor-pages`, and `geo-monitor` commands with live data instead of estimates.

**Required environment variables:**

| Variable | Description |
|---|---|
| `DATAFORSEO_USERNAME` | DataForSEO account username (email) |
| `DATAFORSEO_PASSWORD` | DataForSEO account password |

**Where to get credentials:**
1. Create an account at [app.dataforseo.com/register](https://app.dataforseo.com/register)
2. Your login email is the username, your account password is the password
3. API access is included with all plans. Billing is pay-as-you-go per task; see the provider's pricing page for current rates
4. Test with the sandbox environment first (set `DATAFORSEO_SANDBOX=true` for free testing with sample data)

**9 API modules available:**

| Module | What It Provides |
|---|---|
| SERP | Google/Bing/Yahoo organic results, YouTube search results, video deep analysis |
| Keywords Data | Search volume, keyword trends over time |
| DataForSEO Labs | Keyword ideas, difficulty scores, intent classification, competitor domains, ranked keywords, subdomains |
| Backlinks | Full backlink profiles with spam scores, referring domains, anchor text distribution |
| On-Page | Lighthouse-based page analysis, content parsing, technical signals |
| Domain Analytics | Technology stack detection, WHOIS data |
| Content Analytics | Content analysis, phrase trends, search intent |
| Business Data | Business listings search, Google Business Profile data |
| App Data | AI visibility scraping (ChatGPT web search), LLM mention tracking |

**Example usage:**
```
You: Research keywords for "AI marketing tools" — I need volume, difficulty, and intent classification
→ Uses DataForSEO Labs for keyword ideas, volume, difficulty, and intent

You: Analyze the backlink profile of competitor.com and compare it to ours
→ Uses DataForSEO Backlinks module for full profile with spam scoring

You: Check if our brand is being mentioned in ChatGPT responses
→ Uses DataForSEO App Data module for AI visibility scraping and LLM mention tracking
```

---

### Marketing Automation -- New Platforms (v2.1.0)

v2.1.0 adds two enterprise marketing automation platforms, complementing the existing ActiveCampaign integration.

#### Marketo

**What it enables:** Lead management, campaign orchestration, smart lists, email programs, and engagement scoring. Powers the `send-email-campaign`, `segment-audience`, and `lead-import` commands for Marketo users.

**Required environment variables:**

| Variable | Description |
|---|---|
| `MARKETO_CLIENT_ID` | Marketo REST API client ID |
| `MARKETO_CLIENT_SECRET` | Marketo REST API client secret |
| `MARKETO_MUNCHKIN_ID` | Your Marketo Munchkin account ID |

**Where to get credentials:**
1. Go to Marketo > Admin > Integration > LaunchPoint
2. Create a new Custom Service for API access
3. Copy the Client ID and Client Secret
4. Your Munchkin ID is under Admin > Integration > Munchkin

**Example usage:**
```
You: Create a Marketo smart list of leads who engaged with our webinar but haven't converted, then build a nurture campaign
```

---

#### Pardot

**What it enables:** Prospect management, campaign tracking, engagement scoring, and form management. Powers the `send-email-campaign`, `segment-audience`, and `lead-import` commands for Pardot (Salesforce Marketing Cloud Account Engagement) users.

**Required environment variables:**

| Variable | Description |
|---|---|
| `PARDOT_BUSINESS_UNIT_ID` | Pardot business unit ID |
| `SALESFORCE_ACCESS_TOKEN` | Salesforce OAuth access token (Pardot uses Salesforce SSO) |
| `SALESFORCE_INSTANCE_URL` | Your Salesforce instance URL |

**Where to get credentials:**
1. Pardot now authenticates through Salesforce SSO
2. Use a Salesforce Connected App with Pardot API scope
3. Your Business Unit ID is found in Pardot > Settings > Account
4. Generate a Salesforce access token via OAuth flow

**Example usage:**
```
You: Pull our Pardot prospect engagement scores and identify the top 50 leads ready for sales handoff
```

---

### Quick Reference: v2.1.0 Environment Variables

| Integration | Variables | Shared Credential |
|---|---|---|
| Odoo | `ODOO_URL`, `ODOO_DB`, `ODOO_API_KEY` | -- |
| Freshsales | `FRESHSALES_API_KEY`, `FRESHSALES_DOMAIN` | -- |
| Monday CRM | `MONDAY_API_TOKEN` | -- |
| Dynamics 365 | `DYNAMICS_365_URL`, `DYNAMICS_365_CLIENT_ID`, `DYNAMICS_365_CLIENT_SECRET`, `DYNAMICS_365_TENANT_ID` | Azure AD |
| Copper | `COPPER_API_KEY`, `COPPER_USER_EMAIL` | -- |
| Close | `CLOSE_API_KEY` | -- |
| Keap | `KEAP_API_KEY` | -- |
| Jira | `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` | Atlassian |
| Asana | `ASANA_ACCESS_TOKEN` | -- |
| ClickUp | `CLICKUP_API_TOKEN` | -- |
| Canva | `CANVA_API_KEY` | -- |
| Figma | `FIGMA_ACCESS_TOKEN` | -- |
| Moz | `MOZ_ACCESS_ID`, `MOZ_SECRET_KEY` | -- |
| Google PageSpeed | `PAGESPEED_API_KEY` | -- |
| Marketo | `MARKETO_CLIENT_ID`, `MARKETO_CLIENT_SECRET`, `MARKETO_MUNCHKIN_ID` | -- |
| Pardot | `PARDOT_BUSINESS_UNIT_ID`, `SALESFORCE_ACCESS_TOKEN`, `SALESFORCE_INSTANCE_URL` | Salesforce SSO |

---

### Translation Services (v2.2.0)

v2.2.0 adds four translation service integrations for multilingual content creation and localization. These power the `translate-content`, `localize-campaign`, `language-audit`, `language-config`, `multilingual-score`, and `hreflang-check` commands.

#### DeepL

**Best for**: European languages (German, French, Spanish, Italian, Portuguese, Dutch, Polish, Russian), Japanese, Korean, Chinese

1. Sign up at [deepl.com](https://www.deepl.com/pro-api)
2. Get your API key from the DeepL account dashboard
3. Set environment variable: `DEEPL_API_KEY=your-api-key`
4. Features: Formality control (formal/informal), glossary support, document translation

**Required environment variables:**

| Variable | Description |
|---|---|
| `DEEPL_API_KEY` | DeepL API authentication key |

**Example usage:**
```
You: Translate our product launch email into German with formal tone
```

---

#### Sarvam AI

**Best for**: Indian languages — Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi, and 13 more Indic languages

1. Sign up at [sarvam.ai](https://www.sarvam.ai)
2. Get your API key from the Sarvam dashboard
3. Set environment variable: `SARVAM_API_KEY=your-api-key`
4. Features: 22 Indic languages, transliteration, language detection, native quality

**Required environment variables:**

| Variable | Description |
|---|---|
| `SARVAM_API_KEY` | Sarvam AI API authentication key |

**Example usage:**
```
You: Translate our campaign landing page copy into Hindi, Tamil, and Telugu
```

---

#### Google Cloud Translation

**Best for**: Broad coverage (100+ languages), rare languages, Arabic, Thai, Vietnamese, Indonesian

1. Create a Google Cloud project and enable the Translation API
2. Create a service account and download the credentials JSON
3. Set environment variable: `GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json`
4. Features: 100+ languages, batch translation, adaptive translation, language detection

**Required environment variables:**

| Variable | Description |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to Google Cloud service account JSON (same as GA4) |

**Example usage:**
```
You: Translate our FAQ page into Arabic, Thai, and Vietnamese
```

---

#### Lara Translate

**Best for**: Marketing content with translation memories, context-aware translation, brand consistency

1. Sign up at [laratranslate.com](https://www.laratranslate.com)
2. Get your API key from the dashboard
3. Set environment variable: `LARA_API_KEY=your-api-key`
4. Features: Translation memories, context-aware, 100+ languages, marketing content specialization

**Required environment variables:**

| Variable | Description |
|---|---|
| `LARA_API_KEY` | Lara Translate API authentication key |

**Example usage:**
```
You: Translate our brand messaging framework into French and Spanish with marketing context
```

---

### Quick Reference: v2.2.0 Environment Variables

| Integration | Variables | Shared Credential |
|---|---|---|
| DeepL | `DEEPL_API_KEY` | -- |
| Sarvam AI | `SARVAM_API_KEY` | -- |
| Google Cloud Translation | `GOOGLE_APPLICATION_CREDENTIALS` | GCP service account |
| Lara Translate | `LARA_API_KEY` | -- |

---

## 4. Multi-CRM Setup for Agencies

### The Challenge

The `.mcp.json` file supports a single set of credentials per MCP server. If you manage one brand, this is straightforward. But agencies managing multiple clients -- each with their own HubSpot portal, their own GA4 property, their own Meta ad account -- run into a credential management challenge.

### v2.0.0 Credential Profiles

v2.0.0 introduces `/digital-marketing-pro:credential-switch`, which manages per-brand credential profiles stored at `~/.claude-marketing/credentials/`. Each brand maps to its own set of platform environment variable names, so when you switch brands, the plugin knows which credentials belong to which client.

The credential manager (`credential-manager.py`) stores a JSON mapping for each brand slug:

```json
{
  "brand_slug": "acme-corp",
  "profiles": {
    "google-analytics": {"GA_PROPERTY_ID": "111111111"},
    "hubspot": {"HUBSPOT_ACCESS_TOKEN": "pat-na1-acme-token"},
    "mailchimp": {"MAILCHIMP_API_KEY": "abc123-us14"}
  }
}
```

When you run `/digital-marketing-pro:credential-switch acme-corp`, the plugin loads the corresponding credential profile and maps the environment variables for that brand's platforms. The actual credential values still need to be set as environment variables on your machine, but the mapping between brand and credential set is now managed automatically.

This eliminates the manual juggling of previous versions. You still have the option of using the patterns below as supplementary approaches for advanced setups.

---

### Pattern A: Environment Variable Swapping

The simplest approach. Manually change the environment variables before starting work on a different client.

```bash
# Working on Client A (their GA4 property, their HubSpot portal)
export GA_PROPERTY_ID="111111111"
export HUBSPOT_ACCESS_TOKEN="<your hubspot access token>"

# Switching to Client B
export GA_PROPERTY_ID="222222222"
export HUBSPOT_ACCESS_TOKEN="<your hubspot access token>"
```

**Best for:** Agencies with 2-3 clients on the same platforms. Quick to execute, nothing to maintain beyond the credential values themselves.

**Limitation:** Requires restarting Claude Code after changing environment variables for MCP servers to pick up the new values.

---

### Pattern B: Multiple .mcp.json Files

Maintain separate MCP configuration files per client and swap the active one.

```bash
# One-time setup: create per-client configs from the connector catalog
# (no .mcp.json ships, so start from the example catalog and trim per client)
cp .mcp.json.example .mcp-acme-corp.json      # Edit with Acme Corp's servers + credentials
cp .mcp.json.example .mcp-techflow.json        # Edit with TechFlow's servers + credentials
cp .mcp.json.example .mcp-greenleaf.json       # Edit with GreenLeaf's servers + credentials

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

**Best for:** Clients unwilling to grant credential access, or CRMs without a configured MCP server (Salesforce, Pipedrive, Zoho, Close, Monday CRM, etc.). Also useful when a client prefers to share exports rather than API credentials.

**Trade-off:** You lose the real-time query capability (Claude cannot pull fresh data mid-conversation), but all analysis, planning, and content creation modules work the same way once the data is in the session.

---

### Pattern D: Per-Session Configuration

Create shell scripts that set all environment variables for a specific client, then launch Claude Code.

```bash
# File: clients/acme-corp/env.sh
export GA_PROPERTY_ID="111111111"
export GSC_SITE_URL="https://acmecorp.com"
export GOOGLE_APPLICATION_CREDENTIALS="/keys/acme-corp-sa.json"
export HUBSPOT_ACCESS_TOKEN="<your hubspot access token>"
export MAILCHIMP_API_KEY="<your mailchimp api key>"
export SLACK_BOT_TOKEN="<your slack bot token>"

# File: clients/techflow/env.sh
export GA_PROPERTY_ID="222222222"
export GSC_SITE_URL="https://techflow.io"
export GOOGLE_APPLICATION_CREDENTIALS="/keys/techflow-sa.json"
export META_ACCESS_TOKEN="<your meta access token>"
export META_AD_ACCOUNT_ID="act_987654321"
export STRIPE_API_KEY="<your stripe api key>"
```

Usage:

```bash
# Start a session for Acme Corp
source ./clients/acme-corp/env.sh && claude

# Start a session for TechFlow
source ./clients/techflow/env.sh && claude
```

**Best for:** Agencies that want clean, repeatable separation between client sessions. Each session starts with a known-good credential set. Combine this with `/digital-marketing-pro:switch-brand` at session start to load the matching brand profile.

**Security note:** Store these env files outside of version control. Add `clients/*/env.sh` to your `.gitignore`.

---

---

## 5. What Works Without Integrations

The plugin is designed to be fully functional with zero MCP connections enabled. Here is what the offline baseline includes:

### Always Available (No Integrations Required)

| Capability | What Powers It |
|---|---|
| Content creation (briefs, calendars, social posts, email sequences) | 164 skills + `platform-specs.md` (format specs for 15+ platforms) |
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

### Original Integrations (v1.0--v1.9)

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

### v2.0.0 Integrations

| Integration | Variables | Shared Credential |
|---|---|---|
| Twitter/X | `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_SECRET` | -- |
| Instagram | `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ACCOUNT_ID` | -- |
| LinkedIn Publishing | `LINKEDIN_PUBLISHING_TOKEN`, `LINKEDIN_ORG_ID` | -- |
| TikTok Content | `TIKTOK_CONTENT_TOKEN` | -- |
| YouTube | `YOUTUBE_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS` | GCP service account |
| Pinterest | `PINTEREST_ACCESS_TOKEN` | -- |
| SendGrid | `SENDGRID_API_KEY` | -- |
| Klaviyo | `KLAVIYO_API_KEY` | -- |
| Customer.io | `CUSTOMERIO_API_KEY`, `CUSTOMERIO_SITE_ID` | -- |
| Brevo | `BREVO_API_KEY` | -- |
| Mailgun | `MAILGUN_API_KEY`, `MAILGUN_DOMAIN` | -- |
| Zoho CRM | `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN` | -- |
| Pipedrive | `PIPEDRIVE_API_TOKEN` | -- |
| Mixpanel | `MIXPANEL_API_SECRET`, `MIXPANEL_PROJECT_ID` | -- |
| Amplitude | `AMPLITUDE_API_KEY`, `AMPLITUDE_SECRET_KEY` | -- |
| BigQuery | `BIGQUERY_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS` | GCP service account |
| Pinecone | `PINECONE_API_KEY`, `PINECONE_ENVIRONMENT`, `PINECONE_INDEX_NAME` | -- |
| Qdrant | `QDRANT_URL`, `QDRANT_API_KEY` | -- |
| Supermemory | `SUPERMEMORY_API_KEY` | -- |
| Graphiti | `GRAPHITI_API_URL`, `GRAPHITI_API_KEY` | -- |
| Notion | `NOTION_API_KEY` | -- |
| Google Drive | `GOOGLE_APPLICATION_CREDENTIALS` | GCP service account |
| Webflow | `WEBFLOW_API_TOKEN`, `WEBFLOW_SITE_ID` | -- |
| Twilio | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` | -- |
| Intercom | `INTERCOM_ACCESS_TOKEN` | -- |
| Linear | `LINEAR_API_KEY` | -- |
| Optimizely | `OPTIMIZELY_API_TOKEN`, `OPTIMIZELY_PROJECT_ID` | -- |
| Supabase | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | -- |

**Total unique variables:** 98 across all 68 integrations (because `GOOGLE_APPLICATION_CREDENTIALS` is shared across GA4, GSC, Google Ads, Sheets, YouTube, BigQuery, and Google Drive, and Pardot shares Salesforce OAuth credentials).

**Minimum setup for maximum coverage:** A single GCP service account JSON file + your GA4 Property ID + GSC Site URL gives you up to seven Google integrations (GA4, GSC, Sheets, YouTube, BigQuery, Google Drive, Google Ads) from a shared credential base.

---

*Digital Marketing Pro -- Integrations & CRM Guide*
