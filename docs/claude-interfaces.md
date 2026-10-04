# Claude Interface Compatibility Guide

**Digital Marketing Pro v3.17.0**

This plugin works in both **Claude Code** and **Claude Cowork** with full feature support. Some components also work in Claude Desktop (without Cowork) and Claude.ai Web, but with significant limitations. This guide is honest about what works where, what degrades, and what you lose entirely.

---

## Overview

Digital Marketing Pro comprises **164 skills**, **24 specialist agents**, **5 top-level slash commands**, **94 Python scripts**, **14 HTTP MCP connectors**, and **169 reference knowledge files**. Hooks ship empty by default (as of v3.1+) for clean multi-plugin coexistence; the prior 3-phase hook configuration is preserved at `hooks/hooks-reference.example.json` for users who want to re-enable specific lifecycle events.

The plugin uses the standard Claude plugin format: `.claude-plugin/plugin.json` manifest, `skills/` directories with SKILL.md frontmatter, `agents/` for specialist agents, `hooks/hooks.json` for lifecycle automation, `scripts/` for Python execution, and `.mcp.json` for live data integrations. This format is supported by both Claude Code and Claude Cowork.

---

## Claude Code (Full Support)

Everything works. Claude Code is the original target platform, and every feature was designed for it.

### What works

- **Hooks**: Empty by default as of v3.1+ for clean multi-plugin coexistence. Prior SessionStart / PreToolUse / SessionEnd hook configuration preserved at `hooks/hooks-reference.example.json` — re-enable per-event by copying entries into `hooks/hooks.json` if you want automated brand context injection, content-compliance interception, or insight persistence.
- **Skills and Commands**: All 18 top-level `/digital-marketing-pro:` slash commands available. All 164 skills (organized into modules like content-engine, seo-audit, aeo-geo, agency-dashboard, compliance, etc.) auto-discoverable via SKILL.md frontmatter routing.
- **Agents**: All 24 specialist agents activate based on conversation context (Marketing Strategist, Content Creator, SEO Specialist, Media Buyer, Analytics Analyst, Brand Guardian, Competitive Intel, PR Outreach, Growth Engineer, Influencer Manager, Email Specialist, CRO Specialist, Social Media Manager, Agency Operations, Marketing Scientist, Localization Specialist, Performance Monitor, Quality Assurance, Memory Manager, CRM Manager, Journey Orchestrator, Intelligence Curator, Market Intelligence, Execution Coordinator). Ongoing competitor monitoring is handled by Competitive Intel in `mode: monitoring` (the former standalone Competitor Intelligence agent merged into it).
- **Scripts**: All 94 Python scripts run natively — covering brand management, content scoring, campaign tracking, email testing, A/B testing, social optimization, technical SEO auditing, local SEO checking, ROI calculation, budget optimization, CLV analysis, revenue forecasting, GEO/AEO visibility tracking, C2PA content provenance, and more. Requires Python 3.8+ with optional dependencies.
- **MCP**: 14 HTTP MCP connectors available when env vars are configured (Slack, Canva, Figma, HubSpot, Amplitude, Notion, Ahrefs, SimilarWeb, Klaviyo, Google Calendar, Gmail, Stripe, Asana, Webflow). Additional Cowork-compatible aggregator paths (Pipedream, Composio, Zapier, Make.com) catalogued in `.mcp.json.connectors-reference`.
- **Memory**: Full persistent brand memory at `~/.claude-marketing/`. Brand profiles, campaign data, audience segments, competitor intelligence, content libraries, and marketing insights all persist across sessions.
- **Reference Knowledge**: All 169 reference files loaded automatically across the 164 skills.

### What a session looks like

```
$ claude
=== DIGITAL MARKETING PRO ===
Brand: GreenPeak Outdoors (greenpeak-outdoors)
Industry: Outdoor Recreation (regulated: no)
Model: B2C_DTC | Revenue: transactional | Sales cycle: impulse-to-1-week
Voice: Formality 4/10 | Energy 8/10 | Humor 5/10 | Authority 6/10
Tone: adventurous, authentic, knowledgeable
Avoid: cheap, basic | Prefer: premium, sustainable
Channels: email, instagram, youtube (primary: email)
Goals: repeat_purchase_growth | KPIs: repeat_rate, ltv, email_revenue_pct
Markets: US, Canada
Competitors: TrailPeak Gear, REI, Backcountry
Campaigns: 4 total
Profile: ~/.claude-marketing/brands/greenpeak-outdoors/profile.json
===

You: Help me plan a summer campaign
(All modules, agents, scripts, and MCP data available automatically)
```

