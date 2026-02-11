---
name: content-brief
description: Use when the user needs a detailed content brief with keyword targets, outline, structure, voice guidelines, and SEO requirements for a specific piece of content.
---

# /dm:content-brief

## Purpose

Create a production-ready content brief that a writer can execute without additional context. Includes keyword strategy, content outline, structural requirements, brand voice guidelines, and on-page SEO specifications.

## Input Required

The user must provide (or will be prompted for):

- **Topic or working title**: What the content is about
- **Content type**: Blog post, landing page, pillar page, guide, whitepaper, etc.
- **Target keyword(s)**: Primary keyword or topic cluster (or ask for research)
- **Target audience**: Who this content is for
- **Funnel stage**: Awareness, consideration, or decision
- **Competitive URLs**: Optional — existing content to outperform

## Process

1. **Load brand context**: Read `~/.claude-marketing/brands/_active-brand.json` for the active slug, then load `~/.claude-marketing/brands/{slug}/profile.json`. Apply brand voice, compliance rules for target markets (`skills/context-engine/compliance-rules.md`), and industry context. If no brand exists, ask: "Set up a brand first (/dm:brand-setup)?" — or proceed with defaults.
2. Research keyword landscape: primary keyword, secondary keywords, related questions
3. Analyze top-ranking content for the target keyword to identify gaps and opportunities
4. Define content angle and unique value proposition versus existing results
5. Build a detailed outline with H2/H3 structure, key points per section, and word count targets
6. Specify on-page SEO requirements: title tag, meta description, URL slug, internal links, schema markup
7. Document voice and tone guidelines specific to this piece
8. Define success metrics: target ranking, traffic, engagement, conversions

## Output

A structured content brief containing:

- Target keyword map (primary, secondary, LSI, questions to answer)
- Content outline with heading hierarchy and key points per section
- Word count target and content format specifications
- Brand voice and tone guidance for this specific piece
- On-page SEO checklist (title, meta, headers, links, schema)
- Visual/media requirements
- Internal and external linking strategy
- Success metrics and measurement plan

## Agents Used

- **content-creator** — Outline structure, angle, voice guidelines, content strategy
- **seo-specialist** — Keyword research, on-page SEO requirements, competitive content analysis
