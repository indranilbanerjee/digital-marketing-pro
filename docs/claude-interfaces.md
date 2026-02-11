# Claude Interface Compatibility Guide

**Digital Marketing Pro v1.2.1**

This plugin works in both **Claude Code** and **Claude Cowork** with full feature support. Some components also work in Claude Desktop (without Cowork) and Claude.ai Web, but with significant limitations. This guide is honest about what works where, what degrades, and what you lose entirely.

---

## Overview

Digital Marketing Pro comprises 33 skills (13 modules + 19 commands + context engine), 10 specialist agents, 14 Python scripts, 12 MCP server integrations, 86 reference knowledge files, and a 3-phase hook system (SessionStart, PreToolUse, SessionEnd) that manages brand context, content compliance, and insight persistence automatically.

The plugin uses the standard Claude plugin format: `.claude-plugin/plugin.json` manifest, `skills/` directories with SKILL.md frontmatter, `agents/` for specialist agents, `hooks/hooks.json` for lifecycle automation, `scripts/` for Python execution, and `.mcp.json` for live data integrations. This format is supported by both Claude Code and Claude Cowork.

---

## Claude Code (Full Support)

Everything works. Claude Code is the original target platform, and every feature was designed for it.

### What works

- **Hooks**: SessionStart runs `setup.py --summary` and injects a rich brand context block (name, industry, voice settings, compliance flags, channels, goals, competitors, campaign history) at the start of every session. PreToolUse intercepts Write/Edit calls to check marketing content for brand voice alignment and compliance violations. SessionEnd auto-saves key marketing insights to your brand profile via `campaign-tracker.py`.
- **Skills and Commands**: All 19 `/dm:` slash commands are available (brand-setup, campaign-plan, content-brief, seo-audit, aeo-audit, competitor-analysis, ad-creative, email-sequence, content-calendar, pr-pitch, landing-page-audit, performance-report, funnel-audit, launch-plan, audience-profile, influencer-brief, crisis-response, social-strategy, switch-brand). All 13 module skills and the context engine skill are loaded and active.
- **Agents**: All 10 specialist agents (Marketing Strategist, Content Creator, SEO Specialist, Media Buyer, Analytics Analyst, Brand Guardian, Competitive Intel, PR Outreach, Growth Engineer, Influencer Manager) activate based on conversation context.
- **Scripts**: All 14 Python scripts run natively (setup.py, brand-voice-scorer.py, content-scorer.py, adaptive-scorer.py, campaign-tracker.py, social-post-formatter.py, headline-analyzer.py, readability-analyzer.py, keyword-clusterer.py, email-preview.py, schema-generator.py, utm-generator.py, competitor-scraper.py, ai-visibility-checker.py). Requires Python 3.8+ with optional dependencies.
- **MCP**: All 12 integrations available when env vars are configured (Google Analytics 4, Google Search Console, Google Ads, Meta Business Suite, HubSpot, Mailchimp, LinkedIn Marketing, SEMrush, Ahrefs, Stripe, Google Sheets, Slack).
- **Memory**: Full persistent brand memory at `~/.claude-marketing/`. Brand profiles, campaign data, audience segments, competitor intelligence, content libraries, and marketing insights all persist across sessions.
- **Reference Knowledge**: All 86 reference files loaded automatically across 14 skill modules.

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

### Best for

All serious marketing work. Ongoing brand management, multi-client agency workflows, campaign planning and execution, performance analysis with live data, content production at scale, and anything that benefits from persistent memory and automatic compliance checking. Available on macOS, Windows, and Linux.

---

## Claude Cowork (Full Support)

Claude Cowork is Anthropic's agentic desktop assistant, available as part of Claude Desktop on macOS and Windows. Cowork supports the same plugin format as Claude Code, which means **everything in Digital Marketing Pro works in Cowork**.

### What works

Every feature listed in the Claude Code section above also works in Cowork:

