# Business KPIs to Marketing Strategy

> A practitioner's guide for CMOs and marketing strategy leads using the Digital Marketing Pro plugin.
>
> This document shows how to connect business objectives to measurable KPIs, translate KPI gaps into campaign strategies, and close the measurement loop so every planning cycle is smarter than the last.

---

## Table of Contents

1. [The Strategy-to-Measurement Loop](#1-the-strategy-to-measurement-loop)
2. [Step 1: Define Business Objectives](#2-step-1-define-business-objectives)
3. [Step 2: Build the KPI Framework](#3-step-2-build-the-kpi-framework)
4. [Step 3: Translate KPIs to Campaign Strategy](#4-step-3-translate-kpis-to-campaign-strategy)
5. [Step 4: Execute and Measure](#5-step-4-execute-and-measure)
6. [Step 5: Close the Loop](#6-step-5-close-the-loop)
7. [KPI Frameworks by Business Model](#7-kpi-frameworks-by-business-model)
8. [How Adaptive Scoring Connects to KPIs](#8-how-adaptive-scoring-connects-to-kpis)

---

## 1. The Strategy-to-Measurement Loop

Most marketing teams treat planning and measurement as separate activities. Strategy happens in a quarterly offsite. Reporting happens in a weekly dashboard review. The two rarely speak to each other in a structured way.

The plugin is built around a single continuous cycle:

```
Business Goals --> KPI Framework --> Campaign Strategy --> Execution --> Measurement --> Insights --> Refined Strategy
       |                                                                                                    |
       +----------------------------------------------------------------------------------------------------+
```

Each stage in this loop maps to a specific part of the plugin:

| Stage | What Happens | Plugin Module / Script |
|---|---|---|
| **Business Goals** | Define what success looks like for the business | Brand profile (`goals.primary_objective`, `goals.kpis`, `goals.budget_range`) |
| **KPI Framework** | Decompose goals into a hierarchical metric tree with targets and benchmarks | Analytics & Insights module (`kpi-frameworks.md`) |
| **Campaign Strategy** | Translate KPI gaps into phased campaign plans with budget allocation | Campaign Orchestrator module (budget-allocation.md, channel-strategy.md) |
| **Execution** | Produce content, launch ads, send emails, build funnels | Content Engine, Paid Advertising, Email Marketing modules |
| **Measurement** | Track performance against KPI targets, detect anomalies | `/dm:performance-report` command + `campaign-tracker.py` |
| **Insights** | Extract learnings from what worked and what did not | SessionEnd auto-save hook + `campaign-tracker.py --action save-insight` |
| **Refined Strategy** | Next planning cycle uses historical insights to improve | Campaign Orchestrator reads past campaign data and insights |

The critical insight is that the **Insights** stage is not optional. Without it, every planning cycle starts from scratch. With it, every cycle builds on accumulated institutional knowledge. The plugin automates this through the SessionEnd hook, which saves key learnings to `~/.claude-marketing/brands/{slug}/insights.json` at the end of every working session where marketing decisions were made.

---

## 2. Step 1: Define Business Objectives

Strategy starts with the business, not with marketing channels. Before touching KPIs, campaigns, or budgets, the plugin needs to understand what the business is trying to achieve, what model it operates, and what constraints it faces.

This information lives in the brand profile, specifically in the `goals`, `business_model`, and `industry` sections. You set it up through `/dm:brand-setup` and can update it any time.

### Worked Example: GreenPeak Outdoors

GreenPeak Outdoors is a DTC outdoor gear brand doing $2M in annual recurring revenue. Their products include camping gear, hiking equipment, and consumables like water filters and camp fuel. The business is profitable but growth has plateaued because existing customers are not coming back.

Here is how the conversation looks:

```
You: I need to set marketing goals for GreenPeak. We're doing $2M ARR with a
DTC model selling outdoor gear. Our repeat purchase rate is only 18% and we
want to get it to 30% by Q4.

Plugin: I'll build a goal-driven KPI framework for GreenPeak Outdoors.

Business Context:
- Model: B2C DTC
- Industry: Outdoor Recreation
- Revenue: $2M ARR
- Primary Objective: Increase repeat purchase rate from 18% to 30%
- Timeline: By Q4 (9 months)

Saving brand profile to ~/.claude-marketing/brands/greenpeak-outdoors/profile.json
```

The plugin stores this in the brand profile so every subsequent module — content scoring, campaign planning, performance reporting — automatically aligns to the retention objective without you restating it.

**What the profile captures that matters for KPI work:**

- `goals.primary_objective` — The single most important business outcome (e.g., "increase repeat purchase rate")
- `goals.kpis` — The specific metrics you are tracking against (e.g., repeat rate, email revenue %, LTV)
- `goals.budget_range` — Total marketing budget, which constrains what strategies are feasible
- `business_model.type` — Determines which KPI framework template applies (B2C_DTC, B2B_SaaS, Local_Business, etc.)
- `business_model.revenue_model` — Subscription, transactional, or hybrid changes how retention metrics are calculated
- `industry.primary` — Pulls industry-specific benchmarks from the 22 profiles in `industry-profiles.md`

If you already have a brand profile set up, the plugin uses it automatically. If you provide new goals in conversation, the profile is updated so future sessions reflect the latest objectives.

---

## 3. Step 2: Build the KPI Framework

Once business objectives are defined, the next step is decomposing them into a measurement framework. The Analytics & Insights module uses the KPI tree methodology from `kpi-frameworks.md` to build a four-level metric hierarchy.

### The KPI Tree for GreenPeak Outdoors

```
North Star: 90-Day Repeat Purchase Rate (18% --> 30%)

Primary Metrics:
+-- First Purchase CAC: $45 (target: maintain under $50)
+-- Customer LTV: $180 (target: $240 with improved retention)
+-- Email Revenue %: 22% (target: 35%)
+-- Subscription Conversion: 8% (target: 15%)

Supporting Metrics:
+-- Email Open Rate: 28% (benchmark: 25-35% for DTC)
+-- Cart Abandonment Recovery: 5% (target: 12%)
+-- Post-Purchase NPS: 42 (target: 55)
+-- Replenishment Reminder CTR: N/A (new program)
+-- Loyalty Program Enrollment: N/A (new program)

Diagnostic Metrics:
+-- Time Between First and Second Purchase
+-- Product Category Repeat Rate (consumables vs. durables)
+-- Unsubscribe Rate (email + SMS)
+-- Review Submission Rate
+-- Support Ticket Rate (post-purchase friction signal)
```

### How the Plugin Builds This

The plugin does not generate KPI trees from nothing. It combines three sources:

1. **Business model templates** from `kpi-frameworks.md` — The DTC Brand KPI Tree already defines the North Star (90-Day Repeat Purchase Rate), primary metrics (First Purchase CAC, Repeat Rate, LTV, Subscription Rate), and supporting metrics specific to DTC economics.

2. **Industry benchmarks** from `industry-profiles.md` — The eCommerce/Retail and DTC profiles provide benchmark ranges. For example, the DTC benchmark for repeat purchase rate is 15-25% at median, with top quartile above 30%. GreenPeak's 18% sits at the low end of median, confirming the gap is real and the 30% target is ambitious but achievable (it is a top-quartile outcome).

3. **Brand-specific context** from the profile — GreenPeak's specific revenue, product mix (consumables create natural repurchase triggers), and current metrics shape which supporting and diagnostic metrics matter most. A DTC brand selling only durable goods would have a very different repeat purchase strategy than one with consumables.

### Setting Targets That Are Not Arbitrary

Every target in the KPI tree needs to be grounded in one of three sources:

- **Historical baseline** — What is the current number? The improvement target should be realistic relative to the starting point. Going from 18% to 30% repeat rate in 9 months is aggressive but precedented.
- **Industry benchmark** — Where does the business sit relative to its peer set? The `kpi-frameworks.md` file includes median and top-quartile benchmarks for every metric by business model.
- **Mathematical decomposition** — If the North Star target is 30% repeat rate, what do the supporting metrics need to be to make that possible? Work backward from the goal.

The plugin flags targets that are outside the benchmark range with a note explaining the difficulty. It does not stop you from setting ambitious goals, but it makes sure you go in with clear expectations.

---

## 4. Step 3: Translate KPIs to Campaign Strategy

This is where most organizations drop the ball. They have KPIs in a dashboard and campaigns in a calendar, but the two are not connected. The Campaign Orchestrator module closes this gap by starting every campaign plan from a KPI gap analysis.

### From KPI Gaps to Campaign Decisions

```
You: My repeat purchase rate is 18%. Build me a campaign strategy to hit 30%.

Plugin (Campaign Orchestrator activates):

Gap Analysis:
- Current: 18% repeat rate --> Target: 30% --> Gap: 12 percentage points
- Root causes to address: no post-purchase nurture, no loyalty program,
  no replenishment reminders

Recommended Campaign Strategy:

Phase 1 (Month 1-2): Post-Purchase Email Nurture
- 5-email sequence: thank you --> usage tips --> cross-sell --> review request --> reorder prompt
- Budget: $3,000/mo (email platform + content creation)
- Target KPI: Email Revenue % from 22% --> 28%

Phase 2 (Month 2-4): Loyalty Program Launch
- Points-based system with gear rewards
- Launch campaign across email + Instagram + on-site
- Budget: $8,000 setup + $2,000/mo ongoing
- Target KPI: Loyalty enrollment 15% of customers

Phase 3 (Month 3-6): Replenishment & Retargeting
- Smart reminders for consumables (fuel, water filters, etc.)
- Social retargeting for browse-but-no-repurchase segment
- Budget: $2,500/mo (ads + automation)
- Target KPI: Replenishment reminder CTR 8%+

Budget Allocation:
- 60% Email/Retention ($4,500/mo)
- 30% Social Retargeting ($2,250/mo)
- 10% SMS/Push ($750/mo)
```

### Why This Structure Works

Notice what the plugin did:

1. **Started with the KPI gap**, not with a channel or tactic. The question was not "what should we post on Instagram?" but "what needs to change to move from 18% to 30%?"

2. **Diagnosed root causes** before prescribing solutions. The absence of post-purchase nurture, loyalty mechanics, and replenishment reminders are structural gaps, not creative problems. No amount of better ad copy fixes the absence of a post-purchase email sequence.

3. **Phased the strategy** so early wins fund later investments. The post-purchase email sequence (Phase 1) is the lowest-cost, fastest-to-implement initiative. Results from Phase 1 build the case for the higher-investment loyalty program in Phase 2.

4. **Tied every phase back to a specific KPI**. Phase 1 targets Email Revenue %. Phase 2 targets Loyalty Enrollment. Phase 3 targets Replenishment Reminder CTR. Each phase has a measurable outcome, so you know whether it is working before you reach Q4.

5. **Used the right budget model**. For a retention-focused strategy, the Campaign Orchestrator applied a funnel-weighted allocation model (one of the three models it supports alongside 70/20/10 and efficiency-ranked). Retention channels — email, SMS, on-site loyalty — get 60% of budget because that is where the KPI gap lives.

### Budget Allocation Models

The Campaign Orchestrator offers three allocation frameworks. The right one depends on how much historical data you have:

| Model | When to Use | How It Works |
|---|---|---|
| **70/20/10** | New programs or limited data | 70% to proven channels, 20% to promising channels, 10% experimental |
| **Efficiency-Ranked** | 6+ months of channel performance data | Allocate proportional to each channel's historical CPA or ROAS |
| **Funnel-Weighted** | Clear funnel data showing where drop-off occurs | Allocate to the funnel stages with the largest conversion gaps |

For GreenPeak, the funnel-weighted model made the most sense because the gap was clearly in the post-purchase/repeat stage, not in acquisition. An efficiency-ranked model would likely over-allocate to acquisition channels (where GreenPeak already performs well) and under-invest in the retention gap.

---

## 5. Step 4: Execute and Measure

With the strategy defined and campaigns in flight, the `/dm:performance-report` command becomes the operating rhythm. It pulls KPI data, compares against targets, flags anomalies, and provides recommendations.

### A Real Performance Report

```
You: /dm:performance-report

Performance Report: GreenPeak Outdoors -- Q2 Review

North Star: Repeat Purchase Rate
- Start: 18% --> Current: 22% --> Target: 30% (on track for 28% by Q4)

Campaign Results:
| Campaign              | KPI              | Target | Actual | Status   |
|-----------------------|------------------|--------|--------|----------|
| Post-Purchase Email   | Email Revenue %  | 28%    | 31%    | Exceeded |
| Loyalty Program       | Enrollment       | 15%    | 12%    | Behind   |
| Replenishment         | Reminder CTR     | 8%     | 9.5%   | Exceeded |

Anomaly Alert:
- Loyalty enrollment 20% below target -- investigate: sign-up flow friction?
- Email open rates dropped 4% in Week 8 -- possible: deliverability issue

Recommendations:
1. Double down on post-purchase email (outperforming by 3pp)
2. Simplify loyalty sign-up (reduce form fields from 6 to 3)
3. Run deliverability audit on email domain
```

### What the Plugin Does Under the Hood

The Performance Report command follows a structured process:

1. **Loads the brand profile** — reads `_active-brand.json` to get the brand slug, then loads the full profile from `profile.json`. This gives it the KPI targets, industry context, and compliance rules.

2. **Retrieves campaign history** — runs `campaign-tracker.py --brand greenpeak-outdoors --action list-campaigns` to pull all active campaigns and their associated KPIs.

3. **Ingests performance data** — you provide current metrics through paste, CSV, or connected MCP data sources (GA4, Google Ads, Meta, etc. via the 12 pre-configured MCP servers).

4. **Calculates KPIs** — core calculations per channel: traffic, conversions, revenue, ROAS, CPA, engagement, growth rates.

5. **Runs trend analysis** — period-over-period changes, trajectory projection, and seasonality adjustments.

6. **Detects anomalies** — the Analytics & Insights module uses a structured diagnostic protocol from `anomaly-diagnosis.md`. It checks data integrity first, then isolates the anomaly to a specific segment, then investigates external and internal factors.

7. **Benchmarks results** — compares actuals against both the brand's own targets and industry benchmarks from `industry-profiles.md`.

8. **Generates recommendations** — prioritized by expected impact. The recommendations are grounded in what the data shows, not generic advice.

### Saving Performance Snapshots

Every time a performance report is generated, the data can be saved for future reference:

```
campaign-tracker.py --brand greenpeak-outdoors --action save-performance --data '{
  "campaign_id": "post-purchase-email-20260301",
  "period": "Q2 2026",
  "metrics": {
    "email_revenue_pct": 31,
    "repeat_purchase_rate": 22,
    "loyalty_enrollment": 12
  }
}'
```

The `campaign-tracker.py` script stores these in `~/.claude-marketing/brands/greenpeak-outdoors/performance/`, creating a time-series of snapshots that future reports can reference for trend analysis. You do not need to run this manually — the plugin handles it when you generate a performance report.

---

## 6. Step 5: Close the Loop

This is the step that transforms a one-time campaign into a compounding marketing system. The plugin's SessionEnd hook automatically captures learnings from every working session and stores them for future use.

### How Insights Get Saved

When a session where marketing work was done comes to an end, the SessionEnd hook triggers:

```
(Session ends)
SessionEnd hook: Saving 2 insights for greenpeak-outdoors...
- "Post-purchase email sequence with usage tips drives 3x higher reorder
   rate than discount-only emails"
- "Loyalty program enrollment improves 40% when offered at checkout vs.
   standalone landing page"
```

Under the hood, the hook runs `campaign-tracker.py --action save-insight` for each learning. Insights are stored in `insights.json` as a rolling buffer of the 200 most recent entries. Each insight includes:

- **type** — what kind of learning (session_learning, campaign_result, competitive_observation)
- **insight** — the actual finding in plain language
- **source** — where it came from (session, post-mortem, performance report)
- **context** — what work produced this insight
- **actionable** — whether this can directly inform a future decision

### How Past Insights Shape Future Strategy

The real payoff comes in the next planning cycle. When you start a new session and ask the plugin to plan a campaign, it loads your historical insights and uses them:

```
(Next session)
You: Plan a holiday campaign for Q4.

Plugin: Based on your past insights:
- Post-purchase emails outperform discounts for driving repeats -- using
  education-first approach for holiday nurture sequence
- Loyalty program enrollment improves 40% at checkout -- integrating
  loyalty point bonus into holiday bundle purchase flow
- Replenishment reminders had 9.5% CTR -- scheduling pre-holiday
  "stock up before your trip" reminders for consumables

Holiday Campaign Plan:
Phase 1: Pre-Holiday (October)
  - "Gear Up for Winter" content series via email
  - Replenishment reminders for consumables before holiday trips
  - Loyalty program double-points event announcement

Phase 2: Peak Holiday (November-December)
  - Holiday gift bundles with automatic loyalty enrollment at checkout
  - Gift guide content (email + social + blog)
  - Retargeting past purchasers with "complete your kit" offers

Phase 3: Post-Holiday (January)
  - New Year outdoor resolution campaign
  - Post-gift usage tips for recipients (new customer nurture)
  - Review request sequence for holiday purchases
```

Notice what happened: the plugin did not start from generic holiday campaign best practices. It started from GreenPeak's own data — what has worked, what has not, and what structural investments (loyalty program, post-purchase email) are already in place. The holiday campaign builds on the existing system rather than starting over.

### The Compounding Effect

Each cycle through the loop generates new insights that improve the next cycle:

- **Cycle 1**: Baseline metrics established, KPI framework built, first campaigns launched
- **Cycle 2**: Performance data from Cycle 1 informs budget reallocation; early insights saved
- **Cycle 3**: Insights from Cycles 1-2 shape strategy; efficiency-ranked budget allocation becomes possible
- **Cycle 4+**: The plugin has enough historical data to project trends, predict seasonal patterns, and recommend preemptive actions

By Cycle 4, you are no longer planning campaigns from first principles. You are optimizing a system that has been learning from its own results.

---

## 7. KPI Frameworks by Business Model

The plugin's KPI framework engine (`kpi-frameworks.md`) includes complete metric trees for every major business model. Here is a summary of the North Star, primary KPIs, and most relevant plugin modules for each:

| Business Model | North Star | Primary KPIs | Key Plugin Modules |
|---|---|---|---|
| **B2B SaaS** | Net Revenue Retention | MRR, CAC Payback, Logo Churn, Expansion Revenue | Analytics & Insights, Campaign Orchestrator, Content Engine |
| **eCommerce / DTC** | Customer Lifetime Value | AOV, Repeat Purchase Rate, CAC, Blended ROAS | Analytics & Insights, Paid Advertising, CRO |
| **Local Business** | Monthly Revenue | Foot Traffic, Phone Calls, Review Rating, Local Pack Rank | Analytics & Insights, Reputation Management, SEO |
| **Marketplace** | Gross Merchandise Volume | Take Rate, Liquidity Rate, CAC (both sides), Time to First Transaction | Analytics & Insights, Growth Engineering, Funnel Architect |
| **Lead Gen / B2B Services** | Pipeline Value | MQL-to-SQL Rate, CAC, Deal Velocity, Win Rate | Analytics & Insights, Campaign Orchestrator, Content Engine |
| **Creator / Media** | Audience Growth Rate | Subscribers, Engagement Rate, Revenue per Subscriber | Analytics & Insights, Content Engine, Emerging Channels |
| **Non-Profit** | Donor Lifetime Value | Donation Conversion Rate, Donor Retention Rate, Average Gift Size | Analytics & Insights, Email Marketing, Content Engine |

### Using This Table

When you set up a brand profile, the `business_model.type` field determines which KPI tree template the plugin starts with. You can customize it from there, but the template gives you a professionally structured starting point rather than a blank spreadsheet.

**A few notes on selecting your North Star:**

- **B2B SaaS** uses Net Revenue Retention rather than MRR growth because NRR captures both retention and expansion — the two strongest predictors of long-term SaaS value. A company with 120% NRR can survive even with modest new logo acquisition.

- **eCommerce/DTC** uses Customer Lifetime Value rather than revenue because revenue can grow while unit economics deteriorate. LTV forces you to account for acquisition cost, repeat behavior, and margin together.

- **Local Business** uses Monthly Revenue rather than a marketing-specific metric because for most local businesses, the marketing function is not separated from the business. The owner needs to see how marketing activities connect to money in the register.

- **Marketplace** uses GMV rather than revenue because the platform's health depends on transaction volume across both sides. Take rate (the platform's cut) can be optimized separately once GMV is healthy.

- **Non-Profit** uses Donor Lifetime Value rather than total donations because it accounts for both acquisition and retention. Many non-profits over-invest in new donor acquisition while losing existing donors at unsustainable rates. Donor LTV keeps the focus on the economics that actually matter.

### Complete KPI Trees

The full KPI tree for each business model — with all four levels (North Star, Primary, Supporting, Diagnostic), benchmark ranges, and definitions — is available in `skills/analytics-insights/kpi-frameworks.md`. The reference file includes:

- B2B SaaS KPI Tree with SaaS Quick Ratios (Magic Number, Burn Multiple, Rule of 40)
- eCommerce KPI Tree with channel-level benchmarks
- Marketplace KPI Tree with supply/demand health metrics
- Local Business KPI Tree with Google Business Profile metrics
- DTC Brand KPI Tree with retention-focused metrics
- Industry Benchmark Reference Table comparing CAC Payback, LTV:CAC, Gross Margin, and more across models

---

## 8. How Adaptive Scoring Connects to KPIs

Every piece of content your marketing team produces should be optimized for your actual business objective, not for generic "content quality" metrics. The `adaptive-scorer.py` script makes this connection explicit.

### How It Works

When you score content through the plugin, the adaptive scorer reads your brand profile and adjusts the scoring weights based on three factors:

**1. Industry adjustments** — Each industry has different content priorities. Healthcare content is scored heavily on compliance and readability. eCommerce content is scored heavily on CTAs and SEO. Technology content prioritizes SEO and structure. The scorer references 10 industry-specific weight profiles.

**2. Business model adjustments** — B2B SaaS content needs strong structure and SEO. B2C DTC content needs strong CTAs and readability. Local business content needs dominant SEO. These model-specific weights are blended with industry weights (60% industry-adjusted, 40% model-based).

**3. Goal-based adjustments** — This is where KPIs directly shape content scoring:

| Primary Objective | Scoring Adjustment |
|---|---|
| `lead_generation` | CTA weight boosted +10%, SEO weight boosted +5% |
| `brand_awareness` | Readability weight boosted +10%, SEO weight boosted +5% |
| `conversion` | CTA weight boosted +15%, spam/filler check boosted +5% |
| `thought_leadership` | Readability weight boosted +10%, structure weight boosted +10% |
| `traffic` | SEO weight boosted +15%, readability weight boosted +5% |
| `engagement` | Readability weight boosted +10%, CTA weight boosted +5% |
| `retention` | Readability weight boosted +10%, CTA weight boosted +5% |

### A Practical Example

For GreenPeak Outdoors, the adaptive scorer would compute weights like this:

- **Industry**: Outdoor recreation maps closest to eCommerce — CTA 0.30, SEO 0.25, length 0.10
- **Business model**: B2C_DTC — CTA 0.25, readability 0.20, spam/filler 0.15
- **Goal**: Retention — readability +0.10, CTA +0.05
- **Blended result**: CTA and readability are the dominant scoring dimensions

This means when GreenPeak's marketing team writes a post-purchase email, the scorer will weight call-to-action clarity and readability heavily — because those are what drive repeat purchases. It will weight SEO lightly — because a post-purchase email does not need to rank in search.

Compare this to a B2B SaaS company with a `thought_leadership` objective. Their content scorer would weight readability and structure heavily, with CTA scoring de-emphasized. A thought leadership blog post should be insightful and well-organized, not aggressively pushing a demo CTA in every paragraph.

### The Connection to Business Outcomes

The adaptive scorer creates a direct line from business KPIs to content execution:

```
Business Objective (brand profile)
    |
    v
Adaptive Scoring Weights (adaptive-scorer.py)
    |
    v
Content Quality Threshold (content-scorer.py)
    |
    v
Published Content Aligns with Business Goals
    |
    v
KPIs Improve (measured by performance-report)
    |
    v
Insights Saved (campaign-tracker.py)
    |
    v
Scoring Weights Refined (next cycle)
```

For regulated industries, the adaptive scorer adds an additional layer: if `industry.regulated` is set to `true` in the brand profile, the spam/filler weight is automatically boosted. This ensures content in healthcare, finance, legal, and other regulated industries faces stricter scrutiny for unsubstantiated claims, which protects against compliance violations before content is published.

---

## Putting It All Together

The strategy-to-measurement loop is not a theoretical framework. It is the actual architecture of the plugin, implemented across modules and scripts that work together:

| Step | You Do | The Plugin Does |
|---|---|---|
| Define goals | Tell the plugin your business model, revenue, and primary objective | Stores it in the brand profile; every module reads it automatically |
| Build KPI framework | Review and refine the generated KPI tree | Generates a business-model-specific tree with industry benchmarks |
| Plan campaigns | Describe the KPI gap you want to close | Produces phased campaign strategy with budget allocation tied to KPIs |
| Execute | Create content and launch campaigns | Scores content against your adaptive weights; tracks campaigns |
| Measure | Run `/dm:performance-report` | Compares results to targets, detects anomalies, generates recommendations |
| Learn | End your session | Auto-saves insights; next session starts with accumulated knowledge |

The goal is not to automate strategy. Strategy requires human judgment about where to compete, what risks to take, and which trade-offs to accept. The goal is to ensure that judgment is always informed by structured data, and that every decision you make adds to a growing base of institutional knowledge rather than disappearing into a Slack thread.

Start with `/dm:brand-setup`. Define your goals. Let the KPI framework guide your campaign strategy. Measure what matters. Save what you learn. Repeat.

---

*This guide is part of the Digital Marketing Pro plugin (v1.2.0). For the complete KPI tree reference, see `skills/analytics-insights/kpi-frameworks.md`. For industry benchmark data across 22 industries, see `skills/context-engine/industry-profiles.md`.*
