# Roadmap — Multiagent Sessions API + Memory API integration

**Status:** Planning document (not yet implemented). Targets a future v3.x / v4.0 release.
**Anthropic feature status (May 2026):** Both APIs are in **public beta** under the `managed-agents-2026-04-01` Messages API beta header.

## What Anthropic shipped (April–May 2026)

### Multiagent Sessions & Outcomes API

Formal multi-agent coordination primitives — replaces the ad-hoc "dispatch parallel Task calls from a single message" pattern that DMP v3.4 documents. Provides:

- **Shared session context** between subagents within a managed agent run — no need to re-load state at every dispatch
- **Outcome tracking** — each subagent reports a structured outcome that the orchestrator consumes; success/failure/partial states are first-class
- **Agent-to-agent messaging** — for the complex Agent Teams pattern where teammates claim tasks off a shared backlog rather than being centrally dispatched
- **Initialization parallelism** — already shipped April 24, 2026 as a free win for any dispatch pattern (the basis of DMP v3.4's `~50–80% wall-clock reduction` claim)

### Memory for Managed Agents API

Persistent memory across agent invocations within a managed session. Today DMP uses local JSON files (`~/.claude-marketing/<brand>/insights/`, `_engagement.json`) for the same purpose. The managed-agents Memory API would:

- Move brand-profile + engagement-state + cross-engagement insights into Anthropic-managed memory
- Provide structured read/write APIs from any subagent in the session, with automatic context-window management
- Eliminate the "re-load LIF at each Part transition" pattern (the 1M-context note in `skills/engagement-workflow/SKILL.md` covers the same outcome via raw context, but Memory API is the long-term right answer)

## What DMP would change to adopt this

### Phase A (v3.5 — opt-in beta path, no breaking changes)

- Add `dmp-config: { use_managed_agents_beta: true }` to brand-profile schema
- When set: engagement-state.py writes BOTH to local JSON (current behavior) AND to managed-agent memory (forward path) — dual-write keeps the local-file path working for non-beta users
- Refactor the dispatch sites in `skills/engagement-workflow/SKILL.md` Parts 2, 4, 9, 10, 11 to use the managed-agents subagent primitive when the flag is on; fall back to current Task-tool dispatch when off
- Subagents read shared context from managed memory rather than re-loading the LIF on every dispatch

### Phase B (v4.0 — managed-agents as default, local-file fallback)

- Flip the default: managed-agents is on by default; users who want local-file-only persistence set `use_managed_agents_beta: false`
- Refactor `engagement-state.py` to be a thin wrapper over the Memory API by default
- Document the migration path for users who built tooling around the local JSON files (most agency users)
- Move from "documented parallel dispatch" (current state, hand-tuned) to "managed Agent Teams" (Anthropic-managed task distribution + outcome tracking)

### Phase C (v4.1+ — long-running engagements as managed sessions)

- A multi-week brand engagement (12 parts across 4 weeks of client iteration) becomes a single managed session with persistent state
- No more "re-explain the brand at every conversation start"; the managed session is the source of truth
- The Two-Views Model (v1 unbiased + v2 client-validated) lives natively in managed memory rather than in versioned files

## What we are NOT going to do until Anthropic moves these out of beta

- We will not deprecate the local-file persistence path. Beta APIs change. Users on third-party Claude API access (AWS Bedrock, Vertex AI) may not get managed-agents on the same timeline as direct API users. The local-file path is the durable fallback.
- We will not REQUIRE the beta header. The plugin must work for users who don't have managed-agents enabled on their API key.
- We will not assume Memory API pricing matches current Claude API token pricing. Pricing for memory storage and retrieval has not been published as of May 2026.

## Open questions

- **Pricing.** Anthropic has not published pricing for managed-agent memory storage or for the Multiagent Sessions API beyond standard Claude API token costs. We need pricing clarity before recommending this as the default for agency users running 50–200 brand engagements.
- **Cowork compatibility.** Cowork is the Anthropic Desktop computer-use product — does it support `managed-agents-2026-04-01`? Unverified as of May 2026.
- **Cross-API-provider compatibility.** Users on Claude API via AWS Bedrock or Google Vertex AI may not get managed-agents on the same timeline. The local-file fallback path stays load-bearing for these users.
- **Migration story.** A user who already has 50+ brand engagements in `~/.claude-marketing/<brand>/` needs a one-shot migration to managed memory. Should the v3.5 release include a `/digital-marketing-pro:migrate-to-managed-memory` command, or defer to v4.0?

## Tracking

- Anthropic beta header: `managed-agents-2026-04-01`
- Anthropic docs (when published): platform.claude.com → Messages API → Managed Agents section
- Relevant DMP files when implementation begins: `skills/engagement-workflow/SKILL.md` (dispatch sites), `scripts/engagement-state.py` (persistence), `config/brand-registry-template.json` (to be created — config flag)

## When to revisit this doc

- When Anthropic moves Multiagent Sessions or Memory API to GA
- When Anthropic publishes pricing
- When a real DMP user requests the managed-agents path
- When Cowork support is confirmed

---

**This is a planning document.** No code in DMP implements anything in this doc — the managed-agents path remains unadopted and engagement state still persists to local JSON files. It exists so the team knows the direction and can evaluate whether to start Phase A in a future release.