- **Hooks**: SessionStart, PreToolUse, and SessionEnd all fire in Cowork. Your brand context is auto-injected, content compliance is checked, and insights are auto-saved.
- **Skills and Commands**: All 19 `/dm:` slash commands and all 13 module skills work. Invoke commands by typing `/` in Cowork and navigating to the plugin's commands.
- **Agents**: All 10 specialist agents activate based on conversation context.
- **Scripts**: Python scripts run in Cowork's execution environment. If Python or optional dependencies are missing, scripts fall back gracefully (structured JSON with `"fallback": true` and exit code 0) --- the plugin never crashes.
- **MCP**: All 12 integrations work when configured with your API credentials.
- **Memory**: Full persistent brand memory at `~/.claude-marketing/`. You must authorize Cowork to access this folder (see setup below).
- **Reference Knowledge**: All 86 reference files are loaded automatically.

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
2. **Set up your brand**: Type `/dm:brand-setup` in a Cowork conversation to create your first brand profile.
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
| Marketing skills | 5 (content, campaigns, brand, competitive, analytics) | 13 modules + context engine (14 total) |
| Slash commands | 7 | 19 |
| Specialist agents | 0 | 10 |
| Python scripts | 0 | 14 |
| Reference knowledge files | ~5 | 86 |
| MCP integrations | 9 | 12 |
| Industry profiles | 0 | 22 with benchmarks |
| Compliance rules | 0 | 16 privacy jurisdictions |
| Business models | 0 | 10 models with adaptive scoring |
| Persistent brand memory | No | Yes (cross-session) |
| Campaign tracking | No | Yes (200-entry rolling buffer) |
| Adaptive scoring | No | Yes (industry + model + goal adjustments) |
| Multi-brand switching | No | Yes |
| Hook system | No | 3 hooks (SessionStart, PreToolUse, SessionEnd) |

The Anthropic plugin is a good starting point for light marketing use. Digital Marketing Pro is built for marketing professionals and agencies who need persistent brand intelligence, compliance automation, and deep domain expertise.

### Best for

Marketing professionals who prefer a visual desktop interface over a terminal. Cowork is especially strong for workflows that combine strategy with document creation (campaign decks, formatted reports, content calendars in spreadsheets). Also ideal for visual review of landing pages and ad creatives using Cowork's screen capabilities.

---

## Claude Desktop Without Cowork (Partial Support)

If you use Claude Desktop in standard chat mode (without activating Cowork), plugin support is limited.

### What works

- **Skills and SKILL.md files**: The 33 SKILL.md files can be loaded as context, giving Claude access to the structured instructions for every module and command.
- **Agent behavior rules**: The 10 agent definition files inform Claude's behavior when loaded.
- **Reference knowledge**: All 86 reference knowledge files (industry profiles, compliance rules, platform specs, scoring rubrics, channel strategies, framework templates) can be loaded.
- **MCP integrations**: If MCP servers are configured separately in Claude Desktop's own settings, integrations can work.

### What does not work

- **SessionStart hook**: No automatic brand context injection. You must describe your brand at the start of each conversation.
- **PreToolUse hook**: No automatic content compliance checking. You must ask Claude to review content against your brand guidelines explicitly.
- **SessionEnd hook**: No auto-save of marketing insights. Session learnings are not persisted.
- **Python scripts**: The 14 Python scripts will not run without terminal access.
- **Campaign tracking and adaptive scoring**: These require Python script execution and persistent file system access.
- **Slash commands**: May not be available depending on plugin support in standard Desktop mode.

### Workaround: Knowledge-Only Mode

Even without hooks and scripts, Claude Desktop can still deliver significant value if the reference files are loaded. You get access to all 86 reference knowledge files covering industry benchmarks, compliance rules, platform specifications, scoring rubrics, and strategic frameworks. Follow SKILL.md instructions manually for any of the 19 commands.

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
| Slash commands (/dm:) | Yes | Yes | Depends on plugin support | No |
| Brand memory (persistent) | Yes | Yes | No | No |
| SessionStart hook (auto brand context) | Yes | Yes | No | No |
| PreToolUse hook (compliance checking) | Yes | Yes | No | No |
| SessionEnd hook (insight auto-save) | Yes | Yes | No | No |
| Python scripts (14 tools) | Yes | Yes | No | No |
| MCP integrations (12 platforms) | Yes | Yes | Yes (separate config) | No |
| Reference knowledge (86 files) | Auto-loaded | Auto-loaded | Auto-loaded if plugin supported | Manual upload via Projects |
| Specialist agents (10 agents) | Yes | Yes | Depends on plugin support | No |
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

Digital Marketing Pro delivers its full value in **Claude Code** and **Claude Cowork**. Both interfaces support every plugin feature: hooks, persistent memory, Python scripts, MCP integrations, slash commands, and specialist agents. Cowork adds visual capabilities (document creation, screen review) on top. Other interfaces can access the knowledge base (86 reference files), but they lose the automation, persistence, and live data connections.

For marketing professionals: if you have Claude Pro, Max, Team, or Enterprise, use Cowork for the visual desktop experience or Claude Code for the terminal experience. Both give you the complete plugin.
