---
name: influencer-brief
description: Use when the user needs an influencer campaign brief with discovery criteria, creator guidelines, FTC compliance checklist, and measurement plan.
---

# /dm:influencer-brief

## Purpose

Create a complete influencer campaign brief that covers creator discovery criteria, content guidelines, compliance requirements, compensation framework, and performance measurement.

## Input Required

The user must provide (or will be prompted for):

- **Campaign objective**: Awareness, engagement, conversions, content generation, or event promotion
- **Product/service**: What the influencer will promote
- **Target audience**: Who the campaign should reach
- **Platform(s)**: Instagram, TikTok, YouTube, X, LinkedIn, podcasts
- **Budget**: Total influencer budget or per-creator range
- **Creator tier**: Nano (1-10K), Micro (10-100K), Mid (100K-500K), Macro (500K-1M), Mega (1M+)
- **Timeline**: Campaign dates and content delivery deadlines
- **Content type**: Posts, stories, reels, videos, reviews, unboxing, tutorials, live streams

## Process

1. **Load brand context**: Read `~/.claude-marketing/brands/_active-brand.json` for the active slug, then load `~/.claude-marketing/brands/{slug}/profile.json`. Apply brand voice, compliance rules for target markets (`skills/context-engine/compliance-rules.md`), and industry context. If no brand exists, ask: "Set up a brand first (/dm:brand-setup)?" — or proceed with defaults.
2. Define creator discovery criteria: niche, audience demographics, engagement rate minimums, brand safety filters, aesthetic alignment
3. Build the creator brief: campaign overview, key messages, creative freedom boundaries, required and prohibited elements, hashtags, disclosures
4. Draft compensation framework: flat fee, performance bonus, affiliate commission, product gifting, or hybrid
5. Create content approval workflow: draft review, revision rounds, posting timeline
6. Build FTC/ASA compliance checklist: disclosure requirements, claim restrictions, platform-specific rules
7. Define usage rights: organic only, paid amplification, repurposing, duration
8. Set measurement framework: reach, engagement, clicks, conversions, CPE, EMV

## Output

A structured influencer campaign brief containing:

- Campaign overview with objectives and success metrics
- Creator discovery criteria and ideal profile description
- Creator brief document (shareable with influencers)
- Key messaging framework with creative guardrails
- Compensation structure and negotiation guidelines
- Content approval and revision process
- FTC/ASA compliance checklist with required disclosures
- Usage rights and licensing terms
- Measurement dashboard with KPIs and reporting cadence

## Agents Used

- **influencer-manager** — Creator strategy, brief development, compliance, measurement, campaign architecture
