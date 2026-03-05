---
name: help
description: "Show the getting started guide, available commands, examples, and help for Digital Marketing Pro"
argument-hint: "[--commands | --examples | --troubleshoot]"
---

# /dm:help

Show the Digital Marketing Pro getting started guide with setup instructions, available commands, usage examples, and troubleshooting.

## Behavior

When invoked, display a structured help overview with the following sections. Use the reference documentation in `docs/getting-started.md` for full details.

### 1. Quick Start Summary

Display this quick orientation:

```
=== DIGITAL MARKETING PRO — HELP ===

Version: 2.5.1
Agents: 25 specialist agents
Skills: 118 slash commands (/dm:*) — all with argument-hint autocomplete
Modules: 16 marketing knowledge domains
Connectors: 14 HTTP + 67 npx integrations

Getting Started:
  1. /dm:brand-setup        — Create your brand profile (start here)
  2. /dm:import-guidelines   — Import voice guides, restrictions, templates
  3. /dm:integrations        — See which connectors are active
  4. /dm:connect <name>      — Set up a new connector
  5. Just ask!               — Describe what you need in natural language
```

### 2. Arguments

| Argument | Effect |
|----------|--------|
| (none) | Show the full help overview |
| `--commands` | List all 117 slash commands grouped by category |
| `--connectors` | Show connector status (shortcut for /dm:integrations) |
| `--brand` | Show current brand profile summary |
| `--examples` | Show 10 example prompts across different marketing tasks |
| `--troubleshoot` | Show common issues and solutions |

### 3. Commands by Category

When `--commands` is specified, group all commands into these categories:

| Category | Example Commands |
|----------|-----------------|
| **Brand Management** | `/dm:brand-setup`, `/dm:switch-brand`, `/dm:import-guidelines` |
| **Strategy & Planning** | `/dm:campaign-plan`, `/dm:launch-plan`, `/dm:social-strategy`, `/dm:media-plan` |
| **Content Creation** | `/dm:content-brief`, `/dm:email-sequence`, `/dm:ad-creative`, `/dm:video-script` |
| **SEO & Technical** | `/dm:seo-audit`, `/dm:tech-seo-audit`, `/dm:keyword-research`, `/dm:aeo-audit` |
| **Analytics & Reporting** | `/dm:performance-report`, `/dm:roi-calculator`, `/dm:attribution-model` |
| **Paid Advertising** | `/dm:media-plan`, `/dm:launch-ad-campaign`, `/dm:budget-optimizer` |
| **Social Media** | `/dm:social-strategy`, `/dm:schedule-social`, `/dm:content-calendar` |
| **Email Marketing** | `/dm:email-sequence`, `/dm:send-email-campaign` |
| **CRM & Data** | `/dm:crm-sync`, `/dm:lead-import`, `/dm:pipeline-update`, `/dm:data-export` |
| **Competitive Intelligence** | `/dm:competitor-analysis`, `/dm:competitor-monitor`, `/dm:share-of-voice` |
| **PR & Outreach** | `/dm:pr-pitch`, `/dm:influencer-brief`, `/dm:crisis-response` |
| **Audience** | `/dm:audience-profile`, `/dm:focus-group`, `/dm:segment-audience` |
| **CRO & Growth** | `/dm:landing-page-audit`, `/dm:funnel-audit`, `/dm:ab-test-plan` |
| **Quality & Evaluation** | `/dm:eval-content`, `/dm:verify-claims`, `/dm:quality-report` |
| **Multilingual** | `/dm:translate-content`, `/dm:localize-campaign`, `/dm:language-config` |
| **Execution & Publishing** | `/dm:publish-blog`, `/dm:send-email-campaign`, `/dm:launch-ad-campaign` |
| **Monitoring** | `/dm:performance-check`, `/dm:anomaly-scan`, `/dm:budget-tracker` |
| **Connector Discovery** | `/dm:integrations`, `/dm:connect`, `/dm:add-integration` |
| **Agency Operations** | `/dm:agency-dashboard`, `/dm:client-report`, `/dm:sop-library` |
| **Memory & Knowledge** | `/dm:save-knowledge`, `/dm:search-knowledge`, `/dm:sync-memory` |

