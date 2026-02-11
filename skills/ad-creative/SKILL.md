---
name: ad-creative
description: Use when the user needs platform-specific ad copy variations with quality scoring for Google RSA, Meta, LinkedIn, TikTok, or other ad platforms.
---

# /dm:ad-creative

## Purpose

Generate high-performing ad copy variations tailored to specific platforms and formats. Each variation is scored for quality and compliance, with recommendations for testing strategy.

## Input Required

The user must provide (or will be prompted for):

- **Product/service**: What is being advertised
- **Platform(s)**: Google Ads, Meta (Facebook/Instagram), LinkedIn, TikTok, X, Pinterest
- **Ad format**: RSA, single image, carousel, video script, story, etc.
- **Campaign objective**: Awareness, traffic, leads, conversions, app installs
- **Target audience**: Who the ads are for
- **Key offer/CTA**: Promotion, value prop, or desired action
- **Landing page URL**: Where the ad will drive traffic (optional)

## Process

1. **Load brand context**: Read `~/.claude-marketing/brands/_active-brand.json` for the active slug, then load `~/.claude-marketing/brands/{slug}/profile.json`. Apply brand voice, compliance rules for target markets (`skills/context-engine/compliance-rules.md`), and industry context. If no brand exists, ask: "Set up a brand first (/dm:brand-setup)?" — or proceed with defaults.
2. Identify platform-specific constraints: character limits, format requirements, policy restrictions
3. Generate 3-5 ad copy variations per platform, each with a distinct angle (benefit, urgency, social proof, curiosity, direct)
4. Score each variation on: brand alignment, clarity, emotional impact, CTA strength, policy compliance
5. Flag any potential policy violations (restricted claims, prohibited language)
6. Recommend A/B testing groupings and priority order
7. If landing page URL is provided, check message match between ad and page

## Output

Per platform, a set of ad copy variations including:

- Headlines, descriptions, and CTAs formatted to platform specifications
- Quality score (1-10) with reasoning per variation
- Policy compliance check with flagged issues
- A/B testing recommendation with hypothesis for each test
- Message match assessment (if landing page provided)
- Creative direction notes for visual/video assets

## Agents Used

- **content-creator** — Ad copy generation, angle development, CTA crafting
- **media-buyer** — Platform specs, policy compliance, testing strategy
- **brand-guardian** — Voice alignment, compliance review, claim verification
