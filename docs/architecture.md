# Technical Architecture Reference

**Digital Marketing Pro** -- Claude Code Plugin v1.5.0

This document describes the internal architecture of the Digital Marketing Pro plugin for developers and contributors. It covers file structure, the WAT framework mapping, component anatomy, the hook system, script conventions, data persistence, adaptive scoring, and extension points.

---

## 1. Plugin File Structure

```
digital-marketing-pro/
├── .claude-plugin/
│   └── plugin.json                    # Plugin manifest (v1.5.0)
├── .mcp.json                          # 12 MCP server configurations
├── hooks/
│   └── hooks.json                     # 3 lifecycle hooks
├── agents/                            # 13 specialist agents
│   ├── marketing-strategist.md
│   ├── content-creator.md
│   ├── seo-specialist.md
│   ├── analytics-analyst.md
│   ├── brand-guardian.md
│   ├── media-buyer.md
│   ├── growth-engineer.md
│   ├── influencer-manager.md
│   ├── competitive-intel.md
│   ├── pr-outreach.md
│   ├── email-specialist.md            # NEW in v1.4.0
│   ├── cro-specialist.md              # NEW in v1.4.0
│   └── social-media-manager.md        # NEW in v1.4.0
├── scripts/                           # 24 Python scripts + requirements
│   ├── setup.py                       # Brand management, initialization
│   ├── campaign-tracker.py            # Campaign persistence + violation tracking
│   ├── adaptive-scorer.py             # Context-aware scoring weights
│   ├── brand-voice-scorer.py          # Voice consistency analysis
│   ├── content-scorer.py              # Content quality scoring
│   ├── social-post-formatter.py       # Platform validation (9 platforms)
│   ├── competitor-scraper.py          # Public competitor data extraction
│   ├── ai-visibility-checker.py       # AI answer engine visibility
│   ├── email-preview.py               # Email rendering preview
│   ├── headline-analyzer.py           # Headline effectiveness scoring
│   ├── keyword-clusterer.py           # Keyword grouping
│   ├── readability-analyzer.py        # Readability metrics
│   ├── schema-generator.py            # JSON-LD schema markup
│   ├── utm-generator.py               # UTM parameters + QR codes
│   ├── guidelines-manager.py          # Brand guidelines CRUD (v1.3.0)
│   ├── email-subject-tester.py        # Email subject line scoring (v1.5.0)
│   ├── spam-score-checker.py          # Email spam risk analysis (v1.5.0)
│   ├── send-time-optimizer.py         # Email send time recommendations (v1.5.0)
│   ├── sample-size-calculator.py      # A/B test sample size calculator (v1.5.0)
│   ├── significance-tester.py         # A/B test significance testing (v1.5.0)
│   ├── form-analyzer.py              # Form conversion optimization (v1.5.0)
│   ├── hashtag-analyzer.py           # Social hashtag analysis (v1.5.0)
│   ├── posting-time-analyzer.py      # Social posting time optimization (v1.5.0)
│   ├── calendar-validator.py         # Content calendar validation (v1.5.0)
│   └── requirements.txt               # Python dependencies
├── skills/                            # 36 skill directories
│   ├── context-engine/                # Shared intelligence layer
│   │   ├── SKILL.md
│   │   ├── industry-profiles.md       # 22 industries
│   │   ├── compliance-rules.md        # 16 jurisdictions + 10 industries
│   │   ├── platform-specs.md          # 20+ platforms
│   │   ├── scoring-rubrics.md         # 7 scoring frameworks
│   │   ├── intelligence-layer.md      # Learning system docs
│   │   └── guidelines-framework.md    # Guidelines structure reference (v1.3.0)
│   ├── brand-setup/SKILL.md           # Brand profile creation
│   ├── switch-brand/SKILL.md          # Brand switching
│   ├── [13 modules]/                  # Core marketing modules
│   │   ├── SKILL.md                   # Module definition
│   │   └── *.md                       # Reference knowledge files
│   ├── import-guidelines/SKILL.md     # Guideline import (v1.3.0)
│   ├── import-sop/SKILL.md           # SOP import (v1.3.0)
│   ├── import-template/SKILL.md      # Template import (v1.3.0)
│   └── [17 commands]/                 # Slash command skills
│       └── SKILL.md                   # Command definition
├── docs/                              # Documentation
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
└── LICENSE
```

