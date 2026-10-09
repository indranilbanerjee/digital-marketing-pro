---
description: "Drive the 12-Part engagement by subcommand: start, next, status, validate, loop. \"advance to the next part\""
argument-hint: "<subcommand> [args]"
allowed-tools: Read Write Edit Bash Glob Grep
---

# /digital-marketing-pro:engagement — 12-Part Engagement Workflow

The engagement command family runs a complete marketing engagement using the 12-Part methodology. Every brand engagement runs through 12 parts in sequence, producing a canonical set of files at each stage.

This command is the entry point. It invokes the [engagement-workflow](../skills/engagement-workflow/SKILL.md) skill, which delegates to part-specific skills (four-core-documents, client-validation-document, growth-plan, yearly-planner, continuous-improvement-loop).

## Subcommands

### `/digital-marketing-pro:engagement start <brand-slug> <engagement-id>`

Initialise a new engagement. Creates the directory tree, writes `_engagement.json`, walks the user through Part 1 Stone vs Opinion intake.

**Example:**
```
/digital-marketing-pro:engagement start acme-corp 2026-q2
```

**Pre-condition:** Brand profile must exist at `~/.claude-marketing/brands/{brand-slug}/profile.json`. If not, run `/digital-marketing-pro:brand-setup` first.

**Checkpointing & resume:** The full checkpoint protocol — open a run on `start`, save each part as it completes, run `/digital-marketing-pro:check --full` before the Part 5 and Part 8 deliverables, then publish and finalize at the end — lives in the skill. See [engagement-workflow/SKILL.md](../skills/engagement-workflow/SKILL.md) § *Checkpointing & Resume* (the single source of truth). Each part's checkpoint saves **that part's own deliverable path** (Part 3 saves the Four Core Documents, Part 8 saves the Growth Plan — never a placeholder for a different part). An interrupted run resumes with `/digital-marketing-pro:resume`, and the finished files land in the visible output folder (`/digital-marketing-pro:output-folder {brand}`).

### `/digital-marketing-pro:engagement status [brand-slug] [engagement-id]`

Show the current engagement status. If brand and id are omitted, shows all active engagements.

**Example:**
```
/digital-marketing-pro:engagement status acme-corp 2026-q2
```

### `/digital-marketing-pro:engagement next [brand-slug] [engagement-id]`

Advance to the next part after confirming current is complete. Will not auto-advance — asks for confirmation.

### `/digital-marketing-pro:engagement validate <brand-slug> <engagement-id>`

Run Part 5 Client Validation. Invokes the `client-validation-document` skill to produce the deliverable. Pre-condition: Parts 2, 3, 4 must be complete.

### `/digital-marketing-pro:engagement re-run-decision <brand-slug> <engagement-id>`

Apply the Decision Matrix to determine which v2 re-runs are needed. Reads the Part 5 Client Validation responses and computes the re-run plan.

**Pre-condition:** Part 5 Client Validation responses must be saved at `engagements/{id}/part-05-client-validation/client-validation-responses.json`.

### `/digital-marketing-pro:engagement update-back <brand-slug> <engagement-id> --doc <doc-id> --reason "<reason>"`

Apply the Update-Back Rule (Part 7+ corrections). Bumps a source document version, saves new file, updates the Living Project Instruction File.

**Example:**
```
/digital-marketing-pro:engagement update-back acme-corp 2026-q2 --doc 3.1 --reason "Segment X CAC corrected from INR 3,000 to INR 4,800 based on Q2 channel data"
```

### `/digital-marketing-pro:engagement lif-show <brand-slug> <engagement-id>`

