---
name: analytics-insights
description: "Invoke when the user needs performance analysis, KPI frameworks, reporting templates, anomaly investigation, competitive intelligence, attribution modeling, marketing mix modeling, incrementality testing, dark social measurement, or privacy-first measurement strategy."
---

# Analytics & Insights

## When to Use This Skill

Activate this module when the user's request involves any of the following:

- **KPI Frameworks**: Defining the right metrics and success measures for a business model, campaign, or channel
- **Performance Reporting**: Building weekly, monthly, quarterly, or campaign-specific reporting templates
- **Anomaly Investigation**: Diagnosing sudden drops or spikes in traffic, conversions, or other metrics
- **Competitive Intelligence**: Analyzing competitor strategies, share of voice, positioning, and performance
- **Attribution Modeling**: Determining how credit for conversions is assigned across marketing touchpoints
- **Marketing Mix Modeling (MMM)**: Estimating the impact of each marketing channel on overall business outcomes
- **Incrementality Testing**: Designing experiments to measure the true causal impact of marketing activities
- **Dark Social Measurement**: Tracking and attributing traffic from private sharing channels (DMs, Slack, email forwards)
- **Privacy-First Measurement**: Adapting measurement strategies for a cookieless, privacy-regulated environment
- **Dashboard Design**: Structuring dashboards for different stakeholder audiences

**Trigger phrases**: "KPIs," "metrics," "reporting," "dashboard," "why did traffic drop," "anomaly," "competitor analysis," "competitive intelligence," "attribution," "marketing mix model," "MMM," "incrementality," "lift test," "dark social," "cookieless," "privacy-first," "ROAS," "ROI," "performance," "what happened to our numbers"

## Brand Context (Auto-Applied)

Before producing any marketing output from this module:

1. **Check session context** — The active brand summary was output at session start. Use the brand name, industry, voice settings, channels, goals, compliance, and competitors shown there.
2. **If you need the full profile**, read: `~/.claude-marketing/brands/{slug}/profile.json`
3. **Apply brand voice** — Formality, energy, humor, authority levels must shape all content tone and word choices
4. **Check compliance** — Auto-apply rules for brand's target_markets and industry using `skills/context-engine/compliance-rules.md`
5. **Reference industry benchmarks** — Consult `skills/context-engine/industry-profiles.md` for the brand's industry
6. **Use platform specs** — Reference `skills/context-engine/platform-specs.md` for character limits and format requirements
7. **Check campaign history** — Run `python campaign-tracker.py --brand {slug} --action list-campaigns` before planning new work
8. **If no brand exists**, say: "No brand profile found. Use /dm:brand-setup to create one, or I can proceed with general best practices."

Do not ask the user for information that already exists in their brand profile.

## Required Context

Before executing analytics work, gather:

1. **Business Model**: SaaS, e-commerce, lead gen, marketplace, etc. (determines the KPI framework)
2. **Business Maturity**: Startup, growth, scale-up, or enterprise (determines measurement sophistication)
3. **Current Metrics**: What is already being tracked? What tools are in use?
4. **Analytics Stack**: Google Analytics (UA/GA4), ad platforms, CRM, BI tools, CDPs, tag managers
5. **Data Availability**: How much historical data exists? What granularity?
6. **Reporting Audience**: Who receives reports? (Exec/C-suite, marketing team, board, clients)
7. **Known Issues**: Any known data quality problems, tracking gaps, or recent changes?
8. **Geographic Scope**: Single market or multi-market (affects privacy regulations)
9. **Privacy Constraints**: GDPR, CCPA, ATT — what consent mechanisms are in place?
10. **Specific Question**: If investigating an anomaly, what exactly changed and when?

For anomaly investigation, prioritize speed. Ask for the specific metric, timeframe, and any known changes. For strategic measurement work, gather the full context.

## Capabilities

