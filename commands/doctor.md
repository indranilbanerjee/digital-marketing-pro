---
description: "Run the readiness doctor: which audit and launch actions are live or blocked. \"why is this action blocked\""
argument-hint: "[--brand <slug>] [--action <id>] [--channel <name>] [--json] [--summary]"
allowed-tools: Bash Read
---

# /digital-marketing-pro:doctor — Per-Action Readiness Check

Resolves every action in the campaign-audit and launch-campaign skill surfaces against the currently configured connectors and reports which mode each one is in:

| Mode | What it means |
|------|---------------|
| `real`              | Action runs end-to-end with no external API. Always available. |
| `manifest_ready`    | A matching connector is configured; the action returns the exact HTTP request manifest for the orchestrator (Claude via MCP) to execute. |
| `stub_unconfigured` | No matching connector is configured; the action returns a structured stub plus a copy-paste setup hint. |

## Quick examples

```
/digital-marketing-pro:doctor                              # full readiness map for default brand
/digital-marketing-pro:doctor --brand acme                 # for a named brand
/digital-marketing-pro:doctor --action inventory --channel google_ads
/digital-marketing-pro:doctor --summary                    # one-line counts
/digital-marketing-pro:doctor --json                       # machine-readable
```

## What it does NOT do

- It does not execute write/launch actions. For that, run the action through the orchestrator (`/digital-marketing-pro:launch-campaign`) which respects approval gates.
- It does not make any network call. It probes `.mcp.json` membership and env-var presence only — credentials are never read or echoed.

## Output sections

1. **Summary line** — count of actions in each of the three modes
2. **Per-action table** — action name, mode, operation type, configured connector or list of candidate connectors
3. **Unlock guide** — for any stub-unconfigured action, the exact next step
4. **Environment block** — detected surface (`claude-code-windows` / `claude-code-mac` / `claude-code-linux` / `cowork-sandbox`)
5. **Model curator block** — registry age + severity (`ok` <60d, `warn` 60-119d, `urgent` >=120d), with the exact `refresh_models.py` command when stale
6. **Cowork+Drive routing block** — only meaningful in Cowork. Shows whether `/digital-marketing-pro:cowork-setup` has been run; flags `urgent` when Cowork is detected but routing is missing (brand state would vanish at session end)

## See also

- [scripts/action-doctor.py](../scripts/action-doctor.py) — the underlying script
- [scripts/connector_resolver.py](../scripts/connector_resolver.py) — the resolver and ACTION_SPECS table
- [scripts/connector-status.py](../scripts/connector-status.py) — the broader connector dashboard (categories, setup guides)
- [/digital-marketing-pro:check](../skills/check/SKILL.md) — pre-publish quality gate
- [/digital-marketing-pro:status](../skills/status/SKILL.md) — brand snapshot

## Run

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/action-doctor.py" "$@"
```
