# Anthropic Software Directory — Submission Packet

> **⚠️ Historical snapshot.** This packet was first drafted for the **v3.4.0** submission (May 2026). The current shipping release has **164 skills, 24 specialist agents, 5 commands, and 94 Python scripts**. The counts and agent list below have been refreshed to the current release; treat CHANGELOG.md + README.md as the authoritative source for exact numbers before any re-submission.

**Plugin:** Digital Marketing Pro
**Current version:** see `.claude-plugin/plugin.json` (originally submitted at 3.4.0)
**Submitter:** Indranil Banerjee — neel@neelverse.com
**Repository:** https://github.com/indranilbanerjee/digital-marketing-pro
**Marketplace:** https://github.com/indranilbanerjee/neels-plugins
**Last updated:** 2026-07-09

This file is the **submission packet** for the Anthropic Software Directory. It is **not** the directory listing — that is submitted via the form at https://platform.claude.com/plugins/submit. This packet pre-stages every input the form will ask for so the actual submission takes 5 minutes, not 5 hours.

(A prior version of this file referenced `https://claude.ai/settings/plugins/submit` as a consumer-surface submission URL; that URL was not verifiable in Anthropic's published docs as of May 2026 and has been removed. Use the platform.claude.com URL.)

## 1. One-line description (for the directory card)

> Multi-agent digital marketing methodology — 12-Part Strategy Flow, Four Core Documents, 24 specialist agents, 16 industry profiles, 16 privacy-law jurisdictions. For agencies and in-house teams.

## 2. Long description (for the directory detail page)

Digital Marketing Pro is an end-to-end engagement methodology for marketing teams running on Claude Code & Cowork. Every brand engagement runs through a canonical 12-Part Strategy Flow producing the Four Core Documents (61 explicit steps), the Two-Views Model (v1 unbiased + v2 client-validated), the Decision Matrix for selective re-runs, the Update-Back Rule for in-life corrections, and a Living Project Instruction File that keeps all downstream skills synchronized to the latest source-of-truth.

The plugin ships 24 specialist agents (marketing-strategist, content-creator, seo-specialist, analytics-analyst, brand-guardian, media-buyer, growth-engineer, influencer-manager, competitive-intel, pr-outreach, email-specialist, cro-specialist, social-media-manager, execution-coordinator, performance-monitor-agent, crm-manager, memory-manager, agency-operations, marketing-scientist, market-intelligence, intelligence-curator, journey-orchestrator, quality-assurance, localization-specialist), 164 skills, 94 Python scripts, 5 top-level commands, 14 HTTP MCP connectors (opt-in), 16 industry profiles (pharma, BFSI, healthcare, legal, real estate, technology, B2B SaaS, e-commerce, consumer goods, education, and more), and 16 privacy-law jurisdictions including the EU AI Act Article 50 (C2PA provenance for AI-generated marketing assets, applicable 2 Aug 2026), DPDP Act Phase II (effective 13 Nov 2026), CCPA ADMT amendments, NY synthetic-performer law, and FTC May 2026 endorsement guidance.

Built for digital marketing agencies managing 50–200 brands, in-house marketing teams with high content volume, content operations in regulated industries, and enterprise brands requiring consistent quality at scale. Multi-plugin coexistence by design (zero global hooks, zero auto-connecting MCP servers). Full Cowork compatibility — all 14 connectors are HTTP, Python scripts run natively.

## 3. Category

`Marketing & Sales` (primary) · `Productivity` (secondary)

## 4. Target audience

- Digital marketing agencies (5–500 employees) running multi-client portfolios
- In-house marketing teams (B2B + B2C) producing 20+ content pieces / month
- Content operations in regulated industries: pharma, BFSI, healthcare, legal
- Marketing consultants and fractional CMOs

## 5. Three+ working prompts / use cases (Anthropic policy requirement)

### Use case 1 — Run a full 12-part brand engagement

```
/digital-marketing-pro:brand-setup
/digital-marketing-pro:engagement
```

Walks the brand through Stone-vs-Opinion intake (Part 1) → unbiased external research (Part 2) → Four Core Documents covering Business & SBU Analysis, Segmentation, Brand Positioning, DMFlow (Part 3, 61 steps) → competitive/customer/market analysis (Part 4) → Client Validation Document (Part 5) → selective v2 re-runs per the Decision Matrix (Part 6) → preparation documents (Part 7) → Growth Plan + 12-month Yearly Planner (Part 8) → channel strategy fan-out across 7 families and up to 17 channels (Part 9, parallel-dispatched) → execution artefacts (Part 10) → AI creative instructions (Part 11) → continuous improvement loop (Part 12). Outputs ~50–60 canonical files in `~/.claude-marketing/brands/<brand>/engagements/<engagement-id>/`.

**Expected duration:** 2–5 hours of conversation across a full engagement; ~$30–80 in Claude API costs using Opus 4.8.

### Use case 2 — Pre-publish quality gate for EU-targeted AI content

```
/digital-marketing-pro:c2pa-metadata \
    --input assets/q3-hero.png \
    --output assets/signed/q3-hero.png \
    --brand "Acme Corp" \
    --generator "Vertex AI image model" \
    --ai-claim ai-generated-content

/digital-marketing-pro:check drafts/q3-launch-blog.md --brand acme-corp --schema blog_post
```

The first command embeds a C2PA provenance manifest in an AI-generated image so it complies with EU AI Act Article 50 (applicable 2 Aug 2026). The second runs a unified quality gate: hallucination check + brand voice scoring + structure validation + claims verification + (for EU-targeted brands) C2PA presence verification on AI-flagged assets. Returns PASS / WARN / BLOCKED with per-issue fix suggestions.

### Use case 3 — Multi-dimensional competitive intelligence with parallel dispatch

```
/digital-marketing-pro:competitor-analysis HubSpot Marketo Klaviyo
```

Dispatches 7 parallel subagents per competitor (content, SEO, paid ads, social, AI visibility, pricing, positioning) and produces a unified competitive intelligence report. Parallel-dispatched per the v3.4 execution discipline — ~6 minutes wall-clock per competitor vs ~35 minutes sequential.

### Use case 4 — Multi-brand agency workflow

```
/digital-marketing-pro:switch-brand pharma-client-a
/digital-marketing-pro:engagement
# ... later
/digital-marketing-pro:switch-brand bfsi-client-b
/digital-marketing-pro:engagement
```

Each brand has its own `~/.claude-marketing/brands/<brand-slug>/` directory with isolated voice, guardrails, jurisdictions, engagements, and insights. Switching is instantaneous — no re-setup, no context bleed between clients.

## 6. Testing account / sample data

**Testing account:** Reviewers can install the plugin from the public marketplace at `indranilbanerjee/neels-plugins` and create a sample brand interactively via `/digital-marketing-pro:brand-setup` (no bundled `config/` template file ships — profiles are generated by the setup skill). No paid services or API keys required for the default knowledge-only mode (covers all 164 skills + 24 agents + 176 reference files). Optional Python scoring scripts use `nltk` and `textstat` (free, open-source).

**Sample brand profile:** Run `/digital-marketing-pro:brand-setup` (Quick or Full mode) to generate a fully populated `profile.json` under `~/.claude-marketing/brands/<slug>/` showing every supported field (voice, audience, channels, guardrails, jurisdictions, etc.). There is no committed `examples/` or `config/` sample directory in the repo.

## 7. Ownership verification

- **Repo:** github.com/indranilbanerjee/digital-marketing-pro — owned by GitHub user @indranilbanerjee (the submitter)
- **Marketplace:** github.com/indranilbanerjee/neels-plugins — same owner
- **Domains referenced:** none — plugin does not host any first-party API. All MCP connectors point to third-party services (Anthropic, Notion, Slack, Canva, Figma, HubSpot, Amplitude, Ahrefs, Similarweb, Klaviyo, Google, Gmail, Stripe, Asana, Webflow). Ownership of those services is held by their respective companies and the plugin only accesses them via official OAuth / HTTP MCP endpoints — no scraping, no credential interception, no impersonation.
- **Trademarks:** "Digital Marketing Pro" and "Neelverse" are submitter's marks. No third-party trademarks used in the plugin name, command names, or UI strings.

## 8. Compliance with Anthropic Software Directory Policy

| Policy area | Plugin status |
|---|---|
| No High-Risk Use Cases | ✓ Plugin does not perform medical diagnosis, legal advice, financial decisions, employment screening, biometric inference, or any other high-risk category per Anthropic's Usage Policy. Industry profiles for healthcare/pharma/legal/finance provide content-creation guardrails ONLY — the plugin explicitly disclaims advisory authority and surfaces compliance-rule violations as warnings, not authoritative judgments. |
| No Usage Policy violation | ✓ Plugin generates marketing content; does not produce malware, illegal goods listings, disinformation, scams, or any prohibited content. Brand `guardrails.prohibited_claims` mechanism is provided so brand owners can declare additional prohibited content per their internal policy. |
| Testing account + sample data + 3+ use cases | ✓ See sections 5 and 6 above. |
| Ownership of APIs / domains / UIs | ✓ See section 7. |
| Maintenance commitment | ✓ Plugin updated at least quarterly; v3.0 (Apr 2026) → v3.1 (May 3) → v3.2 (May 3) → v3.2.1 (May 4) → v3.2.2 (May 9) → v3.3.0 (May 15) → v3.4.0 (May 16) demonstrates active maintenance cadence. Issue triage: <72 hours typical response time via GitHub Issues. |
| Issue response timeframe | ✓ Submitter commits to acknowledging issues within 72 hours and shipping patches for security/correctness within 7 days. Feature requests evaluated quarterly. |
| Software Directory Terms agreement | ☐ To be agreed at submission time via the form. |
| Design guidelines | ✓ Plugin name uses canonical Claude Code namespace `/digital-marketing-pro:<command>`; no bare slash commands that conflict with other plugins; README is onboarding-first per v3.3 restructure; all command frontmatter has `description`, `argument-hint`, `allowed-tools` per Claude Code spec. |

## 9. Cowork compatibility statement

- All 14 HTTP MCP connectors work in both Claude Code and Cowork.
- All 94 Python scripts run natively in Cowork (Cowork is the Anthropic Desktop computer-use product with local filesystem access).
- Plugin ships zero global hooks (`hooks/hooks.json` is empty) and zero auto-connecting MCP servers (no `.mcp.json` ships; connectors are opt-in via `/digital-marketing-pro:connect`). Multi-plugin coexistence by design.
- HTTP-only stack means no stdio/npx dependencies are required; users who want the wider stdio MCP catalog can `cp .mcp.json.example .mcp.json` (Claude Code only) or use the Pipedream/Composio/Zapier/Make.com aggregator paths documented in `.mcp.json.connectors-reference` (Cowork-compatible).

## 10. Verified-badge eligibility (optional second tier)

The Anthropic Verified badge requires additional manual quality and safety review. DM Pro is a candidate based on:
- ~600-reference namespace consistency sweep (v3.2.2) — every documented command works as documented
- Three-layer fact verification pattern (research → fact-check → final review) in content workflows
- EU AI Act Article 50 C2PA implementation (v3.4) — first marketing plugin in the directory to embed provenance manifests
- 16-jurisdiction compliance rule pack maintained quarterly
- Zero known critical issues in the public Issues tracker at submission time

If applying for Verified, additional materials to prepare:
- Security review of `embed-c2pa.py` (handles signing keys — should describe key-management expectations)
- Privacy review of profile.json schema (handles brand data — confirm no PII transmission outside Claude API)
- Code review of `eval-runner.py` (the `/check` gate that BLOCKs publication — quality is load-bearing)

## 11. Screenshots to include with submission

Capture before submitting:
1. `/digital-marketing-pro:status` output for a populated brand (shows the brand snapshot UX)
2. A completed `/digital-marketing-pro:engagement` Part 5 Client Validation Document (shows the methodology output)
3. A `/digital-marketing-pro:check` BLOCKED decision with CRITICAL issues highlighted (shows the quality gate UX)
4. `/digital-marketing-pro:competitor-analysis` final report (shows multi-dimensional output)
5. A C2PA-signed asset verified at https://contentcredentials.org/verify (shows Article 50 compliance in action)

## 12. Submission steps (for the submitter to execute)

1. Open https://platform.claude.com/plugins/submit
2. Plugin name: `digital-marketing-pro`
3. Marketplace source: `github.com/indranilbanerjee/neels-plugins` (custom marketplace) OR `github.com/indranilbanerjee/digital-marketing-pro` (direct repo)
4. Paste section 1 (one-line) into "Short description"
5. Paste section 2 (long description) into "Description"
6. Select category: Marketing & Sales (primary), Productivity (secondary)
7. Upload screenshots from section 11
8. Confirm testing-account + sample-data declaration (sections 5, 6)
9. Confirm ownership (section 7)
10. Check the Software Directory Terms box
11. Submit

Expected review timeline (per Anthropic published docs): basic listing 1–2 weeks; Anthropic Verified 4–6 weeks.

---

**This packet is maintained in the repo at `SUBMISSION.md` so it can be refreshed each release before re-submission.**
