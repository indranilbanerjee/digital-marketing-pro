# Data Analysis & Insights

How Digital Marketing Pro collects, stores, and leverages marketing data across sessions to make every recommendation smarter than the last.

**Audience:** Marketing analysts and data-driven marketers who want to understand the plugin's data infrastructure, how insights accumulate, and how to query historical performance for better decision-making.

---

## Table of Contents

1. [The Data Flow](#1-the-data-flow)
2. [Campaign Data Lifecycle](#2-campaign-data-lifecycle)
3. [How Insights Accumulate](#3-how-insights-accumulate)
4. [Adaptive Scoring](#4-adaptive-scoring)
5. [Performance Tracking Over Time](#5-performance-tracking-over-time)
6. [Querying Your Data](#6-querying-your-data)
7. [Limitations](#7-limitations)

---

## 1. The Data Flow

Every piece of marketing work you do with the plugin feeds into a persistent intelligence loop. Data flows from external sources through analysis, gets distilled into actionable insights, and resurfaces in future sessions to inform new strategies.

```
Data Sources (MCP: GA4, HubSpot, Google Ads, Meta, GSC, SEMrush, etc.)
    |
    v
Session Analysis (Claude + specialist agents)
    |
    v
Insights Generated (patterns, anomalies, learnings)
    |
    v
Campaign Tracker (campaign-tracker.py)
    |
    v
Persistent Memory (~/.claude-marketing/brands/{slug}/)
    |
    v
Future Sessions (insights inform new strategies)
```

**What gets stored and where:**

| Data Type | Storage Location | Format |
|-----------|-----------------|--------|
| Campaign plans | `~/.claude-marketing/brands/{slug}/campaigns/` | Individual JSON files + `_index.json` |
| Performance snapshots | `~/.claude-marketing/brands/{slug}/performance/` | Timestamped JSON files |
| Marketing insights | `~/.claude-marketing/brands/{slug}/insights.json` | Rolling 200-entry JSON array |
| Brand profile | `~/.claude-marketing/brands/{slug}/profile.json` | JSON (created via `/dm:brand-setup`) |

The key principle: local files serve as the plugin's memory. Anything worth keeping is saved to `~/.claude-marketing/` so it survives between sessions and informs future work.

---

## 2. Campaign Data Lifecycle

Campaign data moves through three phases: creation, tracking, and historical reference. Each phase builds on the last so the plugin never starts from zero.

### Phase 1: Creating a Campaign

When you run `/dm:campaign-plan`, the plugin generates a complete campaign plan and saves it automatically:

```
You: /dm:campaign-plan

  Plugin creates a structured campaign plan
  Saved: campaigns/q2-retention-20260415.json
  Index updated: campaigns/_index.json
```

The saved campaign file contains the full plan:

```json
{
  "campaign_id": "q2-retention-20260415",
  "created_at": "2026-04-15T10:30:00.000000",
  "updated_at": "2026-04-15T10:30:00.000000",
  "name": "Q2 Retention",
  "status": "planned",
  "channels": ["email", "social_retargeting", "in_app"],
  "budget": "$15,000/month",
  "goals": [
    "Increase repeat purchase rate by 20%",
    "Reduce churn from 8% to 5%",
    "Boost email engagement rate to 35%"
  ],
  "kpis": {
    "repeat_purchase_rate": {"target": 0.42, "baseline": 0.35},
    "churn_rate": {"target": 0.05, "baseline": 0.08},
    "email_open_rate": {"target": 0.35, "baseline": 0.28}
  },
  "timeline": "April 15 - June 30, 2026",
  "segments": ["lapsed_30d", "high_value", "at_risk"],
  "strategy_summary": "Win-back sequence for lapsed buyers, loyalty program for high-value, proactive outreach for at-risk"
}
```

The campaign index (`_index.json`) provides fast lookup without loading every file:

```json
[
  {
    "campaign_id": "q2-retention-20260415",
    "name": "Q2 Retention",
    "status": "planned",
    "channels": ["email", "social_retargeting", "in_app"],
    "created_at": "2026-04-15T10:30:00.000000"
  },
  {
    "campaign_id": "spring-product-launch-20260301",
    "name": "Spring Product Launch",
    "status": "completed",
    "channels": ["paid_search", "social", "email", "influencer"],
    "created_at": "2026-03-01T09:00:00.000000"
  }
]
```

### Phase 2: Tracking Performance

When you run `/dm:performance-report` for an active campaign, the plugin saves a timestamped snapshot:

```
You: /dm:performance-report for the Q2 retention campaign

  Performance snapshot saved: performance/q2-retention-20260415-143022.json
  Compared against original campaign KPIs
  Variance analysis: email open rate +4% above target, churn rate on track
```

A performance snapshot captures metrics at a specific point in time:

```json
{
  "snapshot_id": "q2-retention-20260415-20260501-143022",
  "recorded_at": "2026-05-01T14:30:22.000000",
  "campaign_id": "q2-retention-20260415",
  "period": "Week 1-2 (April 15 - April 30)",
  "metrics": {
    "email_open_rate": 0.32,
    "email_click_rate": 0.08,
    "repeat_purchase_rate": 0.37,
    "churn_rate": 0.07,
    "revenue_from_retained": 12400,
    "cost_per_reactivation": 8.50
  },
  "channel_breakdown": {
    "email": {"spend": 4200, "conversions": 340, "cpa": 12.35},
    "social_retargeting": {"spend": 6100, "conversions": 180, "cpa": 33.89},
    "in_app": {"spend": 1200, "conversions": 95, "cpa": 12.63}
  },
  "vs_kpi": {
    "repeat_purchase_rate": {"target": 0.42, "actual": 0.37, "variance": -0.05},
    "churn_rate": {"target": 0.05, "actual": 0.07, "variance": +0.02},
    "email_open_rate": {"target": 0.35, "actual": 0.32, "variance": -0.03}
  }
}
```

### Phase 3: Building on History

This is where persistent data pays off. When you plan a new campaign, the plugin checks what came before:

```
You: Plan a Q3 campaign

  Plugin checks campaigns/_index.json
  Loads Q2 retention campaign results
  Loads performance snapshots for Q2
  Loads relevant insights from insights.json

  "Based on Q2 data:
   - Email drove 45% of retention revenue at the lowest CPA ($12.35)
   - Social retargeting underperformed at $33.89 CPA
   - In-app notifications matched email efficiency at $12.63 CPA

   Q3 recommendation: Shift $3,000/month from social retargeting to email
   and in-app. Test push notifications as a fourth channel."
```

The plugin does not start from scratch. Every campaign informs the next one.

---

## 3. How Insights Accumulate

The plugin builds a persistent knowledge base of marketing learnings that compounds over time. This happens both automatically and through explicit commands.

### Automatic Saving (SessionEnd Hook)

Every session where marketing work happens, the SessionEnd hook fires and:

1. Summarizes 1-3 key learnings from the session
2. Saves each via `campaign-tracker.py --action save-insight`
3. Tells you what was saved before the session closes

You do not need to do anything. The plugin handles this on its own.

### Insight Types

Each insight is categorized by type so the plugin can filter and retrieve relevant learnings:

| Type | Description | Example |
|------|-------------|---------|
| `session_learning` | A takeaway from work done in this session | "Personalized subject lines increased open rate by 22%" |
| `performance_discovery` | A finding from analyzing metrics | "LinkedIn outperforms Twitter 3:1 on CPA for B2B SaaS" |
| `strategy_adjustment` | A strategic decision based on data | "Shifted 20% of budget from display to email after Q2 review" |
| `competitor_insight` | Intelligence about competitor activity | "Competitor launched weekly podcast, gaining thought leadership share" |

### Insight Data Structure

Each insight stored in `insights.json` follows this format:

```json
{
  "recorded_at": "2026-05-01T16:45:00.000000",
  "type": "performance_discovery",
  "source": "session",
  "insight": "LinkedIn outperforms Twitter 3:1 on CPA for B2B SaaS leads — $24 vs $72 per qualified lead",
  "context": "Analysis of Q2 paid social campaigns across both platforms, 60-day window",
  "actionable": true
}
```

### Worked Example: Learning Accumulation Over 5 Sessions

This is how the plugin compounds knowledge across sessions for a fictional brand, GreenPeak Outdoor Gear.

**Session 1 -- Campaign Planning:**
```
Work done: Q2 retention email campaign planned and saved
Insight saved: "For GreenPeak, email sequences with educational content
  (gear guides, trail tips) convert 3x better than discount-only emails"
```

**Session 2 -- Content Creation:**
```
Work done: Blog articles written and scored for SEO
Insight saved: "Blog posts over 2,000 words rank significantly better for
  outdoor gear keywords — average position 4.2 vs 12.8 for shorter content"
```

**Session 3 -- Performance Review:**
```
Work done: Social media performance analyzed across platforms
Insight saved: "Instagram Reels drive 5x more engagement than static posts
  for this brand — shift content calendar to 60% video"
```

**Session 4 -- Competitor Analysis:**
```
Work done: Competitive landscape audit completed
Insight saved: "Main competitor increased TikTok presence by 300% —
  opportunity to differentiate on YouTube where they're absent"
```

**Session 5 -- Q3 Planning:**
```
Plugin loads all 4 previous insights automatically before planning begins.

Q3 plan reflects accumulated intelligence:
  - Email strategy: education-first sequences (Session 1 learning)
  - Content strategy: long-form blog posts for SEO (Session 2 learning)
  - Social strategy: 60% video content on Instagram (Session 3 learning)
  - Channel expansion: YouTube investment to exploit competitor gap (Session 4 learning)
```

By Session 5, the plugin has a data-informed view of what works for this brand across channels, content formats, and competitive positioning. No institutional knowledge is lost between sessions.

---

## 4. Adaptive Scoring

Content scoring is not one-size-fits-all. The plugin adjusts scoring weights dynamically based on your brand's industry, business model, goals, and regulatory requirements using `adaptive-scorer.py`.

### How It Works

Scoring starts with base weights for each content type, then applies a series of adjustments.

**Base weights by content type:**

| Dimension | Blog | Email | Ad | Landing Page | Social |
|-----------|------|-------|----|-------------|--------|
| readability | 0.20 | 0.25 | 0.20 | 0.15 | 0.25 |
| seo | 0.25 | 0.05 | 0.10 | 0.25 | 0.05 |
| structure | 0.20 | 0.15 | 0.10 | 0.20 | 0.10 |
| cta | 0.10 | 0.30 | 0.35 | 0.25 | 0.25 |
| spam_filler | 0.10 | 0.15 | 0.15 | 0.05 | 0.20 |
| length | 0.15 | 0.10 | 0.10 | 0.10 | 0.15 |

### Adjustment Layers

Four adjustment layers are applied in sequence:

**Layer 1 -- Industry adjustment.** Replaces base weights with industry-specific priorities.
- Healthcare: boosts compliance (spam_filler) and readability
- Technology: boosts SEO and structure
- Ecommerce: boosts CTA and SEO
- Finance: boosts compliance and readability

**Layer 2 -- Business model adjustment.** Blends industry-adjusted weights (60%) with model-specific priorities (40%).
- B2B SaaS: boosts SEO, CTA, and structure
- B2C DTC: boosts CTA, readability, and compliance
- B2B Services: boosts readability, SEO, and structure

**Layer 3 -- Goal adjustment.** Adds incremental weight to dimensions that support the primary marketing objective.
- Lead generation: CTA +0.10, SEO +0.05
- Thought leadership: readability +0.10, structure +0.10
- Brand awareness: readability +0.10, SEO +0.05
- Conversion: CTA +0.15, compliance +0.05

**Layer 4 -- Regulated industry boost.** If the brand profile marks the industry as regulated (healthcare, finance, legal), compliance weight receives an additional +0.10 boost.

All weights are normalized to sum to 1.0 after all adjustments.

### Worked Example: Healthcare B2B (Thought Leadership Goal)

Starting point -- blog post base weights:

```
readability: 0.20    seo: 0.25    structure: 0.20
cta: 0.10            spam_filler: 0.10    length: 0.15
```

After Layer 1 -- Healthcare industry adjustment:

```
readability: 0.25    seo: 0.25    structure: 0.20
cta: 0.10            spam_filler: 0.25    length: 0.15
                                  ^^^^
               (compliance weight increased for healthcare)
```

After Layer 2 -- B2B Services model blending (60/40):

```
readability: 0.23    seo: 0.23    structure: 0.22
cta: 0.06            spam_filler: 0.21    length: 0.09
                                  ^^^^
                     (structure boosted for B2B Services)
```

After Layer 3 -- Thought leadership goal adjustment:

```
readability: 0.33    seo: 0.23    structure: 0.32
cta: 0.06            spam_filler: 0.21    length: 0.09
^^^^                               ^^^^
(readability +0.10)         (structure +0.10)
```

After Layer 4 -- Regulated industry compliance boost:

```
readability: 0.33    seo: 0.23    structure: 0.32
cta: 0.06            spam_filler: 0.31    length: 0.09
                                  ^^^^
                     (compliance +0.10 for regulated industry)
```

Final adaptive weights (normalized to 1.0):

```
readability: 0.25    seo: 0.17    structure: 0.24
cta: 0.04            spam_filler: 0.23    length: 0.07
```

**What this means in practice:** Content scored for this brand penalizes non-compliant language heavily (spam_filler at 0.23 vs. the default 0.10) and rewards clear, well-structured writing (readability + structure = 0.49 combined). CTA and length become less important because healthcare thought leadership is about trust and authority, not aggressive calls to action. The scoring reflects exactly what matters for this brand.

### Running the Adaptive Scorer

To see computed weights for any brand and content type:

```bash
python adaptive-scorer.py --brand greenpeak --type blog --weights-only
```

Output:

```json
{
  "brand": "greenpeak",
  "content_type": "blog",
  "adaptive_weights": {
    "readability": 0.22,
    "seo": 0.27,
    "structure": 0.20,
    "cta": 0.12,
    "spam_filler": 0.10,
    "length": 0.09
  },
  "adjustments_applied": [
    "industry:ecommerce",
    "model:B2C_DTC",
    "goal:brand_awareness"
  ]
}
```

---

## 5. Performance Tracking Over Time

Performance snapshots are not just single data points. When you take multiple snapshots for the same campaign, they form a time series that reveals trends.

### How Snapshots Build a Picture

Each time you run `/dm:performance-report`, a new timestamped file is saved:

```
performance/
  q2-retention-20260415-20260422-100000.json   (Week 1)
  q2-retention-20260415-20260429-100000.json   (Week 2)
  q2-retention-20260415-20260506-100000.json   (Week 3)
  q2-retention-20260415-20260513-100000.json   (Week 4)
```

With multiple snapshots, the plugin can:

- **Compare early vs. late performance.** Week 1 metrics versus Week 4 metrics for the same campaign show whether your strategy is gaining or losing momentum.
- **Detect trends.** "CTR declining 2% week-over-week across the last three snapshots -- time to refresh creative."
- **Validate KPI targets.** "Repeat purchase rate at Week 4 is 0.40 vs. the target of 0.42 -- within striking distance but email click rates need a lift."
- **Identify inflection points.** "Performance spiked in Week 2 after we launched the educational email series -- confirms the insight from Session 1."

### Example: Trend Analysis Across 4 Weeks

```
Metric: Email Open Rate
  Week 1: 28%  (baseline)
  Week 2: 32%  (+4%, new subject line strategy)
  Week 3: 31%  (-1%, slight regression)
  Week 4: 35%  (+4%, segmentation refinement)

Plugin analysis: "Open rate trending upward with a 7-point improvement
over 4 weeks. The dip in Week 3 coincided with a holiday weekend.
Subject line personalization and list segmentation are both contributing
to gains."
```

```
Metric: Social Retargeting CPA
  Week 1: $38.20
  Week 2: $35.10  (-8%)
  Week 3: $34.80  (-1%)
  Week 4: $33.89  (-3%)

Plugin analysis: "CPA declining but plateauing. Current $33.89 is still
2.7x the email CPA of $12.35. Consider reallocating budget unless
retargeting serves a brand awareness purpose not captured in direct CPA."
```

### Best Practices for Performance Tracking

- **Take snapshots at regular intervals.** Weekly or bi-weekly snapshots create the cleanest time series.
- **Use the same campaign ID.** Snapshots for the same campaign are linked by the campaign ID in the filename, enabling automatic comparison.
- **Include channel breakdowns.** When MCP servers are connected, ask for per-channel metrics so the plugin can identify which channels are driving (or dragging) performance.
- **Let the plugin compare.** Ask "How is Q2 retention performing compared to Week 1?" and the plugin will load both snapshots and run the comparison.

---

## 6. Querying Your Data

You do not need to know file paths or JSON structure. Ask questions in natural language and the plugin retrieves the relevant data.

### Campaign Queries

```
"What campaigns have we run this quarter?"
```
The plugin checks `campaigns/_index.json` and filters by date to list all campaigns created in the current quarter, including their status and channels.

```
"What was our best-performing campaign?"
```
The plugin loads performance snapshots, compares key metrics (ROI, CPA, conversion rate), and identifies the top performer with supporting data.

```
"Show me the full plan for our Spring Product Launch"
```
The plugin locates the campaign by name in the index, loads the full JSON file, and presents the plan in a readable format.

### Insight Queries

```
"What did we learn about email performance?"
```
The plugin calls `campaign-tracker.py --action get-insights` and filters for insights mentioning email, then summarizes the findings.

```
"Show me insights about our competitor Acme Corp"
```
The plugin filters insights by type `competitor_insight` and by keyword to surface everything recorded about that competitor.

```
"What strategy changes have we made this year?"
```
The plugin filters for `strategy_adjustment` type insights and presents them chronologically.

### Performance Queries

```
"How has our repeat purchase rate trended?"
```
The plugin loads multiple performance snapshots containing repeat purchase data and presents the trend over time.

```
"Compare last month's performance to this month"
```
The plugin identifies the most recent snapshots from each period and runs a side-by-side comparison with variance analysis.

```
"Which channel has the lowest CPA?"
```
The plugin examines channel breakdowns across recent performance snapshots and ranks channels by cost per acquisition.

### Cross-Reference Queries

The most powerful queries combine multiple data types:

```
"Based on everything we know, where should we increase budget next quarter?"
```
The plugin loads campaign history, performance trends, and accumulated insights, then synthesizes a recommendation grounded in your actual data rather than generic benchmarks.

---

## 7. Limitations

Understanding what the data layer does not do is just as important as knowing what it does.

| Limitation | Impact | Workaround |
|-----------|--------|------------|
| Insights are text-based, not structured metrics | Cannot auto-calculate trends from insight text alone | Use specific numbers in performance reports; the plugin can parse them from snapshots |
| 200-entry insight cap | Very old insights roll off the buffer as new ones are added | Most recent insights are the most relevant; critical learnings resurface in campaign plans |
| No automated A/B test tracking | Must manually record test results and outcomes | Ask the plugin to record a test result as an insight after each test concludes |
| No cross-brand insight sharing | Cannot auto-apply learning from Brand A to Brand B | Manually reference across brands: "Apply what we learned from Brand A's email strategy" |
| Performance data not aggregated | Each snapshot is an independent file, not a time-series database | Ask the plugin to compare multiple snapshots; it loads and compares them on the fly |
| MCP server dependency for live data | Without connected MCP servers, the plugin relies on manually provided metrics | Connect GA4, GSC, and ad platform MCP servers for automated data ingestion |
| No automatic anomaly alerting | The plugin detects anomalies during analysis but does not push alerts between sessions | Run `/dm:performance-report` regularly to catch issues; the plugin flags anomalies when it sees them |

### What This Means in Practice

The data layer is a **persistent memory**, not a data warehouse. It stores decisions, learnings, and snapshots in a lightweight format that helps the plugin make better recommendations over time. For heavy-duty analytics (multi-dimensional pivots, statistical significance testing, real-time dashboards), use your dedicated analytics tools and bring the findings into the plugin as context.

The sweet spot is using the plugin's data layer for **institutional knowledge** -- the kind of strategic context that usually lives in someone's head and gets lost when they leave the team. Campaign rationale, channel performance patterns, competitor observations, voice guidelines, what worked and what did not. That is what compounds across sessions and makes each recommendation sharper.

---

*Digital Marketing Pro v1.2.0 -- Data Analysis & Insights Guide*