**Total: 180 files** (167 plugin files + 13 documentation files).

The 13 modules are: content-engine, campaign-orchestrator, paid-advertising, analytics-insights, aeo-geo, audience-intelligence, cro, digital-pr, funnel-architect, growth-engineering, influencer-creator, reputation-management, and emerging-channels.

The 22 commands are: ad-creative, aeo-audit, audience-profile, campaign-plan, competitor-analysis, content-brief, content-calendar, crisis-response, email-sequence, funnel-audit, import-guidelines, import-sop, import-template, influencer-brief, landing-page-audit, launch-plan, performance-report, pr-pitch, seo-audit, social-strategy, and switch-brand.

The 13 agents are: marketing-strategist, content-creator, seo-specialist, analytics-analyst, brand-guardian, media-buyer, growth-engineer, influencer-manager, competitive-intel, pr-outreach, email-specialist, cro-specialist, and social-media-manager.

---

## 2. WAT Framework Mapping

The plugin follows the WAT architecture (Workflows, Agents, Tools), which separates probabilistic AI reasoning from deterministic code execution.

### Workflows (SKILL.md files + hooks.json)

SKILL.md files serve as workflow definitions. Each one specifies:

- **When to activate** -- trigger patterns and natural language phrases that route to this skill
- **What inputs are needed** -- required context, brand profile fields, user-provided parameters
- **What process to follow** -- numbered steps from brand context loading through output generation
- **What to output** -- structured deliverable format
- **Which agents to invoke** -- specialist agents required for this workflow

`hooks.json` defines the session lifecycle (SessionStart, PreToolUse, SessionEnd) that wraps all workflows with brand context injection and compliance checking.

Together, SKILL.md files and hooks form the "instructions" layer that the AI agent reads and follows.

### Agents (agents/*.md)

Thirteen specialist agents with distinct expertise areas and behavior rules. Each agent:

1. Loads brand context before producing any output (Rule 1 in every agent)
2. Follows domain-specific guidelines (8-11 behavior rules including guideline enforcement)
3. Produces structured output in a defined format
4. Calls Python scripts for deterministic scoring and analysis
5. Queries MCP servers for live data when available
6. Loads brand guidelines and enforces restrictions
7. Persists campaign data and insights via campaign-tracker.py
8. Recommends handoffs to other agents when work crosses domains

Multiple agents can collaborate on a single task. For example, the `/dm:campaign-plan` command invokes both marketing-strategist and media-buyer agents.

### Tools (scripts/*.py)

Twenty-four Python scripts handle deterministic execution: scoring, formatting, data persistence, and analysis. Every script:

- Accepts CLI arguments via argparse
- Produces JSON output to stdout
- Degrades gracefully when optional dependencies are missing (exit 0 + fallback JSON)
- Accepts `--brand SLUG` for brand-aware operations

**Why this separation matters:** When AI handles every step directly, accuracy compounds downward. Five steps at 90% accuracy each yields only 59% end-to-end success. By offloading scoring, formatting, and persistence to deterministic scripts, the AI agent focuses on orchestration and decision-making where it excels.

---

## 3. Module Skill Anatomy

Every module SKILL.md follows this structure:

