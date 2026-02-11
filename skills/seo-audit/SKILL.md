---
name: seo-audit
description: Use when the user needs a comprehensive SEO audit covering technical health, on-page optimization, content quality, E-E-A-T signals, local SEO, and link profile analysis.
---

# /dm:seo-audit

## Purpose

Perform a comprehensive SEO audit that evaluates a website across all major ranking dimensions. Produces a prioritized action plan with estimated impact and effort for each recommendation.

## Input Required

The user must provide (or will be prompted for):

- **Website URL**: The domain or specific pages to audit
- **Target keywords**: Primary keywords the site should rank for (optional — can be researched)
- **Competitors**: 2-3 competitor URLs for benchmarking (optional)
- **Audit scope**: Full site or specific area (technical, content, local, links)
- **Known issues**: Any existing problems the user is aware of

## Process

1. **Load brand context**: Read `~/.claude-marketing/brands/_active-brand.json` for the active slug, then load `~/.claude-marketing/brands/{slug}/profile.json`. Apply brand voice, compliance rules for target markets (`skills/context-engine/compliance-rules.md`), and industry context. If no brand exists, ask: "Set up a brand first (/dm:brand-setup)?" — or proceed with defaults.
2. **Technical audit**: Crawlability, indexation, Core Web Vitals, mobile usability, structured data, HTTPS, XML sitemap, robots.txt, canonical tags, redirect chains
3. **On-page audit**: Title tags, meta descriptions, heading hierarchy, keyword usage, image alt text, internal linking structure, URL structure
4. **Content audit**: Thin content, duplicate content, content gaps, freshness, E-E-A-T signals (author pages, citations, credentials, first-hand experience)
5. **Local SEO** (if applicable): Google Business Profile, NAP consistency, local schema, reviews, local link profile
6. **Link profile**: Domain authority, backlink quality, toxic links, anchor text distribution, link velocity, competitor link gap
7. Score each dimension on a 1-10 scale
8. Prioritize findings by impact (high/medium/low) and effort (quick win/medium/major project)
9. Generate the audit report with actionable recommendations

## Output

A structured SEO audit report containing:

- Executive summary with overall health score
- Technical SEO scorecard with specific issues and fixes
- On-page optimization findings per page/template
- Content quality assessment with gap analysis
- E-E-A-T evaluation and improvement recommendations
- Local SEO assessment (if applicable)
- Link profile analysis with opportunities
- Prioritized action plan sorted by impact-to-effort ratio

## Agents Used

- **seo-specialist** — All audit dimensions, scoring, prioritization, and recommendations
