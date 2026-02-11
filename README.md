# Digital Marketing Pro — Claude Code & Cowork Plugin

[![Version](https://img.shields.io/badge/version-1.5.0-blue.svg)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-optional-yellow.svg)](#python-dependencies-optional)
[![Cowork](https://img.shields.io/badge/cowork-compatible-purple.svg)](docs/claude-interfaces.md#claude-cowork-full-support)

The most comprehensive digital marketing plugin for Claude Code and Claude Cowork. 13 integrated modules covering the entire marketing spectrum from strategy to execution to measurement.

## What This Plugin Does

Digital Marketing Pro transforms Claude into a full-stack marketing intelligence system. It covers every marketing discipline, adapts to any business model, auto-applies compliance rules, and learns from your past campaigns.

### 13 Core Modules

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

### Key Differentiators

- **10 business models** supported (B2B SaaS, eCommerce, Local, Agency, Creator, Enterprise, Non-Profit, Marketplace, DTC, B2B Services)
- **22 industry profiles** with benchmarks and compliance rules
- **16 privacy law jurisdictions** auto-applied (GDPR, CCPA, PIPL, DPDPA, and more)
- **13 specialist agents** that activate based on conversation context, call Python scripts for scoring, query MCP servers for live data, enforce brand guidelines, and persist campaign learnings
- **Brand guidelines enforcement** — import voice guides, restrictions, channel styles, messaging frameworks; automatically applied across all modules
- **Deliverable templates** and **agency SOPs** — custom output formats and workflow definitions
- **22 slash commands** for direct access to common workflows
- **24 Python scripts** for deterministic execution (scoring, analysis, generation, guidelines management, email testing, A/B testing, social optimization)
- **12 MCP integrations** for connecting your own marketing accounts (GA4, Search Console, Google Ads, Meta, HubSpot, Mailchimp, etc.)
- **Persistent brand memory** that learns across sessions
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
All 13 modules, 13 agents, 22 commands, and 87 reference knowledge files work with zero dependencies.

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
| `/dm:aeo-audit` | AI visibility audit |
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
| `/dm:switch-brand` | Switch active brand (multi-client) |

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
├── .claude-plugin/plugin.json    # Plugin manifest (v1.5.0)
├── skills/                       # 36 skill directories (13 modules + 22 commands + context engine)
├── agents/                       # 13 specialist agents
├── hooks/hooks.json              # Session lifecycle, compliance gates, and guideline checks
├── scripts/                      # 24 Python execution scripts + requirements.txt
├── .mcp.json                     # Optional MCP integrations config
├── docs/                         # 11 documentation guides
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
└── LICENSE
```

See [Architecture Reference](docs/architecture.md) for the full technical deep-dive.

## MCP Integrations (Optional)

The plugin works fully without any external API connections. For users who want to pull live data from their own marketing tools, the `.mcp.json` configuration file includes pre-configured MCP server definitions for 12 marketing platforms.

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

See the [Integrations Guide](docs/integrations-guide.md) for setup instructions, required environment variables, and multi-CRM patterns for agencies.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

[MIT](LICENSE)

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on skill structure, agent definitions, script conventions, and how to submit changes.
