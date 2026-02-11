# Changelog

All notable changes to the Digital Marketing Pro plugin are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This project uses [Semantic Versioning](https://semver.org/).

## [1.5.0] - 2026-02-12

### Added
- **9 new domain-specific Python scripts** (all zero-dependency, stdlib-only), bringing the total from 15 to 24 scripts:
  - **Email domain** (3 scripts for `email-specialist` agent):
    - `scripts/email-subject-tester.py` — Score email subject lines for open-rate effectiveness (length, spam triggers, personalization, power words, emoji usage)
    - `scripts/spam-score-checker.py` — Check email content for spam risk indicators (word density, punctuation, caps ratio, link density)
    - `scripts/send-time-optimizer.py` — Recommend optimal email send times by industry and audience type (built-in benchmark tables)
  - **CRO domain** (3 scripts for `cro-specialist` agent):
    - `scripts/sample-size-calculator.py` — Calculate A/B test sample size and estimated test duration (Z-test based, stdlib math)
    - `scripts/significance-tester.py` — Test A/B results for statistical significance (Z-test for proportions + chi-squared, p-value, confidence intervals)
    - `scripts/form-analyzer.py` — Analyze web forms for conversion optimization (field friction scoring, mobile-friendliness, progressive disclosure)
  - **Social media domain** (3 scripts for `social-media-manager` agent):
    - `scripts/hashtag-analyzer.py` — Analyze hashtags per platform (count, length, broad/niche mix, banned hashtag detection)
    - `scripts/posting-time-analyzer.py` — Recommend optimal posting times per platform and industry (built-in engagement data)
    - `scripts/calendar-validator.py` — Validate content calendar structure (frequency, variety, gap detection, weekend coverage)

### Changed
- **7 SKILL.md files updated** with new agent references:
  - 5 command skills gained new agents in "Agents Used" section: `email-sequence` (+email-specialist), `landing-page-audit` (+cro-specialist), `social-strategy` (+social-media-manager), `content-calendar` (+social-media-manager), `funnel-audit` (+cro-specialist)
  - 2 module skills gained new "Agents Used" section: `cro` (+cro-specialist), `emerging-channels` (+social-media-manager)
- **3 agent files updated** with new script references in "Tools & Scripts" section:
  - `agents/email-specialist.md` — Added email-subject-tester.py, spam-score-checker.py, send-time-optimizer.py
  - `agents/cro-specialist.md` — Added sample-size-calculator.py, significance-tester.py, form-analyzer.py
  - `agents/social-media-manager.md` — Added hashtag-analyzer.py, posting-time-analyzer.py, calendar-validator.py
- `.claude-plugin/plugin.json` version bumped from 1.4.0 to 1.5.0, script count 15 → 24
- `README.md` updated version badge and script counts
- `docs/getting-started.md` version 1.4.0 → 1.5.0
- `docs/architecture.md` version 1.4.0 → 1.5.0, file tree updated with 9 new scripts, script tables updated, file count 171 → 180

## [1.4.0] - 2026-02-11

### Added
- **3 new specialist agents** — Email Specialist, CRO Specialist, and Social Media Manager, bringing the total from 10 to 13 agents
  - `agents/email-specialist.md` — deliverability engineering, automation architecture, lifecycle sequences, A/B testing, list hygiene, CAN-SPAM/GDPR/CASL compliance
  - `agents/cro-specialist.md` — landing page optimization, A/B testing methodology, form optimization, pricing psychology, checkout optimization, statistical analysis
  - `agents/social-media-manager.md` — platform-native strategy (8 platforms), content calendars, algorithm optimization, community management, social commerce, UGC curation

### Changed
- **All 13 agents upgraded** from ~30-37 lines to ~100-120 lines each with 5 new functional sections:
  - **Tools & Scripts** — exact CLI commands for calling the plugin's 15 Python scripts with arguments and usage context
  - **MCP Integrations** — which of the 12 MCP servers each agent should query (all marked optional)
  - **Brand Data & Campaign Memory** — which persistent files to load from `~/.claude-marketing/brands/{slug}/`
  - **Reference Files** — which context-engine reference files to consult for each domain
  - **Cross-Agent Collaboration** — specific handoff recommendations between agents
- 8 agents gained **guideline enforcement behavior rules** (marketing-strategist, seo-specialist, media-buyer, analytics-analyst, competitive-intel, pr-outreach, growth-engineer, influencer-manager) — all 13 agents now enforce brand guidelines
- All 13 agents now reference `campaign-tracker.py` for campaign memory and `guidelines-manager.py` for brand guideline loading
- `brand-guardian.md` gained rule 11 (campaign memory pattern analysis) and expanded tool integration (6 scripts)
- `content-creator.md` gained rule 10 (campaign memory) and expanded tool integration (9 scripts)
- `.claude-plugin/plugin.json` version bumped from 1.3.0 to 1.4.0
- `README.md` updated agent count references (10 → 13), version badge
- `docs/getting-started.md` updated agent count references and version
- `docs/architecture.md` updated to v1.4.0 — agent roster expanded, agent definition structure updated with 5 new sections, file counts updated

## [1.3.0] - 2026-02-11

### Added
- **Brand Guidelines System** — persistent per-brand guidelines that go beyond numeric voice scores to capture detailed rules, restrictions, and styles
  - 5 built-in guideline categories: voice & tone, messaging, restrictions, channel styles, visual identity — plus custom guidelines
  - `_manifest.json` index with rule counts, metadata, and category tracking
  - Channel styles override base voice settings per platform (LinkedIn can be formal while Instagram is casual)
  - Automatic enforcement across all 13 modules, 22 commands, and content review
- **Deliverable Templates** — custom output formats for reports, proposals, briefs, and other deliverables
  - Per-brand template storage at `~/.claude-marketing/brands/{slug}/templates/`
  - Commands check for matching templates before using default formats
- **Agency SOPs** — workflow definitions that apply across all clients
  - Stored at `~/.claude-marketing/sops/` (agency-level, not per-brand)
  - Content approval workflows, campaign checklists, escalation procedures, QA processes
- **Guideline Violation Tracking** — `campaign-tracker.py` now tracks guideline violations with severity, category, and suggestions for pattern analysis
- `scripts/guidelines-manager.py` — new CLI script for guidelines, templates, and SOP CRUD operations (stdlib-only, no new dependencies)
- `skills/context-engine/guidelines-framework.md` — reference file for structuring and applying brand guidelines
- `/dm:import-guidelines` command — interactive import of brand guidelines, restrictions, and channel styles
- `/dm:import-sop` command — import agency SOPs and workflow definitions
- `/dm:import-template` command — import deliverable templates for custom output formats
- `docs/brand-guidelines.md` — comprehensive guide for guidelines, templates, and SOPs with worked examples
- Brand Context point 9 in all 13 module SKILL.md files — automatic guideline checking and enforcement
- Guidelines summary line in SessionStart brand output (rule counts, restriction counts, template counts)

### Changed
- All 22 command SKILL.md files: step 1 extended to load guidelines, templates, and SOPs alongside brand profile
- `hooks/hooks.json` SessionStart: now also runs `guidelines-manager.py --action summary` for guideline context
- `hooks/hooks.json` PreToolUse: now checks `restrictions.md` for banned words and restricted claims in content
- `hooks/hooks.json` SessionEnd: now logs guideline violations via `campaign-tracker.py --action save-violation`
- `agents/brand-guardian.md`: added rules 9-10 for guideline restriction checking and SOP compliance verification
- `agents/content-creator.md`: added rule 9 for applying guidelines, messaging framework, and channel styles before writing
- `scripts/setup.py`: `init_memory_dirs()` now creates `sops/` directory; `create_brand()` now creates `guidelines/` and `templates/` subdirectories; `print_brand_summary()` now outputs guidelines summary line
- `scripts/campaign-tracker.py`: added `save-violation` and `get-violations` actions with severity/category filtering
- `docs/getting-started.md`: added section 5 "Importing Your Brand Guidelines" with walkthrough, updated section numbers, added guidelines to Next Steps
- `README.md`: added 3 new commands to Commands table, updated Key Differentiators, updated architecture tree, added Documentation table entry
- `.claude-plugin/plugin.json` version bumped from 1.2.1 to 1.3.0

## [1.2.1] - 2026-02-11

### Added
- Claude Cowork compatibility documentation — full Cowork section in `docs/claude-interfaces.md` with installation instructions, bonus capabilities (document creation, visual review, app integration), setup guide, and comparison with Anthropic's official marketing plugin
- Cowork installation option (Option C) in `README.md` and `docs/getting-started.md`
- Cowork badge in `README.md`
- Plugin Marketplace section in `docs/claude-interfaces.md`

### Changed
- `docs/claude-interfaces.md` rewritten — expanded from 234 to ~350 lines, added Cowork (full support) section, updated Feature Comparison table with 4 columns (Code, Cowork, Desktop, Web), added document creation and visual review rows
- `README.md` title updated: "Claude Code Plugin" → "Claude Code & Cowork Plugin"
- `README.md` "Which Claude Interface?" table updated with Cowork column
- `docs/getting-started.md` prerequisites and installation updated for Cowork, Next Steps links to Cowork guide
- `plugin.json` version bumped from 1.2.0 to 1.2.1

## [1.2.0] - 2026-02-11

### Added
- Rich brand context injection at session start — Claude receives full brand summary (voice, industry, compliance, goals, competitors) automatically
- `print_brand_summary()` function in `setup.py` with `--summary` CLI flag — outputs 15-line brand context
- `## Brand Context (Auto-Applied)` section in all 13 module SKILL.md files — references context-engine reference files
- Explicit brand loading path (`_active-brand.json` → `profile.json`) in all 17 command SKILL.md files
- SessionEnd hook auto-saves marketing insights via `campaign-tracker.py`
- "How It Works" section in README.md (session lifecycle, brand context flow, multi-client workflow)
- Comprehensive documentation suite (`docs/` folder with 10 guides)
- LICENSE file (MIT)
- CHANGELOG.md
- CONTRIBUTING.md

### Fixed
- `brand-voice-scorer.py` graceful fallback — returns structured JSON and `exit(0)` instead of crashing when NLTK is missing
- `content-scorer.py` graceful fallback — same pattern for missing NLTK and textstat dependencies
- SessionStart hook now uses `--summary` flag (was `--check-brand` which only output the brand name)

### Changed
- `hooks.json` SessionStart command: `--check-brand` replaced with `--summary` for rich context injection
- `hooks.json` SessionEnd prompt: simple reminder replaced with auto-save insights workflow
- `setup.py` no-args fallback: calls `print_brand_summary()` instead of `check_brand()`
- `plugin.json` version bumped from 1.1.0 to 1.2.0

## [1.1.0] - 2026-02-10

### Added
- `campaign-tracker.py` — persistent campaign memory with save/retrieve for campaigns, performance snapshots, and insights (200-entry rolling buffer)
- `adaptive-scorer.py` — brand-context-aware content scoring with industry, business model, and goal-based weight adjustments
- `intelligence-layer.md` — documentation of the adaptive learning system architecture
- `/dm:switch-brand` command for multi-client brand switching
- Quick setup mode in `/dm:brand-setup` (5 essential questions vs. 17 full questions)
- 12 MCP server integrations (GA4, Google Search Console, Google Ads, Meta, HubSpot, Mailchimp, LinkedIn, SEMrush, Ahrefs, Stripe, Google Sheets, Slack)
- Threads and Bluesky platform support in `social-post-formatter.py`
- Cross-platform SessionStart hook (works on Windows, macOS, Linux)

### Fixed
- Schema alignment: `brand-voice-scorer.py` `normalize_profile()` now correctly converts setup.py integer scale (1-10) to float scale (0.0-1.0)
- `requirements.txt` stripped from 16 packages (~600 MB) to 4 core packages (~15 MB)
- TikTok character limit updated to 4,000 characters
- PreToolUse hook SKIP logic improved — no longer interferes with non-marketing file edits

### Changed
- `plugin.json` version bumped from 1.0.0 to 1.1.0
- SessionEnd hook uses natural language prompt instead of rigid format
- `requirements.txt` reorganized into core and optional dependencies

## [1.0.0] - 2026-02-09

### Added
- Initial release
- 13 marketing modules: Content Engine, Campaign Orchestrator, Paid Advertising, Analytics & Insights, AEO/GEO Intelligence, Audience Intelligence, CRO, Digital PR, Funnel Architect, Growth Engineering, Influencer & Creator, Reputation Management, Emerging Channels
- 19 slash commands (`/dm:campaign-plan`, `/dm:ad-creative`, `/dm:seo-audit`, etc.)
- 10 specialist agents (Marketing Strategist, Content Creator, SEO Specialist, Analytics Analyst, Brand Guardian, Media Buyer, Growth Engineer, Influencer Manager, Competitive Intel, PR Outreach)
- 14 Python execution scripts (setup, scoring, formatting, analysis, generation)
- Context engine with 5 reference files: industry profiles (22 industries), compliance rules (16 jurisdictions), platform specs (20+ platforms), scoring rubrics (7 frameworks), intelligence layer
- 86 reference knowledge files across all modules
- Brand profiling system with persistent storage at `~/.claude-marketing/`
- SessionStart, PreToolUse, and SessionEnd hooks
- `.mcp.json` configuration template for 12 marketing platforms
