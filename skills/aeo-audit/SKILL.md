---
name: aeo-audit
description: Use when the user wants to assess how their brand appears in AI-powered search and answer engines like ChatGPT, Perplexity, Google AI Overviews, and Gemini.
---

# /dm:aeo-audit

## Purpose

Evaluate the brand's visibility and accuracy across AI answer engines. Analyze how the brand is cited, described, and recommended by ChatGPT, Perplexity, Google AI Overviews, and similar platforms. Produce optimization recommendations to improve AI visibility.

## Input Required

The user must provide (or will be prompted for):

- **Brand name**: The brand to audit
- **Website URL**: Primary domain
- **Key queries**: 5-10 queries a potential customer might ask that should surface the brand
- **Competitors**: 2-3 competitors for comparison
- **Product/service categories**: What the brand should be known for

## Process

1. **Load brand context**: Read `~/.claude-marketing/brands/_active-brand.json` for the active slug, then load `~/.claude-marketing/brands/{slug}/profile.json`. Apply brand voice, compliance rules for target markets (`skills/context-engine/compliance-rules.md`), and industry context. If no brand exists, ask: "Set up a brand first (/dm:brand-setup)?" — or proceed with defaults.
2. Define a test query set: branded queries, category queries, comparison queries, "best of" queries, problem-solution queries
3. Analyze how the brand appears in AI responses for each query type
4. Check citation accuracy: Are facts correct? Are URLs valid? Is the description current?
5. Compare brand mention frequency and sentiment against competitors
6. Assess source authority: Which sources are AI engines pulling brand info from?
7. Evaluate structured data and knowledge panel presence
8. Identify content gaps where the brand should appear but does not
9. Generate optimization recommendations for improved AI visibility

## Output

A structured AEO audit report containing:

- AI visibility scorecard across platforms (ChatGPT, Perplexity, Google AI Overviews)
- Query-by-query results showing where the brand appears, how it is described, and citation sources
- Competitor comparison matrix for AI visibility
- Citation accuracy assessment with corrections needed
- Source authority analysis — which pages/sites drive AI mentions
- Content gap list — queries where the brand is absent but should appear
- Optimization playbook: structured data, content strategy, authority building, and entity optimization

## Agents Used

- **seo-specialist** — AI search analysis, entity optimization, structured data, citation strategy
