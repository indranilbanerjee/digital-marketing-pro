# Getting Started with Digital Marketing Pro

**Version 2.0.0** | A plugin for Claude Code and Claude Cowork

Digital Marketing Pro transforms Claude into a marketing command center that knows your brand, understands your industry, and produces strategy and content that sounds like you wrote it. This guide walks you through installation, brand setup, and your first marketing task.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [First Run --- What Happens](#3-first-run--what-happens)
4. [Your First Brand Profile](#4-your-first-brand-profile)
5. [Importing Your Brand Guidelines (Optional)](#5-importing-your-brand-guidelines-optional)
6. [Your First Marketing Task](#6-your-first-marketing-task)
7. [Understanding the Session Lifecycle](#7-understanding-the-session-lifecycle)
8. [Python Dependencies (Optional)](#8-python-dependencies-optional)
9. [Available Commands](#9-available-commands)
10. [Next Steps](#10-next-steps)

---

## 1. Prerequisites

You need exactly one thing to get started:

- **Claude Code** installed and working on your machine (macOS, Windows, or Linux), **or**
- **Claude Cowork** (part of Claude Desktop on macOS and Windows --- requires Claude Pro, Max, Team, or Enterprise)

That is it. Everything else is optional.

**Optional but nice to have:**

- **Python 3.8 or newer** --- unlocks advanced scoring features like brand voice analysis and content readability. The plugin works perfectly without Python; you just get bonus capabilities if it is installed.
- **No API keys required** --- the plugin ships with 124 reference knowledge files that power all 16 marketing modules. The optional MCP integrations (46 platform connections including Google Analytics, Search Console, Meta Ads, CRMs, email platforms, and others) use your own account credentials and can be configured later.

> **Bottom line:** If you can run Claude Code or Claude Cowork, you can use this plugin right now.

---

## 2. Installation

You have three options depending on which Claude interface you use.

### Option A: Install in Claude Code (from a local directory)

If you have the plugin files on your machine (downloaded or cloned):

```
claude plugin add /path/to/digital-marketing-pro
```

On Windows, that might look like:

```
claude plugin add "C:\Users\yourname\Downloads\digital-marketing-pro"
```

### Option B: Install in Claude Code (from the plugin registry)

If the plugin has been published to the Claude plugin registry:

```
claude plugin add digital-marketing-pro
```

### Option C: Install in Claude Cowork

If you use Claude Cowork (the agentic mode in Claude Desktop):

1. Compress the `digital-marketing-pro/` folder into a ZIP file
2. Open Cowork in Claude Desktop
3. Click **Plugin** in the left sidebar
4. Click **+** then **Upload**
5. Select your ZIP file

Or browse the [Claude plugin marketplace](https://claude.com/plugins) directly from Cowork: click **Plugin** → **+** → **Browse plugins** → search for "Digital Marketing Pro."

> **Cowork note:** After installing, Cowork will ask for permission to access `~/.claude-marketing/` when it first tries to read or write brand data. Grant this permission --- it is where your brand profiles and campaign history are stored.

For full details on Cowork capabilities (document creation, visual review, app integration), see the [Claude Interfaces Guide](claude-interfaces.md#claude-cowork-full-support).

### What successful installation looks like

After running either command, you should see output similar to this:

```
Installing plugin: digital-marketing-pro v2.0.0
  - 16 marketing modules loaded
  - 68 slash commands registered (/dm:*)
  - 18 specialist agents available
  - 46 MCP integrations configured
  - 3 event hooks configured (SessionStart, PreToolUse, SessionEnd)

Plugin "digital-marketing-pro" installed successfully.
Run /dm:brand-setup to create your first brand profile.
```

If you see an error instead, verify that your Claude Code installation is up to date and that the path to the plugin directory is correct.

---

## 3. First Run --- What Happens

The moment you start a new session in Claude Code or Cowork after installing the plugin, a few things happen automatically behind the scenes. You do not need to do anything --- this is just so you understand what is going on.

### The startup sequence

1. **SessionStart hook fires** --- the plugin's event system detects that a new session has begun.

2. **The setup script runs** --- it checks for dependencies and looks for your active brand profile (`setup.py --check-deps --summary`).

3. **You see a status banner** --- the output depends on whether you have a brand profile set up yet.

### If you have not set up a brand yet

You will see this:

```
=== DIGITAL MARKETING PRO ===
No active brand. Run /dm:brand-setup to create one.
===
```

This is your cue to create your first brand profile (covered in the next section).

### If you already have an active brand

You will see a 15-line brand summary that looks something like this:

```
=== DIGITAL MARKETING PRO ===
Brand: Greenfield Coffee Roasters (greenfield-coffee-roasters)
Industry: Food & Beverage (regulated: no)
Model: B2C_DTC | Revenue: transactional
Voice: Formality 4/10 | Energy 7/10 | Humor 4/10 | Authority 6/10
Traits: warm, knowledgeable, passionate
Channels: email (primary), instagram
Markets: US | Compliance: FTC, CAN-SPAM
Goals: Grow subscriber list by 40% in Q2
Competitors: Blue Bottle, Counter Culture, Stumptown
Active campaigns: 2 | Tracked insights: 14
Python: lite (nltk, textstat)
MCP: Google Analytics, Mailchimp connected
===
```

This summary is not just for you to read --- it is injected directly into the session context so that every marketing response from that point forward is grounded in your brand's voice, industry, compliance requirements, and strategic goals.

---

## 4. Your First Brand Profile

Let us walk through setting up a brand from scratch. For this example, we will create a profile for **Greenfield Coffee Roasters**, a direct-to-consumer specialty coffee brand.

### Starting brand setup

Type the following in your Claude Code or Cowork session:

```
/dm:brand-setup
```

The plugin will walk you through an interactive profiling conversation. By default, it uses **Quick Setup** mode, which asks just 5 essential questions.

### Quick Setup walkthrough

Here is what the conversation looks like:

```
You: /dm:brand-setup

Plugin: I'll help you set up your brand profile. Let's start with the essentials.

         Quick Setup (5 questions)
         -------------------------

         1. What's your brand or business name?
You:     Greenfield Coffee Roasters

         2. In one sentence, what does Greenfield Coffee Roasters do?
You:     We roast and sell single-origin specialty coffee direct to consumers online

         3. Who is your primary customer?
You:     Coffee enthusiasts aged 25-45 who care about sourcing and sustainability

         4. Pick 3 words that describe how your brand communicates:
You:     Warm, knowledgeable, passionate

         5. Where do you primarily market? (social media, email, SEO, paid ads, etc.)
You:     Email and Instagram
```

### What happens behind the scenes

From those 5 answers, the plugin intelligently builds a complete brand profile:

- **Industry** detected as Food & Beverage based on your description
- **Business model** identified as B2C DTC (direct to consumer, transactional revenue)
- **Compliance rules** loaded for FTC endorsement guidelines and CAN-SPAM (email marketing)
- **Voice dimensions** mapped from your 3 words:
  - "Warm" translates to Formality 4/10, Humor 4/10
  - "Knowledgeable" translates to Authority 6/10
  - "Passionate" translates to Energy 7/10
- **Channel specs** loaded for email (subject line limits, preview text guidelines) and Instagram (caption lengths, hashtag best practices)
- **Sensible defaults** set for everything else (you can refine later)

### The confirmation

After processing, you see your brand summary:

```
Brand profile created!

Brand: Greenfield Coffee Roasters (greenfield-coffee-roasters)
Industry: Food & Beverage (regulated: no)
Model: B2C_DTC | Revenue: transactional
Voice: Formality 4/10 | Energy 7/10 | Humor 4/10 | Authority 6/10
Traits: warm, knowledgeable, passionate
Channels: email (primary), instagram
Markets: US | Compliance: FTC, CAN-SPAM
Saved to: ~/.claude-marketing/brands/greenfield-coffee-roasters/profile.json

Quick profile created! You can refine it anytime with /dm:brand-setup --full
```

### Where your profile lives

Your brand data is stored locally on your machine at:

```
~/.claude-marketing/brands/greenfield-coffee-roasters/profile.json
```

This is a persistent location outside the plugin directory, so your brand profiles survive plugin updates.

### Want more detail? Use Full Setup

The Quick Setup is great for getting started fast, but if you want a more thorough profile, run:

```
/dm:brand-setup --full
```

Full Setup asks 17 questions across 6 categories:

| Category             | Questions | What it captures                                        |
|----------------------|-----------|---------------------------------------------------------|
| Brand Identity       | 4         | Name, elevator pitch, USP, mission and values           |
| Business Model       | 3         | Business type, revenue model, price range, sales cycle  |
| Industry & Compliance| 3         | Industry, regulated status, target markets              |
| Brand Voice          | 4         | Voice dimensions (1-10 scales), personality traits, this-not-that examples, sample content |
| Channels & Goals     | 2         | Active channels, primary goal, KPIs, budget, team size  |
| Competitors          | 1         | 3-5 competitors with strengths and weaknesses           |

You can also run Full Setup later to fill in sections you skipped. It will preserve your existing answers and only ask about what is missing.

---

## 5. Importing Your Brand Guidelines (Optional)

If your brand has a style guide, messaging framework, restriction list, or channel-specific rules, you can import them now. Guidelines go beyond the numeric voice scores in your brand profile — they capture the detailed rules that make content authentically on-brand.

```
/dm:import-guidelines
```

You can paste content from existing documents or describe rules conversationally:

```
You: Here's our brand voice guide: We're friendly but professional.
     Never use jargon. Always explain technical concepts simply.
     Sentences should be under 20 words.
```

The plugin extracts the rules, structures them into the right category, and saves them. They are then enforced automatically when creating content.

**What you can import:**
- **Voice & tone rules** — writing style, dos/don'ts, readability rules
- **Restrictions** — banned words, restricted claims, mandatory disclaimers
- **Channel styles** — per-channel tone and format rules (LinkedIn vs. Instagram vs. email)
- **Messaging frameworks** — approved key messages, taglines, positioning
- **Deliverable templates** — custom formats for reports, proposals, briefs (`/dm:import-template`)
- **Agency SOPs** — approval workflows, launch checklists, escalation procedures (`/dm:import-sop`)

Guidelines persist across sessions — import once, enforced every time. You can always add more later.

> See `docs/brand-guidelines.md` for the full guide with worked examples and all guideline categories.

---

## 6. Your First Marketing Task

Now that your brand profile is set up, try asking for some real marketing deliverables. You do not need to use any special commands --- just describe what you need in plain language.

### Example: Writing a welcome email sequence

```
You: Write a 3-email welcome sequence for new subscribers
```

Here is what happens behind the scenes when you make this request:

1. **Content Engine activates** --- the plugin recognizes this as an email marketing task
2. **Brand voice loads** --- your "warm, knowledgeable, passionate" voice profile shapes every word
3. **Compliance rules applied** --- CAN-SPAM requirements (unsubscribe link, physical address) are factored in
4. **Platform specs loaded** --- email best practices are applied (subject line under 40 characters for mobile, preview text 40-90 characters)

### What you receive

The plugin delivers a complete 3-email sequence, each with:

- **Subject line** (optimized for mobile preview length)
- **Preview text** (the snippet visible in inbox before opening)
- **Body copy** (written in your brand voice, structured for scannability)
- **Call to action** (clear, single CTA per email)

For Greenfield Coffee Roasters, the sequence would follow this arc:

| Email | Timing      | Theme                          | Voice emphasis  |
|-------|-------------|--------------------------------|-----------------|
| 1     | Immediate   | Welcome + brand story          | Warm            |
| 2     | Day 3       | Brewing guide + product rec    | Knowledgeable   |
| 3     | Day 7       | First purchase offer           | Passionate      |

- **Email 1** tells the Greenfield origin story, emphasizing sustainable sourcing and the people behind the beans. Tone is welcoming, like a friend inviting you into their world.
- **Email 2** shares a practical brewing guide (pour-over, French press, or AeroPress) and recommends a specific single-origin coffee to try. Tone is authoritative but approachable, sharing expertise without being preachy.
- **Email 3** extends a first-purchase offer with language that conveys genuine enthusiasm for quality. Tone is energetic and direct, with a clear CTA to shop.

### Other things to try

Here are a few more requests that work well as a first task:

- "Create a content calendar for next month" --- activates the Content Engine with your channels and content pillars
- "Audit my competitor Blue Bottle Coffee" --- activates Competitive Intelligence with industry benchmarks
- "Write Instagram captions for our new Ethiopian single-origin" --- activates Content Engine with Instagram platform specs
- "Build a buyer persona for our ideal customer" --- activates Audience Intelligence with your existing audience data
- "Plan a product launch for our new cold brew line" --- activates Campaign Orchestrator with your channels and budget context

Every response is automatically shaped by your brand profile. You never have to remind the plugin about your voice, audience, or compliance requirements.

---

## 7. Understanding the Session Lifecycle

Digital Marketing Pro operates across three phases in every Claude Code or Cowork session. Understanding this lifecycle helps you get the most out of the plugin.

### Phase 1: Session Start

**What happens:** The SessionStart hook fires and loads your active brand context into the session.

**What this means for you:** From the very first message you type, Claude already knows your brand name, voice settings, industry, compliance requirements, target audience, active channels, competitors, and current goals. You never have to re-explain who you are or what your brand sounds like.

**What you see:** The 15-line brand summary banner printed at the top of your session.

### Phase 2: During Your Session

**What happens:** As you make requests, the appropriate marketing modules activate automatically. Three things are applied to every piece of marketing output:

- **Brand voice** --- content matches your formality, energy, humor, and authority settings
- **Compliance rules** --- outputs respect regulations for your industry and target markets (GDPR, FTC, HIPAA, and others)
- **Industry benchmarks** --- recommendations are calibrated to realistic performance standards for your sector

**The PreToolUse hook:** When the plugin writes content to a file, the PreToolUse hook can check it for brand alignment and compliance before saving. This acts as a guardrail to catch anything that drifts off-brand.

**What you see:** Marketing deliverables that sound like they came from someone who has worked with your brand for months, not minutes.

### Phase 3: Session End

**What happens:** The SessionEnd hook fires and saves key marketing insights from the session to your brand profile. This includes things like:

- New audience insights discovered during persona research
- Competitor intelligence gathered during analysis
- Campaign decisions and strategic direction
- Content performance hypotheses

**What this means for you:** The next time you start a session, those insights are already part of your brand context. The plugin gets smarter about your brand over time, building a growing body of institutional marketing knowledge.

**What you see:** A brief confirmation that insights have been saved.

### The lifecycle in one diagram

```
Session Start              During Session             Session End
     |                          |                          |
     v                          v                          v
Brand context            Modules activate           Insights saved
auto-loaded         Voice + Compliance + Benchmarks    to brand profile
     |               applied to all outputs              |
     v                          |                        v
15-line summary          You work normally         Ready for next
printed                  (just ask for things)        session
```

---

## 8. Python Dependencies (Optional)

Digital Marketing Pro is designed to work at full capability without Python. All 16 marketing modules, 18 specialist agents, and 68 slash commands function using the plugin's built-in reference knowledge. Python adds bonus scoring and automation features.

### Three dependency modes

| Mode               | Install size | What it adds                                                       |
|--------------------|--------------|--------------------------------------------------------------------|
| **Knowledge-only** | 0 MB         | All modules, agents, and commands. No Python needed.               |
| **Lite**           | ~15 MB       | Brand voice scoring, content quality scoring, readability analysis  |
| **Full**           | ~50 MB       | Competitor scraping, QR code generation, AI visibility checking     |

### Knowledge-only (default)

This is what you get out of the box. No setup required.

You have access to:
- All 16 marketing modules with 124 reference knowledge files
- All 68 `/dm:` slash commands
- All 18 specialist agents
- Brand profiling, session hooks, and campaign tracking
- Industry benchmarks, compliance rules, and platform specifications

The plugin will tell you when a Python-dependent feature is unavailable and will gracefully skip it rather than throwing an error.

### Lite mode

If you want brand voice scoring and content readability analysis, install two small packages:

```
pip install nltk textstat
```

This unlocks:
- **Brand voice scoring** --- quantitative alignment score (0-100) measuring how well content matches your voice profile
- **Content quality scoring** --- readability grade level, sentence complexity, and vocabulary analysis
- **Readability analysis** --- Flesch-Kincaid, Gunning Fog, and other standard readability metrics

### Full mode

For the complete feature set, install all dependencies:

```
pip install -r /path/to/digital-marketing-pro/scripts/requirements.txt
```

This adds everything in Lite mode, plus:
- **Competitor scraping** --- automated extraction of competitor page titles, meta descriptions, and content structure
- **QR code generation** --- create QR codes for UTM-tagged URLs (useful for print-to-digital campaigns)
- **AI visibility checking** --- programmatic checks of how your brand appears in AI answer engines (requires OpenAI or Anthropic API key in `.env`)

### How to check your current mode

The brand summary banner shown at session start includes a Python status line:

```
Python: not installed          (knowledge-only mode)
Python: lite (nltk, textstat)  (lite mode)
Python: full (all deps)        (full mode)
```

---

## 9. Available Commands

Digital Marketing Pro provides 68 slash commands, all prefixed with `/dm:`. You can type these directly in your Claude Code session.

### Brand Management

| Command | What it does |
|---------|-------------|
| `/dm:brand-setup` | Create or update a brand profile through interactive guided setup |
| `/dm:switch-brand` | Switch the active brand for multi-client and agency workflows |

### Strategy and Planning

| Command | What it does |
|---------|-------------|
| `/dm:campaign-plan` | Build a multi-channel campaign plan with objectives, targeting, budget, and KPIs |
| `/dm:launch-plan` | Create a product or feature launch playbook across pre-launch, launch day, and post-launch phases |
| `/dm:social-strategy` | Develop a platform-specific social media strategy with content pillars and growth plan |
| `/dm:competitor-analysis` | Run a multi-dimensional competitive analysis covering content, SEO, ads, social, and positioning |
| `/dm:media-plan` | Holistic paid media planning with channel allocation, flight scheduling, and creative rotation |
| `/dm:client-onboarding` | Post-sale client onboarding workflow with kickoff agenda, discovery questionnaire, and 30-60-90 plan |
| `/dm:qbr-plan` | Quarterly Business Review preparation with performance retrospective and strategic recommendations |

### Content Creation

| Command | What it does |
|---------|-------------|
| `/dm:content-brief` | Generate a detailed content brief with keyword targets, outline, and SEO requirements |
| `/dm:content-calendar` | Build a monthly or quarterly content calendar with platform assignments and repurposing workflows |
| `/dm:email-sequence` | Create a complete email sequence with subject lines, body copy, timing, and segmentation |
| `/dm:ad-creative` | Produce platform-specific ad copy variations with quality scoring for Google, Meta, LinkedIn, and TikTok |
| `/dm:video-script` | Video marketing script writing for YouTube, TikTok, Reels, and LinkedIn with hooks and timestamps |
| `/dm:case-study-plan` | Structured case study creation with CSR framework, interview questions, and distribution strategy |

### Analysis and Audits

| Command | What it does |
|---------|-------------|
| `/dm:seo-audit` | Run a comprehensive SEO audit covering technical health, on-page, content, E-E-A-T, and links |
| `/dm:tech-seo-audit` | Technical SEO audit: Core Web Vitals, crawlability, indexation, redirects, site architecture, security |
| `/dm:local-seo-audit` | Local SEO audit: Google Business Profile, NAP consistency, citations, local pack, reviews |
| `/dm:aeo-audit` | Assess how your brand appears in AI-powered search and answer engines (ChatGPT, Perplexity, Google AI Overviews) |
| `/dm:landing-page-audit` | Score a landing page across above-fold clarity, trust signals, form friction, and mobile experience |
| `/dm:funnel-audit` | Analyze your customer funnel for drop-off points, bottlenecks, and optimization opportunities |
| `/dm:performance-report` | Generate a marketing performance report with KPI tracking, trend analysis, and recommendations |

### Outreach and PR

| Command | What it does |
|---------|-------------|
| `/dm:pr-pitch` | Create media pitch packages with templates, target media lists, and outreach strategy |
| `/dm:influencer-brief` | Build an influencer campaign brief with discovery criteria, creator guidelines, and FTC compliance |
| `/dm:crisis-response` | Get rapid crisis assessment with severity scoring, stakeholder messaging, and communication timeline |

### Audience

| Command | What it does |
|---------|-------------|
| `/dm:audience-profile` | Build a detailed buyer persona with demographics, psychographics, behaviors, and content preferences |

### Data & Optimization

| Command | What it does |
|---------|-------------|
| `/dm:keyword-research` | Guided keyword research with clustering, intent mapping, and content gap analysis |
| `/dm:roi-calculator` | Calculate campaign ROI with 5 attribution models and budget efficiency ranking |
| `/dm:ab-test-plan` | Plan A/B tests with hypothesis framework, sample size calculation, and duration estimation |
| `/dm:content-repurpose` | Generate content repurposing strategy with derivative format matrix and publishing calendar |
| `/dm:retargeting-strategy` | Build retargeting campaign architecture with audience segmentation and frequency capping |
| `/dm:martech-audit` | Audit marketing technology stack across 11 functions with overlap detection and gap analysis |
| `/dm:budget-optimizer` | Data-driven budget reallocation with diminishing returns modeling and efficiency ranking |
| `/dm:attribution-model` | Multi-touch attribution setup with model selection and credit distribution rules |
| `/dm:creative-testing-framework` | Systematic creative testing strategy with testing matrix and holdout controls |
| `/dm:executive-dashboard` | C-suite dashboard design with business-outcome metrics and alert thresholds |
| `/dm:client-proposal` | Generate agency client proposal with situation analysis, strategy, scope, and pricing |
| `/dm:review-response` | Draft brand-aligned review responses with tone templates and escalation detection |
| `/dm:webinar-plan` | End-to-end webinar planning with promotion timeline, email sequences, and post-event nurture |

### Execution & Publishing

| Command | What it does |
|---------|-------------|
| `/dm:publish-blog` | Publish blog post to WordPress/Webflow with SEO metadata and scheduling |
| `/dm:send-email-campaign` | Send email campaign via SendGrid/Klaviyo/Brevo with personalization and A/B testing |
| `/dm:launch-ad-campaign` | Create paid ad campaign on Google/Meta/LinkedIn/TikTok with budget safeguards |
| `/dm:schedule-social` | Schedule posts to Twitter/Instagram/LinkedIn/TikTok/YouTube/Pinterest |
| `/dm:send-report` | Generate and deliver performance report via Slack, email, or Sheets |

### CRM & Data

| Command | What it does |
|---------|-------------|
| `/dm:crm-sync` | Sync marketing contacts and deals to Salesforce/HubSpot/Zoho/Pipedrive |
| `/dm:lead-import` | Import leads from forms, CSV, or manual entry into CRM with deduplication |
| `/dm:pipeline-update` | Update deal stages, values, and notes in CRM pipeline |
| `/dm:segment-audience` | Create or update audience segments in CRM or email platform |
| `/dm:data-export` | Export marketing data to BigQuery, Google Sheets, or Supabase |

### Monitoring

| Command | What it does |
|---------|-------------|
| `/dm:performance-check` | Pull live metrics from all connected platforms for instant performance snapshot |
| `/dm:campaign-status` | Check status of all active campaigns with execution history |
| `/dm:anomaly-scan` | Detect anomalies --- traffic drops, spend spikes, deliverability issues |
| `/dm:budget-tracker` | Real-time budget tracking across all ad platforms with pacing analysis |

### Memory & Knowledge

| Command | What it does |
|---------|-------------|
| `/dm:save-knowledge` | Save brand knowledge to vector database for RAG retrieval |
| `/dm:search-knowledge` | Semantic search across all stored brand knowledge |
| `/dm:sync-memory` | Batch sync session learnings and campaign history to persistent memory |

### Communication

| Command | What it does |
|---------|-------------|
| `/dm:send-sms` | Send SMS or WhatsApp marketing message via Twilio or Brevo |
| `/dm:send-notification` | Send team notification via Slack with campaign updates or alerts |

### Agency Operations

| Command | What it does |
|---------|-------------|
| `/dm:agency-dashboard` | Portfolio-level view across all clients with KPI health and budget pacing |
| `/dm:client-report` | Generate white-labeled client-facing performance report |
| `/dm:sop-library` | Manage agency SOPs --- create, assign to brands, track compliance |
| `/dm:credential-switch` | Switch active brand credential profile for multi-client management |

### Brand Team Management

| Command | What it does |
|---------|-------------|
| `/dm:team-assign` | Assign marketing tasks to team members based on role and capacity |
| `/dm:region-config` | Configure regional settings --- timezone, language, compliance, currency |
| `/dm:exec-summary` | Generate C-suite executive summary with portfolio ROI and strategic recommendations |

### Tip: You do not always need slash commands

Slash commands are useful for structured, templated outputs. But you can also just describe what you need in natural language:

```
"Help me write ad copy for our new cold brew"
"What should our content strategy look like for Q3?"
"I need to respond to negative reviews on Google"
```

The plugin's 16 modules will activate based on the intent of your request, whether or not you use a slash command. The commands simply give you a direct shortcut to a specific workflow.

---

## 10. Next Steps

You are set up and ready to go. Here are some resources for when you want to go deeper.

### Guides

- **Importing brand guidelines** --- If your brand has a voice guide, restriction list, or channel-specific style rules, see `docs/brand-guidelines.md` for the full guide on importing guidelines, templates, and agency SOPs.

- **Managing multiple brands** --- If you work with more than one brand or run an agency, see `docs/multi-brand-guide.md` for brand switching, side-by-side comparison, and multi-client workflows.

- **Execution & Publishing** --- v2.0.0 adds full execution capabilities. Every action goes through an approval workflow (draft → review → approve → execute → monitor). See the execution commands above.

- **CRM Integration** --- Connect Salesforce, HubSpot, Zoho, or Pipedrive for bidirectional data sync. See `docs/integrations-guide.md` for setup.

- **Memory & RAG** --- Store and retrieve brand knowledge across sessions using Pinecone, Qdrant, or Supermemory vector databases. See the Memory & Knowledge commands above.

- **Connecting your marketing tools** --- The plugin supports 46 MCP server integrations spanning analytics, advertising, CRM, email, social publishing, memory/RAG, and more. See `docs/integrations-guide.md` to connect your accounts.

- **KPI-driven strategy** --- Learn how to set up marketing KPI frameworks, build reporting dashboards, and track campaign performance over time in `docs/strategy-and-kpis.md`.

- **Understanding the architecture** --- For a technical deep dive into how the 16 modules, 18 agents, context engine, and hook system work together, see `docs/architecture.md`.

- **Using Cowork** --- If you are using Claude Cowork (or considering it), see `docs/claude-interfaces.md` for Cowork-specific capabilities like document creation, visual page review, and a comparison with Anthropic's official marketing plugin.

### Quick reference: The 16 marketing modules

These are the knowledge domains that power the plugin. They activate automatically based on your requests.

| Module                  | Coverage                                                            |
|-------------------------|---------------------------------------------------------------------|
| Content Engine          | SEO content, ad copy, email, social, landing pages, brand voice, accessibility, multilingual |
| Campaign Orchestrator   | Campaign planning, budget allocation, channel strategy, UTM tracking, post-mortems, ABM |
| Audience Intelligence   | Buyer personas, segmentation, Jobs-to-Be-Done, psychographic profiling |
| Analytics & Insights    | KPI frameworks, reporting, anomaly diagnosis, competitive intel, attribution, MMM |
| Paid Advertising        | Google Ads, Meta Ads, LinkedIn Ads, TikTok Ads, programmatic, retail media, bid strategy |
| AEO/GEO                | AI visibility, answer engine optimization, citation optimization, entity consistency |
| Funnel Architect        | Journey mapping, funnel design, attribution models, gap analysis    |
| CRO                     | Landing page audits, A/B testing, form optimization, pricing psychology, checkout optimization |
| Digital PR              | Media outreach, press releases, thought leadership, newsjacking, E-E-A-T authority |
| Growth Engineering      | Product-led growth, referral systems, viral loops, launch strategy, retention, affiliate |
| Influencer & Creator    | Influencer discovery, creator briefs, FTC compliance, contracts, UGC, performance tracking |
| Reputation Management   | Review strategy, crisis communication, brand safety, sentiment monitoring, recovery playbooks |
| Emerging Channels       | Voice search, visual search, conversational commerce, social commerce, podcasts, video, community |
| Technical SEO           | Core Web Vitals, crawlability, indexation, site architecture, redirects, JavaScript SEO, mobile-first |
| Local SEO               | Google Business Profile, NAP consistency, citations, local pack, location pages, multi-location |
| Marketing Automation    | Automation workflows, lead scoring, nurture sequences, marketing operations, MAP strategy |

### Getting help

If something is not working as expected:

1. Check that your brand profile exists: look for a file at `~/.claude-marketing/brands/_active-brand.json`
2. Re-run brand setup if needed: `/dm:brand-setup`
3. Check Python status in your session start banner (if you expected scoring features)
4. For MCP integration issues, verify your API credentials in the `.mcp.json` configuration

---

*Digital Marketing Pro v2.0.0 --- Built for marketing professionals who want strategy, execution, and publishing that stays on-brand, every time. Plan it, approve it, execute it, monitor it --- all from Claude Code and Claude Cowork.*
