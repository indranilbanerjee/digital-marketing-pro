# Historical Data & Campaign Memory

**Version 1.2.0** | A guide to how Digital Marketing Pro remembers, learns, and applies past marketing work

Digital Marketing Pro does not start from scratch every session. It builds a persistent memory of your campaigns, performance metrics, and strategic learnings --- then uses that history to make every future recommendation sharper. This guide explains what gets saved, how it informs new work, and how to query and manage your marketing data over time.

---

## Table of Contents

1. [What Gets Saved Automatically](#1-what-gets-saved-automatically)
2. [How History Informs New Work](#2-how-history-informs-new-work)
3. [Querying Past Data](#3-querying-past-data)
4. [Campaign Post-Mortems](#4-campaign-post-mortems)
5. [Cross-Session Learning in Practice](#5-cross-session-learning-in-practice)
6. [Data Management](#6-data-management)

---

## 1. What Gets Saved Automatically

Every marketing session generates persistent data. You do not need to remember to save anything --- the plugin handles it. There are three types of data that accumulate over time.

### Campaign Plans

When you create a campaign through `/dm:campaign-plan`, the Campaign Orchestrator agent, or any workflow that produces a structured campaign, the full plan is saved automatically.

What gets stored:

- Campaign name, status, and creation date
- Objectives and target KPIs
- Channel mix with budget allocation percentages
- Timeline and milestone dates
- Target audience and segmentation criteria
- Key messaging and creative direction

Campaign plans are written to individual JSON files in your brand's `campaigns/` directory. An index file (`_index.json`) maintains a quick-lookup table of all campaigns with their name, status, date, and channels. This index is what the plugin reads first when checking your history --- it avoids loading every campaign file just to list what you have done.

Campaign plans never expire. Every campaign you create is preserved indefinitely, giving you a complete record of your marketing strategy over time.

### Performance Snapshots

When you run `/dm:performance-report` or any analysis that produces campaign metrics, a timestamped performance snapshot is saved.

What gets stored:

- Campaign ID linking the snapshot to a specific campaign
- The time period the metrics cover
- Channel-level performance data (impressions, clicks, conversions, CPA, ROAS, and others)
- KPI progress against targets
- Notable trends or anomalies flagged during analysis

Each snapshot gets a filename that includes both the campaign ID and a timestamp (for example, `bf-2025-20251201-143022.json`), so you can have multiple snapshots for the same campaign showing how performance evolved over time. This is how the plugin identifies trends --- it compares snapshots chronologically to see whether metrics are improving or declining.

Performance snapshots also never expire. The full history is preserved.

### Session Insights

At the end of every marketing session, the SessionEnd hook automatically saves 1 to 3 key learnings from the work you did. You do not trigger this manually --- it happens in the background when your session closes.

What gets stored:

- The insight itself (a concise, actionable statement)
- The type of insight: `session_learning`, `performance_discovery`, `strategy_adjustment`, or `competitor_insight`
- The source context (what work produced the insight)
- A timestamp for when it was recorded
- Whether the insight is actionable (most are)

Examples of auto-saved insights:

- "Countdown timer in abandonment emails had 3.2x conversion vs standard reminder" (session_learning)
- "Instagram Stories with product demos outperformed static carousel ads 2:1" (performance_discovery)
- "Shifting 15% of Google Ads budget to email retargeting reduced CPA by 22%" (strategy_adjustment)
- "Competitor launched subscription model --- consider loyalty/retention positioning" (competitor_insight)

Insights are stored in a 200-entry rolling buffer. Once you exceed 200 insights, the oldest entries are removed as new ones come in. For most teams, this covers 3 to 6 months of active marketing work. If you need to preserve older insights, see the archiving section in Data Management below.

---

## 2. How History Informs New Work

The plugin does not just store data --- it actively uses it. Every module's workflow includes a step that says: "Check campaign history --- run `campaign-tracker.py --brand {slug} --action list-campaigns` before planning new work." This is baked into the system, not something you need to remember.

Here is how it works in practice.

### Worked Example: "Plan a Black Friday Campaign"

```
You: Plan a Black Friday campaign for GreenPeak

Plugin: Let me check your campaign history...

Found: "Black Friday 2025" campaign (created November 2025)
- Channels: Email (40% budget), Instagram (30%), Google Ads (20%), SMS (10%)
- Results: Email drove 52% of Black Friday revenue
- Top insight: "Countdown timer in abandonment emails had 3.2x
  conversion vs standard reminder"
- Underperformer: Google Ads had $28 CPA (target was $18)

Also found 3 relevant insights:
- "Subscribers who received teaser emails 2 weeks early had 40%
  higher Black Friday spend"
- "Instagram Stories with product demos outperformed static
  carousel ads 2:1"
- "SMS sent at 7am had 3x open rate vs 10am for this audience"

Black Friday 2026 Plan (incorporating learnings):
- Increase email budget to 50% (proven top performer)
- Start teaser campaign 2 weeks early (40% higher spend from
  early teasers)
- Use countdown timer abandonment emails again (3.2x conversion)
- Shift Google Ads budget to Instagram Stories (demo format,
  2:1 better performance)
- Send SMS at 7am (3x open rate)
- Add video demos to Instagram (outperformed carousel)
```

Notice what happened. The plugin did not ask you what worked last year. It already knew. It pulled the prior campaign, found the performance snapshots, searched for relevant insights, and used all of that to build a plan that avoids last year's mistakes and doubles down on what worked.

### What the Intelligence Layer Does Behind the Scenes

When any module or agent makes a recommendation, it follows a five-step decision framework defined in the intelligence layer:

1. **Load brand context** --- pull in voice, industry, compliance, and goals
2. **Check campaign history** --- find past campaigns of the same type
3. **Apply industry benchmarks** --- calibrate recommendations to realistic standards
4. **Check compliance** --- auto-apply geographic and industry regulations
5. **Save learnings** --- capture new insights for future reference

Steps 2 and 5 are where historical data comes in. The system reads from the past and writes to the future, every session.

---

## 3. Querying Past Data

You do not need to know file paths or JSON structures to access your history. Just ask in plain language.

### Campaign History Queries

```
"What campaigns have we run?"
```
Lists all campaigns from the index with status, date, and channels.

```
"What campaigns did we run in Q2?"
```
Filters the campaign index by date range (April through June).

```
"Show me the details of our product launch campaign"
```
Loads the full campaign plan file, including objectives, budget, channels, timeline, and KPIs.

```
"Which campaigns are still active?"
```
Filters by status field (planned, active, completed, paused).

### Performance Queries

```
"How did our last product launch perform?"
```
Finds the most recent launch-type campaign, loads its performance snapshots, and summarizes the results against targets.

```
"What's our historical CPA on Google Ads?"
```
Aggregates CPA data across all performance snapshots that include Google Ads metrics.

```
"Compare Q1 and Q2 email performance"
```
Pulls performance snapshots from both quarters and presents a side-by-side comparison of key email metrics.

```
"Are our Instagram engagement rates improving?"
```
Loads chronological performance snapshots with Instagram data and identifies the trend direction.

### Insight Queries

```
"What did we learn about email marketing?"
```
Searches the insights buffer for entries related to email --- subject lines, open rates, sequences, deliverability, and anything else tagged with email context.

```
"Show me what worked for Instagram last year"
```
Filters insights and performance data for Instagram-specific learnings, sorted by date.

```
"What competitor insights do we have?"
```
Returns all insights with type `competitor_insight` from the rolling buffer.

```
"What strategic changes have we made recently?"
```
Returns insights with type `strategy_adjustment`, most recent first.

### Combining Queries

You can also ask compound questions:

```
"Based on everything we know, what channels should we prioritize
for Q3?"
```

The plugin pulls campaign performance data, channel-level metrics from snapshots, and strategic insights, then synthesizes a recommendation grounded in your actual history rather than generic advice.

---

## 4. Campaign Post-Mortems

Post-mortems turn completed campaigns into institutional knowledge. When you run a post-mortem, the plugin loads the original campaign plan, all associated performance snapshots, and relevant insights --- then produces an honest assessment of what worked, what did not, and what to do differently next time.

### How Post-Mortem Data Feeds the Learning Loop

```
You: Run a post-mortem on the Q2 Retention Campaign

Plugin:
Campaign: Q2 Retention Campaign (April--June 2026)
Objective: Increase repeat purchase rate from 18% to 25%
Actual Result: Achieved 22% (partially met)

What Worked:
- Post-purchase email sequence: 45% open rate, 8% click rate
- Replenishment reminders: 9.5% CTR (exceeded 8% target)
- Educational content in emails: 3x better than discount-only

What Didn't:
- Loyalty program enrollment: 12% (missed 15% target)
- Social retargeting: $22 CPA (over $15 target)
- SMS re-engagement: 2% conversion (below 5% target)

Learnings Saved:
1. "Education-first email approach converts 3x better than
   discount-only for DTC outdoor"
2. "Loyalty sign-up friction: reducing form fields from 6 to 3
   expected to improve enrollment 30-40%"
3. "Social retargeting underperforms for this audience ---
   consider shifting to email retargeting"

These learnings automatically inform the Q3 campaign plan.
```

Those three learnings are saved as insights with type `session_learning`. The next time you plan a retention campaign, the plugin will surface them. It will recommend the education-first email approach, suggest simplifying the loyalty enrollment form, and steer budget away from social retargeting toward email retargeting --- all based on evidence from your own data, not generic best practices.

### Running Post-Mortems at the Right Time

Post-mortems are most valuable when you have at least one performance snapshot to compare against the original plan. A campaign plan without metrics is just a strategy review. The combination of plan plus performance is what produces actionable learnings.

Good times to run a post-mortem:

- Immediately after a campaign ends, while context is fresh
- At the end of each quarter, reviewing all campaigns from that period
- Before planning a sequel campaign (for example, Black Friday 2026 before you plan Black Friday 2027)
- When performance data from MCP integrations (Google Analytics, Meta Ads, and others) is available for validation

---

## 5. Cross-Session Learning in Practice

The real power of campaign memory shows up across sessions. Each session adds to the knowledge base, and subsequent sessions benefit from everything that came before.

### How It Builds Over Time

```
Session 1 (Monday): Created Q3 content campaign plan
  Saved: Campaign plan with 4 content pillars, 3 channels,
         monthly budget of $12,000
  Insight: "Video content pillar should lead based on Q2
           engagement data"

Session 2 (Wednesday): Reviewed week 1 performance
  Saved: Performance snapshot --- blog traffic up 18%, email
         open rate at 34%
  Insight: "How-to blog posts drive 2.4x more organic traffic
           than thought leadership pieces"
  Insight: "Tuesday 10am send time outperforming Thursday 2pm
           by 22% open rate"

Session 3 (Friday): Ran competitor analysis
  Saved: Competitor insight on rival's new content strategy
  Insight: "Competitor X shifted to short-form video --- gap
           in long-form educational content we can fill"

Session 4 (Next Monday): Started planning month 2 of campaign
  Plugin automatically loads:
  - Original campaign plan from Session 1
  - Performance snapshot from Session 2
  - All 4 insights from Sessions 1-3

  Result: Month 2 plan shifts budget toward how-to blog content
  (2.4x traffic), moves email sends to Tuesday 10am (22% better),
  and adds long-form educational video to fill the gap the
  competitor left behind.
```

No one had to remember any of this. The plugin loaded it, surfaced the relevant pieces, and incorporated them into the new plan.

### The Intelligence Layer Across Sessions

The intelligence layer defines a consistent pattern that every module follows:

1. **Load context** --- brand profile, voice, compliance
2. **Check history** --- campaigns, performance, insights
3. **Apply benchmarks** --- industry standards adjusted for brand specifics
4. **Check compliance** --- regulations for your markets and industry
5. **Save learnings** --- new insights from the current session

Steps 2 and 5 are the memory loop. Step 2 reads from previous sessions. Step 5 writes for future sessions. Over weeks and months, this builds a body of marketing intelligence that is specific to your brand, grounded in your actual performance data, and constantly refined.

---

## 6. Data Management

### Where Your Data Lives

All persistent marketing data is stored locally on your machine at `~/.claude-marketing/brands/{slug}/`. Each brand has its own isolated directory.

```
~/.claude-marketing/brands/{slug}/
  profile.json                            Brand identity and settings
  insights.json                           200 most recent learnings
  campaigns/
    _index.json                           All campaigns (quick lookup)
    bf-2025-20251101.json                 Full campaign plan
    q2-retention-20260401.json            Full campaign plan
  performance/
    bf-2025-20251201-143022.json          Performance snapshot
    q2-retention-20260501-091530.json     Performance snapshot
    q2-retention-20260601-100215.json     Later snapshot (same campaign)
```

This location is outside the plugin directory intentionally. Plugin updates, reinstalls, and cache clears will not touch your brand data.

### Data Limits

| Data type              | Limit                | What happens at the limit                  |
|------------------------|----------------------|--------------------------------------------|
| Campaign plans         | No limit             | All campaigns preserved indefinitely       |
| Performance snapshots  | No limit             | All snapshots preserved indefinitely       |
| Session insights       | 200-entry rolling buffer | Oldest entries removed when new ones added |
| Brand profiles         | No limit             | Create as many brands as you need          |

The 200-insight limit is designed to keep the most relevant learnings accessible without the file growing indefinitely. At a pace of 2 to 3 insights per session and 3 to 4 sessions per week, the buffer covers roughly 4 to 6 months of marketing work.

### Backup Recommendations

Your `~/.claude-marketing/` directory contains all of your marketing intelligence --- brand profiles, campaign history, performance data, and accumulated learnings. Treat it like any other important business data.

**Basic backup:** Copy the entire `~/.claude-marketing/brands/` directory to a backup location on a regular schedule. Weekly is a good cadence for active marketing teams.

**Cloud sync:** Point a cloud sync service (OneDrive, Dropbox, Google Drive, or iCloud) at the `~/.claude-marketing/` folder. This gives you automatic, continuous backup with version history.

**Team sharing:** If multiple team members need access to the same brand history, the simplest approach is to sync the brand's directory through a shared cloud folder. Each person's plugin will read from and write to the same files.

### Archiving a Brand

When you stop actively marketing a brand but want to preserve its history:

```
Rename the directory:
  ~/.claude-marketing/brands/greenfield-coffee
  ~/.claude-marketing/brands/_archived-greenfield-coffee
```

The underscore prefix is a convention that keeps archived brands out of the active brand list while preserving all data. If you need to reactivate the brand later, rename it back.

### Resetting Specific Data

Sometimes you want a clean slate for part of a brand's data without losing everything.

**Reset insights only** (start fresh with learnings):
Delete `insights.json`. The file will be recreated automatically the next time the SessionEnd hook saves an insight.

**Reset campaign history** (remove all campaign records):
Delete `campaigns/_index.json` and all campaign JSON files in the `campaigns/` directory. Performance snapshots in `performance/` can be deleted separately or kept.

**Reset everything for a brand** (complete fresh start):
Delete the entire brand slug directory. Run `/dm:brand-setup` to create a new profile from scratch.

### Preserving Insights Beyond the 200-Entry Buffer

If your team generates insights faster than the buffer can hold them, or you want a permanent archive:

1. Periodically copy `insights.json` to a dated backup (for example, `insights-2026-Q1.json`) in a separate archive directory
2. The plugin will continue managing the rolling buffer in the original file
3. Your archived files preserve the full history for reference

This is a manual process by design --- most teams find that the 200-entry buffer covers their needs, and older insights naturally become less relevant as strategies evolve.

### Understanding the File Formats

All data files are standard JSON, human-readable, and editable with any text editor. If you ever need to manually correct a campaign name, adjust an insight, or merge data from two sources, you can open the files directly.

Campaign index entries look like this:

```json
{
  "campaign_id": "black-friday-2025-20251101",
  "name": "Black Friday 2025",
  "status": "completed",
  "channels": ["email", "instagram", "google-ads", "sms"],
  "created_at": "2025-11-01T09:30:00"
}
```

Insight entries look like this:

```json
{
  "recorded_at": "2026-01-15T16:42:00",
  "type": "performance_discovery",
  "source": "session",
  "insight": "Tuesday 10am email sends outperform Thursday 2pm by 22% open rate",
  "context": "Q1 content campaign performance review",
  "actionable": true
}
```

These formats are stable across plugin versions. Your data will remain readable and usable through future updates.

---

## Summary

Digital Marketing Pro builds marketing intelligence over time through three persistent data types: campaign plans that capture your strategic decisions, performance snapshots that track results, and session insights that distill learnings. The intelligence layer reads this history before every recommendation and writes new learnings after every session, creating a continuous improvement loop that makes the plugin more valuable the longer you use it.

You do not need to manage any of this manually. Campaigns save when you create them. Performance saves when you analyze it. Insights save when your session ends. The data lives at `~/.claude-marketing/brands/{slug}/`, survives plugin updates, and is yours to back up, archive, or reset as needed.

The best marketing teams learn from their own data. This system makes sure nothing gets lost.

---

*Digital Marketing Pro v1.2.0 --- Built for marketing professionals who want strategy and execution that stays on-brand, every time.*