- **KPI Tree Generation per Business Model**: Hierarchical metric frameworks that connect top-level business goals to actionable marketing metrics, customized for SaaS, e-commerce, lead gen, marketplace, subscription, media, and other models
- **Standardized Reporting**: Templates for weekly performance snapshots, monthly strategic reviews, quarterly business reviews, and campaign post-mortems — each designed for different stakeholder audiences
- **Anomaly Detection and Root Cause Diagnosis**: Structured diagnostic framework for investigating sudden metric changes — systematic elimination of causes (tracking issues, external events, algorithm changes, seasonality, competitive actions, internal changes)
- **Competitive Intelligence Framework**: Methodology for monitoring competitor activity across channels (SEO, paid, social, content, PR), estimating competitor spend, and benchmarking performance
- **Marketing Mix Modeling (MMM) Guidance**: Framework for understanding channel-level contribution to business outcomes, including data requirements, model design considerations, and result interpretation
- **Incrementality Test Design**: Experiment design for geo-based lift tests, holdout tests, conversion lift studies, and matched-market tests to measure true causal marketing impact
- **Dark Social Tracking**: Methods for measuring private sharing activity (link shorteners, UTM-equipped sharing buttons, dedicated landing pages, survey-based attribution) and estimating dark social contribution
- **Cookieless Attribution**: Privacy-first attribution approaches including server-side tracking, first-party data strategies, modeled conversions, media mix modeling, and probabilistic methods
- **Privacy-First Measurement Stack**: Complete measurement architecture designed for GDPR/CCPA compliance, iOS ATT, cookie deprecation, and evolving privacy regulations
- **Dashboard Architecture**: Stakeholder-appropriate dashboard design with metric hierarchy, visualization best practices, and alert configuration

## Process

**Primary Workflow: Measurement Framework & Reporting**

1. **Business Context & Goal Alignment**
   - Classify the business model and maturity stage
   - Identify the north star metric (the single metric most tied to business value)
   - Map business goals to marketing objectives to tactical metrics (KPI tree)
   - Determine reporting audience and their decision-making needs

2. **KPI Tree Construction**
   - Start with the top-level business goal (revenue, growth, profitability)
   - Break into marketing contribution metrics (marketing-sourced revenue, CAC, LTV)
   - Decompose into channel-level metrics (channel CPA, ROAS, conversion rate)
   - Add leading indicators (traffic, engagement, pipeline, MQLs)
   - For each KPI, define:
     - **Definition**: Exactly how it is calculated (no ambiguity)
     - **Source**: Where the data comes from
     - **Benchmark**: Target or industry benchmark
     - **Cadence**: How often it is reviewed
     - **Owner**: Who is responsible for this metric
   - Limit the framework to 15-25 KPIs total — more causes metric fatigue and diluted focus

3. **Reporting Template Design**
   - **Weekly Snapshot** (for marketing team):
     - Key metrics vs. target (traffic, leads, conversions, spend, CPA)
     - Week-over-week trends with directional indicators
     - Top 3 wins and top 3 concerns
     - Action items for the coming week
   - **Monthly Strategic Review** (for marketing leadership):
     - Month-over-month and year-over-year performance
     - Channel contribution breakdown
     - Funnel conversion rate analysis
     - Budget utilization and efficiency metrics
     - Strategic insights and recommendations
   - **Quarterly Business Review** (for executive/board):
     - Marketing contribution to business goals
     - CAC, LTV, and payback period trends
     - Competitive positioning update
     - Next quarter strategic priorities
   - **Campaign Report** (per campaign):
     - Performance vs. pre-defined KPIs
     - Channel-by-channel analysis
     - Creative and audience performance
     - Learnings and recommendations