```markdown
---
name: module-name
description: "One sentence describing when to invoke this module."
---

# Module Name

## When to Use This Skill
[Trigger patterns -- natural language phrases that route to this module]

## Brand Context (Auto-Applied)
[9-step brand context loading sequence -- identical across all 13 modules:
 1. Check session context for brand summary
 2. Load full profile from ~/.claude-marketing/brands/{slug}/profile.json
 3. Apply brand voice (formality, energy, humor, authority)
 4. Check compliance via context-engine/compliance-rules.md
 5. Reference industry benchmarks via context-engine/industry-profiles.md
 6. Use platform specs via context-engine/platform-specs.md
 7. Check campaign history via campaign-tracker.py
 8. Fallback message if no brand exists
 9. Check and enforce brand guidelines if guidelines/_manifest.json exists]

## Required Context
[What information the module needs from the user or brand profile]

## Capabilities
[Bulleted list of what the module can produce]

## Reference Knowledge Files
[List of .md files in this module's directory that inform its output]
```

The Brand Context block is standardized across all 13 modules to ensure consistent brand-aware behavior. Step 9 (guideline enforcement) was added in v1.3.0. If you modify this block, update it in all module SKILL.md files.

---

## 4. Command Skill Anatomy

Every command SKILL.md follows this structure:

```markdown
---
name: command-name
description: "One sentence describing when to invoke this command."
---

# /dm:command-name

## Purpose
[What this command produces and when to use it]

## Input Required
[Parameters the user must provide or will be prompted for]

## Process
1. **Load brand context**: Read ~/.claude-marketing/brands/_active-brand.json
   for the active slug, then load profile.json. Apply voice, compliance,
   industry context. If no brand exists, prompt for brand-setup or proceed
   with defaults.
2-N. [Command-specific steps]

## Output
[Structured deliverable format]

## Agents Used
[Which specialist agents this command invokes, with their roles]
```

Step 1 is always explicit brand context loading with the full file path. This was standardized in v1.2 to replace earlier vague "load brand profile" instructions that caused inconsistent behavior.

---

## 5. Agent Definitions

Each agent file in `agents/` follows this structure (updated in v1.4.0):

```markdown
---
name: agent-name
description: "Invoke when the user needs [specialty area]."
---

# Agent Name

[Persona description: experience level, sectors covered, thinking style]

## Core Capabilities
[4-5 bullet points describing frameworks, techniques, and domain knowledge]

## Behavior Rules
1. Always load brand context first. [Specific instructions for checking
   ~/.claude-marketing/brands/ and applying brand profile data]
2-N. [Domain-specific behavioral guidelines]
N. Check brand guidelines for content. [Load guidelines/_manifest.json,
   apply restrictions, voice rules, and channel styles]

## Output Format
[How this agent structures its deliverables]

## Tools & Scripts                         # NEW in v1.4.0
[Which Python scripts to call, with exact CLI commands, arguments, and when to use them.
 All paths use ${CLAUDE_PLUGIN_ROOT}/scripts/script-name.py]

## MCP Integrations                        # NEW in v1.4.0
[Which MCP servers to query for live data. All marked as optional.]

## Brand Data & Campaign Memory            # NEW in v1.4.0
[Which persistent files to load from ~/.claude-marketing/brands/{slug}/:
 Always load: profile.json, guidelines/_manifest.json
 Load when relevant: campaigns/, competitors.json, insights.json, audiences.json]

## Reference Files                         # NEW in v1.4.0
[Which context-engine reference files to consult for this domain:
 scoring-rubrics.md, platform-specs.md, industry-profiles.md, etc.]

## Cross-Agent Collaboration               # NEW in v1.4.0
[Specific handoff recommendations: which agents to coordinate with, what data to pass,
 and when to request collaboration]
```

### Agent Roster

