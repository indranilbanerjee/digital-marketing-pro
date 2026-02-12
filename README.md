# Digital Marketing Pro — Claude Code & Cowork Plugin

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-optional-yellow.svg)](#python-dependencies-optional)
[![Cowork](https://img.shields.io/badge/cowork-compatible-purple.svg)](docs/claude-interfaces.md#claude-cowork-full-support)

The most comprehensive digital marketing plugin for Claude Code and Claude Cowork. 16 integrated modules covering the entire marketing spectrum from strategy to execution to measurement — including dedicated Technical SEO, Local SEO, and Marketing Automation modules. **v2.0 adds a full execution layer**: publish content, send emails, launch ads, schedule social, sync CRMs, manage persistent memory, and deliver reports — all with human-in-the-loop approval workflows. Multi-client agency operations with credential profiles, portfolio dashboards, and team management.

## What This Plugin Does

Digital Marketing Pro transforms Claude into a full-stack marketing intelligence system. It covers every marketing discipline, adapts to any business model, auto-applies compliance rules, and learns from your past campaigns.

### 16 Core Modules

| Module | What It Covers |
|--------|---------------|
| **AEO/GEO Intelligence** | AI visibility, answer engine optimization, citation optimization, entity consistency |
| **Funnel Architect** | Customer journey mapping, attribution modeling, funnel gap analysis |
| **Campaign Orchestrator** | Campaign planning, budget allocation, UTM tracking, post-mortems, ABM |
| **Audience Intelligence** | Buyer personas, Jobs-to-Be-Done, segmentation, psychographic profiling |
| **Content Engine** | SEO content, ad copy, emails, social, landing pages, calendars, brand voice, accessibility, multilingual |
| **Digital PR & Authority** | Media outreach, press releases, thought leadership, newsjacking, E-E-A-T |
| **Analytics & Insights** | KPI frameworks, reporting, anomaly detection, MMM, incrementality, dark social, privacy-first measurement |
| **Paid Advertising** | Google, Meta, LinkedIn, TikTok, programmatic, retail media networks |
| **CRO** | Landing page audits, A/B testing, form optimization, pricing psychology |
| **Growth Engineering** | PLG, referral systems, viral loops, launch strategy, retention, affiliates |
| **Influencer & Creator** | Discovery, briefs, FTC compliance engine, contracts, UGC, measurement |
| **Reputation Management** | Review strategy, 3-tier crisis communication, brand safety, recovery |
| **Emerging Channels** | Voice search, visual search, social commerce, community, podcast, video |
| **Technical SEO** | Core Web Vitals, crawlability, indexation, site architecture, redirects, JavaScript SEO, mobile-first |
| **Local SEO** | Google Business Profile, NAP consistency, citations, local pack, location pages, multi-location |
| **Marketing Automation** | Automation workflows, lead scoring, nurture sequences, marketing operations, MAP strategy |

### Key Differentiators

- **10 business models** supported (B2B SaaS, eCommerce, Local, Agency, Creator, Enterprise, Non-Profit, Marketplace, DTC, B2B Services)
- **22 industry profiles** with benchmarks and compliance rules
- **16 privacy law jurisdictions** auto-applied (GDPR, CCPA, PIPL, DPDPA, and more)
- **18 specialist agents**, including 5 new execution agents (execution-coordinator, performance-monitor, CRM manager, memory manager, agency operations), that activate based on conversation context, call 42 Python scripts for scoring, query MCP servers for live data, enforce brand guidelines, and persist campaign learnings
- **Brand guidelines enforcement** — import voice guides, restrictions, channel styles, messaging frameworks; automatically applied across all modules
- **Deliverable templates** and **agency SOPs** — custom output formats and workflow definitions
- **68 slash commands** for direct access to common workflows — including 26 new execution commands for publishing, CRM, monitoring, memory, communication, agency ops, and team management
- **42 Python scripts** for deterministic execution (scoring, analysis, generation, guidelines management, email testing, A/B testing, social optimization, technical SEO auditing, local SEO checking, ROI calculation, budget optimization, CLV analysis, revenue forecasting, content repurposing, review response drafting, link profile analysis, ad budget pacing, approval workflow, execution tracking, performance monitoring, CRM sync, credential management, team management, report generation, memory management)
- **46 MCP integrations** for connecting your own marketing accounts AND executing actions (social publishing, email sending, CRM writes, ad campaign creation, SMS, vector databases, knowledge management, and more)
- **Persistent brand memory** that learns across sessions
- **5-layer memory architecture** — session context → vector DB RAG (Pinecone/Qdrant) → temporal knowledge graphs (Graphiti) → universal agent memory (Supermemory) → knowledge base (Notion/Google Drive)
- **Human-in-the-loop execution** — every write action requires explicit approval with risk-level classification (low/medium/high/critical) and industry-specific compliance gates
- **Agency operations** — multi-client credential profiles, portfolio health dashboards, SOP library, team role management, white-labeled client reports, executive summaries
- **Adaptive scoring** that adjusts to your industry, business model, and goals

## Installation

### Option A: Add from a local directory

Clone or download this plugin directory, then register it with Claude Code:

```
claude plugins add /path/to/digital-marketing-pro
```

### Option B: Place in your plugins directory

Copy or clone the plugin directly into your Claude Code plugins folder:

```
~/.claude/plugins/digital-marketing-pro/
```

### Option C: Install in Claude Cowork

1. Compress the `digital-marketing-pro/` folder into a ZIP file
2. Open Cowork in Claude Desktop
3. Click **Plugin** in the left sidebar → **+** → **Upload**
4. Select the ZIP file

Or install from the [Claude plugin marketplace](https://claude.com/plugins) if published. See the [Claude Interfaces Guide](docs/claude-interfaces.md#installing-in-cowork) for full details.

### First-Run Setup

On first use, the plugin will:
1. Create `~/.claude-marketing/` for persistent brand data
2. Check Python dependencies (knowledge-only mode by default — no Python needed)
3. Display brand context summary (or prompt to set up your first brand)

### Python Dependencies (Optional)

The plugin works fully without any Python installation. All marketing knowledge, frameworks, agent capabilities, and slash commands work out of the box.

**Knowledge-only mode (0 MB, no install)** — Default
All 16 modules, 18 agents, 68 commands, and 124 reference knowledge files work with zero dependencies.

**Lite mode (~15 MB)** — Enables scoring scripts
```
pip install nltk textstat
```
Adds: brand voice scoring, content quality scoring, readability analysis.

**Full mode (~50 MB)** — Enables all scripts
```
pip install -r scripts/requirements.txt
```
Adds everything in lite mode plus: competitor scraping (`beautifulsoup4`, `requests`), QR code generation, and AI visibility API checking.

## Quick Start

### 1. Set Up Your Brand
```
/dm:brand-setup
```
Interactive brand profiling — answers questions about your brand identity, voice, audience, channels, and goals. Choose quick mode (5 questions) or full mode (17 questions).

### 2. Import Your Guidelines (Optional)
```
/dm:import-guidelines
```
Import your brand's voice guide, restrictions, channel styles, or messaging framework. These are enforced automatically across all content. See the [Brand Guidelines Guide](docs/brand-guidelines.md).

### 3. Start Marketing
Just talk naturally. The plugin detects intent and activates the right modules:

- "Help me plan a Q2 campaign" → Campaign Orchestrator + Marketing Strategist
- "Write a blog post about..." → Content Engine + SEO Specialist
- "How does my brand appear in ChatGPT?" → AEO/GEO Intelligence
- "Review my landing page" → CRO + Analytics Analyst
- "We have a PR crisis" → Crisis Communication + Brand Guardian

See the [Getting Started Guide](docs/getting-started.md) for a full walkthrough with examples.

## How It Works

### Session Lifecycle

1. **Session Start** — Plugin automatically loads your brand context:
   - Checks Python dependencies (optional — plugin works without them)
   - Displays brand summary: name, industry, voice settings, channels, goals, compliance, competitors
   - Loads brand guidelines summary (rule counts, restrictions, templates, SOPs)
   - This context is available throughout the session — you do not need to re-explain your brand

2. **During the Session** — Ask for marketing help naturally:
   - Plugin matches your request to the right module(s) and agent(s)
   - Brand voice, compliance rules, industry benchmarks, and guidelines are auto-applied
   - Past campaign data and insights are checked for relevant context
   - Content is automatically checked for brand alignment and guideline compliance when written (PreToolUse hook)

3. **Session End** — Key insights auto-saved to your brand profile:
   - Marketing decisions and learnings persist across sessions
   - Plugin gets smarter about your brand over time

### Brand Context Flow

```
Session Start
  → setup.py --summary
  → Rich brand context injected (voice, industry, compliance, goals)
  → Guidelines summary loaded (restrictions, channel styles, templates, SOPs)

User Request ("write me a LinkedIn post")
  → Content Engine module activated
  → Brand voice auto-applied (formality, authority, tone)
  → Brand guidelines enforced (restrictions checked, channel style applied)
  → Compliance rules checked for target markets
  → Platform specs loaded (character limits, best practices)
  → Content created on-brand

Session End
  → Insights saved to brand profile
  → Guideline violations logged for pattern analysis
  → Available in next session
```

### Multi-Client Workflow (Agencies)

1. Create profiles per client: `/dm:brand-setup`
2. Switch clients: `/dm:switch-brand` or say "switch to [client name]"
3. All outputs instantly adapt to the active client's voice, compliance, and context
4. Each client's campaign data and insights are stored separately

See the [Multi-Brand & Agency Guide](docs/multi-brand-guide.md) for detailed workflows.

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Installation, first brand setup, first marketing task — with worked examples |
| [Brand Guidelines](docs/brand-guidelines.md) | Importing voice guides, restrictions, channel styles, templates, and agency SOPs |
| [Multi-Brand & Agency Guide](docs/multi-brand-guide.md) | Multi-brand corporations (P&G pattern) and agency multi-client workflows |
| [Strategy & KPI Mapping](docs/strategy-and-kpis.md) | Business objectives → KPI frameworks → campaign strategy → measurement loop |
| [Integrations Guide](docs/integrations-guide.md) | MCP setup for GA4, HubSpot, Google Ads, Meta, and 8 more — including multi-CRM patterns |
| [Data & Insights](docs/data-and-insights.md) | Data flow, adaptive scoring, cross-session learning, campaign memory |
| [Competitor Intelligence](docs/competitor-intelligence.md) | Setting up competitors, running analysis, responding to competitive moves |
| [Historical Data](docs/historical-data.md) | How past campaigns and insights inform future strategies |
| [Cross-Channel Sync](docs/cross-channel-sync.md) | Keeping strategy synchronized across email, social, ads, and more |
| [Claude Interfaces](docs/claude-interfaces.md) | What works in Claude Code, Cowork, Desktop, and Claude.ai (with Cowork installation guide) |
| [Architecture](docs/architecture.md) | Technical deep-dive for contributors and power users |

## Which Claude Interface?

| | Claude Code | Claude Cowork | Claude Desktop (no Cowork) | Claude.ai Web |
|-|:-----------:|:-----------:|:--------------:|:-------------:|
| Full plugin support | Yes | Yes | Partial | No |
| Brand memory | Yes | Yes | No | No |
| MCP integrations | Yes | Yes | Yes | No |
| Document creation (Excel, PPT) | No | Yes | No | No |
| Recommended for | Terminal workflows | Visual desktop workflows | Quick content | One-off questions |

See the [Claude Interfaces Guide](docs/claude-interfaces.md) for details, including Cowork installation instructions and a comparison with Anthropic's official marketing plugin.

## Commands

All commands use the `/dm:` prefix. If another plugin shares a command name, use the full form `/digital-marketing-pro:command-name`.

| Command | What It Does |
|---------|-------------|
| `/dm:brand-setup` | Create or update brand profile |
| `/dm:campaign-plan` | Generate campaign plan |
| `/dm:content-brief` | Create content brief |
| `/dm:seo-audit` | SEO audit |
| `/dm:tech-seo-audit` | Technical SEO audit (Core Web Vitals, crawlability, indexation, redirects, security) |
| `/dm:local-seo-audit` | Local SEO audit (GBP, NAP consistency, citations, local pack, reviews) |
| `/dm:aeo-audit` | AI visibility audit |
| `/dm:attribution-model` | Multi-touch attribution setup with model selection and credit distribution |
| `/dm:case-study-plan` | Structured case study creation with CSR framework and distribution strategy |
| `/dm:client-onboarding` | Post-sale onboarding workflow with kickoff agenda and access checklist |
| `/dm:competitor-analysis` | Competitor deep-dive |
| `/dm:ad-creative` | Generate ad copy variations |
| `/dm:email-sequence` | Design email sequence |
| `/dm:content-calendar` | Build content calendar |
| `/dm:pr-pitch` | Create media pitch |
| `/dm:landing-page-audit` | Score landing page |
| `/dm:performance-report` | Generate performance report |
| `/dm:funnel-audit` | Analyze customer funnel |
| `/dm:launch-plan` | Product launch playbook |
| `/dm:audience-profile` | Build buyer persona |
| `/dm:influencer-brief` | Create influencer campaign brief |
| `/dm:crisis-response` | Rapid crisis response plan |
| `/dm:social-strategy` | Social media strategy |
| `/dm:import-guidelines` | Import brand guidelines, restrictions, and channel styles |
| `/dm:import-template` | Import deliverable templates (reports, proposals, briefs) |
| `/dm:import-sop` | Import agency SOPs and workflow definitions |
| `/dm:keyword-research` | Guided keyword research with clustering and intent mapping |
| `/dm:roi-calculator` | Campaign ROI calculation with multi-touch attribution |
| `/dm:ab-test-plan` | A/B test planning with sample size and hypothesis framework |
| `/dm:content-repurpose` | Content repurposing strategy with derivative format matrix |
| `/dm:creative-testing-framework` | Systematic creative testing strategy with testing matrix and holdout controls |
| `/dm:executive-dashboard` | C-suite dashboard design with business-outcome metrics and alert thresholds |
| `/dm:retargeting-strategy` | Retargeting campaign architecture with audience segmentation |
| `/dm:martech-audit` | Marketing technology stack audit with gap analysis |
| `/dm:media-plan` | Holistic paid media planning with channel allocation and flight scheduling |
| `/dm:budget-optimizer` | Data-driven budget reallocation with diminishing returns modeling |
| `/dm:qbr-plan` | Quarterly Business Review preparation with performance retrospective |
| `/dm:client-proposal` | Agency client proposal with strategy, scope, and pricing |
| `/dm:review-response` | Brand-aligned review response drafting with tone templates |
| `/dm:video-script` | Video marketing script writing for YouTube, TikTok, Reels, and LinkedIn |
| `/dm:webinar-plan` | End-to-end webinar planning with promotion and nurture strategy |
| `/dm:switch-brand` | Switch active brand (multi-client) |
| `/dm:publish-blog` | Publish blog post to WordPress/Webflow with SEO, categories, scheduling |
| `/dm:send-email-campaign` | Send email campaign via SendGrid/Klaviyo/Customer.io/Brevo/Mailgun |
| `/dm:launch-ad-campaign` | Create paid ad campaign on Google Ads/Meta/LinkedIn/TikTok with budget safeguards |
| `/dm:schedule-social` | Schedule posts to Twitter/Instagram/LinkedIn/TikTok/YouTube/Pinterest |
| `/dm:send-report` | Generate and deliver performance report via Slack, email, or Sheets |
| `/dm:crm-sync` | Sync marketing contacts/deals to Salesforce/HubSpot/Zoho/Pipedrive |
| `/dm:lead-import` | Import leads from forms/CSV/manual entry into CRM with deduplication |
| `/dm:pipeline-update` | Update deal stages, values, and notes in CRM pipeline |
| `/dm:segment-audience` | Create/update audience segments in CRM or email platform |
| `/dm:data-export` | Export marketing data to BigQuery, Google Sheets, or Supabase |
| `/dm:performance-check` | Pull live metrics from all connected platforms, instant performance snapshot |
| `/dm:campaign-status` | Check status of all active campaigns across platforms |
| `/dm:anomaly-scan` | Detect anomalies — drops, spikes, overspend, deliverability issues |
| `/dm:budget-tracker` | Real-time budget tracking across all ad platforms with pacing analysis |
| `/dm:save-knowledge` | Save brand knowledge to vector DB for future RAG retrieval |
| `/dm:search-knowledge` | Semantic search across all stored brand knowledge |
| `/dm:sync-memory` | Batch sync session learnings to persistent memory layer |
| `/dm:send-sms` | Send SMS/WhatsApp marketing message via Twilio or Brevo |
| `/dm:send-notification` | Send team notification via Slack or Intercom |
| `/dm:agency-dashboard` | Portfolio-level view across all client brands |
| `/dm:client-report` | Generate white-labeled client-facing performance report |
| `/dm:sop-library` | Manage agency SOPs — create, assign, track compliance |
| `/dm:credential-switch` | Switch active brand credential profile for multi-client management |
| `/dm:team-assign` | Assign marketing tasks to team members by role and capacity |
| `/dm:region-config` | Configure regional/market settings — timezone, language, compliance |
| `/dm:exec-summary` | Generate C-suite-ready executive summary with portfolio ROI |

## Persistent Memory

The plugin stores brand data at `~/.claude-marketing/`:

```
~/.claude-marketing/
├── brands/
│   ├── your-brand/
│   │   ├── profile.json          # Brand identity, voice, goals
│   │   ├── audiences.json        # Personas and segments
│   │   ├── competitors.json      # Competitor profiles
│   │   ├── campaigns/            # Past campaign data (indexed for fast lookup)
│   │   ├── performance/          # Performance snapshots over time
│   │   ├── insights.json         # Marketing learnings (last 200)
│   │   ├── guidelines/           # Brand guidelines, restrictions, channel styles
│   │   ├── templates/            # Custom deliverable templates
│   │   ├── content-library/      # Content inventory
│   │   └── voice-samples/        # Brand voice examples
│   └── _active-brand.json        # Currently active brand
├── sops/                         # Agency-level SOPs (apply across all brands)
├── templates/                    # Global templates
├── industry-data/                # Cached benchmarks
└── settings.json                 # Plugin preferences
```

**Multi-client support**: Agencies can create separate brand profiles and switch between them instantly. See the [Multi-Brand Guide](docs/multi-brand-guide.md).

## Architecture

```
digital-marketing-pro/
├── .claude-plugin/plugin.json    # Plugin manifest (v2.0.0)
├── skills/                       # 85 skill directories (16 modules + 68 commands + context engine)
├── agents/                       # 18 specialist agents
├── hooks/hooks.json              # Session lifecycle, compliance gates, guideline checks, and MCP write safety
├── scripts/                      # 42 Python execution scripts + requirements.txt
├── .mcp.json                     # 46 optional MCP integrations
├── docs/                         # 11 documentation guides
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
└── LICENSE
```

See [Architecture Reference](docs/architecture.md) for the full technical deep-dive.

## MCP Integrations (Optional)

The plugin works fully without any external API connections. For users who want to pull live data from their own marketing tools, the `.mcp.json` configuration file includes pre-configured MCP server definitions for 46 marketing platforms.

| Integration | What It Enables |
|-------------|----------------|
| **Google Analytics 4** | Traffic, conversions, audience data for performance reports |
| **Google Search Console** | Ranking data, queries, CTR for SEO audits |
| **Google Ads** | Campaign performance, keyword data, bid optimization |
| **Meta Business Suite** | Facebook/Instagram ads, audience insights |
| **HubSpot CRM** | Contacts, deals, email performance, pipeline data |
| **Mailchimp** | Email campaign analytics, list management |
| **LinkedIn Marketing** | Ad performance, company page analytics |
| **SEMrush** | Keyword research, competitor analysis, backlink data |
| **Ahrefs** | Backlink profiles, keyword explorer, content gaps |
| **Stripe** | Revenue data, conversion tracking, LTV calculations |
| **Google Sheets** | Export reports and calendars to spreadsheets |
| **Slack** | Send marketing reports and campaign alerts to channels |
| **TikTok Ads** | Campaign performance, creative insights, audience analytics |
| **Shopify** | eCommerce orders, products, customers, sales analytics |
| **WordPress** | Content publishing, post management, SEO metadata |
| **Salesforce** | CRM pipeline, opportunity data, lead management |
| **Google Looker Studio** | Dashboard data, report embedding, cross-platform visualization |
| **ActiveCampaign** | Email automation, lead scoring, CRM contacts, workflows |

See the [Integrations Guide](docs/integrations-guide.md) for setup instructions, required environment variables, and multi-CRM patterns for agencies.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

[MIT](LICENSE)

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on skill structure, agent definitions, script conventions, and how to submit changes.