Display the Living Project Instruction File (the engagement's "currently true" record).

### `/digital-marketing-pro:engagement file-tree <brand-slug> <engagement-id>`

Show the engagement directory file tree.

### `/digital-marketing-pro:engagement list-engagements [brand-slug]`

List all engagements (optionally filtered by brand).

### `/digital-marketing-pro:engagement four-core <brand-slug> <engagement-id> [--doc 3.X] [--view v2] [--combined]`

Produce the Four Core Documents (Part 3). Shorthand for invoking the `four-core-documents` skill. Flags: `--doc` (single id `3.1` or comma-separated `"3.1,3.3"`), `--view v2` (Part 6 re-runs), `--combined` (stitch all four into the 3.C executive reference).

### `/digital-marketing-pro:engagement growth-plan <brand-slug> <engagement-id>`

Produce the Growth Plan (Part 8). Shorthand for invoking the `growth-plan` skill.

### `/digital-marketing-pro:engagement yearly-planner <brand-slug> <engagement-id>`

Produce the Yearly Planner (Part 8 companion). Shorthand for invoking the `yearly-planner` skill.

### `/digital-marketing-pro:engagement loop <brand-slug> <engagement-id>`

Produce a Part 12 Continuous Improvement deliverable (quarterly brief or ad-hoc). Shorthand for invoking the `continuous-improvement-loop` skill.

## Typical Engagement Flow

A complete engagement runs through these commands over weeks to months:

```
# Day 1: Setup
/digital-marketing-pro:brand-setup acme-corp                              # Creates brand profile (one-time per brand)
/digital-marketing-pro:engagement start acme-corp 2026-q2                 # Initialises engagement; walks Part 1 intake

# Days 2-7: Unbiased research (Parts 2-4)
# (delegated to existing skills: market-intelligence, competitor-analysis, audience-intelligence)
/digital-marketing-pro:engagement next acme-corp 2026-q2                  # Advance to Part 2 after Part 1 complete
# ... repeat advancement after each part

# Day 8: Strategic core (Part 3)
/digital-marketing-pro:engagement four-core acme-corp 2026-q2             # Produces all 4 core documents (61 steps)

# Day 14: Client validation (Part 5)
/digital-marketing-pro:engagement validate acme-corp 2026-q2              # Produces client validation document
# ... client reviews; responses captured in client-validation-responses.json

# Day 17: V2 re-runs (Part 6)
/digital-marketing-pro:engagement re-run-decision acme-corp 2026-q2       # Computes re-run plan
/digital-marketing-pro:engagement four-core acme-corp 2026-q2 --view v2 --doc 3.3   # Re-run specific docs as v2

# Days 18-21: Preparation + flagship deliverables (Parts 7-8)
/digital-marketing-pro:engagement next acme-corp 2026-q2                  # Advance to Part 7
# (Part 7 prep docs produced via campaign-orchestrator + content-engine + analytics-insights)
/digital-marketing-pro:engagement growth-plan acme-corp 2026-q2           # Part 8 flagship
/digital-marketing-pro:engagement yearly-planner acme-corp 2026-q2        # Part 8 operational companion

# Days 22-30: Channel execution (Parts 9-11)
/digital-marketing-pro:engagement next acme-corp 2026-q2                  # Advance to Part 9
# (Part 9 channel docs produced via per-channel skills in paid-advertising/aeo-geo/etc.)
# (Parts 10-11 produced via content-engine in execution mode)

# Day 31 onwards: Continuous improvement (Part 12)
/digital-marketing-pro:engagement next acme-corp 2026-q2                  # Activate Part 12 — runs continuously
# Quarterly briefs at QBR; ad-hoc briefs as significant signals warrant:
/digital-marketing-pro:engagement loop acme-corp 2026-q2
```

## What the workflow produces

A typical engagement produces 50–60 files in this canonical structure:

```
~/.claude-marketing/brands/acme-corp/engagements/2026-q2/
├── _engagement.json
├── living-instruction-file.md
├── part-01-client-inputs/
│   ├── stone-facts.json
│   ├── opinion-hypotheses.json
│   └── intake-questionnaire.md
├── part-02-external-research/  (3 research docs)
├── part-03-four-core-documents/
│   ├── v1/  (3.1, 3.2, 3.3, 3.4)
│   └── v2/  (subset re-run per Decision Matrix)
├── part-04-competitive-customer-market/
│   ├── v1/  (4.1, 4.2, 4.3, 4.4)
│   └── v2/
├── part-05-client-validation/
│   ├── client-validation-document.md
│   └── client-validation-responses.json
├── part-06-v2-reruns/  (record of decisions; actual re-runs land in part-03/v2 + part-04/v2)
├── part-07-preparation/  (6 prep docs)
├── part-08-growth-plan/
│   ├── growth-plan.md  (+ PDF + DOCX)
│   └── yearly-planner.md  (+ PDF + XLSX)
├── part-09-channel-strategy/  (up to 17 channel docs)
├── part-10-execution-artefacts/
├── part-11-ai-creative-instructions/
├── part-12-continuous-improvement/
│   ├── signals.jsonl
│   ├── quarterly-briefs/
│   └── ad-hoc-briefs/
└── reports/
    ├── monthly/
    ├── quarterly/
    └── annual/
```

## Related references

- [engagement-flow-methodology.md](../skills/context-engine/engagement-flow-methodology.md) — the full 12-Part methodology
- [four-core-documents-spec.md](../skills/context-engine/four-core-documents-spec.md) — Part 3 specification
- [decision-matrix-rerun.md](../skills/context-engine/decision-matrix-rerun.md) — Part 6 re-run logic
- [update-back-rule.md](../skills/context-engine/update-back-rule.md) — Part 7+ correction protocol
- [growth-plan-template.md](../skills/context-engine/growth-plan-template.md) — Part 8 deliverable template
- [yearly-planner-template.md](../skills/context-engine/yearly-planner-template.md) — Part 8 companion template