| Agent | Activates On | Primary Frameworks | Key Scripts |
|-------|-------------|-------------------|-------------|
| marketing-strategist | Strategy, planning, positioning, GTM | SOSTAC, RACE, AARRR | utm-generator, campaign-tracker |
| content-creator | Writing, copywriting, content production | PAS, AIDA, storytelling | brand-voice-scorer, content-scorer, social-post-formatter, headline-analyzer, email-preview |
| seo-specialist | SEO, AEO, GEO, keywords, technical SEO | E-E-A-T, topic clusters | keyword-clusterer, schema-generator, ai-visibility-checker, competitor-scraper |
| analytics-analyst | Metrics, KPIs, reports, anomalies | Attribution, MMM, incrementality | utm-generator, adaptive-scorer, campaign-tracker |
| brand-guardian | Compliance, voice consistency, quality | Brand scorecards, voice scales | brand-voice-scorer, content-scorer, readability-analyzer, adaptive-scorer |
| media-buyer | Ad platforms, budget, bidding, targeting | ROAS, CPM/CPC modeling | utm-generator, content-scorer, headline-analyzer |
| growth-engineer | PLG, referrals, viral loops, retention | AARRR, ICE scoring, cohort analysis | content-scorer, utm-generator |
| influencer-manager | Creator partnerships, UGC, briefs | Tier frameworks, FTC compliance | social-post-formatter, content-scorer, brand-voice-scorer |
| competitive-intel | Competitor analysis, market positioning | Perceptual maps, SWOT, gap analysis | competitor-scraper, keyword-clusterer |
| pr-outreach | Media relations, press releases, pitches | Newsjacking, PESO model | content-scorer, readability-analyzer, headline-analyzer |
| email-specialist | Email marketing, deliverability, automation | Lifecycle, RFM, A/B testing | email-preview, content-scorer, readability-analyzer, brand-voice-scorer, headline-analyzer, adaptive-scorer, email-subject-tester, spam-score-checker, send-time-optimizer |
| cro-specialist | CRO, landing pages, A/B testing, pricing | Hypothesis testing, Bayesian analysis | content-scorer, headline-analyzer, readability-analyzer, adaptive-scorer, sample-size-calculator, significance-tester, form-analyzer |
| social-media-manager | Social media, community, content calendars | Platform-native strategy, algorithm signals | social-post-formatter, content-scorer, headline-analyzer, brand-voice-scorer, hashtag-analyzer, posting-time-analyzer, calendar-validator |

Every agent's Rule 1 mandates loading brand context before producing output. Every agent has a guideline enforcement rule. Every agent references campaign-tracker.py and guidelines-manager.py. These are the three most important architectural invariants in the agent system.

---

## 6. Context Engine

The shared intelligence layer lives at `skills/context-engine/` and provides reference data consumed by all modules, commands, and agents.

| File | Content | Approximate Size |
|------|---------|-----------------|
| industry-profiles.md | 22 industries with KPIs, benchmarks, compliance requirements, and recommended channels | ~1500 lines |
| compliance-rules.md | 16 geographic privacy laws (GDPR, CCPA, etc.), 10 industry regulations, FTC disclosure rules, 5 platform advertising policies, WCAG accessibility | ~800 lines |
| platform-specs.md | 8 social platforms with character limits and format specs, email specifications, 5 ad platform requirements, 11 schema markup types | ~1200 lines |
| scoring-rubrics.md | 7 scoring frameworks: content quality, ad effectiveness, email performance, landing page conversion, social engagement, PR impact, and brand voice consistency | ~400 lines |
| intelligence-layer.md | Adaptive learning system architecture -- how insights accumulate and inform future scoring | ~200 lines |
| guidelines-framework.md | Brand guidelines structure -- how to organize, store, and apply voice guides, restrictions, channel styles, and templates (v1.3.0) | ~300 lines |

**Critical note:** All modules reference these files. A change to compliance-rules.md affects compliance checking across the entire plugin. A change to platform-specs.md affects every content-producing module. Test broadly after modifying context-engine files.

---

## 7. Hook System

Three lifecycle hooks are defined in `hooks/hooks.json`. They wrap every Claude Code session with brand context injection, compliance checking, and insight persistence.

### SessionStart (type: command)

- **Fires:** When a Claude Code session begins
- **Runs:** `python setup.py --check-deps --summary`
- **Behavior:** Checks Python dependencies, reads the active brand profile, and outputs a 15-line brand context summary. This summary is injected directly into Claude's context window so the AI has brand name, industry, voice settings, channels, goals, compliance requirements, and competitor names available immediately.
- **Fallback:** If Python is unavailable, falls back to `echo Digital Marketing Pro loaded` so the session still starts.

