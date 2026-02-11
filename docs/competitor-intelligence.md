# Competitor Intelligence Guide

**Digital Marketing Pro v1.2.0** | Turning publicly available data into strategic advantage

Competitor intelligence is not about copying what others do. It is about understanding the market landscape well enough to make smarter decisions --- identifying gaps your competitors have missed, anticipating their next moves, and positioning your brand where competition is weakest and opportunity is highest.

This guide walks you through every aspect of competitive intelligence in Digital Marketing Pro: setting up competitors in your brand profile, running multi-dimensional analyses, interpreting results, responding to competitor moves, and keeping your intelligence current over time.

---

## Table of Contents

1. [Setting Up Competitors in Your Brand Profile](#1-setting-up-competitors-in-your-brand-profile)
2. [Running a Competitive Analysis](#2-running-a-competitive-analysis)
3. [What competitor-scraper.py Captures](#3-what-competitor-scraperpy-captures)
4. [Six Dimensions of Competitive Intelligence](#4-six-dimensions-of-competitive-intelligence)
5. [Responding to Competitor Moves](#5-responding-to-competitor-moves)
6. [Keeping Intelligence Current](#6-keeping-intelligence-current)
7. [Connecting Competitor Insights to Strategy](#7-connecting-competitor-insights-to-strategy)

---

## 1. Setting Up Competitors in Your Brand Profile

Competitor data lives in two places. The summary is stored in your main `profile.json` under a `competitors` array, and the detailed intelligence accumulates in a dedicated `competitors.json` file at `~/.claude-marketing/brands/{slug}/competitors.json`. Both are created and updated automatically as you work.

### Adding competitors during brand setup

When you run `/dm:brand-setup --full`, question 17 asks about your competitive landscape. This is where you provide the initial list:

```
Question 17: Who are your main competitors? (names and URLs)

You:
- TrailPeak Gear (trailpeakgear.com) — direct competitor, strong on Instagram
- REI (rei.com) — aspirational competitor, dominant in SEO
- Backcountry (backcountry.com) — indirect competitor, strong email program
```

The plugin parses your response and stores each competitor with structured fields:

| Field | What it captures | Example |
|-------|-----------------|---------|
| **Name** | Company or brand name | TrailPeak Gear |
| **URL** | Primary website | trailpeakgear.com |
| **Relationship** | How they compete with you | direct, indirect, or aspirational |
| **Strengths** | What they do well | Strong Instagram presence, gear review authority |
| **Weaknesses** | Where they fall short | No TikTok, generic brand voice |
| **Primary channels** | Where they are most active | Instagram, SEO, email |

Quick Setup mode (the default 5-question flow) does not ask about competitors. If you used Quick Setup initially, you can add competitors at any time without re-running the full setup.

### Adding or updating competitors after setup

You do not need to re-run brand setup to manage your competitor list. Just tell the plugin what changed in natural language:

```
You: Add MountainX as a new competitor — they just launched and are
     aggressive on TikTok

Plugin: Added MountainX to your competitor profile:
        - Name: MountainX
        - Relationship: direct (new entrant)
        - Strengths: TikTok-first strategy, aggressive launch
        - Primary channels: TikTok
        Saved to competitors list. Run /dm:competitor-analysis to analyze them.
```

Other updates work the same way:

- "Remove Backcountry from my competitor list --- they pivoted to a different market"
- "Update TrailPeak Gear --- they just launched a YouTube channel with 5K subscribers"
- "Change REI from aspirational to direct --- we now compete for the same keywords"

Every update is persisted to both `profile.json` and `competitors.json`, so the intelligence carries across sessions.

---

## 2. Running a Competitive Analysis

The `/dm:competitor-analysis` command activates a multi-dimensional competitive analysis powered by the competitive-intel agent. Here is what a full session looks like.

### Starting the analysis

```
You: /dm:competitor-analysis

Plugin: I see 3 competitors in your profile:
        1. TrailPeak Gear (direct)
        2. REI (aspirational)
        3. Backcountry (indirect)

        Which competitors should I analyze? And which dimensions?
        - Full analysis (all dimensions)
        - Content strategy only
        - SEO comparison only
        - Social media benchmarking
        - Paid advertising intelligence
        - AI visibility comparison

You: Full analysis on TrailPeak Gear, and SEO comparison with REI
```

### What happens behind the scenes

Once you select competitors and dimensions, several things fire in sequence:

1. **Brand context loads** --- your voice profile, industry, channels, goals, and compliance rules are pulled from `profile.json` so every comparison is anchored to your brand's strategic position.
2. **competitive-intel agent activates** --- this specialist agent handles all competitive dimensions, benchmarking, gap analysis, and strategic recommendations.
3. **competitor-scraper.py runs** --- the script extracts publicly available data from TrailPeak Gear's and REI's websites (page titles, meta descriptions, heading structure, tech stack, social links, schema markup). It respects robots.txt and never accesses restricted pages.
4. **MCP integrations pull live data** --- if you have SEMrush or Ahrefs configured in your `.mcp.json`, the plugin pulls real-time keyword rankings, backlink profiles, and content gap data. These integrations are optional; the analysis works without them using the scraper data and the agent's reference knowledge.
5. **Analysis synthesizes all sources** --- the agent combines scraped data, MCP data (if available), reference frameworks from `competitive-intelligence.md`, and your brand context into a structured report.

### Example output: Full analysis

```
## TrailPeak Gear --- Full Competitive Analysis

### Content Strategy
- Blog frequency: 3 posts/week (vs. your 1/week)
- Top formats: gear reviews (45%), how-to guides (30%), lifestyle (25%)
- Average post length: 1,800 words
- Content gap: They dominate gear reviews. You have no comparison content.
- Opportunity: Their lifestyle content is generic --- your brand voice
  (warm, passionate) would differentiate in this category.

### SEO Analysis
- Domain Authority: 42 (vs. your 28)
- Keyword overlap: 340 shared keywords, they rank higher on 78%
- Top content gap: "best hiking boots 2026" — they rank #3, you don't rank
- Backlink comparison: 2,400 referring domains vs. your 800
- Technical: Both on Shopify, similar page speed scores
- Opportunity: 62 keywords where you rank 11-20 and they rank 4-10 —
  these are the fastest wins with targeted content updates.

### Social Media
- Instagram: 45K followers, 3.2% engagement (vs. your 12K, 4.1%)
- TikTok: 8K followers, just started (opportunity: they're early too)
- LinkedIn: Not active (gap for B2B wholesale opportunity)
- Posting cadence: 5x/week on Instagram (vs. your 3x/week)
- Observation: Their engagement rate is below yours despite 3.5x the
  followers — your content resonates more per impression.

### Paid Advertising
- Running Google Shopping + Meta carousel ads
- Estimated monthly spend: $15-25K (Medium confidence — inferred from
  ad volume and industry CPMs)
- Key messaging: "Tested by real hikers" (social proof angle)
- Landing pages: Product pages with review widgets, no dedicated
  landing pages for campaigns
- Gap: No YouTube ads detected. No LinkedIn ads.

### AI Visibility
- Appears in ChatGPT responses for "best outdoor gear brands": yes
- Appears in Google AI Overviews for product queries: partially
- Entity consistency: Strong (consistent NAP, Wikipedia mention)
- Your brand: Not appearing in AI answers for category queries yet
- Opportunity: Building structured data and citation-worthy content
  could close this gap within 6-12 months.

### SWOT Summary

| | TrailPeak Gear |
|---|---|
| **Strengths** | Content volume, SEO authority, gear review reputation |
| **Weaknesses** | Low TikTok presence, no LinkedIn, generic brand voice |
| **Opportunities** | TikTok first-mover advantage, B2B wholesale channel |
| **Threats** | Growing SEO gap if they maintain 3x content velocity |

### Strategic Recommendations (Prioritized)

1. **Launch a gear review content series** (High impact, Medium effort)
   Closes the biggest content gap. Your authentic voice gives you a
   differentiation advantage over their formulaic reviews.

2. **Target the 62 keywords where you rank 11-20** (High impact, Low effort)
   Fastest SEO wins. Update existing pages with better content depth.

3. **Invest in TikTok before they establish dominance** (Medium impact,
   Medium effort) — Both brands are early. Your higher engagement rate
   suggests your content style translates well to short-form video.

4. **Build a YouTube presence** (High impact, High effort)
   Neither competitor is active. First-mover advantage for video content
   in your category.
```

### Example output: SEO-only comparison

When you request a single dimension, the output goes deeper on that specific area:

```
## REI vs. Your Brand --- SEO Comparison

### Domain Metrics
| Metric | Your Brand | REI |
|--------|-----------|-----|
| Domain Authority | 28 | 89 |
| Organic Keywords | 2,400 | 1.2M |
| Referring Domains | 800 | 245K |
| Monthly Organic Traffic | ~8K | ~42M |

### Realistic Benchmarking Note
REI is an aspirational competitor — a $3.8B co-op with 20+ years of
SEO investment. Direct metric comparison is not the point. Instead,
focus on what you can learn from their strategy at your scale.

### What REI Does Well That You Can Adapt
1. **Expert content hubs** — REI's "Expert Advice" section ranks for
   thousands of informational queries. You can build a smaller version
   targeting your top 20 product categories.
2. **User-generated content** — Reviews and member stories create
   thousands of indexable pages. Consider adding a review system and
   customer story features.
3. **Internal linking architecture** — REI's category > subcategory >
   product linking is textbook. Audit your internal link structure
   against this model.
```

The competitive-intel agent always normalizes comparisons for company size, industry, and brand maturity. It will not tell you to "match REI's backlink profile" when you are a growing DTC brand --- it identifies the transferable strategic patterns instead.

---

## 3. What competitor-scraper.py Captures

The `competitor-scraper.py` script is the plugin's deterministic data collection tool. It extracts structured information from publicly accessible web pages and respects ethical boundaries.

### Data points extracted

| Data Point | Description |
|-----------|-------------|
| **Page title** | The `<title>` tag content --- reveals positioning and keyword targeting |
| **Meta description** | The meta description tag --- shows how they pitch themselves in search results |
| **Heading structure** | H1, H2, and H3 tags --- reveals content hierarchy and topic focus |
| **Technology stack** | CMS (WordPress, Shopify, Squarespace), analytics (GA4, GTM), marketing tools (HubSpot, Facebook Pixel, Hotjar), and frontend frameworks (React, Next.js, Tailwind) |
| **Social media links** | Links to Facebook, Twitter/X, LinkedIn, Instagram, YouTube, TikTok, Pinterest found on the page |
| **Schema markup** | JSON-LD and microdata types present (Organization, Product, Article, FAQ, etc.) |
| **Open Graph data** | OG title and description --- shows how they optimize for social sharing |
| **Canonical URL** | Whether they use canonical tags and how (important for SEO comparison) |

### What the scraper does NOT do

- It never accesses login-protected or paywalled content
- It never scrapes pages blocked by robots.txt
- It never captures personal data, email addresses, or private information
- It adds a random delay between requests to avoid overwhelming servers
- It only visits the specific URL you provide --- it does not crawl entire sites

### How it works technically

When the plugin needs competitor website data, it runs:

```
python competitor-scraper.py --url trailpeakgear.com
```

The script first checks the target site's `robots.txt` file. If the requested page is disallowed, the script returns an error message explaining the restriction and does not proceed. If the page is allowed, it fetches the HTML, parses it with BeautifulSoup, and returns a structured JSON object with all extracted data points.

### When the scraper is not enough

The scraper captures what is visible on a single page. For deeper competitive intelligence --- keyword rankings, backlink profiles, traffic estimates, historical data --- you need the SEMrush or Ahrefs MCP integrations. See the section on keeping intelligence current for details on configuring these.

---

## 4. Six Dimensions of Competitive Intelligence

The plugin's competitive analysis covers six distinct dimensions. You can run all six together or focus on specific areas depending on what you need.

### Content Strategy

What they publish, how often, and what performs.

The competitive-intel agent analyzes competitor content across these factors:

- **Publishing frequency** --- how often they post and whether cadence is increasing or decreasing
- **Content formats** --- blog posts, videos, podcasts, guides, case studies, tools, and their relative mix
- **Topic authority** --- which content pillars they own and where they rank consistently
- **Content quality** --- depth, originality, expertise signals, and production value
- **Content gaps** --- topics they cover that you do not (and vice versa)
- **Distribution** --- how they promote content across channels

This dimension answers: Where is our content strategy weaker than the competition, and where do we have an opening they have not exploited?

### SEO Analysis

Domain authority, keyword overlap, ranking gaps, and backlinks.

- **Domain metrics** --- authority/rating scores, total organic keywords, estimated organic traffic
- **Keyword overlap** --- shared keywords and who ranks higher on each
- **Ranking gaps** --- high-value keywords where competitors rank and you do not
- **Quick wins** --- keywords where you rank positions 11-20 and a content update could push you to page one
- **Backlink profile** --- referring domains, link velocity, anchor text distribution
- **Technical SEO** --- page speed, Core Web Vitals, mobile experience, indexation

With the SEMrush MCP connected, the plugin pulls live keyword and ranking data. With Ahrefs MCP connected, it pulls detailed backlink intelligence. Without either, the analysis relies on the scraper output and the agent's frameworks for qualitative assessment.

### Paid Advertising

Ad copy patterns, landing pages, estimated spend, and platform focus.

- **Active platforms** --- Google Search, Google Shopping, Meta/Instagram, LinkedIn, TikTok, YouTube
- **Creative patterns** --- what ad formats they use, visual style, messaging themes
- **Offer structures** --- discounts, free trials, bundles, urgency tactics
- **Landing page strategy** --- dedicated landing pages vs. product pages, conversion elements present
- **Estimated spend** --- inferred from ad volume, impression data, and industry CPMs (labeled as Medium confidence)
- **Competitive messaging** --- what value propositions and proof points they lead with

The agent references publicly available ad libraries (Meta Ad Library, Google Ads Transparency Center) as data sources. It clearly labels observed data versus inferences.

### Social Media

Platform presence, engagement, audience growth, and content mix.

- **Platform coverage** --- which platforms each competitor is active on
- **Audience size and growth** --- follower counts and trajectory
- **Engagement rates** --- likes, comments, shares relative to audience size
- **Content mix** --- ratio of promotional, educational, entertaining, and community content
- **Posting cadence** --- frequency and consistency of publishing
- **Community management** --- response times, conversation quality, sentiment

This dimension reveals where competitors are over-invested and where platform white space exists for your brand.

### AI Visibility

How competitors appear in AI-powered search and answer engines.

- **AI answer presence** --- whether the competitor appears in ChatGPT, Perplexity, or Google AI Overview responses for category queries
- **Entity consistency** --- how consistently the brand's name, description, and attributes appear across data sources that AI models reference
- **Citation presence** --- whether competitor content is cited as a source in AI-generated answers
- **Comparison positioning** --- how the competitor is characterized when AI models compare brands in the category
- **Knowledge panel completeness** --- structured data presence in Google's Knowledge Graph

AI visibility is an emerging dimension. The plugin uses the AEO/GEO module's frameworks to assess this. If you have AI visibility checking enabled (requires OpenAI or Anthropic API key in `.env` and Full Python mode), the plugin can run programmatic checks.

### Pricing and Positioning

Price points, value proposition, and market segment.

- **Pricing model** --- subscription, one-time, freemium, tiered, usage-based
- **Price points** --- actual prices for comparable products or services
- **Value proposition** --- the core promise the competitor makes to customers
- **Market segment** --- premium, mid-market, budget, or niche positioning
- **Differentiation claims** --- what they say makes them different
- **Social proof strategy** --- reviews, testimonials, case studies, certifications, trust badges

This dimension helps you understand where competitors are positioned on the price-value spectrum and where gaps exist for your brand to occupy.

---

## 5. Responding to Competitor Moves

Intelligence is only valuable when it informs action. The plugin helps you evaluate competitor moves against your brand context and recommends responses that align with your strategy, resources, and goals.

### Example: Evaluating a competitor's new initiative

```
You: TrailPeak just launched a podcast called "Trail Talk" — they're
     interviewing famous hikers. Should we do the same?

Plugin: Let me evaluate this against your brand context...

        Analysis:
        - Your brand voice (warm, knowledgeable, passionate) suits audio
          content well
        - Your primary channels are email and Instagram — adding a podcast
          diversifies reach but stretches your team of 3
        - Podcast ROI typically takes 12-18 months to materialize
        - Your competitive advantage is on Instagram (higher engagement
          rate than TrailPeak despite smaller audience)

        Recommendation: Not yet. Instead:
        1. Launch a YouTube series (TrailPeak is absent there — first-mover
           advantage for you)
        2. Repurpose your Instagram Reels content as YouTube Shorts (low
           incremental effort)
        3. Monitor TrailPeak's podcast metrics for 6 months — download
           numbers, guest quality, social mentions
        4. If it gains traction, consider a seasonal podcast (lower
           commitment than year-round)

        This recommendation aligns with your goal of increasing repeat
        purchases — YouTube has better conversion potential than podcasts
        for DTC brands.
```

Notice that the plugin does not give a generic answer. It weighs the move against your specific voice profile, team size, channel strengths, and business goals. The recommendation accounts for resource constraints (team of 3) and strategic priorities (repeat purchases, not brand awareness).

### Example: Responding to a pricing change

```
You: Backcountry just dropped their prices 20% across all hiking boots.
     Our customers are asking about it.

Plugin: Let me assess the competitive impact...

        Context:
        - Your positioning: premium quality, sustainably sourced materials
        - Backcountry's relationship: indirect competitor (different brand
          positioning)
        - Your audience values quality and sustainability over lowest price

        Assessment:
        - A 20% blanket discount suggests inventory clearance or strategic
          repositioning, not permanent pricing
        - Your customer overlap with Backcountry is low (different segments)
        - Price-matching would undermine your premium positioning

        Recommended response:
        1. Do NOT match the discount
        2. Publish a "Why quality hiking boots cost more" content piece —
           lean into your sustainability and durability story
        3. Offer a "Boot guarantee" instead — free resoling or repair
           within 2 years (adds value without cutting price)
        4. Run a targeted email to customers who browsed boots recently —
           emphasize long-term value per wear
        5. Monitor your boot category conversion rate for 2 weeks to
           confirm the price cut is not affecting your sales
```

### Response playbooks built into the plugin

The competitive intelligence reference knowledge includes structured playbooks for common competitive scenarios:

- **Competitor launches a price cut** --- assess scope, measure impact, respond with value over matching
- **Competitor launches a new product or feature** --- assess overlap, gauge demand, decide whether to follow, differentiate, or ignore
- **Competitor increases ad spend** --- verify the increase, measure auction impact, optimize efficiency over escalation
- **New competitor enters the market** --- profile immediately, classify tier, monitor traction signals, strengthen incumbent advantages

Each playbook provides a decision framework rather than a rigid script. The plugin applies your brand context to determine which response option fits your situation.

---

## 6. Keeping Intelligence Current

Competitive intelligence degrades fast. A competitor can launch a new channel, change pricing, or shift positioning in a matter of weeks. The plugin supports both structured review cadences and real-time monitoring.

### Review frequency by competitor tier

| Competitor Tier | Review Frequency | What to Check |
|----------------|-----------------|---------------|
| **Tier 1** (direct, aggressive) | Monthly | Content output, SEO rankings, active ads, social engagement, pricing changes |
| **Tier 2** (direct, stable) | Quarterly | Content strategy shifts, SEO position changes, major campaigns |
| **Tier 3** (indirect/aspirational) | Semi-annually | Strategic repositioning, new channel launches, market segment moves |
| **Tier 4** (new entrants) | Quarterly | Funding, product launches, initial traction metrics, hiring patterns |

### Running periodic reviews

You do not need to remember the schedule. Just ask:

```
You: It's been a month — run a competitive check on TrailPeak Gear

Plugin: Running Tier 1 monthly review for TrailPeak Gear...
        (competitor-scraper.py refreshes website data)
        (SEMrush MCP pulls latest keyword and backlink changes)

        Changes since last review (January 15):
        - New blog section: "Trail Talk" podcast show notes (12 posts)
        - Domain Authority: 42 → 43 (+1)
        - 28 new referring domains acquired
        - Instagram: 45K → 47K followers (+4.4%)
        - TikTok: 8K → 12K followers (+50% — accelerating)
        - New schema markup: Podcast and Episode types added
        - Tech stack change: Added Klaviyo (email marketing platform)

        Key takeaway: They are investing heavily in podcast-driven growth
        and building their email program (Klaviyo addition). TikTok growth
        is accelerating faster than expected.

        Recommended actions:
        1. Accelerate your YouTube strategy — their attention is on audio,
           not video
        2. Note Klaviyo adoption — expect improved email sequences from
           them within 60 days
        3. Upgrade TrailPeak's TikTok from "just started" to "growing
           presence" in your competitor profile
```

### Live data with SEMrush and Ahrefs MCP integrations

If you have either (or both) of these integrations configured, the plugin's competitive analysis gains access to real-time SEO and backlink data:

**SEMrush MCP** (requires `SEMRUSH_API_KEY` in `.env`):
- Live keyword ranking positions for you and competitors
- Keyword gap analysis showing terms they rank for and you do not
- Domain-level traffic estimates and trends
- Backlink analytics and new/lost links
- Advertising research (paid keyword data)

**Ahrefs MCP** (requires `AHREFS_API_KEY` in `.env`):
- Detailed backlink profiles with referring domain quality
- Content explorer showing top-performing competitor content by backlinks and social shares
- Keyword explorer with click-through rate data
- Content gap analysis across multiple competitors simultaneously
- Historical ranking data for trend analysis

**Without MCP integrations**, the plugin still delivers strong competitive analysis using the scraper data, your input, the competitive-intel agent's analytical frameworks, and the 86 reference knowledge files. The MCP integrations add quantitative depth, not a fundamentally different analysis.

### Automatic insight persistence

Every time you run a competitive analysis or discuss competitors, the plugin's SessionEnd hook saves relevant insights via `campaign-tracker.py`. These are stored in your brand's `insights.json` file at `~/.claude-marketing/brands/{slug}/`. In your next session, these insights are loaded as part of your brand context, so the plugin remembers what it learned.

Examples of automatically saved insights:

- "TrailPeak Gear added Klaviyo to their tech stack (detected Feb 2026)"
- "REI ranks for 62 keywords where we rank 11-20 (identified Feb 2026)"
- "No competitor has a YouTube presence --- first-mover opportunity"
- "TrailPeak TikTok growing at 50% month-over-month"

This cross-session memory means your competitive intelligence accumulates over time rather than starting from zero each session.

---

## 7. Connecting Competitor Insights to Strategy

Competitive intelligence is most powerful when it feeds directly into your marketing planning. The plugin does this automatically --- every module that produces strategy checks your competitor data for relevant gaps and opportunities.

### Example: Competitor data shaping a content strategy

```
You: Plan my Q3 content strategy

Plugin (checking competitor data automatically):
        - Gap identified: TrailPeak dominates gear reviews but you have
          none
        - Gap identified: Neither competitor has a YouTube presence
        - Gap identified: REI's email open rate benchmark suggests room
          to improve yours

        Q3 Content Strategy:

        Priority 1: Launch Gear Review Series (closes TrailPeak gap)
        - 2 gear reviews per month across hiking boots, backpacks, and
          apparel
        - Differentiation: your reviews emphasize sustainability and
          durability testing, not just performance specs
        - Distribution: blog + email digest + Instagram carousel
          summaries

        Priority 2: Start YouTube Channel (first-mover advantage)
        - Repurpose top-performing Instagram Reels as YouTube Shorts
          (low effort, high reach)
        - 1 long-form video per month: "Trail Tested" gear review
          in the field
        - Neither TrailPeak nor Backcountry has video — you own this
          channel

        Priority 3: Email Subject Line Optimization (close REI gap)
        - Current open rate: 22% vs. REI's estimated 28-32%
        - Test curiosity-driven subject lines (REI's best performers
          use this pattern)
        - A/B test personalization with first name vs. without
```

### Example: Competitor data informing a campaign plan

```
You: /dm:campaign-plan for our spring hiking boot launch

Plugin (incorporating competitor intelligence):
        Competitive context applied:
        - TrailPeak runs Google Shopping + Meta carousel ads for boots
        - Their key message: "Tested by real hikers" (social proof angle)
        - They do NOT run YouTube or LinkedIn ads
        - Backcountry's 20% discount ended — pricing pressure has eased

        Campaign recommendation includes:
        - YouTube pre-roll ads (uncontested channel for boot marketing)
        - Message angle: sustainability + durability (differentiates from
          TrailPeak's "tested by hikers" social proof — you go deeper
          with "built to last, sourced responsibly")
        - Timing: Launch 2 weeks before TrailPeak's typical spring
          campaign (based on their historical ad library patterns)
```

### Example: Competitive gaps feeding into SEO priorities

```
You: /dm:seo-audit

Plugin (incorporating competitor intelligence):
        Competitor-informed findings:
        - 62 keywords where you rank 11-20 and TrailPeak ranks 4-10 —
          these are your highest-priority content updates
        - TrailPeak has no content targeting "sustainable hiking gear" —
          this is an uncontested keyword cluster worth 2,400 monthly
          searches
        - REI's "Expert Advice" hub model is working — consider building
          a similar (smaller scale) resource section
```

### The intelligence loop

Competitive intelligence in Digital Marketing Pro follows a continuous loop:

```
Set up competitors          Run analysis            Identify gaps
      |                          |                       |
      v                          v                       v
 profile.json            competitive-intel         Content, SEO, ads,
 competitors.json        agent + scraper +         social, AI, pricing
                         MCP data                  opportunities
      ^                                                  |
      |                                                  v
Save new insights  <---  Execute strategy  <---   Plan campaigns
(campaign-tracker.py)    with competitive          informed by gaps
                         advantage
```

Each cycle makes the system smarter. Insights saved today become context for tomorrow's analysis. Competitor profiles grow richer as you gather more data. Strategic recommendations become more precise as the plugin learns which competitor moves matter and which are noise.

### Getting the most out of competitive intelligence

**Start with Tier 1 competitors.** Do not try to track everyone at once. Focus your first full analysis on your most direct, aggressive competitor. Expand to Tier 2 and Tier 3 once you have a rhythm.

**Be specific in your questions.** "Analyze TrailPeak's content strategy and tell me where we can win" produces better output than "Tell me about TrailPeak." The competitive-intel agent is designed to focus on actionable gaps, but specificity helps it prioritize.

**Update competitor data when you learn something.** If you notice a competitor launched a new product, changed their pricing, or hired a new marketing lead, tell the plugin. Human observation combined with automated data collection produces the best intelligence.

**Connect every insight to an action.** The plugin's competitive-intel agent follows a rule: every competitive finding should include what the competitor is doing, why it likely works, what it means for your brand, and a specific recommended response. If you receive intelligence without a clear action, ask: "What should I do about this?"

**Review your competitor list quarterly.** Markets shift. New entrants appear. Former threats pivot away. Run a quick check every quarter: "Review my competitor list --- is it still accurate?" The plugin will help you add, remove, or reclassify competitors based on current market conditions.

---

*Digital Marketing Pro v1.2.0 --- Competitive intelligence that turns market awareness into strategic advantage.*