4. **Anomaly Investigation Protocol**
   When a user reports a sudden metric change, follow this diagnostic sequence:

   - **Step 1: Verify the Data**
     - Is the tracking code still firing correctly?
     - Did a tag manager change, consent tool update, or analytics filter change occur?
     - Check for platform outages or reporting delays
     - If data is corrupted, fix tracking first — do not analyze bad data

   - **Step 2: Define the Anomaly Precisely**
     - Which metric changed? By how much? Over what time period?
     - Is it all traffic or a specific segment (channel, device, geography, page)?
     - Did it happen suddenly or gradually?

   - **Step 3: Check External Factors**
     - Google algorithm update (check SEMrush Sensor, MozCast)
     - Industry news or seasonal patterns
     - Competitor activity changes
     - Platform policy or feature changes

   - **Step 4: Check Internal Factors**
     - Website changes (deployments, URL changes, redirects)
     - Content changes (published, removed, or modified)
     - Campaign changes (launched, paused, budget shifted)
     - Technical issues (site speed, server errors, mobile rendering)

   - **Step 5: Isolate and Diagnose**
     - Cross-reference the anomaly with the identified factors
     - Determine the most likely root cause
     - Estimate the impact and expected recovery timeline
     - Recommend corrective actions

5. **Privacy-First Measurement Architecture**
   - Audit current measurement for privacy compliance gaps
   - Design a measurement stack that works without third-party cookies:
     - Server-side tracking for owned touchpoints
     - First-party data enrichment strategy
     - Privacy-compliant consent management
     - Platform-native conversion APIs (Meta CAPI, Google Enhanced Conversions)
     - Modeled conversions for attribution gaps
     - Marketing mix modeling for channel-level effectiveness
     - Incrementality testing for causal validation
   - Create a transition plan from current state to privacy-first architecture
   - Account for iOS ATT impact on iOS-heavy audience segments

## Reference Files

- `kpi-frameworks.md` — Business-model-specific KPI trees, metric definitions, benchmark databases, and north star metric selection guide
- `reporting-templates.md` — Weekly, monthly, quarterly, and campaign reporting templates with stakeholder-appropriate formatting and visualization guidance
- `anomaly-diagnosis.md` — Diagnostic decision tree, common root causes by metric type, verification checklists, and resolution playbooks
- `competitive-intelligence.md` — Competitor monitoring methodology, tool recommendations, benchmarking frameworks, and competitive response playbooks
- `mmm-framework.md` — Marketing mix modeling data requirements, model design guidance, result interpretation, and optimization recommendations
- `incrementality-testing.md` — Experiment design templates (geo lift, holdout, conversion lift), statistical power calculations, and result analysis frameworks
- `dark-social-tracking.md` — Dark social measurement methods, implementation guides for tracking private shares, and estimation models
- `privacy-first-measurement.md` — Cookieless attribution approaches, consent management architecture, server-side tracking implementation, and privacy regulation compliance guide

## Output Formats

| Deliverable | Format | Description |
|---|---|---|
| KPI Framework | Document + spreadsheet | Hierarchical metric tree with definitions, benchmarks, owners, and cadence |
| Weekly Performance Report | Document / dashboard spec | Templated snapshot of key metrics, trends, wins, concerns, and actions |
| Monthly Strategic Report | Document / dashboard spec | In-depth analysis with channel breakdown, funnel analysis, and recommendations |
| Anomaly Diagnosis Report | Document | Root cause analysis with evidence, impact estimate, and corrective actions |
| Competitive Intelligence Brief | Document + spreadsheet | Competitor overview, channel analysis, share of voice, and strategic implications |
| MMM Readiness Assessment | Document | Data availability audit, model feasibility analysis, and implementation roadmap |
| Incrementality Test Plan | Document | Experiment design, sample size, timeline, hypothesis, and success criteria |
| Measurement Architecture | Document + diagram | Full measurement stack design with privacy compliance and implementation plan |
| Dashboard Specification | Document + wireframe | Dashboard layout, metric selection, visualization types, and alert rules |

## Edge Cases

### Insufficient Data for MMM (<2 Years)
- **Situation**: User wants marketing mix modeling but has less than 2 years of consistent marketing data
- **Approach**: Be honest about the limitation — MMM requires sufficient time-series data to separate signal from noise. With less than 2 years: (1) Start collecting and structuring data now for future modeling. (2) Use simpler channel-level attribution as a bridge. (3) Run incrementality tests to get causal data on key channels. (4) Consider lighter-weight approaches like regression analysis on available data with clear caveats about confidence levels. (5) Build toward MMM readiness with a data collection roadmap. Do not attempt to build a full MMM on insufficient data — the results will be misleading and potentially harmful to budget decisions.