### PreToolUse (type: prompt, matcher: Write|Edit)

- **Fires:** Before Claude writes or edits any file
- **Matcher:** Only triggers on Write and Edit tool calls
- **Behavior:** First checks whether the target file is marketing content. If the file is not in a marketing plugin directory and is not a marketing deliverable (ad copy, email, social post, blog, landing page, press release), responds `SKIP` immediately. If it is marketing content and a brand profile exists, checks: (1) brand voice alignment, (2) industry compliance, (3) FTC disclosure requirements for influencer/sponsored content.
- **Design principle:** Non-marketing file operations are never delayed or interfered with. The hook is designed to be invisible for non-marketing work.

### SessionEnd (type: prompt)

- **Fires:** When the session ends
- **Behavior:** If marketing work was done during the session, summarizes 1-3 key insights or decisions, then persists them via `campaign-tracker.py --action save-insight`. If no meaningful marketing work occurred, skips silently.
- **Persistence:** Each insight is saved as a `session_learning` entry in the brand's insights.json rolling buffer.

---

## 8. Script Architecture

All 24 scripts in `scripts/` follow consistent conventions.

### Conventions

- **CLI interface:** argparse for all arguments. No positional-only args.
- **Output:** JSON to stdout. Parseable by the AI agent or piped to other tools.
- **Graceful fallback:** When optional dependencies (nltk, textstat, requests, etc.) are missing, scripts output `{"fallback": true, ...}` with a human-readable message and exit with code 0. They never crash with exit code 1 due to missing optional deps.
- **Brand-aware:** `--brand SLUG` loads the brand profile from `~/.claude-marketing/brands/{slug}/`.
- **Paths:** All file paths use `pathlib.Path.home() / ".claude-marketing"`. Nothing is hardcoded to a specific user directory.

### Dependency Tiers

| Tier | Dependencies | Scripts |
|------|-------------|---------|
| Zero deps (always work) | Python stdlib only | setup.py, campaign-tracker.py, utm-generator.py (basic mode), schema-generator.py, guidelines-manager.py, email-subject-tester.py, spam-score-checker.py, send-time-optimizer.py, sample-size-calculator.py, significance-tester.py, form-analyzer.py, hashtag-analyzer.py, posting-time-analyzer.py, calendar-validator.py |
| Lite | nltk, textstat | brand-voice-scorer.py, content-scorer.py, readability-analyzer.py, headline-analyzer.py |
| Full | + requests, beautifulsoup4, qrcode, Pillow | competitor-scraper.py, utm-generator.py (QR mode), email-preview.py |
| Optional | + openai, anthropic | ai-visibility-checker.py (API mode) |

The zero-deps tier ensures that core brand management and campaign tracking always work, even on a fresh Python install with no pip packages. The lite tier covers the most commonly used scoring scripts. Full and optional tiers add capabilities that require external services or heavier libraries.

### Schema Versioning

Brand profiles follow schema version `1.0.0` (defined in `setup.py` as `SCHEMA_VERSION`). The setup script includes schema migration logic for upgrading profiles created by earlier plugin versions.

---

## 9. MCP Configuration

`.mcp.json` defines 12 MCP (Model Context Protocol) server integrations. These connect Claude Code to the user's own marketing platform accounts.

### Server List

| Server | Package | Purpose |
|--------|---------|---------|
| google-analytics | @anthropic/mcp-google-analytics | GA4 traffic, conversions, audience data |
| google-search-console | @anthropic/mcp-google-search-console | Rankings, queries, CTR for SEO |
| google-ads | mcp-google-ads | Campaign performance, keyword data, bids |
| meta-marketing | mcp-meta-marketing | Facebook/Instagram ads, audience insights |
| hubspot | @anthropic/mcp-hubspot | CRM contacts, deals, email performance |
| slack | @anthropic/mcp-slack | Marketing reports, campaign alerts |
| google-sheets | @anthropic/mcp-google-sheets | Report exports, content calendars |
| mailchimp | mcp-mailchimp | Email campaign analytics, list management |
| stripe | @anthropic/mcp-stripe | Revenue data, conversion tracking, LTV |
| linkedin-marketing | mcp-linkedin-marketing | Ad performance, company page analytics |
| semrush | mcp-semrush | Keyword research, competitor analysis |
| ahrefs | mcp-ahrefs | Backlink profiles, content gap analysis |

