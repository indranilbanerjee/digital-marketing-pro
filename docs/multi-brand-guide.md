# Multi-Brand & Agency Guide

A guide to managing multiple brands, corporate portfolios, and agency client rosters with the Digital Marketing Pro plugin for Claude Code.

---

## Table of Contents

1. [How Brand Profiles Work](#how-brand-profiles-work)
2. [Multi-Brand Corporation Pattern](#multi-brand-corporation-pattern)
3. [Agency Multi-Client Pattern](#agency-multi-client-pattern)
4. [Listing and Managing Brands](#listing-and-managing-brands)
5. [Limitations & Workarounds](#limitations--workarounds)
6. [Best Practices](#best-practices)

---

## How Brand Profiles Work

Every brand you create gets its own isolated directory at `~/.claude-marketing/brands/{slug}/`. A slug is a lowercase, hyphenated identifier derived from the brand name (for example, "Artisan Bakery" becomes `artisan-bakery`).

### What Lives Inside a Brand Profile

```
~/.claude-marketing/brands/{slug}/
  profile.json           Brand identity, voice settings, business model, goals
  audiences.json         Buyer personas and audience segments
  competitors.json       Competitor profiles and analysis data
  insights.json          Marketing learnings accumulated over time (last 200)
  campaigns/             Campaign plans and post-mortems
  performance/           Performance snapshots over time
  content-library/       Saved content pieces and templates
  voice-samples/         Reference content that exemplifies the brand voice
```

The `profile.json` file is the heart of each brand. It stores:

- **Identity** -- tagline, mission, vision, values, USP, positioning statement
- **Business model** -- type (B2B SaaS, B2C eCommerce, Local, etc.), revenue model, price range, sales cycle
- **Industry** -- primary/secondary industries, regulated status, compliance codes
- **Brand voice** -- four numeric dimensions plus word lists:
  - `formality` (1-10): 1 = casual like a friend, 10 = formal like a law firm
  - `energy` (1-10): 1 = calm and measured, 10 = enthusiastic and bold
  - `humor` (1-10): 1 = never uses humor, 10 = humor is central to the brand
  - `authority` (1-10): 1 = peer-level friendly guide, 10 = expert thought leader
  - `tone_keywords`, `avoid_words`, `prefer_words`: word lists that shape language choices
- **Channels** -- active marketing channels, primary channel, social handles
- **Competitors** -- names, URLs, relationship type, strengths and weaknesses
- **Goals** -- primary objective, KPIs, budget range, team size
- **Target markets** -- countries and regions, which trigger compliance rules automatically

### The Active Brand

Only one brand is active at a time. The file `~/.claude-marketing/brands/_active-brand.json` tracks which brand is currently live:

```json
{
  "active_slug": "artisan-bakery",
  "updated_at": "2026-02-11T09:30:00"
}
```

Every module, command, and agent reads this file to determine which brand context to apply. When you switch brands, the entire plugin pivots to the new brand's voice, compliance rules, industry benchmarks, and campaign history.

### Full Isolation Between Brands

Each brand is completely self-contained. There is no shared state between profiles:

- Campaign data for Brand A is invisible when Brand B is active
- Insights learned from one brand do not bleed into another
- Voice settings, compliance rules, and competitor tracking are entirely separate
- Content libraries and voice samples are brand-specific

This isolation is critical for agencies handling competing clients and for corporations maintaining distinct brand identities. There is no practical limit to the number of brand profiles you can create.

---

## Multi-Brand Corporation Pattern

This pattern is for companies that own multiple consumer-facing brands under a single corporate umbrella.

### Worked Example: Procter & Gamble

You are the marketing coordinator at P&G, responsible for Tide (laundry), Pampers (baby care), and Gillette (personal care).

#### Setting Up the Brands

```
You: /dm:brand-setup

Brand name: Tide
Elevator pitch: America's #1 laundry detergent, delivering powerful clean in every load.
Business type: B2C DTC | Industry: Consumer Packaged Goods
Voice: Formality 3, Energy 9, Humor 5, Authority 6
Tone keywords: energetic, confident, bold, clean, powerful
Avoid: gentle, delicate, luxury | Prefer: powerful, clean, fresh, tackle, brilliant
Channels: TV, Instagram, TikTok | Competitors: Persil, All, Arm & Hammer

You: /dm:brand-setup

Brand name: Pampers
Elevator pitch: Helps babies and toddlers sleep, play, and grow.
Business type: B2C DTC | Industry: Baby & Childcare (regulated)
Voice: Formality 4, Energy 5, Humor 3, Authority 7
Tone keywords: warm, nurturing, trustworthy, gentle, reassuring
Avoid: cheap, aggressive, extreme | Prefer: gentle, soft, comfort, protection, care
Channels: Instagram, Pinterest, parenting blogs | Competitors: Huggies, Luvs, Honest Company

You: /dm:brand-setup

Brand name: Gillette
Elevator pitch: The world's leading men's grooming brand.
Business type: B2C DTC | Industry: Personal Care
Voice: Formality 5, Energy 7, Humor 4, Authority 8
Tone keywords: confident, aspirational, modern, precise, premium
Avoid: cheap, basic, feminine | Prefer: precision, performance, best, confidence, sharp
Channels: YouTube, Instagram, sports sponsorships | Competitors: Dollar Shave Club, Harry's, Schick
```

#### Naming Conventions

Use the `{parent}-{brand}` naming pattern: `pg-tide`, `pg-pampers`, `pg-gillette`. This groups brands logically when listed and makes corporate ownership clear.

Other examples: `unilever-dove`, `nestle-nespresso`, `loreal-maybelline`.

#### Switching Brands and Seeing the Difference

```
You: /dm:switch-brand pg-tide
You: Write a TikTok campaign concept for our new detergent pods

(Output uses Tide's energetic/bold voice, CPG compliance, TikTok 4000-char specs,
 references Persil and Arm & Hammer as competitive context)

You: /dm:switch-brand pg-pampers
You: Write a TikTok campaign concept for our new overnight diapers

(Output uses Pampers' warm/nurturing voice, childcare advertising compliance,
 TikTok specs, references Huggies and Luvs -- completely different tone)
```

Same platform. Same content type. Completely different output -- because brand context drives everything.

#### Corporate Brand Guidelines Pattern

Create a corporate parent profile (`pg-corporate`) alongside individual brands. Use it as a baseline when setting up each brand, and switch to it for corporate-level communications.

| Voice Dimension | P&G Corporate | Tide | Pampers | Gillette |
|----------------|--------------|------|---------|----------|
| Formality      | 6            | 3    | 4       | 5        |
| Energy         | 5            | 9    | 5       | 7        |
| Humor          | 3            | 5    | 3       | 4        |
| Authority      | 8            | 6    | 7       | 8        |

Corporate keeps `authority` at 8 across the board. Tide overrides `energy` to 9 for its bold voice. Pampers stays calm. Gillette sits between them.

This is a manual process -- there is no automatic inheritance between profiles. You reference the corporate profile as a guide when configuring each brand.

#### Cross-Brand Campaign Coordination

For campaigns that span multiple brands, use this workflow:

1. **Plan in the corporate profile.** Switch to `pg-corporate` and outline the shared strategy and timeline.
2. **Execute per brand.** Switch to each brand and create brand-specific deliverables:

```
You: /dm:switch-brand pg-corporate
You: /dm:campaign-plan
(Outline the multi-brand holiday campaign: timeline, shared themes, budget split)

You: /dm:switch-brand pg-tide
You: Create Tide-specific holiday assets. Focus on Instagram and TikTok.

You: /dm:switch-brand pg-pampers
You: Create Pampers-specific holiday assets. Focus on Instagram and Pinterest.

You: /dm:switch-brand pg-gillette
You: Create Gillette-specific holiday assets. Focus on YouTube and Instagram.
```

3. **Review for consistency.** Switch back to `pg-corporate` and review all outputs against shared objectives.

---

## Agency Multi-Client Pattern

This pattern is for marketing agencies managing multiple clients with distinct identities, goals, and competitive landscapes.

### Worked Example: BrightSpark Marketing Agency

| Client | Industry | Model | Primary Channel |
|--------|----------|-------|----------------|
| TechFlow SaaS | Technology | B2B SaaS | LinkedIn |
| Artisan Bakery | Food & Beverage | Local Business | Instagram |
| Greenfield Coffee | CPG / DTC | B2C DTC | Instagram |
| Luxury Hotel Group | Hospitality | B2C eCommerce | Email |
| FitnessPro App | Health & Fitness | B2C DTC | TikTok |

### Client Onboarding Workflow

**Step 1: Create the brand profile (full mode)**

Use the 17-question full setup for agency clients. The deeper the profile, the better every output.

```
You: /dm:brand-setup
(Answer all 17 questions from the client kickoff meeting and brand guidelines)
```

**Step 2: Import competitor data**

```
You: /dm:competitor-analysis
```

**Step 3: Set channel handles**

```
You: Update the brand profile with these handles:
     Instagram: @artisanbakerynyc, Facebook: /ArtisanBakeryNYC
```

**Step 4: Create the first campaign plan**

```
You: /dm:campaign-plan
```

With the profile complete, every future request for this client uses their full context automatically.

### A Day in the Life

**9:00 AM -- Session starts, last active client loads automatically**

```
=== DIGITAL MARKETING PRO ===
Brand: Artisan Bakery (artisan-bakery)
Industry: Food & Beverage (regulated: no)
Model: Local_Business | Revenue: transactional | Sales cycle: same-day
Voice: Formality 3/10 | Energy 6/10 | Humor 5/10 | Authority 4/10
Tone: warm, community-focused, artisanal, inviting, local
Channels: Instagram, Facebook, Google Business (primary: Instagram)
Goals: foot traffic increase | KPIs: store visits, Instagram engagement
Competitors: NYC Bread Co, Borough Bakehouse, La Petite Boulangerie
Campaigns: 4 total
===
```

**9:05 AM -- Quick task for the bakery, then switch**

```
You: Draft this week's Instagram posts for Artisan Bakery

(Warm, community-focused Instagram content with food photography tips,
 local event tie-ins. Uses "artisanal," "handcrafted," "neighborhood.")

You: /dm:switch-brand techflow-saas

Plugin: Switched to TechFlow SaaS (techflow-saas).
        Industry: Technology. Business model: B2B SaaS.
        Voice: professional, authoritative, data-driven.
```

**9:15 AM -- Work on the SaaS client**

```
You: Write a LinkedIn campaign for our Q2 product launch targeting enterprise CTOs

(Professional B2B content with LinkedIn 3000-char specs, SaaS KPIs like MRR
 and churn rate, enterprise buying committee language. Completely different
 tone from the bakery content.)
```

**10:00 AM -- Switch to the hotel client**

```
You: /dm:switch-brand luxury-hotel-group
You: /dm:email-sequence
You: Design a 5-email welcome sequence for new loyalty program members

(Elegant, experiential email copy with hospitality benchmarks, luxury voice.
 References competitor loyalty programs for differentiation.)
```

Three clients, three industries, three distinct voices -- all in one session.

### Data Isolation Guarantee

**Client data never crosses boundaries.** When TechFlow SaaS is active, you see only TechFlow's campaigns, insights, performance data, voice settings, compliance rules, and competitor landscape. When you switch to Artisan Bakery, TechFlow's data is completely invisible. This is enforced by design, not convention.

If you manage competing clients in the same industry, their strategies, insights, and campaign data remain completely separate.

### Team Handoffs

Brand profiles can be shared across team members:

- **Shared drive / cloud sync**: Place `~/.claude-marketing/` on a shared or synced folder. Each team member gets access to all brand profiles.
- **Manual copy**: Copy `~/.claude-marketing/brands/{slug}/` to another machine.
- The `_active-brand.json` file is per-machine -- two team members can have different brands active simultaneously.
- Coordinate profile updates to avoid cloud sync conflicts on `profile.json`.

---

## Listing and Managing Brands

### Viewing All Brands

```
You: /dm:switch-brand

Output:
  BRANDS:
    * TechFlow SaaS [techflow-saas]
      Artisan Bakery [artisan-bakery]
      Greenfield Coffee [greenfield-coffee]
      Luxury Hotel Group [luxury-hotel-group]
      FitnessPro App [fitness-app-pro]
```

The asterisk (`*`) marks the currently active brand.

### Switching Brands

**Slash command:**
```
You: /dm:switch-brand techflow-saas
```

**Natural language:**
```
You: Switch to the bakery client
```

The plugin supports fuzzy matching -- partial matches on slug or brand name will prompt a suggestion.

### Updating a Brand

Run `/dm:brand-setup` while a brand is active, and the plugin will ask what you want to update rather than starting from scratch. You can also update fields directly:

```
You: Update the Artisan Bakery profile: add TikTok to active channels
     and set the humor dimension to 7
```

---

## Limitations & Workarounds

| Limitation | Workaround |
|-----------|------------|
| Flat profiles (no parent-child hierarchy) | Use naming conventions (`pg-tide`, `pg-pampers`) and create a corporate parent profile as a reference |
| No brand-level access control | All profiles accessible to anyone with file system access. Restrict permissions on the brands directory |
| One active brand at a time | Switch before working on a different brand. Batch tasks per brand |
| No automatic cross-brand insight sharing | Manually reference insights from other brands when needed |
| MCP credentials shared across brands | Swap environment variables in `.env` when switching between brands with different ad accounts |
| No brand archiving built-in | Rename slug directory to `_archived-{slug}` (directories starting with `_` are ignored by the listing command) |
| No bulk brand operations | Update brands one at a time, or write a script to iterate over `brands/*/profile.json` |
| Session state resets on new session | Last active brand loads automatically. Switch immediately if needed |

---

## Best Practices

### Naming Conventions

**Agencies:** `{client}-{brand}` -- `brightcorp-main`, `localcafe-downtown`
**Corporations:** `{parent}-{brand}` -- `pg-tide`, `pg-pampers`
**Freelancers:** `{descriptive-name}` -- `my-saas-startup`, `client-jones-realty`

Avoid special characters, spaces, and uppercase in slugs.

### Setup Mode Selection

**Use full setup (17 questions)** for long-term agency clients, high-volume content brands, regulated industries, and shared team profiles.

**Use quick setup (5 questions)** for short-term projects, prospect testing, personal experiments, and situations where you need to start immediately.

You can always upgrade from quick to full by running `/dm:brand-setup` again.

### Voice Dimension Reference

| Formality | Example Brands |
|-----------|---------------|
| 1-3       | Wendy's Twitter, Mailchimp, Slack |
| 4-6       | Apple, Airbnb, Nike |
| 7-10      | McKinsey, The Economist, Deloitte |

| Energy | Example Brands |
|--------|---------------|
| 1-3    | Calm app, Muji, Patagonia |
| 4-6    | Nike, Spotify, Apple |
| 7-10   | Red Bull, GoPro, Monster Energy |

| Humor | Example Brands |
|-------|---------------|
| 1-3   | IBM, Goldman Sachs, Google |
| 4-6   | Old Spice, Duolingo, Salesforce |
| 7-10  | Wendy's, Liquid Death, MoonPie |

| Authority | Example Brands |
|-----------|---------------|
| 1-3       | BuzzFeed, a friend's recommendation |
| 4-6       | HubSpot, Moz, Refinery29 |
| 7-10      | Harvard Business Review, Mayo Clinic, FDA |

### Maintenance Schedule

**Weekly:** Review generated content against brand voice. Revisit dimensions if outputs drift.

**Monthly:** Update KPIs and performance data. Refine `avoid_words` and `prefer_words`. Add new voice samples.

**Quarterly:** Update competitor lists and re-run `/dm:competitor-analysis`. Review target markets. Check compliance for regulatory changes.

**Annually:** Full `/dm:brand-setup` refresh for each active brand. Archive churned clients. Review portfolio consistency.

### Backup Strategy

The `~/.claude-marketing/brands/` directory is all of your brand intelligence. Include it in your regular backup system. For agencies, consider version-controlling profiles with Git:

```
cd ~/.claude-marketing
git init && git add brands/ && git commit -m "Brand profile backup"
```

### Handling Competing Clients

If your agency manages two competitors in the same industry:

1. The plugin enforces data isolation, but be mindful in your own prompts -- never reference one client's data when working on the other.
2. Differentiate voice dimensions even if both brands want similar tones. Use distinct `tone_keywords`, energy, and humor levels.
3. Batch your work per brand rather than switching between competitors rapidly.

---

## Quick Reference

| Task | Command |
|------|---------|
| Create a new brand (quick) | `/dm:brand-setup` |
| Create a new brand (full) | `/dm:brand-setup --full` |
| List all brands | `/dm:switch-brand` (no argument) |
| Switch active brand | `/dm:switch-brand {slug}` |
| View active brand summary | Start a new session or ask "What brand is active?" |
| Update existing brand | `/dm:brand-setup` while brand is active |
| Archive a brand | Rename directory to `_archived-{slug}` |
| Restore an archived brand | Rename directory back to `{slug}` |
| Backup all brands | Copy `~/.claude-marketing/brands/` |

---

*Part of the Digital Marketing Pro documentation. For installation and general usage, see the main README.*