### iOS ATT Destroying Attribution
- **Situation**: Significant portion of conversions are untrackable due to iOS App Tracking Transparency opt-outs, making attribution data unreliable
- **Approach**: Acknowledge the gap explicitly rather than pretending attribution data is still complete. Implement: (1) Platform conversion APIs (Meta CAPI, Google Enhanced Conversions) to recover some signal. (2) Server-side tracking for owned touchpoints. (3) Modeled conversions using platform statistical models (with appropriate skepticism about platform self-reporting). (4) First-party data matching where consent exists. (5) Marketing mix modeling as a complement to click-based attribution. (6) Incrementality testing for high-spend channels. (7) Survey-based attribution ("how did you hear about us?") as a qualitative check. The goal is triangulation — no single method is sufficient; combine multiple approaches.

### Dark Social Dominating Referral Traffic
- **Situation**: Large portion of "direct" traffic is actually from private sharing (Slack, WhatsApp, email forwards, Discord) and attribution is blind
- **Approach**: Estimate dark social impact by analyzing "direct" traffic to non-homepage URLs (people rarely type deep URLs directly). Implement measurement improvements: (1) Add social sharing buttons with UTM parameters to track shared links. (2) Use link shorteners with tracking for shareable content. (3) Create dedicated landing pages for community/sharing use cases. (4) Add "how did you find this?" surveys to key conversion points. (5) Monitor content share velocity using social listening tools. (6) Accept that some dark social will remain unmeasured and build that uncertainty into reporting. (7) Consider investing more in dark-social-friendly channels (community, word-of-mouth, referral) even without perfect measurement.

### Multi-Touch B2B Attribution Across 12+ Month Cycles
- **Situation**: B2B enterprise deals take 12-24 months with dozens of touchpoints across multiple stakeholders, making traditional attribution models meaningless
- **Approach**: Abandon pure last-touch or first-touch models — neither represents reality. Implement: (1) Account-based attribution that measures touchpoints at the account level, not individual level. (2) Influence-based reporting that shows which channels contributed to pipeline, even if they didn't "source" the deal. (3) Weight models toward time-decay with higher weights on recent high-intent touchpoints. (4) Use self-reported attribution from sales team and buyer surveys as a complement to digital tracking. (5) Measure channel effectiveness by pipeline velocity (does this channel accelerate deals?) not just by sourcing. (6) Accept that perfect attribution is impossible for complex B2B and focus on directional insights rather than false precision.

### Regulated Data Handling
- **Situation**: User is in healthcare (HIPAA), financial services, education (FERPA), or other industries with strict data handling regulations
- **Approach**: Before any analytics implementation, flag the regulatory context. Ensure: (1) PII is never passed through analytics platforms without proper consent and processing agreements. (2) Data storage complies with regional requirements (data residency). (3) Consent management is explicit and granular. (4) Analytics vendors have appropriate compliance certifications (SOC 2, BAA for HIPAA, etc.). (5) User-level tracking is replaced with cohort or aggregate analysis where required. (6) Data retention policies are documented and enforced. Recommend involving a compliance officer or legal counsel for any measurement architecture in regulated industries. Never assume general analytics best practices are compliant in regulated contexts.

## Related Skills

- **Campaign Orchestrator** — For translating analytics insights into campaign optimizations, budget reallocation, and strategic decisions
- **Funnel Architect** — For connecting funnel-stage metrics to the KPI framework and diagnosing conversion rate anomalies
- **Content Engine** — For measuring content performance, identifying content decay, and informing content strategy with data
- **AEO/GEO Intelligence** — For tracking AI visibility metrics and incorporating AI citation data into the measurement framework
- **Audience Intelligence** — For validating persona hypotheses with behavioral data and building data-driven segments
- **Digital PR & Authority** — For measuring earned media impact, backlink acquisition, and share of voice