### Configuration Pattern

```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "@scope/mcp-package-name"],
      "env": {
        "API_KEY": "${ENV_VAR_NAME}"
      },
      "description": "What this server provides"
    }
  }
}
```

All credentials are referenced via `${ENV_VAR}` placeholders. Servers only activate when the corresponding environment variables are set. No credentials are stored in plugin code. The plugin works fully without any MCP servers enabled -- they add live data capabilities but are not required.

---

## 10. Data Persistence Model

All persistent data lives in `~/.claude-marketing/`, never in the plugin directory (since plugins may be cached or reinstalled).

```
~/.claude-marketing/
├── settings.json                      # Global plugin settings
├── brands/
│   ├── _active-brand.json             # {"active_slug": "brand-slug"}
│   └── {slug}/
│       ├── profile.json               # Brand profile (schema 1.0.0)
│       ├── audiences.json             # Audience segments
│       ├── competitors.json           # Competitor data
│       ├── insights.json              # 200-entry rolling buffer
│       ├── campaigns/
│       │   ├── _index.json            # Campaign index
│       │   └── {id}-{date}.json       # Individual campaigns
│       ├── performance/
│       │   └── {id}-{timestamp}.json  # Performance snapshots
│       ├── guidelines/                # Brand guidelines (v1.3.0)
│       │   ├── _manifest.json         # Rule counts, categories, metadata
│       │   ├── voice-and-tone.md      # Writing style rules
│       │   ├── messaging.md           # Approved positioning, proof points
│       │   ├── restrictions.md        # Banned words, restricted claims
│       │   ├── channel-styles.md      # Per-platform tone overrides
│       │   └── visual-identity.md     # Visual brand rules
│       ├── templates/                 # Custom deliverable templates (v1.3.0)
│       ├── content-library/           # Reusable content
│       └── voice-samples/             # Brand voice examples
├── sops/                              # Agency-level SOPs (v1.3.0)
├── templates/                         # Global templates
└── industry-data/                     # Cached benchmarks
```

### Key Design Decisions

- **`_active-brand.json`** is the single source of truth for which brand is currently active. Every command reads this file first.
- **`insights.json`** is a 200-entry rolling buffer. When it exceeds 200 entries, the oldest entries are dropped. This prevents unbounded growth while preserving recent learning.
- **Campaign files** use `{id}-{date}.json` naming for chronological sorting and easy cleanup.
- **Brand isolation:** Each brand slug gets its own directory. No data leaks between brands. The `switch-brand` command updates `_active-brand.json` to change context.

### Brand Profile Schema (profile.json)

The profile contains: company name, industry, business model, brand voice settings (formality, energy, humor, authority on 0.0-1.0 scales), target markets, channels, goals, compliance requirements, and competitor names. Voice settings are stored as floats (0.0-1.0) internally; the setup script's `normalize_profile()` function converts the user-facing 1-10 integer scale to this internal representation.

---

## 11. Adaptive Scoring System

`adaptive-scorer.py` wraps `content-scorer.py` with brand-aware weight computation. Instead of using fixed scoring weights, it adjusts weights based on three factors from the brand profile.

### Weight Computation Flow