### Cost tracking — `/usage` per-model breakdown (Claude Code v2.1.149+)

Claude Code v2.1.149 (released May 2026) exposes per-model token usage and projected cost via the `/usage` slash command. For agencies running multi-client workloads, this is the cleanest way to attribute Claude Code consumption to brands:

- **Per-session view**: shows tokens consumed by each model (e.g. Opus 5, Fable 5, Sonnet 5, Haiku 4.5) and any sub-agent runs in the current session — with billed cost in USD if your account has billing enabled.
- **Time-window view**: `/usage --since 7d` aggregates the last 7 days. Useful for the weekly agency pulse.
- **Project / directory scoped**: usage is tracked per working directory, so a brand-per-directory pattern (`~/work/clients/{slug}`) automatically gives you brand-attributable spend without extra tooling.

**Operational implications:**

- The 12-Part engagement (~250K–600K tokens) bills meaningfully against an agency account when run repeatedly across 50–200 brands. `/usage` lets you charge through to clients with defensible per-engagement cost numbers.
- 1M-context single-conversation engagements (Opus 4.7+ and the Claude 5 family — see `skills/engagement-workflow/SKILL.md`) trade more tokens for fewer round-trips — `/usage` confirms whether that tradeoff is net cheaper for your tier.
- On Pro / 5× / 20× Max plans, `/usage` shows quota burn rate against the rolling 5-hour and weekly windows — the warning to stop firing parallel sub-agents *before* you cap out, not after.

**Where to surface this in client reports**: the `/digital-marketing-pro:agency-dashboard` skill's "team utilization" section now references `/usage` output as the source of truth for Claude Code consumption costs (see the dashboard skill for the workflow).

### Best for

All serious marketing work. Ongoing brand management, multi-client agency workflows, campaign planning and execution, performance analysis with live data, content production at scale, and anything that benefits from persistent memory and automatic compliance checking. Available on macOS, Windows, and Linux.

---

## Claude Cowork (Full Support)

Claude Cowork is Anthropic's agentic desktop assistant, available as part of Claude Desktop on macOS and Windows. Cowork supports the same plugin format as Claude Code, which means **everything in Digital Marketing Pro works in Cowork**.

### What works

Every feature listed in the Claude Code section above also works in Cowork:

- **Hooks**: Ship empty by default (as of v3.1+), so nothing auto-fires — the same clean multi-plugin behavior as Claude Code. If you copy the reference SessionStart / PreToolUse / SessionEnd entries from `hooks/hooks-reference.example.json` back into `hooks/hooks.json`, they fire in Cowork too (auto brand-context injection, content-compliance interception, insight persistence).
- **Skills and Commands**: All 18 top-level `/digital-marketing-pro:` slash commands and all 164 skills work. Invoke commands by typing `/` in Cowork and navigating to the plugin's commands.
- **Agents**: All 24 specialist agents activate based on conversation context.
- **Scripts**: Python scripts run in Cowork's execution environment. If Python or optional dependencies are missing, scripts fall back gracefully (structured JSON with `"fallback": true` and exit code 0) --- the plugin never crashes.
- **MCP**: All 14 HTTP MCP connectors work when configured with your API credentials.
- **Memory**: Full persistent brand memory at `~/.claude-marketing/`. You must authorize Cowork to access this folder (see setup below).
- **Reference Knowledge**: All 169 reference files are loaded automatically.

### Cowork bonus capabilities

Cowork adds capabilities beyond what Claude Code offers for marketing work:

- **Document creation**: Cowork can create formatted Excel spreadsheets, PowerPoint presentations, and Word documents directly. Ask it to export your content calendar to Excel, create a campaign pitch deck, or generate a formatted performance report.
- **Visual review**: Cowork uses the Computer Use API to see your screen. It can review actual landing pages, social media posts, and ad creatives visually --- not just from code or text descriptions.
- **Sub-agent coordination**: Cowork can run parallel sub-agents for complex tasks. When you ask for a comprehensive campaign plan, Cowork can coordinate multiple specialist agents simultaneously.
- **App integration**: Cowork can interact with apps on your desktop (Google Drive, Gmail, Chrome, Slack, Notion, Asana) for end-to-end marketing workflows.

### Installing in Cowork

