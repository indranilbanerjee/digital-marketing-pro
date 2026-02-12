# Changelog

All notable changes to the Digital Marketing Pro plugin are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This project uses [Semantic Versioning](https://semver.org/).

## [2.0.0] - 2026-02-12

### Added — Execution Layer
- **26 new slash commands** bringing the total from 42 to 68 — adding a complete execution layer:
  - **Publishing (5)**: `/dm:publish-blog`, `/dm:send-email-campaign`, `/dm:launch-ad-campaign`, `/dm:schedule-social`, `/dm:send-report`
  - **CRM & Data (5)**: `/dm:crm-sync`, `/dm:lead-import`, `/dm:pipeline-update`, `/dm:segment-audience`, `/dm:data-export`
  - **Monitoring (4)**: `/dm:performance-check`, `/dm:campaign-status`, `/dm:anomaly-scan`, `/dm:budget-tracker`
  - **Memory & Knowledge (3)**: `/dm:save-knowledge`, `/dm:search-knowledge`, `/dm:sync-memory`
  - **Communication (2)**: `/dm:send-sms`, `/dm:send-notification`
  - **Agency Operations (4)**: `/dm:agency-dashboard`, `/dm:client-report`, `/dm:sop-library`, `/dm:credential-switch`
  - **Brand Team (3)**: `/dm:team-assign`, `/dm:region-config`, `/dm:exec-summary`
- **5 new specialist agents** bringing the total from 13 to 18:
  - `execution-coordinator` — bridges planning and execution with approval workflow
  - `performance-monitor-agent` — live data monitoring, anomaly detection, campaign health
  - `crm-manager` — cross-CRM operations (Salesforce/HubSpot/Zoho/Pipedrive)
  - `memory-manager` — persistent brand knowledge via RAG, knowledge graphs, cross-session memory
  - `agency-operations` — multi-client portfolio management, SOPs, credential profiles, team management
- **8 new Python scripts** bringing the total from 34 to 42:
  - `approval-manager.py` — approval lifecycle (draft → pending → approved → executed)
  - `execution-tracker.py` — audit trail for all platform executions
  - `performance-monitor.py` — metrics aggregation, anomaly detection, baseline management
  - `memory-manager.py` — vector DB/RAG interface, knowledge graph prep, sync orchestration
  - `crm-sync.py` — CRM data preparation, field mapping, deduplication
  - `report-generator.py` — formatted reports for Slack, email, Google Sheets
  - `credential-manager.py` — per-brand credential profiles for agency multi-client management
  - `team-manager.py` — team roles, permissions, approval chains, capacity management
- **7 new reference knowledge files** bringing the total from 117 to 124:
  - `execution-workflows.md` — standard operating procedures for every execution type
  - `approval-framework.md` — risk classification, approval rules, rollback procedures
  - `platform-publishing-specs.md` — platform API requirements and content format specs
  - `memory-architecture.md` — 5-layer persistent memory system design
  - `crm-integration-guide.md` — CRM connection patterns, field mapping, deduplication
  - `agency-operations-guide.md` — multi-client management, portfolio scoring, SOPs, credential isolation
  - `team-roles-framework.md` — role definitions, permission matrix, approval chains, capacity planning
- **28 new MCP server integrations** bringing the total from 18 to 46: Twitter/X, Instagram, LinkedIn Publishing, TikTok Content, YouTube, Pinterest, SendGrid, Klaviyo, Customer.io, Brevo, Mailgun, Zoho CRM, Pipedrive, Mixpanel, Amplitude, BigQuery, Pinecone, Qdrant, Supermemory, Graphiti, Notion, Google Drive, Webflow, Twilio, Intercom, Linear, Optimizely, Supabase
- **Execution safety hook**: New PreToolUse hook with `mcp_.*` matcher that intercepts all MCP write operations — verifies user approval, compliance, budget limits, and consent before allowing any external platform action
- **Human-in-the-loop approval workflow**: Every execution action classified by risk level (low/medium/high/critical) with industry-specific compliance gates and rollback procedures
- **5-layer memory architecture**: Session context → Vector DB RAG (Pinecone/Qdrant) → Temporal knowledge graphs (Graphiti) → Universal agent memory (Supermemory) → Knowledge base (Notion/Google Drive)
- **Agency multi-client operations**: Per-client credential profiles, portfolio health dashboards, SOP library with compliance tracking, team role management with capacity planning
- **Brand team management**: Team roles and permissions, cross-team workflows, regional/market configuration, executive reporting

### Changed
- `plugin.json` updated to v2.0.0 with execution layer description and updated counts
- `.mcp.json` expanded from 18 to 46 server configurations
- `hooks/hooks.json` extended with MCP write safety interceptor
- All documentation updated with v2.0.0 counts and new sections

## [1.9.0] - 2026-02-12

### Added
- **8 new slash commands** bringing the total from 34 to 42 — closing the agency operations gap:
  - `/dm:client-onboarding` (`skills/client-onboarding/SKILL.md`) — post-sale onboarding workflow with kickoff meeting agenda, discovery questionnaire, stakeholder mapping, access checklist, 30-60-90 day expectations setting
  - `/dm:qbr-plan` (`skills/qbr-plan/SKILL.md`) — Quarterly Business Review preparation with performance retrospective, strategic recommendations, upsell opportunities, next quarter roadmap
  - `/dm:media-plan` (`skills/media-plan/SKILL.md`) — holistic paid media planning across channels with flight dates, budget waves, creative rotation, channel allocation, contingency reserves
  - `/dm:video-script` (`skills/video-script/SKILL.md`) — video marketing script writing for YouTube, TikTok, Instagram Reels, LinkedIn with hook variants, timestamps, visual direction, accessibility
  - `/dm:executive-dashboard` (`skills/executive-dashboard/SKILL.md`) — C-suite dashboard design with business-outcome north-star metrics, visualization recommendations, alert thresholds, narrative guidance
  - `/dm:case-study-plan` (`skills/case-study-plan/SKILL.md`) — structured case study creation workflow with CSR framework, interview questions, format variations (PDF/web/slide/video), distribution strategy
  - `/dm:attribution-model` (`skills/attribution-model/SKILL.md`) — multi-touch attribution setup with model selection (last-touch/first-touch/linear/time-decay/position-based/data-driven/MMM), credit distribution rules, platform implementation guides
  - `/dm:creative-testing-framework` (`skills/creative-testing-framework/SKILL.md`) — systematic creative testing strategy with testing matrix, holdout controls, sample size per variant, significance thresholds, iteration cadence
- **2 new reference knowledge files** bringing the total from 115 to 117:
  - `skills/paid-advertising/media-planning.md` — media planning framework, channel allocation methodology, flighting strategies (continuous/pulsing/fighting), budget waves, creative rotation cadence, cross-channel synergy
  - `skills/content-engine/video-scripting.md` — platform-specific video formats (YouTube/TikTok/Reels/Shorts/LinkedIn), script structures (AIDA/PAS), 12 hook formulas, timestamp annotation, visual direction, accessibility, CTA placement

### Fixed
- `scripts/setup.py` `create_brand()` function now initializes `insights.json` file when creating new brands — previously this file was referenced by all 13 agents and context-engine but not auto-created, causing errors on first insight save

### Removed
- `.mcp_new.json` — empty orphan file from development
- `mcp_config.json` — legacy 12-server MCP config (replaced by `.mcp.json` in v1.8.0)

### Changed
- `.claude-plugin/plugin.json` version bumped from 1.8.0 to 1.9.0, command count 34 → 42, reference files 115 → 117
- `README.md` updated: version badge 1.8.0 → 1.9.0, command count 34 → 42, reference files 115 → 117, 8 new command rows in commands table, architecture tree updated
- `docs/getting-started.md` version 1.8.0 → 1.9.0, command count and reference file counts updated
- `docs/architecture.md` version 1.8.0 → 1.9.0, file tree updated, file count 233 → 243, command list updated with 8 new entries

## [1.8.0] - 2026-02-12

### Added
- **Marketing Automation module** (`skills/marketing-automation/`) — new dedicated module covering automation workflow design, lead scoring models, nurture sequences, marketing operations, and MAP platform strategy
  - `skills/marketing-automation/SKILL.md` — module definition with workflow design, lead scoring, nurture sequences, and marketing ops capabilities
  - `skills/marketing-automation/automation-workflows.md` — trigger types, 10+ workflow patterns (welcome, abandoned cart, re-engagement, onboarding, win-back), branching logic, cross-channel orchestration
  - `skills/marketing-automation/lead-scoring.md` — explicit and implicit scoring, negative scoring, score thresholds (cold/warm/MQL/SQL), progressive profiling, decay, sales handoff rules
  - `skills/marketing-automation/nurture-sequences.md` — lifecycle stages, 7 sequence types with cadence and content mapping, multi-channel nurture, timing science, template sequences
  - `skills/marketing-automation/marketing-ops.md` — data hygiene, tech stack management, deliverability (SPF/DKIM/DMARC), compliance automation, MAP comparison matrix (HubSpot/ActiveCampaign/Klaviyo/Mailchimp/Marketo/Pardot)
- **15 new reference knowledge files** across 10 existing modules, bringing reference files from 96 to 115:
  - `skills/paid-advertising/microsoft-ads.md` — Bing Ads, Microsoft Audience Network, LinkedIn profile targeting, Import from Google Ads
  - `skills/paid-advertising/retargeting-audiences.md` — audience segments, platform-specific retargeting, sequential messaging, frequency capping, privacy impact
  - `skills/analytics-insights/dashboard-design.md` — dashboard hierarchy (executive/operational/campaign), visualization best practices, alert thresholds, tool recommendations
  - `skills/analytics-insights/clv-analysis.md` — CLV models (historical/predictive/contractual), CLV:CAC ratio, cohort analysis, industry benchmarks
  - `skills/content-engine/personalization.md` — personalization levels, data requirements, email/website/ad personalization, testing personalization, privacy
  - `skills/content-engine/case-studies.md` — CSR framework, interview questions, data presentation, format variations, distribution strategy, industry templates
  - `skills/campaign-orchestrator/sales-enablement.md` — battle cards, sales content mapping to stages, objection handling, proposal templates, content metrics
  - `skills/growth-engineering/experimentation-frameworks.md` — ICE/RICE/PIE scoring, hypothesis format, experiment types, growth experiment categories, velocity
  - `skills/digital-pr/link-building-tactics.md` — 13 link building methods ranked, outreach templates, anchor text strategy, red flags, competitive gap analysis
  - `skills/cro/personalization-testing.md` — segment-based testing, behavioral targeting, dynamic content, holdout testing, testing roadmap
  - `skills/audience-intelligence/customer-research-methods.md` — quantitative and qualitative methods, survey design, JTBD research, win/loss analysis, VoC programs
  - `skills/funnel-architect/sales-marketing-alignment.md` — shared funnel definitions, SLAs, lead handoff, feedback loops, RevOps, shared metrics
  - `skills/reputation-management/review-management-platforms.md` — review platforms by industry, generation strategies, response framework by rating, monitoring tools, legal considerations
  - `skills/emerging-channels/ai-marketing-tools.md` — AI for content/SEO/ads/email/social/analytics/CRO, prompt engineering for marketers, AI governance, cost-benefit
  - `skills/influencer-creator/micro-influencer-strategy.md` — influencer tiers, micro/nano advantages, discovery, vetting, compensation models, gifting programs, scaling
- **6 new MCP integrations** bringing the total from 12 to 18:
  - `tiktok-ads` — TikTok Ads campaign performance, creative insights, audience analytics, Spark Ads data
  - `shopify` — Shopify eCommerce orders, products, customers, inventory, sales analytics
  - `wordpress` — WordPress content publishing, post management, SEO metadata
  - `salesforce` — Salesforce CRM pipeline, opportunity data, lead management, account insights
  - `google-looker-studio` — Google Looker Studio dashboard data, report embedding, cross-platform visualization
  - `activecampaign` — ActiveCampaign email automation, lead scoring, CRM contacts, automation workflows

### Changed
- `.claude-plugin/plugin.json` version bumped from 1.7.0 to 1.8.0, module count 15 → 16, reference files 96 → 115, MCP integrations 12 → 18
- `.mcp.json` expanded with 6 new server entries
- `README.md` updated: version badge 1.7.0 → 1.8.0, module count 15 → 16, new module row, MCP count 12 → 18, 6 new MCP rows, architecture tree updated
- `docs/getting-started.md` version 1.7.0 → 1.8.0, module count and reference file counts updated
- `docs/architecture.md` version 1.7.0 → 1.8.0, file tree updated, file count 213 → 233, module list updated, MCP server list updated

## [1.7.0] - 2026-02-12

### Added
- **10 new slash commands** bringing the total from 24 to 34:
  - `/dm:keyword-research` (`skills/keyword-research/SKILL.md`) — guided keyword research with clustering, intent mapping, and content gap analysis
  - `/dm:roi-calculator` (`skills/roi-calculator/SKILL.md`) — campaign ROI calculation with 5 attribution models and budget efficiency ranking
  - `/dm:ab-test-plan` (`skills/ab-test-plan/SKILL.md`) — A/B test planning with hypothesis framework, sample size calculation, and test duration estimation
  - `/dm:content-repurpose` (`skills/content-repurpose/SKILL.md`) — content repurposing strategy with derivative format matrix, effort estimates, and publishing calendar
  - `/dm:retargeting-strategy` (`skills/retargeting-strategy/SKILL.md`) — retargeting campaign architecture with audience segmentation, frequency capping, and creative sequencing
  - `/dm:martech-audit` (`skills/martech-audit/SKILL.md`) — marketing technology stack audit across 11 functions with overlap detection and gap analysis
  - `/dm:budget-optimizer` (`skills/budget-optimizer/SKILL.md`) — data-driven budget reallocation with diminishing returns modeling and efficiency ranking
  - `/dm:client-proposal` (`skills/client-proposal/SKILL.md`) — agency client proposal generation with situation analysis, strategy, scope, timeline, and pricing
  - `/dm:review-response` (`skills/review-response/SKILL.md`) — brand-aligned review response drafting with tone templates, escalation detection, and multi-variant output
  - `/dm:webinar-plan` (`skills/webinar-plan/SKILL.md`) — end-to-end webinar planning with promotion timeline, email sequences, and post-event nurture strategy
- **8 new Python scripts** (all zero-dependency, stdlib-only), bringing the total from 26 to 34:
  - `scripts/roi-calculator.py` — campaign ROI with 5 attribution models (last_touch, first_touch, linear, time_decay, position_based), LTV:CAC ratio, budget efficiency ranking
  - `scripts/budget-optimizer.py` — budget reallocation using diminishing returns model (square-root scaling), efficiency-proportional allocation, minimum spend thresholds
  - `scripts/clv-calculator.py` — customer lifetime value with 3 models (simple, contractual, cohort), LTV:CAC health assessment, segment-weighted analysis
  - `scripts/content-repurposer.py` — 9 source content types mapping to 4-8 derivative formats, auto-generated content calendar, ROI multiplier calculation
  - `scripts/review-response-drafter.py` — 5-tier rating response logic, 4 tone modifiers, escalation detection (health/safety, legal, profanity), 3 response variants per review
  - `scripts/ad-budget-pacer.py` — spend pacing with linear projection, trend analysis (7-day moving average, weekend patterns), per-channel pacing, severity classification
  - `scripts/link-profile-analyzer.py` — domain diversity, authority bucketing (5 DA ranges), follow/nofollow ratio, anchor text classification (6 categories), profile health score 0-100
  - `scripts/revenue-forecaster.py` — linear regression + growth rate models, blended forecast, seasonal multipliers, confidence ranges (±15% widening by 3% per month)

### Changed
- **5 agent files updated** with new script references in "Tools & Scripts" section:
  - `agents/analytics-analyst.md` — added roi-calculator.py, clv-calculator.py, budget-optimizer.py, revenue-forecaster.py, ad-budget-pacer.py
  - `agents/media-buyer.md` — added ad-budget-pacer.py, budget-optimizer.py
  - `agents/content-creator.md` — added content-repurposer.py, review-response-drafter.py
  - `agents/marketing-strategist.md` — added roi-calculator.py, budget-optimizer.py, revenue-forecaster.py
  - `agents/seo-specialist.md` — added link-profile-analyzer.py
- `.claude-plugin/plugin.json` version bumped from 1.6.0 to 1.7.0, command count 24 → 34, script count 26 → 34
- `README.md` updated: version badge 1.6.0 → 1.7.0, command count 24 → 34, script count 26 → 34, 10 new command rows in commands table, architecture tree updated
- `docs/getting-started.md` version 1.6.0 → 1.7.0, command count and script count updated
- `docs/architecture.md` version 1.6.0 → 1.7.0, file tree updated with new scripts, file count 195 → 213, command list updated, agent roster updated, dependency tier table updated

## [1.6.0] - 2026-02-12

### Added
- **Technical SEO module** (`skills/technical-seo/`) — new dedicated module covering Core Web Vitals optimization, crawlability audits, site architecture, indexation management, JavaScript SEO, mobile-first indexing, redirect auditing, structured data, and international technical SEO
  - `skills/technical-seo/SKILL.md` — module definition with 12-step audit process
  - `skills/technical-seo/core-web-vitals.md` — LCP, INP, CLS thresholds, causes, fixes, measurement tools, optimization priority framework
  - `skills/technical-seo/crawlability.md` — robots.txt, XML sitemaps, crawl budget, JavaScript rendering, log file analysis, orphan pages
  - `skills/technical-seo/site-architecture.md` — URL structure, internal linking, pagination, faceted navigation, breadcrumbs, site migration planning
  - `skills/technical-seo/indexation.md` — canonical tags, meta robots, index coverage, duplicate content, index bloat, new content indexation
  - `skills/technical-seo/international-seo.md` — hreflang implementation, ccTLD vs subdomain vs subdirectory, geotargeting, localization vs translation, search engine market share by country
- **Local SEO module** (`skills/local-seo/`) — new dedicated module covering Google Business Profile optimization, NAP consistency, citation management, local pack strategy, location pages, multi-location management, and local schema
  - `skills/local-seo/SKILL.md` — module definition with 10-step local SEO audit process
  - `skills/local-seo/gbp-optimization.md` — GBP completeness checklist, categories, attributes, photos, posts, Q&A, insights, suspension prevention
  - `skills/local-seo/citation-management.md` — NAP consistency, citation sources by industry, data aggregators, audit methodology, multi-location citations
  - `skills/local-seo/local-content.md` — local keyword research, location pages, city pages, "near me" optimization, voice search, seasonal content
  - `skills/local-seo/multi-location.md` — multi-location GBP management, store locators, franchise SEO, location opening/closing checklists, hierarchy
- **2 new slash commands**:
  - `/dm:tech-seo-audit` (`skills/tech-seo-audit/SKILL.md`) — comprehensive technical SEO audit with Core Web Vitals scorecard, crawlability, indexation, site architecture, security, and prioritized fixes
  - `/dm:local-seo-audit` (`skills/local-seo-audit/SKILL.md`) — local SEO audit with GBP scorecard, NAP consistency report, citation audit, review analysis, and 90-day action plan
- **2 new Python scripts** (both zero-dependency, stdlib-only):
  - `scripts/tech-seo-auditor.py` — URL-level technical SEO checks using `urllib.request`: HTTP status codes, redirect chain detection, meta tag parsing (title, description, canonical, viewport, robots), security headers (HTTPS, HSTS), TTFB measurement, compression detection, scoring (0-100)
  - `scripts/local-seo-checker.py` — NAP consistency analysis with address normalization (18 abbreviation expansions) and GBP profile completeness scoring across 16 weighted fields with industry-specific recommendations

### Changed
- `agents/seo-specialist.md` — added tech-seo-auditor.py and local-seo-checker.py to Tools & Scripts section; added 9 new reference files (5 technical-seo + 4 local-seo) to Reference Files section
- `.claude-plugin/plugin.json` version bumped from 1.5.0 to 1.6.0, module count 13 → 15, script count 24 → 26
- `README.md` updated: version badge 1.5.0 → 1.6.0, module count 13 → 15, command count 22 → 24, script count 24 → 26, reference file count 87 → 96, 2 new module rows in core modules table, 2 new command rows in commands table, architecture tree updated
- `docs/getting-started.md` version 1.5.0 → 1.6.0, module count and command count updated
- `docs/architecture.md` version 1.5.0 → 1.6.0, file tree updated with new modules/commands/scripts, file count 180 → 195, module list and command list updated, agent roster updated, dependency tier table updated

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