1. **Load base weights** for the content type (blog, email, ad, landing_page, social)
2. **Apply industry modifier** from `INDUSTRY_WEIGHT_MODS` -- 10 industry profiles with per-dimension weights (e.g., healthcare boosts readability and spam_filler detection)
3. **Apply business model modifier** from `MODEL_WEIGHT_MODS` -- 8 business models with per-dimension weights (e.g., B2C eCommerce boosts CTA weight)
4. **Blend:** 60% industry weights + 40% business model weights
5. **Apply goal modifier** from `GOAL_WEIGHT_MODS` -- 7 goal types that add incremental boosts (e.g., lead_generation adds +0.10 to CTA and +0.05 to SEO)
6. **Regulated industry boost:** If the brand's industry is in the regulated set (healthcare, finance, legal), compliance weight gets an additional +0.10
7. **Normalize** all weights to sum to 1.0
8. **Output** final adaptive weights as JSON

### Scoring Dimensions

The system scores content across these dimensions, with weights adjusted by the flow above:

- **seo** -- keyword usage, meta optimization, search intent alignment
- **readability** -- Flesch-Kincaid, sentence complexity, vocabulary level
- **cta** -- call-to-action presence, clarity, and persuasiveness
- **structure** -- headings, formatting, logical flow, scanability
- **spam_filler** -- filler phrases, spam trigger words, content quality
- **length** -- appropriate content length for the format and platform

---

## 12. Extension Points

### Adding a New Module

1. Create `skills/{module-name}/SKILL.md` with the standard module structure (see Section 3)
2. Include the standardized Brand Context (Auto-Applied) block -- copy it from an existing module
3. Add reference knowledge files as `skills/{module-name}/*.md`
4. Update plugin documentation if the module introduces new capabilities

### Adding a New Command

1. Create `skills/{command-name}/SKILL.md` with the standard command structure (see Section 4)
2. Step 1 of the Process must be explicit brand context loading with the full `_active-brand.json` path
3. List which agents the command uses in the Agents Used section

### Adding a New Agent

1. Create `agents/{agent-name}.md` with the standard agent structure (see Section 5)
2. Rule 1 of Behavior Rules must load brand context from `~/.claude-marketing/brands/`
3. Define the Collaboration section to specify handoff points with other agents

### Adding a New Script

1. Create `scripts/{script-name}.py` following the conventions in Section 8
2. Use argparse for all arguments, output JSON to stdout
3. Implement graceful fallback for any non-stdlib dependencies
4. Accept `--brand SLUG` if the script needs brand context
5. Add dependencies to the appropriate tier in `requirements.txt`

### Adding a New MCP Server

1. Add an entry to `.mcp.json` following the pattern in Section 9
2. Use `${ENV_VAR}` placeholders for all credentials
3. Add a `description` field explaining what data the server provides
4. Document the required environment variables in the setup guide

### Extending the Context Engine

- **New industry profile:** Add to `skills/context-engine/industry-profiles.md` following the existing format (KPIs, benchmarks, compliance notes, recommended channels)
- **New compliance rules:** Add to `skills/context-engine/compliance-rules.md` under the appropriate section (geographic, industry, platform, or accessibility)
- **New platform specs:** Add to `skills/context-engine/platform-specs.md` with character limits, format requirements, and best practices
- **New scoring rubric:** Add to `skills/context-engine/scoring-rubrics.md` following the existing rubric structure

**Important:** Changes to context-engine files affect all modules and commands that reference them. Test across multiple modules after making changes.

---

## Architectural Invariants

These are rules that must not be broken when extending the plugin:

1. **Brand context first.** Every module, command, and agent must load brand context before producing marketing output. This is the single most important design rule.
2. **Scripts never crash on missing deps.** Optional dependency imports must be wrapped in try/except with fallback JSON output and exit code 0.
3. **No credentials in code.** All API keys and tokens go through environment variables or `~/.claude-marketing/` config files.
4. **Persistent data in ~/.claude-marketing/ only.** The plugin directory may be cached, relocated, or reinstalled. User data must survive that.
5. **JSON output from scripts.** All script output must be machine-parseable JSON so the AI agent can consume it programmatically.
6. **SKILL.md frontmatter required.** Every skill directory must have a SKILL.md with `name` and `description` in YAML frontmatter for Claude Code's skill discovery.
7. **PreToolUse must not block non-marketing work.** The compliance hook must respond `SKIP` for any file that is not marketing content.
