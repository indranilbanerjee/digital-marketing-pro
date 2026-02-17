# Digital Marketing Pro — Claude Code & Cowork Plugin

[![Version](https://img.shields.io/badge/version-2.2.0-blue.svg)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-optional-yellow.svg)](#python-dependencies-optional)
[![Cowork](https://img.shields.io/badge/cowork-compatible-purple.svg)](docs/claude-interfaces.md#claude-cowork-full-support)

The most comprehensive digital marketing plugin for Claude Code and Claude Cowork. 16 integrated modules covering the entire marketing spectrum from strategy to execution to measurement — including dedicated Technical SEO, Local SEO, and Marketing Automation modules. **v2.0 adds a full execution layer**: publish content, send emails, launch ads, schedule social, sync CRMs, manage persistent memory, and deliver reports — all with human-in-the-loop approval workflows. Multi-client agency operations with credential profiles, portfolio dashboards, and team management. **v2.1 adds predictive intelligence, GEO monitoring, competitor monitoring, SEO execution, self-healing campaigns, creative intelligence, compound intelligence, synthetic audience testing, journey orchestration, and more.** **v2.2 adds a comprehensive evaluation/QA layer (hallucination detection, claim verification, output validation, composite scoring, quality regression tracking) and full multilingual support (4 translation MCP servers, automatic language routing, transcreation, cultural adaptation, multilingual SEO).**

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
- **25 specialist agents**, including 5 execution agents, 2 predictive intelligence agents, and agents for competitor intelligence, compound intelligence, journey orchestration, quality assurance, and localization, that activate based on conversation context, call 64 Python scripts for scoring, query MCP servers for live data, enforce brand guidelines, and persist campaign learnings
- **Brand guidelines enforcement** — import voice guides, restrictions, channel styles, messaging frameworks; automatically applied across all modules
- **Deliverable templates** and **agency SOPs** — custom output formats and workflow definitions
- **115 slash commands** for direct access to common workflows — including execution, monitoring, predictive intelligence, GEO monitoring, competitor monitoring, SEO execution, creative intelligence, compound intelligence, journey orchestration, synthetic audience testing, evaluation/QA, multilingual support, and more
- **64 Python scripts** for deterministic execution (scoring, analysis, generation, guidelines management, email testing, A/B testing, social optimization, technical SEO auditing, local SEO checking, ROI calculation, budget optimization, CLV analysis, revenue forecasting, content repurposing, review response drafting, link profile analysis, ad budget pacing, approval workflow, execution tracking, performance monitoring, CRM sync, credential management, team management, report generation, memory management, SEO execution, competitor tracking, GEO tracking, PDF generation, revenue simulation, churn prediction, macro signal tracking, creative fatigue prediction, intelligence graphing, journey engine, growth loop modeling, campaign health monitoring, narrative mapping, audience simulation, hallucination detection, claim verification, output validation, eval running, quality tracking, eval config management, prompt A/B testing, language routing)
- **67 MCP integrations** for connecting your own marketing accounts AND executing actions (social publishing, email sending, CRM writes, ad campaign creation, SMS, vector databases, knowledge management, CRM platforms, PM/design tools, SEO/monitoring, marketing automation, translation services, and more)
- **Persistent brand memory** that learns across sessions
- **5-layer memory architecture** — session context → vector DB RAG (Pinecone/Qdrant) → temporal knowledge graphs (Graphiti) → universal agent memory (Supermemory) → knowledge base (Notion/Google Drive)
- **Human-in-the-loop execution** — every write action requires explicit approval with risk-level classification (low/medium/high/critical) and industry-specific compliance gates
- **Agency operations** — multi-client credential profiles, portfolio health dashboards, SOP library, team role management, white-labeled client reports, executive summaries
- **Adaptive scoring** that adjusts to your industry, business model, and goals
- **Predictive intelligence** — revenue simulation, churn prediction, market timing signals
- **GEO monitoring** — AI visibility tracking across ChatGPT, Perplexity, Gemini, Copilot
- **Competitor monitoring** — ongoing competitive scanning with change detection, share of voice, and alerts
- **Self-healing campaigns** — auto-correction within guardrails for campaign health
- **Creative intelligence** — fatigue prediction and content decay scanning
- **Compound intelligence** — cross-agent learning hub with confidence scoring
- **Synthetic audience testing** — simulated focus groups from CRM data
- **Journey orchestration** — cross-channel journey state machines and growth loop modeling

## Installation

### ⚠️ MCP Server Configuration (Optional - Opt-In Only)

This plugin integrates with 67 external services via MCP servers (social media platforms, CRM systems, ad networks, analytics tools, marketing automation platforms, translation services, and more). **MCP integrations are 100% opt-in** and require manual configuration:

**To enable MCP integrations:**

1. Install the plugin first (see options below)
2. Navigate to the plugin directory: `~/.claude/plugins/digital-marketing-pro/` (or your installation path)
3. Copy the example MCP config: `cp .mcp.json.example .mcp.json`
4. Edit `.mcp.json` and add your API keys and credentials for the platforms you want to use
5. Follow the [MCP Integration Guide](docs/integrations-guide.md) for detailed setup instructions
6. Restart Claude Desktop to activate the integrations

**The plugin works fully WITHOUT MCP servers** — all 115 skills, 25 agents, frameworks, and knowledge files function immediately. MCP is ONLY needed if you want to execute actions on external platforms (publish content, send emails, launch ads, sync CRM data, etc.). Most users will not need MCP configuration.

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
All 16 modules, 25 agents, 115 commands, and 143 reference knowledge files work with zero dependencies.

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
- "How does my brand appear in ChatGPT?" → AEO/GEO Intelligence + GEO Monitoring
- "Review my landing page" → CRO + Analytics Analyst
- "We have a PR crisis" → Crisis Communication + Brand Guardian
- "Predict next quarter's revenue" → Predictive Intelligence + Marketing Scientist
- "Monitor our competitors" → Competitor Intelligence + Competitor Monitoring
- "Test this message with a focus group" → Synthetic Audience Testing

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
| [Integrations Guide](docs/integrations-guide.md) | MCP setup for GA4, HubSpot, Google Ads, Meta, and more — including multi-CRM patterns |
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
| `/dm:seo-implement` | Execute SEO changes — meta tags, schema markup, redirects via CMS MCP |
| `/dm:rank-monitor` | Track keyword rankings over time with trend analysis and alerts |
| `/dm:serp-tracker` | Monitor SERP feature ownership (featured snippets, PAA, local pack) |
| `/dm:redirect-manager` | Plan, validate, and deploy redirect chains with loop detection |
| `/dm:competitor-monitor` | Start ongoing competitive scanning with change detection and baselines |
| `/dm:share-of-voice` | Calculate share of voice across organic, paid, and social channels |
| `/dm:competitor-alerts` | Configure real-time alerts for competitor changes (pricing, ads, content) |
| `/dm:geo-monitor` | Track brand visibility across AI platforms (ChatGPT, Perplexity, Gemini, Copilot) |
| `/dm:entity-audit` | Audit brand entity consistency across knowledge graphs and AI models |
| `/dm:narrative-tracker` | Monitor how AI platforms describe your brand vs competitors |
| `/dm:pdf-report` | Generate PDF performance reports with charts and executive summary |
| `/dm:live-dashboard` | Create real-time dashboard with live metric connections |
| `/dm:attribution-report` | Multi-touch attribution analysis with model comparison |
| `/dm:cohort-analysis` | Customer cohort analysis with retention curves and LTV trends |
| `/dm:simulate` | Run revenue simulation with scenario modeling and Monte Carlo analysis |
| `/dm:what-if` | What-if analysis for budget, channel, and strategy changes |
| `/dm:churn-risk` | Predict customer churn risk with intervention recommendations |
| `/dm:creative-health` | Assess creative fatigue across campaigns with refresh recommendations |
| `/dm:content-decay-scan` | Scan content library for decay — traffic drops, outdated info, broken links |
| `/dm:learn` | Save cross-agent learnings to compound intelligence graph |
| `/dm:recall` | Retrieve past learnings with confidence scoring and context |
| `/dm:autopilot-status` | View self-healing campaign status — auto-corrections, guardrail triggers |
| `/dm:journey-design` | Design cross-channel customer journey with state machines and triggers |
| `/dm:loop-detect` | Identify and model growth loops (viral, content, paid, sales) |
| `/dm:dark-funnel` | Analyze dark funnel touchpoints — communities, DMs, word-of-mouth signals |
| `/dm:data-import` | Import external data from CSV, APIs, or databases into the plugin |
| `/dm:add-integration` | Add custom MCP integration for unsupported platforms |
| `/dm:narrative-landscape` | Map competitive narrative positioning across the market |
| `/dm:counter-narrative` | Generate counter-narrative strategy against competitor positioning |
| `/dm:focus-group` | Run synthetic focus group simulation from CRM persona data |
| `/dm:message-test` | A/B test messaging variants against synthetic audience segments |
| `/dm:market-weather` | Macro market signal dashboard — economic, seasonal, trend indicators |
| `/dm:intelligence-report` | Cross-domain intelligence briefing combining all monitoring signals |
| `/dm:pricing-test` | Price sensitivity testing with Van Westendorp and Gabor-Granger models |

## Predictive Intelligence

Revenue simulation, churn prediction, and market timing powered by the **marketing-scientist** and **market-intelligence** agents. Run Monte Carlo simulations, model what-if scenarios, track macro signals, and predict customer churn with intervention recommendations.

- `/dm:simulate` — revenue simulation with scenario modeling
- `/dm:what-if` — what-if analysis for budget and strategy changes
- `/dm:churn-risk` — churn prediction with intervention playbooks
- `/dm:market-weather` — macro market signal monitoring
- `/dm:intelligence-report` — cross-domain intelligence briefing
- `/dm:pricing-test` — price sensitivity testing

## GEO Monitoring

Track your brand's visibility across AI platforms — ChatGPT, Perplexity, Gemini, and Copilot. Monitor how AI models describe your brand, audit entity consistency, and track narrative changes over time.

- `/dm:geo-monitor` — AI platform visibility tracking
- `/dm:entity-audit` — entity consistency across knowledge graphs
- `/dm:narrative-tracker` — AI narrative monitoring

## Competitor Monitoring

Ongoing competitive scanning with change detection, share of voice tracking, and real-time alerts. The **competitor-intelligence** agent maintains baselines, detects changes in competitor pricing, ads, content, and positioning.

- `/dm:competitor-monitor` — continuous competitive scanning
- `/dm:share-of-voice` — SOV across organic, paid, and social
- `/dm:competitor-alerts` — real-time change alerts

## SEO Execution

Move beyond audits to execution. Deploy meta tag updates, schema markup, and redirects directly through CMS MCP integrations. Track rankings and SERP feature ownership over time.

- `/dm:seo-implement` — execute SEO changes via CMS
- `/dm:rank-monitor` — keyword ranking tracking
- `/dm:serp-tracker` — SERP feature monitoring
- `/dm:redirect-manager` — redirect deployment and validation

## Self-Healing Campaigns

Campaigns that auto-correct within defined guardrails. The **campaign-health-monitor** script detects budget pacing issues, performance drops, and deliverability problems, then applies corrections automatically with full audit trails.

- `/dm:autopilot-status` — view auto-corrections and guardrail triggers

## Creative Intelligence

Predict creative fatigue before it impacts performance. Scan content libraries for decay — traffic drops, outdated information, and broken links. Proactive refresh recommendations.

- `/dm:creative-health` — creative fatigue assessment
- `/dm:content-decay-scan` — content library health scan

## Compound Intelligence

Cross-agent learning hub where insights from one agent improve all others. The **intelligence-curator** agent maintains a confidence-scored intelligence graph that grows smarter with every interaction.

- `/dm:learn` — save learnings to intelligence graph
- `/dm:recall` — retrieve past learnings with confidence scoring

## Synthetic Audience Testing

Simulate focus groups and message tests using synthetic audiences built from your CRM data and persona profiles. Test messaging, positioning, and creative before spending budget.

- `/dm:focus-group` — synthetic focus group simulation
- `/dm:message-test` — message A/B testing against synthetic segments

## Journey Orchestration

Design and manage cross-channel customer journeys with state machines, triggers, and growth loop modeling. The **journey-orchestrator** agent manages journey state across email, social, ads, and web. Detect growth loops and analyze dark funnel touchpoints.

- `/dm:journey-design` — cross-channel journey design
- `/dm:loop-detect` — growth loop identification and modeling
- `/dm:dark-funnel` — dark funnel analysis

### Evaluation & Quality Assurance
- **Hallucination detection** — Pattern-based detection of fabricated statistics, fake URLs, unsubstantiated claims, and made-up entities
- **Claim verification** — Cross-check marketing claims against evidence data with fuzzy matching
- **Output validation** — Validate content structure against 8 built-in schemas (blog, email, ad, social, landing page, press release, brief, plan)
- **Composite eval scoring** — 6-dimension evaluation with A+ through F grading and configurable weights
- **Quality regression tracking** — 30-day rolling baselines with automatic regression detection
- **Prompt A/B testing** — Compare quality scores across content variations
- **Eval-before-publish gates** — Automatic quality checks before content enters approval workflow
- **7 eval commands**: /dm:eval-content, /dm:verify-claims, /dm:validate-output, /dm:quality-report, /dm:eval-config, /dm:prompt-test, /dm:eval-suite

### Multilingual Support
- **4 translation MCP servers** — DeepL (European/CJK), Sarvam AI (22 Indic languages), Google Cloud Translation (100+ languages), Lara Translate (marketing-context)
- **Automatic language routing** — Detects source language and routes to optimal translation service
- **Translation quality scoring** — Length ratio, formatting preservation, key term consistency, placeholder integrity
- **Transcreation framework** — Cultural recreation for emotional content (CTAs, slogans, headlines) with brief templates
- **Cultural adaptation** — Hofstede dimensions applied to marketing: social proof, urgency, trust signals per market
- **Multilingual SEO** — hreflang auditing, international sitemaps, Baidu/Yandex/Naver optimization
- **RTL support** — Arabic, Hebrew, Farsi, Urdu layout guidance
- **Indic language expertise** — Hindi, Tamil, Telugu, Bengali + 5 more via Sarvam AI with transliteration support
- **6 multilingual commands**: /dm:translate-content, /dm:localize-campaign, /dm:language-audit, /dm:language-config, /dm:multilingual-score, /dm:hreflang-check

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
├── .claude-plugin/plugin.json    # Plugin manifest (v2.2.0)
├── skills/                       # 132 skill directories (16 modules + 115 commands + context engine)
├── agents/                       # 25 specialist agents
├── hooks/hooks.json              # Session lifecycle, compliance gates, guideline checks, and MCP write safety
├── scripts/                      # 64 Python execution scripts + requirements.txt
├── .mcp.json                     # 67 optional MCP integrations
├── docs/                         # 11 documentation guides
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
└── LICENSE
```

See [Architecture Reference](docs/architecture.md) for the full technical deep-dive.

### Agents (25)

| Agent | Role |
|-------|------|
| `marketing-strategist` | Overall strategy, campaign planning, budget allocation |
| `content-creator` | Content writing across all formats and channels |
| `seo-specialist` | SEO audits, keyword strategy, technical SEO, local SEO |
| `analytics-analyst` | Performance analysis, reporting, anomaly detection |
| `brand-guardian` | Brand voice enforcement, guideline compliance |
| `media-buyer` | Paid advertising strategy, bid optimization, budget pacing |
| `growth-engineer` | Growth loops, viral mechanics, retention, PLG |
| `influencer-manager` | Influencer discovery, briefs, campaign management |
| `competitive-intel` | Competitor analysis and market positioning |
| `pr-outreach` | Media relations, press releases, thought leadership |
| `email-specialist` | Email deliverability, automation, lifecycle sequences |
| `cro-specialist` | Conversion optimization, A/B testing, form optimization |
| `social-media-manager` | Platform-native social strategy, community management |
| `execution-coordinator` | Bridges planning and execution with approval workflow |
| `performance-monitor-agent` | Live data monitoring, anomaly detection, campaign health |
| `crm-manager` | Cross-CRM operations (Salesforce/HubSpot/Zoho/Pipedrive) |
| `memory-manager` | Persistent brand knowledge via RAG and knowledge graphs |
| `agency-operations` | Multi-client portfolio management, SOPs, credential profiles |
| `competitor-intelligence` | Ongoing competitive scanning with change detection |
| `marketing-scientist` | Revenue simulation, churn prediction, statistical modeling |
| `market-intelligence` | Macro signal tracking, market timing, economic indicators |
| `intelligence-curator` | Cross-agent learning hub with confidence scoring |
| `journey-orchestrator` | Cross-channel journey state machines, growth loops |
| `quality-assurance` | Multi-dimensional content evaluation, hallucination detection, quality tracking |
| `localization-specialist` | Translation routing, transcreation, cultural adaptation, multilingual SEO |

### Scripts (64)

| Script | Purpose |
|--------|---------|
| `setup.py` | Brand profiling and session initialization |
| `brand-voice-scorer.py` | Brand voice alignment scoring |
| `content-scorer.py` | Content quality scoring |
| `readability-analyzer.py` | Readability analysis (Flesch-Kincaid, etc.) |
| `competitor-scraper.py` | Competitor website analysis |
| `social-post-formatter.py` | Platform-specific social formatting |
| `qr-code-generator.py` | QR code generation |
| `visibility-checker.py` | AI visibility checking |
| `campaign-tracker.py` | Campaign memory and insights persistence |
| `adaptive-scorer.py` | Context-aware adaptive scoring |
| `guidelines-manager.py` | Brand guidelines CRUD operations |
| `email-subject-tester.py` | Email subject line scoring |
| `spam-score-checker.py` | Email spam risk checking |
| `send-time-optimizer.py` | Email send time optimization |
| `sample-size-calculator.py` | A/B test sample size calculation |
| `significance-tester.py` | Statistical significance testing |
| `form-analyzer.py` | Form conversion optimization |
| `hashtag-analyzer.py` | Hashtag analysis per platform |
| `posting-time-analyzer.py` | Social posting time optimization |
| `calendar-validator.py` | Content calendar validation |
| `tech-seo-auditor.py` | Technical SEO auditing |
| `local-seo-checker.py` | Local SEO NAP consistency checking |
| `roi-calculator.py` | Campaign ROI calculation |
| `budget-optimizer.py` | Budget reallocation optimization |
| `clv-calculator.py` | Customer lifetime value calculation |
| `content-repurposer.py` | Content repurposing strategy |
| `review-response-drafter.py` | Review response drafting |
| `ad-budget-pacer.py` | Ad budget pacing analysis |
| `link-profile-analyzer.py` | Link profile health analysis |
| `revenue-forecaster.py` | Revenue forecasting |
| `approval-manager.py` | Approval lifecycle management |
| `execution-tracker.py` | Execution audit trail |
| `performance-monitor.py` | Metrics aggregation and anomaly detection |
| `memory-manager.py` | Vector DB/RAG interface and sync |
| `crm-sync.py` | CRM data preparation and sync |
| `report-generator.py` | Formatted report generation |
| `credential-manager.py` | Per-brand credential profiles |
| `team-manager.py` | Team roles, permissions, capacity |
| `seo-executor.py` | SEO change tracking and execution via CMS |
| `competitor-tracker.py` | Competitive baselines, diff, SOV, pricing, ads |
| `geo-tracker.py` | AI visibility auditing across ChatGPT, Perplexity, Gemini, Copilot |
| `pdf-generator.py` | PDF report generation and scheduling |
| `revenue-simulator.py` | Monte Carlo revenue simulation |
| `churn-predictor.py` | Customer churn prediction |
| `macro-signal-tracker.py` | Macro economic and market signal tracking |
| `creative-fatigue-predictor.py` | Creative fatigue prediction |
| `intelligence-graph.py` | Cross-agent intelligence graph |
| `journey-engine.py` | Cross-channel journey state machines |
| `growth-loop-modeler.py` | Growth loop identification and modeling |
| `campaign-health-monitor.py` | Self-healing campaign monitoring |
| `narrative-mapper.py` | Competitive narrative mapping |
| `audience-simulator.py` | Synthetic audience simulation |
| `hallucination-detector.py` | Pattern-based hallucination detection |
| `claim-verifier.py` | Marketing claim cross-verification |
| `output-validator.py` | Content structure validation against schemas |
| `eval-runner.py` | Master evaluation suite orchestrator |
| `quality-tracker.py` | Eval score persistence and regression tracking |
| `eval-config-manager.py` | Per-brand quality thresholds and weights |
| `prompt-ab-tester.py` | Prompt variation quality comparison |
| `language-router.py` | Translation service routing and language detection |

## MCP Integrations (Optional)

The plugin works fully without any external API connections. For users who want to pull live data from their own marketing tools, the `.mcp.json` configuration file includes pre-configured MCP server definitions for 67 marketing platforms.

### Analytics & Data

| Integration | What It Enables |
|-------------|----------------|
| **Google Analytics 4** | Traffic, conversions, audience data for performance reports |
| **Google Search Console** | Ranking data, queries, CTR for SEO audits |
| **Mixpanel** | Product analytics, user behavior, funnel analysis |
| **Amplitude** | Product analytics, cohort analysis, experimentation |
| **BigQuery** | Data warehouse queries, cross-platform analysis |
| **Google Looker Studio** | Dashboard data, report embedding, cross-platform visualization |

### Advertising

| Integration | What It Enables |
|-------------|----------------|
| **Google Ads** | Campaign performance, keyword data, bid optimization |
| **Meta Business Suite** | Facebook/Instagram ads, audience insights |
| **LinkedIn Marketing** | Ad performance, company page analytics |
| **TikTok Ads** | Campaign performance, creative insights, audience analytics |

### SEO & Monitoring

| Integration | What It Enables |
|-------------|----------------|
| **SEMrush** | Keyword research, competitor analysis, backlink data |
| **Ahrefs** | Backlink profiles, keyword explorer, content gaps |
| **Moz** | Domain authority, keyword tracking, site crawl data |
| **Google PageSpeed** | Core Web Vitals, performance scoring, optimization suggestions |
| **Brandwatch** | Social listening, sentiment analysis, brand monitoring |

### CRM

| Integration | What It Enables |
|-------------|----------------|
| **HubSpot CRM** | Contacts, deals, email performance, pipeline data |
| **Salesforce** | CRM pipeline, opportunity data, lead management |
| **Zoho CRM** | Contacts, deals, automation, lead management |
| **Pipedrive** | Deal pipeline, activity tracking, sales analytics |
| **Odoo** | CRM, sales, marketing, inventory, all-in-one ERP |
| **Freshsales** | AI lead scoring, deal management, email tracking |
| **Monday CRM** | Visual pipelines, automations, team collaboration |
| **Microsoft Dynamics 365** | Enterprise CRM, sales insights, customer service |
| **Copper** | Google Workspace-native CRM, relationship tracking |
| **Close** | Inside sales CRM, calling, email sequences |
| **Keap** | Small business CRM, automation, payments |

### Email & Messaging

| Integration | What It Enables |
|-------------|----------------|
| **Mailchimp** | Email campaign analytics, list management |
| **SendGrid** | Transactional and marketing email sending |
| **Klaviyo** | eCommerce email/SMS automation, segmentation |
| **Customer.io** | Behavioral email/push automation |
| **Brevo** | Email, SMS, WhatsApp campaigns |
| **Mailgun** | Email API, deliverability monitoring |

### Social Publishing

| Integration | What It Enables |
|-------------|----------------|
| **Twitter/X** | Post scheduling, engagement tracking |
| **Instagram** | Content publishing, story management |
| **LinkedIn Publishing** | Article and post publishing |
| **TikTok Content** | Video publishing, trend data |
| **YouTube** | Video publishing, analytics |
| **Pinterest** | Pin creation, board management |

### CMS & eCommerce

| Integration | What It Enables |
|-------------|----------------|
| **WordPress** | Content publishing, post management, SEO metadata |
| **Webflow** | CMS content publishing, design-aware publishing |
| **Shopify** | eCommerce orders, products, customers, sales analytics |

### Marketing Automation

| Integration | What It Enables |
|-------------|----------------|
| **ActiveCampaign** | Email automation, lead scoring, CRM contacts, workflows |
| **Marketo** | Enterprise marketing automation, lead management, campaign orchestration |
| **Pardot** | B2B marketing automation, lead nurturing, ROI reporting |

### Memory & Knowledge

| Integration | What It Enables |
|-------------|----------------|
| **Pinecone** | Vector database for RAG-powered brand knowledge |
| **Qdrant** | Vector search for semantic knowledge retrieval |
| **Supermemory** | Universal agent memory across sessions |
| **Graphiti** | Temporal knowledge graphs for campaign learning |
| **Notion** | Knowledge base content management |
| **Google Drive** | Document storage and retrieval |

### Communication & Revenue

| Integration | What It Enables |
|-------------|----------------|
| **Slack** | Send marketing reports and campaign alerts to channels |
| **Twilio** | SMS/WhatsApp messaging |
| **Intercom** | Customer messaging, team notifications |
| **Stripe** | Revenue data, conversion tracking, LTV calculations |

### Project Management & Design

| Integration | What It Enables |
|-------------|----------------|
| **Jira** | Issue tracking, sprint management, marketing project workflows |
| **Asana** | Task management, project timelines, team coordination |
| **ClickUp** | All-in-one project management, docs, goals |
| **Canva** | Design creation, template management, brand kit |
| **Figma** | Design collaboration, prototyping, asset export |

### Testing & Database

| Integration | What It Enables |
|-------------|----------------|
| **Linear** | Issue tracking, project management |
| **Optimizely** | A/B testing, experimentation |
| **Supabase** | Database operations, real-time data |

### Translation Services

| Integration | What It Enables |
|-------------|----------------|
| **DeepL** | European and CJK language translation with formality control and glossaries |
| **Sarvam AI** | 22 Indic language translation with transliteration support |
| **Google Cloud Translation** | 100+ language translation with batch processing and language detection |
| **Lara Translate** | Marketing-context translation with translation memories |

See the [Integrations Guide](docs/integrations-guide.md) for setup instructions, required environment variables, and multi-CRM patterns for agencies.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

[MIT](LICENSE)

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on skill structure, agent definitions, script conventions, and how to submit changes.
