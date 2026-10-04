# Digital Marketing Pro — agent context

This file is auto-loaded by OpenAI Codex, Google Antigravity, GitHub Copilot CLI, Cursor (when in the agent context chain), and other Agent Skills runtimes. It is the equivalent of `CLAUDE.md` for non-Claude surfaces.

## What this plugin is

Digital Marketing Pro is a comprehensive open-source AI marketing plugin shipping **164 skills, 24 specialist agents, a 12-Part Strategy Flow, and EU AI Act Article 50 readiness**. Built for marketing agencies, in-house teams running 50–200 brands, and consultancies.

**Supported surfaces (v3.33.3):** Claude Code (CLI + IDE extensions), Anthropic Cowork, OpenAI Codex (CLI + IDE + App), Cursor 2.5+, GitHub Copilot CLI, Google Antigravity 2.0 (CLI + IDE), **Hermes Agent (Nous Research, Desktop v0.15.2+)**, **OpenClaw (formerly Clawdbot/Moltbot)**, **Grok (xAI Build CLI, native `.grok-plugin/` pair)**. Plus 35+ additional platforms via the Agent Skills open standard (Goose, OpenHands, OpenCode, Junie, Gemini CLI, Roo Code, Kiro, Amp, Letta, Mux, Factory, Workshop, Tabnine, Mistral Vibe, and more — see README "Works on 40+ agent harnesses").

