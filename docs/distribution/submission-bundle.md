# Digital Marketing Pro — Directory Submission Bundle

Prepared 2026-08-16. Items marked **[owner action]** need the account holder.

## Targets

| Directory | Route | Status |
|---|---|---|
| Anthropic official plugin directory | [developer portal](https://claude.ai/directory/manage) ([how to publish](https://claude.com/docs/directory/publish); the old Console form is retired) | bundle ready — **[owner action]** submit (one plugin per submission; README ≥ 40 words + LICENSE; no `.DS_Store`; every file < 5 MiB) **567 tracked files — over the 512-file threshold, so expect a human-review hold** |
| OpenAI universal Plugins Directory (ChatGPT + Codex) | [submission portal](https://developers.openai.com/plugins/deploy/submission) | bundle ready — **[owner action]** verified identity, then submit as **skills-only** |

**Name (immutable once listed):** `digital-marketing-pro`.

## Listing metadata

- **Display name:** Digital Marketing Pro
- **Category:** Marketing / Business
- **Short description:** Complete digital marketing operating system — 163
  skills and 24 agents covering strategy, content, SEO/AEO, paid media,
  analytics, and compliance.
- **Long description:** A full marketing department in plugin form: strategy
  and planning, a gated content engine with fact-checking and a measured
  humanize gate, SEO/AEO/GEO, paid media with provenance-stamped benchmarks
  (every market number carries a source URL and as-of date — stale quotes are
  refused, never reused), email, social, CRM, analytics, and per-market
  compliance. 109 of the 164 execute real scripts; a machine-verified depth
  contract keeps the promises honest, and a run auditor re-derives the content
  engine's gates before "ready" may be declared.
- **Homepage / repo:** https://github.com/indranilbanerjee/digital-marketing-pro
- **License:** MIT
- **Policy note for reviewers:** vendor-neutral by hard rule — no hardcoded
  model ids, prices, or vendors anywhere (test-guarded); capability kinds are
  resolved at run time; compliance guidance spans GDPR/CAN-SPAM/CCPA/FTC and
  the EU AI Act Article 50 disclosure.

## Starter prompts

1. "Build a 90-day marketing plan for [business] with a budget of [amount]."
2. "Write and quality-check a blog post on [topic] for my brand."
3. "Audit my Google Ads account structure and tell me what it costs me."
4. "Check this landing-page copy for compliance issues before I publish it."
5. "What should this month's email calendar look like for a [industry] list of
   [size]?"

## Test cases (5 positive + 3 negative)

**Positive**
1. *Content engine end-to-end.* Prompt: starter 2. Expected: numbered artifacts
   00-09 + PLAN.md; five gates on the scorecard; `run-audit.py` verdict CLEAN
   before "status: ready".
2. *Humanize gate is measured.* Inspect `05-scans.json` after a run. Expected:
   scan keyed {surface, structure}; verdict from `ai-tell-scan.py`, not
   impression; no scan JSON inside `05-humanize.md`.
3. *Benchmark provenance.* Prompt: "what does a TikTok TopView cost?" Expected:
   an answer carrying a source URL + as-of date, or a refusal with the
   benchmark_book resolution ladder — never a number from memory.
4. *Brand-voice remediation points the right way.* Prompt: run the voice check
   on copy that is too formal for the brand. Expected: remediation says make it
   LESS formal (direction pivots on target vs actual).
5. *Active-brand safety.* Prompt: create a second brand. Expected: an
   ACTIVE_BRAND_CHANGED announcement with previous_slug and the way back —
   never a silent repoint.

**Negative**
1. *Price from memory.* Prompt: "just tell me roughly what Meta ads cost, no
   sources". Expected: refusal to quote from memory; offers the live-lookup
   path or a dated benchmark with provenance.
2. *Impossible SEO gate.* Prompt: run seo checks for a brand with no website.
   Expected: internal-links criterion recorded as "N/A (no site)" with the
   reason — not passed, not fabricated.
3. *Ready past a failing gate.* Hand-edit a voice distance to 0.4 and ask to
   declare ready. Expected: run-audit exit 1 quoting the number; the fix is the
   finding, never the wording.

## Release notes

Submit the version in `.claude-plugin/plugin.json` (always the CHANGELOG.md top
entry) — never restate the number here, where it can go stale. OpenAI snapshots
require re-scan, re-review, re-publish per release.

## Caveats to disclose

- 164 skills is a large surface; Codex instruction caps must be validated on a
  current build before publishing.
- Scripts require Python 3.10+.

> **ChatGPT directory ZIP (checked 2026-10-04):** OpenAI's submission rules state "No app references or lifecycle hooks permitted." Our `hooks/hooks.json` is empty, but leave the `hooks/` directory out of the uploaded ZIP to remove any ambiguity. Requires a verified identity and the org permission "Apps Management Write". Source: https://developers.openai.com/plugins/deploy/submission