### 4. Example Prompts

When `--examples` is specified, show these real-world examples:

```
Getting Started:
  /dm:brand-setup
  → Create your brand profile interactively (5 quick questions or 17 detailed)

Strategy:
  "Plan a product launch for our new cold brew line"
  → Activates Campaign Orchestrator with your brand context

Content:
  "Write a 3-email welcome sequence for new subscribers"
  → Creates emails in your brand voice with compliance rules applied

SEO:
  /dm:seo-audit https://example.com
  → Full technical + content + E-E-A-T audit with action items

Competitive:
  /dm:competitor-analysis "Blue Bottle, Counter Culture, Stumptown"
  → Multi-dimensional analysis: content, SEO, ads, social, positioning

Paid Ads:
  /dm:media-plan --budget=50000 --channels="google,meta,linkedin"
  → Channel allocation, flight schedule, creative rotation plan

Analytics:
  /dm:performance-check
  → Pull live metrics from all connected platforms

Execution:
  /dm:publish-blog --platform=wordpress --status=draft
  → Publish with SEO metadata, or export HTML for manual upload

AI Visibility:
  /dm:aeo-audit
  → Check how your brand appears in ChatGPT, Perplexity, Google AI Overviews

Connectors:
  /dm:connect hubspot
  → Step-by-step OAuth setup for HubSpot CRM connector
```

### 5. Troubleshooting

When `--troubleshoot` is specified, show common issues:

| Issue | Solution |
|-------|----------|
| "No active brand" message | Run `/dm:brand-setup` to create your first brand profile |
| Python features unavailable | Install: `pip install nltk textstat` (lite mode) or full requirements.txt |
| MCP connector not working | Run `/dm:integrations` to check status, `/dm:connect <name>` for setup |
| Brand voice seems off | Run `/dm:brand-setup --full` for detailed 17-question profiling |
| Commands not recognized | Ensure plugin is installed: check "Manage Plugin" in Cowork or `claude plugin list` |
| Session context missing | Brand context loads on SessionStart — start a fresh session |
| Google Drive not showing | Google Drive is a platform-level integration — check Claude Desktop → Settings → Integrations |

### 6. Skill Platform Features

When `--platform` argument is used or when showing the full help, include this section:

```
=== SKILL PLATFORM FEATURES ===

Argument Hints (55 skills):
  All user-invocable skills show autocomplete hints in the Skills UI.
  Example: /dm:seo-audit shows [URL]
  Example: /dm:campaign-plan shows [product/service --budget=N]

Execution Safety (17 skills):
  Skills that write to external platforms require explicit user invocation.
  Claude cannot auto-trigger: publish-blog, send-email-campaign,
  launch-ad-campaign, schedule-social, send-report, and 12 more.
  This works alongside the MCP write approval hook.

Quality Evals (3 skills):
  campaign-plan, seo-audit, and content-engine have evals/evals.json
  with structured test cases for quality benchmarking.
```

### 7. Documentation References

Point users to these resources for deeper dives:

| Guide | What it covers |
|-------|---------------|
| `docs/getting-started.md` | Full setup walkthrough with examples |
| `docs/brand-guidelines.md` | Importing voice guides, restrictions, templates |
| `docs/integrations-guide.md` | Connecting marketing tools (67 integrations) |
| `docs/multi-brand-guide.md` | Agency workflows, brand switching |
| `docs/strategy-and-kpis.md` | KPI frameworks, reporting dashboards |
| `docs/architecture.md` | Technical deep dive: modules, agents, hooks |
| `docs/claude-interfaces.md` | Cowork-specific capabilities |
| `docs/competitor-intelligence.md` | Competitive monitoring setup |
| `docs/cross-channel-sync.md` | Cross-channel campaign coordination |
| `CONNECTORS.md` | All available connectors by category |

## Output Format

Present information in clean, scannable tables and code blocks. Keep the output concise — this is a quick reference, not a tutorial. Link to the full documentation for detailed walkthroughs.