There are three ways to install Digital Marketing Pro in Cowork:

**Method 1: Upload in the Cowork UI**

1. Compress the `digital-marketing-pro/` folder into a ZIP file
2. Open Cowork in Claude Desktop
3. Click **Plugin** in the left sidebar
4. Click **+** then **Upload**
5. Select your ZIP file
6. The plugin installs immediately

**Method 2: Install from the marketplace**

If the plugin has been published to the [Claude plugin marketplace](https://claude.com/plugins):

1. Open Cowork
2. Click **Plugin** in the left sidebar
3. Click **+** then **Browse plugins**
4. Search for "Digital Marketing Pro"
5. Click **Install**

**Method 3: Install via CLI (if you also have Claude Code)**

```
claude plugin install digital-marketing-pro
```

This installs the plugin for both Claude Code and Cowork on the same machine.

### Setup after installation

After installing, you need to authorize folder access for persistent brand memory:

1. **Authorize the data folder**: When Cowork first tries to access `~/.claude-marketing/`, it will request folder permission. Grant it. This folder stores your brand profiles, campaign data, and marketing insights.
2. **Set up your brand**: Type `/digital-marketing-pro:brand-setup` in a Cowork conversation to create your first brand profile.
3. **Configure MCP integrations (optional)**: If you want live data from Google Analytics, HubSpot, or other platforms, set the required environment variables. See the [Integrations Guide](integrations-guide.md).

### What a Cowork session looks like

```
[Cowork starts a new conversation]

=== DIGITAL MARKETING PRO ===
Brand: GreenPeak Outdoors (greenpeak-outdoors)
Industry: Outdoor Recreation (regulated: no)
Model: B2C_DTC | Revenue: transactional | Sales cycle: impulse-to-1-week
Voice: Formality 4/10 | Energy 8/10 | Humor 5/10 | Authority 6/10
...
===

You: Create a Q3 product launch plan for our new ultralight tent,
     then build the content calendar in a spreadsheet.

Cowork: [Plans the launch across email, Instagram, YouTube]
        [Creates an Excel spreadsheet with the content calendar]
        [Saves the campaign plan to your brand's campaign history]
```

Cowork can chain marketing strategy (from the plugin's knowledge) with document creation (from Cowork's native capabilities) in a single workflow.

### Cowork vs. Anthropic's official marketing plugin

Anthropic ships a [marketing plugin](https://github.com/anthropics/knowledge-work-plugins) as part of their knowledge-work-plugins collection. Digital Marketing Pro is significantly more comprehensive:

| Capability | Anthropic Marketing Plugin | Digital Marketing Pro |
|---|---|---|
| Marketing skills | 5 (content, campaigns, brand, competitive, analytics) | 164 skills (16 core modules + atomic skills + context engine) |
| Slash commands | 7 | 5 top-level commands |
| Specialist agents | 0 | 24 |
| Python scripts | 0 | 86 |
| Reference knowledge files | ~5 | 169 |
| MCP integrations | 9 | 14 HTTP MCP connectors (+ npx/aggregator catalog) |
| Industry profiles | 0 | 22 with benchmarks |
| Compliance rules | 0 | 16 privacy jurisdictions |
| Business models | 0 | 10 models with adaptive scoring |
| Persistent brand memory | No | Yes (cross-session) |
| Campaign tracking | No | Yes (200-entry rolling buffer) |
| Adaptive scoring | No | Yes (industry + model + goal adjustments) |
| Multi-brand switching | No | Yes |
| Hook system | No | Opt-in (ships empty; reference SessionStart/PreToolUse/SessionEnd config preserved) |

The Anthropic plugin is a good starting point for light marketing use. Digital Marketing Pro is built for marketing professionals and agencies who need persistent brand intelligence, compliance automation, and deep domain expertise.

### Best for

Marketing professionals who prefer a visual desktop interface over a terminal. Cowork is especially strong for workflows that combine strategy with document creation (campaign decks, formatted reports, content calendars in spreadsheets). Also ideal for visual review of landing pages and ad creatives using Cowork's screen capabilities.

---

## Claude Desktop Without Cowork (Partial Support)

If you use Claude Desktop in standard chat mode (without activating Cowork), plugin support is limited.

### What works

- **Skills and SKILL.md files**: The 164 SKILL.md files can be loaded as context, giving Claude access to the structured instructions for every module and command.
- **Agent behavior rules**: The 24 agent definition files inform Claude's behavior when loaded.
- **Reference knowledge**: All 169 reference knowledge files (industry profiles, compliance rules, platform specs, scoring rubrics, channel strategies, framework templates) can be loaded.
- **MCP integrations**: If MCP servers are configured separately in Claude Desktop's own settings, integrations can work.

### What does not work

- **SessionStart hook**: No automatic brand context injection. You must describe your brand at the start of each conversation.
- **PreToolUse hook**: No automatic content compliance checking. You must ask Claude to review content against your brand guidelines explicitly.
- **SessionEnd hook**: No auto-save of marketing insights. Session learnings are not persisted.
- **Python scripts**: The 94 Python scripts will not run without terminal access.
- **Campaign tracking and adaptive scoring**: These require Python script execution and persistent file system access.
- **Slash commands**: May not be available depending on plugin support in standard Desktop mode.

### Workaround: Knowledge-Only Mode

Even without hooks and scripts, Claude Desktop can still deliver significant value if the reference files are loaded. You get access to all 169 reference knowledge files covering industry benchmarks, compliance rules, platform specifications, scoring rubrics, and strategic frameworks. Follow SKILL.md instructions manually for any of the 5 top-level commands.

### What you need to do manually

- **Describe your brand at the start of each conversation.** Include: brand name, industry, business model, voice characteristics (formality, energy, humor, authority on a 1-10 scale), preferred tone, channels, goals, and any compliance requirements.
- **Verify content compliance yourself.** Ask Claude to review content against your brand guidelines explicitly.
- **Save insights manually.** Copy valuable strategic insights to your brand notes yourself.

### Best for

Quick content creation for a known brand, reviewing marketing strategy with reference knowledge loaded, one-off tasks. Not recommended for ongoing brand management or multi-session campaign work.

**Recommendation**: If you have Claude Desktop, enable Cowork for full plugin support. See the Cowork section above.

---

## Claude.ai Web Interface (Limited)

The web interface does not support plugins. None of the plugin features activate natively.

### What works

- Claude's general marketing knowledge (substantial on its own, but not specialized to your brand or equipped with the plugin's frameworks).

### Workaround: Manual Knowledge Loading via Projects

You can use Claude.ai Projects to approximate some of the plugin's knowledge base:

1. Create a Project in Claude.ai.
2. Upload key reference files from the plugin as project knowledge:
   - `skills/context-engine/industry-profiles.md` --- industry benchmarks and business model profiles
   - `skills/context-engine/compliance-rules.md` --- privacy law requirements across 16 jurisdictions
   - `skills/context-engine/platform-specs.md` --- channel specifications, character limits, best practices
   - `skills/context-engine/scoring-rubrics.md` --- content and campaign evaluation frameworks
   - `skills/context-engine/intelligence-layer.md` --- how the modules connect and prioritize
3. Paste your brand profile JSON at the start of conversations so Claude has your brand context.

### What this does not give you

- No automatic brand context injection (you paste it manually each time).
- No slash commands.
- No specialist agent behaviors.
- No Python script execution.
- No campaign memory or insight persistence.
- No MCP integrations.
- No PreToolUse compliance checking.
- No adaptive scoring.

### Best for

One-off marketing questions, quick content drafts when no other interface is available, learning about marketing concepts using the plugin's reference frameworks. Not recommended for ongoing marketing work.

---

## Team Collaboration

If multiple team members use Digital Marketing Pro:

- **Brand profiles are stored locally** at `~/.claude-marketing/` on each machine. Team members working on the same brand need a shared copy of the brand profile directory. Options include syncing via cloud storage (Dropbox, OneDrive, Google Drive) or version-controlling the brand data in a shared repo.
- **MCP credentials are per-user.** Each team member must configure their own environment variables. API keys and access tokens should never be shared in plain text.
- **Campaign insights accumulate per-environment.** If two people run separate sessions for the same brand, their insights are saved to their local `insights.json`. There is no built-in merge mechanism. Teams should establish a convention for consolidating insights periodically.
- **Mixed interface teams work fine.** Some team members can use Claude Code while others use Cowork. The persistent data format at `~/.claude-marketing/` is identical regardless of which interface created it. Brand profiles, campaigns, and insights are fully interchangeable.

---

## Feature Comparison

| Feature | Claude Code | Claude Cowork | Claude Desktop (no Cowork) | Claude.ai Web |
|---|:---:|:---:|:---:|:---:|
| Slash commands (/digital-marketing-pro:) | Yes | Yes | Depends on plugin support | No |
| Brand memory (persistent) | Yes | Yes | No | No |
| SessionStart hook (auto brand context) | Opt-in | Opt-in | No | No |
| PreToolUse hook (compliance checking) | Opt-in | Opt-in | No | No |
| SessionEnd hook (insight auto-save) | Opt-in | Opt-in | No | No |
| Python scripts (86 tools) | Yes | Yes | No | No |
| MCP integrations (14 HTTP connectors) | Yes | Yes | Yes (separate config) | No |
| Reference knowledge (169 files) | Auto-loaded | Auto-loaded | Auto-loaded if plugin supported | Manual upload via Projects |
| Specialist agents (24 agents) | Yes | Yes | Depends on plugin support | No |
| Campaign tracking | Yes | Yes | No | No |
| Adaptive scoring | Yes | Yes | No | No |
| Content compliance (automatic) | Yes | Yes | No | No |
| Multi-client brand switching | Yes | Yes | No | No |
| Cross-session learning | Yes | Yes | No | No |
| Document creation (Excel, PPT) | No (terminal output) | Yes (native) | No | No |
| Visual page review | No | Yes (Computer Use) | No | No |
| Available platforms | macOS, Windows, Linux | macOS, Windows | macOS, Windows | Browser |

---

## Choosing Your Interface

### Use Claude Code when

- You prefer a terminal/CLI workflow.
- You are on Linux (Cowork is not available on Linux yet).
- You are integrating marketing workflows into a development pipeline.
- You want the fastest iteration speed for content production.

### Use Claude Cowork when

- You prefer a visual desktop interface over a terminal.
- You want to create formatted documents (Excel spreadsheets, PowerPoint decks, Word reports) as part of your marketing workflow.
- You need visual review of landing pages, ad creatives, or social posts.
- You are a marketing professional who does not use the command line.
- You want the full plugin experience with a more approachable interface.

### Use Claude Desktop (without Cowork) when

- Quick content creation for a known brand.
- You just need reference knowledge loaded for a one-off task.
- Terminal access is not needed and you do not need persistent memory.

### Use Claude.ai when

- One-off marketing questions that do not need brand-specific context.
- Quick content drafts where you can provide all context inline.
- No other interface is available.

---

## Plugin Marketplace

Digital Marketing Pro can be discovered and installed from the [Claude Plugin Marketplace](https://claude.com/plugins). The marketplace supports both Claude Code and Cowork installations.

To submit or update the plugin in the marketplace, see the [Claude plugin marketplace documentation](https://code.claude.com/docs/en/plugin-marketplaces).

---

## Tips for Non-Plugin Interfaces

If you are working in Claude Desktop (without Cowork) or Claude.ai and want to approximate the plugin experience:

1. **Start every conversation with your brand context.** Include your brand name, industry, business model (B2B SaaS, DTC, etc.), voice settings (formality, energy, humor, authority on a 1-10 scale), preferred tone words, words to avoid, primary channels, current goals, and target markets. This replicates what the SessionStart hook does automatically.

2. **Reference specific frameworks by name.** Even without the files loaded, you can ask Claude to use specific ones: "Use the SOSTAC framework for this campaign plan," "Apply the Jobs-to-Be-Done framework for audience profiling," "Score this landing page against CRO best practices."

3. **Ask for compliance checking explicitly.** "Check this content for GDPR compliance," "Does this need an FTC disclosure?", "Verify this meets CCPA requirements for our California audience."

4. **Request platform-specific formatting.** "Format this as a LinkedIn post under 3000 characters with 3-5 hashtags," "Write this as an Instagram caption under 2200 characters," "Keep this tweet under 280 characters."

5. **Manually track insights between sessions.** Keep a running document of key decisions, what worked, what did not, and strategic pivots.

---

## Summary

Digital Marketing Pro delivers its full value in **Claude Code** and **Claude Cowork**. Both interfaces support every plugin feature: hooks, persistent memory, Python scripts, MCP integrations, slash commands, and specialist agents. Cowork adds visual capabilities (document creation, screen review) on top. Other interfaces can access the knowledge base (169 reference files), but they lose the automation, persistence, and live data connections.

For marketing professionals: if you have Claude Pro, Max, Team, or Enterprise, use Cowork for the visual desktop experience or Claude Code for the terminal experience. Both give you the complete plugin.
