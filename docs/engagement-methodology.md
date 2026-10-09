# The Engagement Methodology Guide

**Methodology version: 3.2** | A user-facing guide to running marketing engagements with Digital Marketing Pro

> The 12-Part methodology itself was introduced in v3.0 and remains structurally unchanged through v3.15. v3.2 adds two adjacent commands that pair well with the engagement workflow: **`/digital-marketing-pro:check`** (pre-publish quality gate for any deliverable produced inside an engagement) and **`/digital-marketing-pro:status`** (engagement progress + brand snapshot). See [docs/v3.2-opt-ins.md](v3.2-opt-ins.md) for the full v3.2 additions.

This guide explains the 12-Part engagement methodology introduced in v3.0 — what it is, when to use it, and exactly how to run a complete engagement from intake through continuous improvement.

If you have used the plugin only for one-off tasks (`/digital-marketing-pro:campaign-plan`, `/digital-marketing-pro:content-engine`, etc.), this guide shows you the higher-leverage way to use it: as a methodology that orchestrates the full engagement.

---

## Table of Contents

1. [Why a Methodology](#1-why-a-methodology)
2. [The 12 Parts at a Glance](#2-the-12-parts-at-a-glance)
3. [Two Ways to Use the Plugin](#3-two-ways-to-use-the-plugin)
4. [Starting Your First Engagement](#4-starting-your-first-engagement)
5. [Walking Through the 12 Parts](#5-walking-through-the-12-parts)
6. [The Two-Views Model](#6-the-two-views-model)
7. [The Decision Matrix](#7-the-decision-matrix)
8. [The Update-Back Rule](#8-the-update-back-rule)
9. [The Living Project Instruction File](#9-the-living-project-instruction-file)
10. [Reading the Engagement Directory](#10-reading-the-engagement-directory)
11. [Quality Discipline](#11-quality-discipline)
12. [Common Patterns and Anti-Patterns](#12-common-patterns-and-anti-patterns)
13. [Reference Documents](#13-reference-documents)

---

## 1. Why a Methodology

Most marketing tools generate isolated outputs — a campaign brief here, an email there, a content piece somewhere else. There is no canonical sequence, no shared state, no enforced structure. The result: inconsistent depth across engagements, missed dependencies between deliverables, and outputs that do not compound across sessions.

The engagement methodology fixes this by making every engagement run through the same 12 parts in sequence, producing the same set of files in the same order, with explicit dependency rules between them. The result is:

- **Consistency** — every brand engagement has the same depth and structure
- **Traceability** — every recommendation cites a source; every assumption is explicit
- **Compounding value** — the engagement directory becomes a living asset that gets richer over time
- **Honest separation of unbiased market view from client perspective** — both views are kept available so the team can stress-test, ideate, and have informed client conversations
- **Selective re-runs** — when client validation changes things, the Decision Matrix re-runs only what needs to change, not everything

The methodology layer is **purely additive** to v2.7. Every existing skill, agent, script, hook, and command still works exactly as before. Engagement is an opt-in workflow — you can still use the plugin for one-off tasks if that fits your situation.

---

## 2. The 12 Parts at a Glance

| Part | Name | Type | Output |
|------|------|------|--------|
| 1 | Client Inputs | Intake | Stone vs Opinion intake (what the client knows for certain vs what they believe) |
| 2 | External Research | Unbiased research | 3 research documents (industry, customer demand signals, ecosystem scan) |
| 3 | **Four Core Documents** | Strategy depth | 4 documents, 61 explicit steps |
| 4 | Competitive + Customer + Market Analysis | Unbiased research | 4 documents (4.1 Competitor Ad Analysis, 4.2 Competitor Positioning, 4.3 Customer Analysis, 4.4 Market Analysis) |
| 5 | **Client Validation Document** | Client-facing | The one true stop. Client accepts/rejects/edits each finding |
| 6 | Selective v2 Re-runs | Strategy depth | Subset of Part 3 + Part 4 docs re-run per the Decision Matrix |
| 7 | Preparation Documents | Internal operating | 6 documents (campaign architecture, naming conventions, approval chains, KPI tree, content pillars, asset inventory) |
| 8 | **Growth Plan + Yearly Planner** | Client-facing | The flagship 11-section client-facing strategy + 12-month operational calendar |
| 9 | Channel Strategy Fan-out | Channel execution | Up to 17 channel documents grouped into 7 families |
| 10 | Execution Artefacts | Channel execution | Communication outputs (ad copy, post copy, headlines, CTAs) |
| 11 | AI Creative Instructions | Channel execution | Visual asset briefs |
| 12 | Continuous Improvement Loop | Continuous | Market + operating signals feeding product/offering decisions |

A typical full-suite engagement produces ~50–60 files in this canonical structure. Out of those, only **Parts 5 and 8** produce client-facing deliverables — the rest are internal operating documents.

---

## 3. Two Ways to Use the Plugin

### Path A — One-off tasks (the v2.x way, still fully supported)

If you need a single deliverable — a content calendar, an email sequence, a competitor analysis — you can still use the plugin exactly as before:

```
/digital-marketing-pro:content-engine           # Generate content
/digital-marketing-pro:email-sequence           # Build an email flow
/digital-marketing-pro:competitor-analysis      # Run a competitor audit
/digital-marketing-pro:campaign-plan            # Plan a single campaign
```

These commands produce immediate output without requiring an engagement context. Use them when:

- You need a quick deliverable, not a full strategy
- You are exploring or learning the plugin
- The work is genuinely one-off (a single ad, a single blog post)
- You do not yet have a brand profile worth investing the methodology in

### Path B — Full engagement methodology (new in v3.0)

If you are running a real marketing engagement — a quarterly strategy, an annual plan, a new client onboarding, a major repositioning — use the engagement workflow:

```
/digital-marketing-pro:engagement start <brand-slug> <engagement-id>
```

This kicks off the 12-Part methodology. The plugin walks you through Stone vs Opinion intake, then orchestrates the production of all subsequent parts. Output lands in a structured directory tree under `~/.claude-marketing/brands/{brand-slug}/engagements/{engagement-id}/`.

Use Path B when:

- You are running a full strategic engagement
- You need traceability and version control
- The work will compound over months
- The brand requires depth and rigour, not speed
- You will be presenting client-facing deliverables (Growth Plan, Yearly Planner)

**Both paths share the same 24 specialist agents, 164 atomic skills, 14 HTTP MCP connectors, brand profile system, and compliance enforcement.** The methodology layer just orchestrates them into a known sequence.

---

## 4. Starting Your First Engagement

### Pre-requisite: a brand profile

Before starting an engagement, you need a brand profile. If you have not created one yet:

```
/digital-marketing-pro:brand-setup
```

Walk through the Quick Setup (5 questions) or Full Setup (17 questions). The brand profile is saved at `~/.claude-marketing/brands/{brand-slug}/profile.json`.

You only need to do this once per brand. The same brand can have multiple engagements over time.

### Initialise the engagement

```
/digital-marketing-pro:engagement start acme-corp 2026-q2
```

This:

1. Creates the engagement directory tree at `~/.claude-marketing/brands/acme-corp/engagements/2026-q2/`
2. Initialises `_engagement.json` (the state file)
3. Creates the Living Project Instruction File
4. Walks you through Part 1 Stone vs Opinion intake

### Walk through Part 1 — Stone vs Opinion intake

The plugin asks you a series of questions in two batches.

**Stone — what the client knows for certain.** Each Stone fact is verifiable or directly observed:

- "What year was the company founded?"
- "How many employees today?"
- "What are your pricing tiers?"
- "Which channels are you currently active on?"
- "What is your CRM and email service provider?"

For each Stone fact, the plugin captures the fact + the source (how the client knows / what document confirms it).

**Opinion — what the client believes.** Each Opinion is treated as a **research question**, not as ground truth:

- "How would you describe your positioning in the market?"
- "Who are your main competitors?"
- "Where do you think your biggest growth opportunity is?"
- "What marketing activity do you believe is working?"

For each Opinion, the plugin captures the hypothesis + the client's evidence + a research question for Parts 2–4 to investigate.

> **Why this matters:** Without Stone vs Opinion separation, client intake contaminates the unbiased research. The client says "we are positioned as premium" — and the unbiased research, instead of independently assessing the brand's actual market position, produces a confirmatory analysis that just restates the client's belief. By tagging the same intake item as Opinion, the unbiased research is forced to genuinely answer: *Is the brand actually positioned as premium in the market? What evidence supports or contradicts this?*

After Part 1, you have two structured intake files:

```
engagements/2026-q2/part-01-client-inputs/
├── stone-facts.json        # Facts treated as ground truth
└── opinion-hypotheses.json # Hypotheses to be researched
```

---

## 5. Walking Through the 12 Parts

After Part 1, you advance through the engagement using either:

```
/digital-marketing-pro:engagement next                           # Confirm current part complete; advance to next
/digital-marketing-pro:engagement status                         # See where you are
/digital-marketing-pro:engagement four-core <brand> <id>         # Produce Part 3 (61 steps across 4 docs)
/digital-marketing-pro:engagement validate <brand> <id>          # Produce Part 5 client validation
/digital-marketing-pro:engagement re-run-decision <brand> <id>   # Apply Decision Matrix for Part 6
/digital-marketing-pro:engagement growth-plan <brand> <id>       # Produce Part 8 flagship deliverable
/digital-marketing-pro:engagement yearly-planner <brand> <id>    # Produce Part 8 operational companion
/digital-marketing-pro:engagement loop <brand> <id>              # Part 12 quarterly or ad-hoc brief
```

Each part has a specific producer. Some parts use the existing v2.x atomic skills; some use the new v3.0 methodology skills.

### Part 2 — External Research

External research without using any client documents. Three outputs:

- Industry overview (size, growth, dynamics, regulations)
- Customer demand signals (search trends, third-party reviews, forum themes)
- Ecosystem scan (technology platforms, vendors, intermediaries)

Uses existing skills: `market-intelligence`, `intelligence-curator`, browser-based research where applicable.

### Part 3 — Four Core Documents (the strategic spine)

The most important part of the engagement. Four documents at strategic depth, 61 total steps:

**3.1 Business & SBU Analysis (18 steps).** SBU identification, revenue streams per SBU, unit economics, value chain, offering portfolio at task-level granularity, pricing architecture, GTM model, sales/distribution architecture, full SWOT with evidence, growth levers, constraints, customer acquisition + retention economics, partnership dependencies, risk profile, strategic implications, open questions.

**3.2 Segmentation Framework (15 steps).** Target groups, sub-TGs, persona development using the [Actionable Persona Format](../skills/context-engine/actionable-persona-format.md) (6-question format), behavioural and psychographic attributes, need-state mapping. For B2B engagements: the [B2B Decision-Making Unit](../skills/context-engine/b2b-decision-making-unit.md) overlay (User / Influencer / Decision-maker / Gatekeeper) plus MQL/SQL definitions and pipeline logic.

**3.3 Brand Positioning & Communications (19 steps).** Positioning options considered, chosen positioning with defence argument, trade-offs, brand promise + proof, message architecture, messaging pillars + proof points per pillar, segment-level messaging variations, full-funnel communication framework, tone-of-voice principles, don't-say rules, sensitive-topic handling, crisis communication posture.

**3.4 DMFlow (9 steps).** Channel selection from the [Five Digital Markets](../skills/context-engine/five-digital-markets.md) (Search / Profile / Contextual / Marketplace / Utility), funnel architecture per channel, media mix logic, budget allocation logic with [In-Market vs Out-Market split](../skills/context-engine/in-market-out-market.md), channel interdependencies, conversion framework, measurement approach.

**Optional: 3.C Combined Core Document.** All four stitched into a single executive-reference file. Produced only when an executive audience needs a single-file read.

Produce all four with:

```
/digital-marketing-pro:engagement four-core <brand> <id>
```

Or produce one specific document:

```
/digital-marketing-pro:engagement four-core <brand> <id> --doc 3.1
```

### Part 4 — Competitive + Customer + Market Analysis

Four parallel research documents:

- **4.1 Competitor Ad Analysis** — what competitors are running and what it tells you
- **4.2 Competitor Positioning** — how competitors position themselves and where the white space is
- **4.3 Customer Analysis** — unbiased customer research (reviews, forums, search behaviour)
- **4.4 Market Analysis** — market sizing (TAM / SAM / SOM), trends, growth dynamics

Every competitor analysis closes with the [Three-Question Output](../skills/context-engine/competitor-3-question-output.md): what they do well to learn from, what they do poorly creating opportunity, and what they are NOT doing that represents white space we can own.

### Part 5 — Client Validation Document (the one true stop)

The single client-facing checkpoint between unbiased research and operating layer.

```
/digital-marketing-pro:engagement validate <brand> <id>
```

Produces a structured document with every material finding from Parts 2–4. For each finding, the client picks ACCEPT / REJECT / EDIT / DEFER and provides reasoning. The Opinion hypotheses captured in Part 1 are revisited here — the unbiased research either confirmed, contradicted, or left open each one.

This is the **one true stop** in the engagement. Nothing in Parts 6+ proceeds until the client signs off.

### Part 6 — Selective v2 Re-runs

After client validation, the Decision Matrix determines which v1 documents need to be re-run as v2 versions.

```
/digital-marketing-pro:engagement re-run-decision <brand> <id>
```

Common re-run triggers:

- Competitors changed → re-run all 4 Core Docs + 4.1 + 4.2
- Target market changed → re-run 4.3 + 4.4
- Audiences changed → re-run 3.2 + 3.3 + 3.4
- Positioning changed → re-run 3.3
- Budget / scope changed → re-run 3.4

The matrix prevents over-re-running (waste) and under-re-running (stale assumptions). See section 7 below.

### Part 7 — Preparation Documents

Six internal documents that bridge strategy to execution:

- Campaign architecture
- Naming conventions
- Approval chains
- KPI tree
- Content pillars
- Asset inventory

Uses existing skills: `campaign-orchestrator`, `content-engine`, `analytics-insights`, `brand-guardian`.

### Part 8 — Growth Plan + Yearly Planner (flagship client deliverables)

The two client-facing outputs that synthesise everything into actionable narrative.

**Growth Plan** (11 sections, 20–30 pages):

```
/digital-marketing-pro:engagement growth-plan <brand> <id>
```

Sections: Executive Summary → Business Context → Target Audience → Strategic Positioning → Channel Strategy → Budget & Media Plan → KPI Framework → Implementation Timeline → Team & Resource Plan → Risk & Contingency → Expected Outcomes (three scenarios).

**Yearly Planner** (12-month operational calendar):

```
/digital-marketing-pro:engagement yearly-planner <brand> <id>
```

Sections: Annual Themes → Monthly Calendar (12 sub-sections) → Seasonal Strategy → Campaign Architecture → Content Pillars Calendar → Channel-Specific Cadence → Resource & Budget Pacing → Quarterly Review Schedule.

Both deliverables export to PDF and DOCX (and XLSX for the Yearly Planner calendar).

### Part 9 — Channel Strategy Fan-out

Up to 17 channel documents grouped into 7 families per [Channel Families](../skills/context-engine/channel-families.md):

- Search & Campaign (9.1, 9.2)
- Paid Platforms (9.3 Google, 9.4 Meta, 9.5 LinkedIn, 9.6 Other Paid, 9.7 Custom Audience Acquisition)
- Organic & Influencer (9.8, 9.9)
- Marketplace & CRM (9.10, 9.11)
- Content / ATL / BTL / PR (9.12, 9.13, 9.14, 9.15)
- Web + Measurement (9.16, 9.17)

Channels not in scope are **deferred**, never placeholder-filled. A typical engagement has 5–10 channel docs, not all 17.

Each channel doc has 4 components: Media (platform strategy), KPIs (measurement plan), Infrastructure (landing pages, forms, tracking, creative formats), Communication (deferred to Part 10).

### Part 10 — Execution Artefacts

The actual ad copy, post copy, headlines, CTAs. Per channel doc from Part 9.

Uses existing skills: `content-engine` (in execution mode), `content-repurpose` (cross-channel adaptation), the `headline-analyzer.py` script (validation), and the `ad-creative` skill for platform-specific creative.

### Part 11 — AI Creative Instructions

Visual asset briefs that feed designers / video producers / image generation tools.

### Part 12 — Continuous Improvement Loop

Runs continuously from go-live onwards. Aggregates four signal sources into product/offering recommendations:

- Quarterly Business Review signals
- Customer feedback themes
- Competitive intelligence
- Team-discovered execution patterns

```
/digital-marketing-pro:engagement loop <brand> <id>
```

Produces structured Part 12 deliverables at each Quarterly Business Review (QBR) and ad-hoc briefs when significant signals warrant.

---

## 6. The Two-Views Model

After Part 5, every engagement carries **two views** of the world. Both remain authoritative for different questions. Neither is deleted.

- **v1** — the unbiased market view from Parts 2–4 (what the market said before the client lens was applied)
- **v2** — the client-validated view (after Part 5 acceptances/edits)

### Which view to consult

| Decision type | Primary view | Use both? |
|---|---|---|
| Operating decisions (channel execution, ad copy direction, content plan, budget allocation per campaign) | v2 | No — v2 only |
| Stress-testing or pivot conversations (a campaign is not working; segment not converting) | Both | Yes |
| Ideation and suggestions (new campaign concepts, untested segments, alternative positioning angles) | Both | Yes — v1 often holds the most creative territory |
| Client conversations about underperformance | Both | Yes — articulate what unbiased market said, what client chose, what data is now suggesting |

### Why keep v1

The "gap between views" is itself strategic information. When v1 identified Segment X as highest-priority but v2 deprioritised it, that gap means something — the client may have private information, or may be over-weighting internal preferences, or may be under-weighting competitive risk. Without v1 preserved, you cannot have those informed conversations later.

---

## 7. The Decision Matrix

After Part 5 client validation, the Decision Matrix automatically determines which v1 documents need to be re-run as v2 versions.

```
/digital-marketing-pro:engagement re-run-decision <brand> <id>
```

The matrix:

| If this changed in Part 5 | Re-run these v2 documents |
|---|---|
| Competitors changed | All 4 Core Docs + 4.1 + 4.2 |
| Target market data changed | 4.3 + 4.4 |
| Audiences changed | 3.2 + 3.3 + 3.4 |
| Positioning changed | 3.3 |
| Budget / scope changed | 3.4 |
| Pricing / offering changed | 3.1 (sections 4 + 7) |
| Unit economics changed | 3.1 (section 4) |
| Minor corrections only | NO full re-run; update inline as v1.1 |

The plugin shows you the re-run plan with estimated cost before executing. You can approve all, modify (skip some), or override (force re-runs the matrix didn't trigger).

---

## 8. The Update-Back Rule

After Part 7 onwards, the engagement operates on v2. But corrections continue to surface during execution — a TG definition turns out to be wrong in field, a competitor is mis-classified, a positioning claim does not hold up under scrutiny, a budget assumption proves unrealistic.

When this happens, the correction is made in the **source document**, not just in the deliverable that caught the error.

```
/digital-marketing-pro:engagement update-back <brand> <id> --doc 3.1 --reason "Segment X CAC corrected from INR 3,000 to INR 4,800 based on Q2 channel data"
```

The plugin:

1. Validates the correction with you
2. Bumps the source document version (v2.0 → v2.1)
3. Saves the new version with a "v2.0 → v2.1 changes" header
4. Updates the Living Project Instruction File so all downstream skills see the change
5. Identifies downstream documents that may need review

The result: the engagement stays honest over its life instead of silently drifting. Every change is versioned and traceable.

---

## 9. The Living Project Instruction File

Every engagement maintains a single **Living Project Instruction File** (LIF) at:

```
~/.claude-marketing/brands/{brand-slug}/engagements/{engagement-id}/living-instruction-file.md
```

This file is the single source of truth for **what is currently true about the engagement**. All skills read it before producing output. All updates land here when source documents change.

The LIF contains:

- **Quick Status** — current part, active campaigns, open review items, outstanding corrections
- **Currently True — Strategic Facts** — current positioning, primary persona, unit economics, channel selections, compliance profile
- **Recent Corrections (Last 30 Days)** — version log of source doc updates
- **Open Items Requiring Resolution** — pending validations, stress-test findings, open opinions
- **Current Part Status** — phase, progress, next required action
- **Version History** — current version of each source document
- **Engagement Health Indicators** — days since updates, compliance violations, scaling candidates

To view:

```
/digital-marketing-pro:engagement lif-show <brand> <id>
```

The LIF is auto-updated when source documents change. You should never hand-edit it — let the engagement-state script maintain it.

---

## 10. Reading the Engagement Directory

Every engagement lives in a canonical directory structure:

```
~/.claude-marketing/brands/acme-corp/engagements/2026-q2/
├── _engagement.json                         # State: current part, decisions log, version history
├── living-instruction-file.md               # The "currently true" record
│
├── part-01-client-inputs/
│   ├── stone-facts.json                     # Verifiable client facts
│   ├── opinion-hypotheses.json              # Client beliefs (research questions)
│   └── intake-questionnaire.md              # Free-form intake notes
│
├── part-02-external-research/               # 3 unbiased research docs
│
├── part-03-four-core-documents/
│   ├── v1/
│   │   ├── 3.1-business-and-sbu-analysis.md
│   │   ├── 3.2-segmentation-framework.md
│   │   ├── 3.3-brand-positioning-and-communications.md
│   │   └── 3.4-dmflow.md
│   └── v2/                                  # Subset re-run per Decision Matrix
│
├── part-04-competitive-customer-market/
│   ├── v1/  (4.1, 4.2, 4.3, 4.4)
│   └── v2/
│
├── part-05-client-validation/
│   ├── client-validation-document.md
│   ├── client-validation-responses.template.json
│   └── client-validation-responses.json     # Client's reviewed decisions
│
├── part-06-v2-reruns/                       # Decision log; actual re-runs land in part-03/v2 + part-04/v2
│
├── part-07-preparation/                     # 6 internal operating documents
│
├── part-08-growth-plan/
│   ├── growth-plan.md                       # Client-facing
│   ├── growth-plan.pdf
│   ├── growth-plan.docx
│   ├── yearly-planner.md                    # Client-facing
│   ├── yearly-planner.pdf
│   └── yearly-planner.xlsx
│
├── part-09-channel-strategy/                # Up to 17 channel docs grouped by family
│
├── part-10-execution-artefacts/             # Ad copy, post copy, headlines, CTAs
│
├── part-11-ai-creative-instructions/        # Visual asset briefs
│
├── part-12-continuous-improvement/
│   ├── signals.jsonl                        # Captured signals over time
│   ├── quarterly-briefs/                    # Structured Part 12 deliverables
│   └── ad-hoc-briefs/                       # Significant-signal ad-hoc briefs
│
└── reports/
    ├── monthly/
    ├── quarterly/
    └── annual/
```

A typical full-suite engagement produces **~50–60 files**. Out of those, only Parts 5 and 8 are client-facing (3 documents); the rest are internal operating documents that prioritise depth, rationale, and assumption discipline.

To see the actual file tree at any time:

```
/digital-marketing-pro:engagement file-tree <brand> <id>
```

---

## 11. Quality Discipline

The methodology enforces several disciplines that make outputs trustworthy and defensible.

### Every claim cites a source

No "we think" — only "the evidence shows" with a cited source. Sources include:

- Client-provided documents (cite filename)
- Public sources (cite URL)
- Industry reports (cite report + page)
- Stone facts from Part 1 (cite the fact ID)
- Estimation methodology (state assumptions explicitly)

### Every assumption is explicit

When estimating CAC, LTV, market size, conversion rates — state the methodology and inputs. "Market size: INR 3,000 Crore (bottom-up estimate based on AISHE 2024 school count + IAMAI digital spend benchmarks)" is trustworthy. "Market size: Large" is useless.

### Every recommendation flows from analysis

No conclusions the body does not support. If a recommendation is not traceable back to specific findings in the analysis, it does not belong in the document.

### Stone facts are facts; Opinions are questions

Do not elevate Opinion to fact in the document. If the unbiased research did not validate an Opinion, it stays as Opinion (or as an open question), not as an asserted fact.

### Three-scenario forecasting

Every projection (revenue, channel performance, growth) presents Conservative / Moderate / Aggressive scenarios with explicit assumptions. Never a single number. See [Three-Scenario Forecasting](../skills/context-engine/three-scenario-forecasting.md).

### Multi-Dimensional Decision Framework

For any consequential decision (channel selection, persona prioritisation, positioning trade-offs), use the [Multi-Dimensional Decision Framework](../skills/context-engine/decision-framework.md) — identify all dimensions, assign weightages, score each option, compute weighted total. No gut-feel decisions.

### Unit economics check

Every channel recommendation, every budget allocation, every campaign approval verifies LTV:CAC ≥ 3.0 health threshold. See [Unit Economics Framework](../skills/context-engine/unit-economics-framework.md).

### Competitor 3-Question Output

Every competitor analysis closes with: what they do well to learn from / what they do poorly creating opportunity / what they are NOT doing that represents white space. See [Competitor 3-Question Output](../skills/context-engine/competitor-3-question-output.md).

---

## 12. Common Patterns and Anti-Patterns

### Patterns that work

**Run Parts 1–4 in roughly a week.** External research can run in parallel with Part 3 strategy work. Do not rush Part 1 intake — getting Stone vs Opinion right pays off across all subsequent parts.

**Schedule Part 5 client validation as a 60–90 minute working session.** The structured findings document is designed to be walked through with the client, not emailed and forgotten. Live walkthrough produces better decisions and faster turnaround.

**Use the Variable budget mechanism** ([Fixed vs Variable Budget](../skills/context-engine/fixed-vs-variable-budget.md)). Every monthly report includes a Variable Budget Recommendation section that turns the budget conversation from "can we spend more?" into "here is where additional spend pays off, with the math."

**Run Part 12 continuously, not just at quarter-end.** Capture signals to `signals.jsonl` as they arrive. The QBR brief becomes a synthesis of what is already captured, not a scramble at quarter-end.

**Bump source document versions for any meaningful correction.** The Update-Back Rule prevents strategic drift. A tactical fix that does not flow back to the source document is destined to be re-discovered as a problem.

### Anti-patterns to avoid

**Skipping Part 1 Stone vs Opinion separation.** "We can capture intake later." No — Parts 2–4 are contaminated if intake conflates Stone with Opinion. The research becomes confirmatory rather than independent.

**Treating v1 as throwaway after Part 5.** v1 is preserved on purpose. Stress-testing, ideation, and informed client conversations all need it. Deleting v1 forfeits a strategic asset.

**Re-running everything after Part 5.** The Decision Matrix exists precisely so you do not over-re-run. Most validations trigger only a subset of v2 re-runs.

**Producing the Growth Plan before Part 5 is signed off.** The Growth Plan synthesises the validated v2 view. Producing it on v1 means the client validation cycles back through every section of the Growth Plan, not just the source documents.

**Treating Part 12 as optional.** A live engagement without Part 12 silently drifts. Six months in, the strategy in v2 no longer matches what the team is actually executing — and nobody notices until the QBR.

**Over-fitting personas to client opinion.** If the client believes Segment X is the priority but the unbiased research disagrees, the persona document captures both views. The team can articulate the gap when execution data starts to land.

**Skipping the source citations to "save time."** Sourceless claims are indistinguishable from hallucinations six months later. The plugin's hallucination detector flags unattributed statistics; the methodology requires citations on everything.

---

## 13. Reference Documents

The methodology is defined across 23 reference documents in `skills/context-engine/`. The most important ones to know:

### Methodology core

- [engagement-flow-methodology.md](../skills/context-engine/engagement-flow-methodology.md) — the master 12-Part methodology spec
- [four-core-documents-spec.md](../skills/context-engine/four-core-documents-spec.md) — the 61-step specification for Part 3
- [two-views-model.md](../skills/context-engine/two-views-model.md) — v1 + v2 architecture
- [decision-matrix-rerun.md](../skills/context-engine/decision-matrix-rerun.md) — when to re-run what
- [update-back-rule.md](../skills/context-engine/update-back-rule.md) — versioning protocol
- [stone-vs-opinion.md](../skills/context-engine/stone-vs-opinion.md) — confidence tagging
- [living-instruction-file-spec.md](../skills/context-engine/living-instruction-file-spec.md) — LIF schema

### Strategic frameworks

- [five-digital-markets.md](../skills/context-engine/five-digital-markets.md) — channel taxonomy (Search / Profile / Contextual / Marketplace / Utility)
- [channel-families.md](../skills/context-engine/channel-families.md) — 7 families covering 17 channels
- [in-market-out-market.md](../skills/context-engine/in-market-out-market.md) — 3-5% vs 95-97% audience split
- [decision-framework.md](../skills/context-engine/decision-framework.md) — multi-dimensional weighted decision-making
- [unit-economics-framework.md](../skills/context-engine/unit-economics-framework.md) — CAC / LTV / payback
- [actionable-persona-format.md](../skills/context-engine/actionable-persona-format.md) — 6-question persona format
- [b2b-decision-making-unit.md](../skills/context-engine/b2b-decision-making-unit.md) — User / Influencer / Decision-maker / Gatekeeper
- [three-scenario-forecasting.md](../skills/context-engine/three-scenario-forecasting.md) — Conservative / Moderate / Aggressive
- [30-60-90-framework.md](../skills/context-engine/30-60-90-framework.md) — Foundation / Validation / Optimisation
- [reporting-cadence.md](../skills/context-engine/reporting-cadence.md) — daily / weekly / monthly / quarterly / annual
- [fixed-vs-variable-budget.md](../skills/context-engine/fixed-vs-variable-budget.md) — Fixed monthly + Variable reserve
- [competitor-3-question-output.md](../skills/context-engine/competitor-3-question-output.md) — required output for every competitor analysis
- [india-market-context.md](../skills/context-engine/india-market-context.md) — DPDP, mobile-first, festive seasonality, WhatsApp, vernacular content, INR benchmarks

### Deliverable templates

- [growth-plan-template.md](../skills/context-engine/growth-plan-template.md) — 11-section flagship structure
- [yearly-planner-template.md](../skills/context-engine/yearly-planner-template.md) — 12-month operational structure
- [monthly-report-template.md](../skills/context-engine/monthly-report-template.md) — 9-section monthly report

### Skills

- [`engagement-workflow`](../skills/engagement-workflow/SKILL.md) — the 12-Part orchestrator
- [`four-core-documents`](../skills/four-core-documents/SKILL.md) — produces Part 3 (61 steps)
- [`client-validation-document`](../skills/client-validation-document/SKILL.md) — produces Part 5
- [`growth-plan`](../skills/growth-plan/SKILL.md) — produces Part 8 flagship
- [`yearly-planner`](../skills/yearly-planner/SKILL.md) — produces Part 8 companion
- [`continuous-improvement-loop`](../skills/continuous-improvement-loop/SKILL.md) — Part 12

### Command

- [`/digital-marketing-pro:engagement`](../commands/engagement.md) — the entry point with all subcommands

### Persistence script

- `scripts/engagement-state.py` — the state management and directory tree script

---

*Digital Marketing Pro v3.0 — The 12-Part Engagement Methodology. Built by [Indranil Banerjee](https://github.com/indranilbanerjee). Issues and contributions welcome.*
