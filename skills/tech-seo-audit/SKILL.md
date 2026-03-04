---
name: tech-seo-audit
description: Use when the user wants a technical SEO audit covering Core Web Vitals, crawlability, indexation, site architecture, page speed, mobile-first indexing, redirect health, structured data, or JavaScript rendering assessment.
argument-hint: "[URL]"
---

# /dm:tech-seo-audit

## Purpose

Run a comprehensive technical SEO audit that covers the infrastructure and code-level factors that affect search engine crawling, indexation, and ranking. This audit focuses on the technical foundation rather than content or backlinks. Produces a prioritized report with specific fixes, expected impact, and implementation guidance.

## Input Required

The user must provide (or will be prompted for):

- **Website URL** (required): The domain or specific section to audit
- **CMS/Platform** (helpful): WordPress, Shopify, Next.js, custom, etc.
- **Known issues** (optional): Any specific technical concerns
- **Site size** (helpful): Approximate number of pages
- **International presence** (optional): Whether site serves multiple countries/languages
- **Access to Google Search Console data** (optional): Enables real data vs estimates

## Process

1. **Load brand context**: Read `~/.claude-marketing/brands/_active-brand.json` for the active slug, then load `~/.claude-marketing/brands/{slug}/profile.json`. Apply brand voice, compliance rules for target markets (`skills/context-engine/compliance-rules.md`), and industry context. **Also check for guidelines** at `~/.claude-marketing/brands/{slug}/guidelines/_manifest.json` — if present, load restrictions and relevant category files. Check for custom templates at `~/.claude-marketing/brands/{slug}/templates/`. Check for agency SOPs at `~/.claude-marketing/sops/`. If no brand exists, ask: "Set up a brand first (/dm:brand-setup)?" — or proceed with defaults.
2. **Load reference files**: Read `skills/technical-seo/core-web-vitals.md`, `skills/technical-seo/crawlability.md`, `skills/technical-seo/site-architecture.md`, `skills/technical-seo/indexation.md`, and `skills/technical-seo/international-seo.md` for detailed technical SEO frameworks
3. **Run tech-seo-auditor script** (if Python available): `python "scripts/tech-seo-auditor.py" --url {url}` to get automated checks on status codes, redirects, meta tags, and page structure
4. **Core Web Vitals assessment**: Evaluate LCP, INP, and CLS using known thresholds. If GSC MCP is connected, pull real CrUX data. Otherwise, provide optimization checklist based on CMS/platform
5. **Crawlability audit**: Check robots.txt configuration, XML sitemap presence and structure, crawl budget considerations, JavaScript rendering impact
6. **Indexation review**: Canonical tag usage, meta robots directives, duplicate content risks, index bloat potential, pagination handling
7. **Site architecture analysis**: URL structure, internal linking patterns, site depth, navigation efficiency, breadcrumbs
8. **Page speed optimization**: Image optimization, render-blocking resources, compression, caching, CDN usage
9. **Mobile-first compliance**: Viewport configuration, responsive design, mobile usability, touch targets
10. **Redirect health check**: Redirect chain detection, mixed HTTP/HTTPS, trailing slash consistency
11. **Structured data review**: Schema markup presence, validation, completeness, opportunity identification
12. **International SEO** (if applicable): Hreflang implementation, language targeting, URL structure
13. **Security check**: HTTPS enforcement, HSTS, mixed content
14. Compile prioritized report: Group findings by severity (Critical / High / Medium / Low), include specific fix instructions, estimated effort, and expected impact for each issue

## Output

A structured technical SEO audit report containing:

- **Audit header**: Brand name, URL, date, CMS/platform, overall health score (0-100)
- **Executive summary**: 3-5 sentence overview of technical health
- **Critical issues** (fix immediately): Issues blocking crawling, indexation, or causing significant ranking impact
- **High priority** (fix this week): Issues with measurable ranking or UX impact
- **Medium priority** (fix this month): Optimization opportunities with moderate impact
- **Low priority** (backlog): Minor improvements and best-practice alignment
- **Each finding includes**: Description, affected URLs/pages, specific fix with code/config examples, estimated effort (hours), expected impact (traffic/ranking)
- **Core Web Vitals scorecard**: LCP, INP, CLS with current estimates and target values
- **Quick wins list**: Top 5 highest-impact, lowest-effort fixes
- **Implementation roadmap**: Suggested timeline for addressing all findings

## Agents Used

- **seo-specialist** — Runs the technical audit across all dimensions, generates structured data recommendations, provides CMS-specific fix guidance, prioritizes findings by impact/effort
