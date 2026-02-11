# AI Visibility Audit — Methodology & Scoring

## Overview

A systematic process for auditing how a brand appears across AI-generated answers on ChatGPT, Perplexity, Google AI Overviews, Gemini, and Microsoft Copilot.

---

## Step 1: Query Selection

Select 15-25 queries across four categories:

### Query Categories

| Category | Purpose | Example Queries |
|----------|---------|----------------|
| **Recommendation** | "Best [product type]" queries | "Best project management tool for startups" |
| **Comparison** | Brand vs competitor queries | "[Brand] vs [Competitor]" |
| **Informational** | "What is [brand]" queries | "What does [Brand] do?" |
| **Problem-Solving** | Pain-point queries | "How to [solve problem brand addresses]" |

### Query Selection Rules

1. Include 4-6 queries per category
2. Mix head terms (high volume) with long-tail (specific intent)
3. Include at least 3 queries where the brand SHOULD be cited but may not be
4. Include branded queries (brand name) and non-branded (category/problem)
5. Prioritize queries that match the brand's target customer JTBD

---

## Step 2: Platform-by-Platform Testing

### Testing Protocol

For each query, test on all 5 platforms and record:

| Field | What to Capture |
|-------|----------------|
| Platform | ChatGPT / Perplexity / Google AI Overview / Gemini / Copilot |
| Query | Exact query text |
| Date tested | For tracking changes over time |
| Model version | e.g., GPT-4, Gemini Pro |
| Brand mentioned? | Yes / No |
| Mention type | Cited, Recommended, Referenced, Mentioned, Absent, Misrepresented |
| Exact text | Copy the AI-generated text mentioning (or not mentioning) the brand |
| Position | Where in the response (first, middle, last, not present) |
| Competitors mentioned | Which competitors appear in the same response |
| Source cited | If Perplexity/AI Overview cites a source, record the URL |
| Accuracy | Is the information about the brand accurate? (Yes / Partially / No) |

### Platform-Specific Notes

- **ChatGPT**: Test with latest model. Note that responses vary by session — test 2-3 times
- **Perplexity**: Check both the answer AND the cited sources list
- **Google AI Overviews**: Not all queries trigger AI Overviews — document which do
- **Gemini**: Test via gemini.google.com, note any "I don't have enough info" responses
- **Copilot**: Test in Bing chat mode for web-grounded responses

---

## Step 3: Scoring Rubric

### Per-Query Scoring

| Score | Label | Definition |
|-------|-------|-----------|
| **5** | Cited | Brand directly mentioned with a link to brand's content as a source |
| **4** | Recommended | Brand explicitly recommended as a top choice |
| **3** | Referenced | Brand mentioned by name in a relevant context |
| **2** | Mentioned | Brand appears but not in a primary/useful way |
| **0** | Absent | Brand does not appear at all |
| **-2** | Misrepresented | Brand appears but with inaccurate or negative information |

### Aggregate Scoring

**AI Visibility Score** = (Sum of per-query scores across all platforms) / (Max possible score) × 100

- **Max possible per query**: 5 points × 5 platforms = 25
- **Max possible total**: 25 × number of queries

### Score Interpretation

| Score Range | Interpretation |
|-------------|---------------|
| 80-100 | Excellent AI visibility — brand is a recognized authority |
| 60-79 | Good — mentioned frequently but room to improve citation rate |
| 40-59 | Moderate — inconsistent presence, clear gaps to address |
| 20-39 | Weak — rarely mentioned, significant optimization needed |
| 0-19 | Minimal — brand is essentially invisible to AI platforms |

---

## Step 4: Competitive Benchmarking

Run the same query set for 3-5 key competitors. Compare:

1. **Visibility Score**: Side-by-side total scores
2. **Citation Rate**: % of queries where each brand is cited (score ≥ 3)
3. **First-Mention Rate**: % of queries where brand appears first
4. **Platform Strength**: Which platforms favor which brands
5. **Query Category Gaps**: Where competitors win vs where you win

---

## Step 5: Gap Analysis

Identify patterns:

- **Query gaps**: Which query categories have the lowest scores?
- **Platform gaps**: Which AI platforms under-represent the brand?
- **Competitor advantages**: What are cited competitors doing differently?
- **Content gaps**: What authoritative content is missing from the brand's ecosystem?
- **Structured data gaps**: What schema markup is missing?
- **Entity gaps**: Are there knowledge graph or Wikipedia/Wikidata issues?

---

## Step 6: Monitoring Cadence

| Priority Level | Audit Frequency | Scope |
|---------------|----------------|-------|
| Priority queries (top 5) | Weekly | All 5 platforms |
| Full query set | Monthly | All 5 platforms |
| Expanded audit (new queries) | Quarterly | All 5 platforms + new query discovery |
| Post-major update | Within 48 hours | Priority queries on affected platform |

### Triggers for Immediate Re-Audit

- New AI model release (GPT update, Gemini update, etc.)
- Major content publish or site restructure
- Significant schema markup implementation
- Competitor AI visibility change detected
- Brand entity correction on Wikipedia/Wikidata