**Cowork-specific:** On Anthropic Cowork the per-session filesystem is ephemeral (`~/.claude-marketing/` AND `${CLAUDE_PLUGIN_DATA}` BOTH vanish at session end — known platform issue #51398). Run `/digital-marketing-pro:cowork-setup` once per team to route brand state through a Google Drive MCP so profiles, plans, and reports survive across sessions.

## How to use it as an agent

1. **Discover skills by description.** All 164 skills auto-discover via SKILL.md frontmatter (`name:` + `description:`). Match user intent to skill description.
2. **Run skills by routing user requests to the matching SKILL.md.** Read the skill body for instructions, scripts to run, references to pull.
3. **Skill bodies may reference Python scripts at `scripts/<name>.py`** — invoke via Bash / `run_shell_command`.
4. **HTTP MCP connectors are opt-in.** See `.mcp.json.connectors-reference` for the full catalog (Slack, HubSpot, Notion, Gmail, Google Calendar, Stripe, Ahrefs, SimilarWeb, Klaviyo, Amplitude, Canva, Figma, Asana, Webflow). User must configure env vars or set up MCP servers before they connect.
5. **Compliance is mandatory.** Skills enforce GDPR / CCPA / EU AI Act / DPDPA / LGPD / 11 other privacy jurisdictions. Don't skip the compliance gates.
6. **C2PA content provenance is required for AI-generated assets in EU campaigns** (Article 50, applicable 2 Aug 2026). Use `scripts/embed-c2pa.py` to sign before delivery.

## Canonical entry points

| User intent | Run skill |
|---|---|
| "Set up a new brand" | `brand-setup` |
| "Run the full strategy flow" | `engagement-workflow` |
| "Build a campaign plan" | `campaign-plan` |
| "Run AEO/GEO audit" | `aeo-geo` (covers Google AI Mode, AI Overviews, ChatGPT search, Claude search, Perplexity, Copilot, Gemini App) |
| "Validate the brand profile" | `validate-profile` |
| "Audit current campaign state" | `campaign-audit` |
| "Launch a multi-channel campaign" | `launch-campaign` |
| "Check connector readiness" | `doctor` (also reports model-registry freshness and Cowork+Drive routing status) |
| "Set up Cowork team persistence" | `cowork-setup` (first-run + when brand state isn't persisting) |
| "Generate an executive dashboard" | `executive-dashboard` |
| "Run a full SEO audit" | `seo-audit` |

## Files in this repo

- `skills/<name>/SKILL.md` — 158 Agent Skills (the surface area). Each is byte-portable across all supported surfaces.
- `agents/<name>.md` — 24 specialist agent definitions (Claude Code subagent format; on Codex use TOML conversion at `~/.codex/agents/`, on Antigravity use `/agent` ad-hoc spawn). Full list in the **Specialist agents (24)** section below.
- `commands/<name>.md` — Claude Code slash commands (`/digital-marketing-pro:<name>`). On other surfaces invoke via natural-language intent — the SKILL.md routing picks up the same handler.
- `plugin.yaml` + `__init__.py` at repo root — **Hermes Agent native plugin** (native since v3.13.0). `__init__.py` exposes `register(ctx)` which walks `skills/` and exposes all 164 skills via `ctx.register_skill()`. Read ONLY by Hermes; ignored by every other platform.
- `openclaw.plugin.json` at repo root — **OpenClaw native manifest** (native since v3.13.0). `skills` field points at `./skills`. OpenClaw also auto-detects `.claude-plugin/plugin.json` as a Claude-compatible bundle fallback.
- `scripts/*.py` — 86 Python helpers (optional, run when Python 3.8+ is present). Includes `_common.py` (shared workspace-root / slugify / atomic-write helpers), `connector_resolver.py` + `connector_executor.py` (8 executable HTTP connectors), `resolve_model.py` + `refresh_models.py` (shared model curator with auto-fall-forward on deprecated IDs), `plugin-metadata.py` (environment + asset probes), `drive-sync-state.py` (Cowork+Drive routing ledger), `check_skill_contracts.py` (doc-vs-argparse linter), and `skill-line-check.py` (CI line guard).
- `tests/test_*.py` + `tests/run_all.py` — 209 stdlib-unittest tests covering `resolve_model`, `drive-sync-state`, `plugin-metadata`, `skill-line-check`, `connector_resolver`, `_common`, engagement/checkpoint/execution state, the doc-vs-script contract scanner, release-consistency locks, the Hermes adapter (`plugin.yaml` + `__init__.py`), and the OpenClaw manifest. Run with `python tests/run_all.py`.
- `settings.json.example` — recommended user settings: `fallbackModel` 3-model resilience chain, the optional `requiredMinimumVersion` managed setting, `skillOverrides`, OTel resource attrs (under `env`).
- `hooks/hooks.json` — ships as `{"hooks":{}}` (zero global hooks). Add hooks at user scope if needed.
- `.mcp.json` — ships as `{"mcpServers":{}}` (zero auto-connecting MCPs). Full catalog at `.mcp.json.connectors-reference`.
- Reference knowledge files live **inside each skill** at `skills/<name>/*.md` (169 of them — there is no top-level `references/` directory), covering compliance, channel mechanics, and AEO/GEO targets.

## Specialist agents (24)

`agents/<name>.md`. The competitive pair `competitive-intel` + `competitor-intelligence` merged into **`competitive-intel`** (with a `mode: snapshot|monitoring` input); `memory-manager` is retained as a thin storage-only agent while `intelligence-curator` owns intake/interpretation. Post-merge roster:

1. `agency-operations`
2. `analytics-analyst`
3. `brand-guardian`
4. `competitive-intel`
5. `content-creator`
6. `crm-manager`
7. `cro-specialist`
8. `email-specialist`
9. `execution-coordinator`
10. `growth-engineer`
11. `influencer-manager`
12. `intelligence-curator`
13. `journey-orchestrator`
14. `localization-specialist`
15. `market-intelligence`
16. `marketing-scientist`
17. `marketing-strategist`
18. `media-buyer`
19. `memory-manager`
20. `performance-monitor-agent`
21. `pr-outreach`
22. `quality-assurance`
23. `seo-specialist`
24. `social-media-manager`

## Cross-platform notes

- **Skills are the universal interface.** Same SKILL.md works on Claude Code, Codex, Antigravity, Cursor, Copilot CLI, Gemini CLI (Agent Skills open standard adopted Dec 2025).
- **Claude Code subagents (`agents/*.md`) are Claude-only as static files.** On Codex use the TOML equivalent at `~/.codex/agents/*.toml`. On Antigravity use the `/agent` slash command for ad-hoc spawning.
- **Slash commands are Claude-only as `commands/*.md` files.** On other surfaces invoke skills by name or natural-language intent.
- **MCP env-var syntax differs by surface.** Claude uses `${user_config.VAR}`; Codex/Antigravity use `$VAR`. Our `.mcp.json` ships empty so this doesn't bite.

## Identity / authority

Built and maintained by Indranil Banerjee (https://indranil.in). MIT-licensed. No telemetry. Part of the Neelverse Marketing Suite.
