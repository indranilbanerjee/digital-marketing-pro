# Contributing to Digital Marketing Pro

Thank you for your interest in improving the Digital Marketing Pro plugin. This guide covers how to contribute effectively.

## How to Contribute

### Reporting Issues

Open a GitHub issue for:
- Bug reports (scripts crashing, incorrect compliance rules, outdated platform specs)
- Feature requests (new modules, additional platforms, more industry profiles)
- Documentation improvements (unclear instructions, missing examples, outdated information)

Include:
- Plugin version (`plugin.json` → `version`)
- Claude Code version
- Steps to reproduce (for bugs)
- Expected vs. actual behavior

### Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/add-podcast-module`)
3. Make your changes following the conventions below
4. Test your changes (see Testing section)
5. Submit a pull request with a clear description of what changed and why

## Plugin File Conventions

### Skill Files (SKILL.md)

Every skill directory must contain a `SKILL.md` file with YAML frontmatter:

```markdown
---
name: skill-name
description: One sentence describing when this skill should be used.
---

# /dm:skill-name

## Purpose
What this skill does and what outcome the user gets.

## Input Required
What information the user must provide.

## Process
Numbered steps the skill follows. Step 1 must load brand context.

## Output
What the skill delivers.

## Agents Used
Which specialist agents are activated.
```

**Module skills** (16 core modules) must include a `## Brand Context (Auto-Applied)` section before `## Required Context`:

```markdown
## Brand Context (Auto-Applied)

Before producing any marketing output from this module:

1. **Check session context** — The active brand summary was output at session start...
2. **If you need the full profile**, read: `~/.claude-marketing/brands/{slug}/profile.json`
3. **Apply brand voice** — Formality, energy, humor, authority levels...
4. **Check compliance** — Auto-apply rules for brand's target_markets...
5. **Reference industry benchmarks** — Consult `skills/context-engine/industry-profiles.md`...
6. **Use platform specs** — Reference `skills/context-engine/platform-specs.md`...
7. **Check campaign history** — Run `python campaign-tracker.py --brand {slug} --action list-campaigns`...
8. **If no brand exists**, say: "No brand profile found. Use /dm:brand-setup to create one..."

Do not ask the user for information that already exists in their brand profile.
```

**Command skills** (42 slash commands) must have an explicit brand loading step as Process step 1:

```markdown
1. **Load brand context**: Read `~/.claude-marketing/brands/_active-brand.json` for the active slug, then load `~/.claude-marketing/brands/{slug}/profile.json`. Apply brand voice, compliance rules for target markets (`skills/context-engine/compliance-rules.md`), and industry context. If no brand exists, ask: "Set up a brand first (/dm:brand-setup)?" — or proceed with defaults.
```

### Agent Definitions (agents/*.md)

Each agent file uses YAML frontmatter and follows this structure:

```markdown
---
name: agent-name
description: One sentence describing the agent's specialty.
---

# Agent Name

## Core Capabilities
Bulleted list of what this agent can do.

## Behavior Rules
Numbered rules the agent must follow. Rule 1 should always load brand context.

## Output Format
How the agent structures its responses.
```

**Key conventions:**
- Agents always load brand context first (Rule 1)
- Agents reference context-engine files for compliance, benchmarks, and specs
- Agents produce structured output (not freeform paragraphs)
- Agents state assumptions explicitly
- Agents include 5 additional sections: `## Tools` (scripts), `## MCP Integrations`, `## Memory Operations`, `## Reference Knowledge`, `## Collaboration` (inter-agent handoffs)

### Python Scripts (scripts/*.py)

Scripts must follow these conventions:

1. **Argparse CLI**: Use `argparse` for all command-line arguments
2. **JSON output**: Print structured JSON to stdout for programmatic consumption
3. **Graceful fallbacks**: If optional dependencies are missing, output a fallback JSON with `"fallback": true` and `sys.exit(0)` — never crash with `sys.exit(1)` on missing optional deps
4. **Brand-aware**: Accept `--brand SLUG` to load brand-specific data from `~/.claude-marketing/brands/{slug}/`
5. **No hardcoded paths**: Use `pathlib.Path.home() / ".claude-marketing"` for the data directory

Example graceful fallback:

```python
try:
    import nltk
except ImportError:
    print(json.dumps({
        "fallback": True,
        "error": "nltk_not_installed",
        "message": "NLTK not installed. Install with: pip install nltk",
        "recommendation": "Install NLTK for automated scoring, or review manually."
    }, indent=2))
    sys.exit(0)
```

### Reference Knowledge Files

Reference files in skill directories (e.g., `kpi-frameworks.md`, `compliance-rules.md`) should:

- Use structured markdown with clear headings and consistent formatting
- Include specific numbers, benchmarks, and thresholds (not vague guidance)
- Cite the source or basis for benchmarks where possible
- Be organized for both human reading and programmatic reference
- Use tables for comparative data
- Keep content current — update benchmarks annually

### Execution Command Skills

Execution commands (publishing, CRM, monitoring, communication) follow additional conventions beyond the standard command SKILL.md format:

1. **Approval step required**: Every execution command must include an explicit approval step before any external write operation. The process must include: "Present the execution plan to the user for review. Wait for explicit approval before proceeding."
2. **Risk level classification**: Execution commands must declare their risk level (low/medium/high/critical) and the corresponding approval requirements from `skills/context-engine/approval-framework.md`.
3. **Rollback documentation**: Commands that modify external state must describe what happens if execution fails and how to roll back.
4. **Platform verification**: Commands that write to MCP platforms must verify the correct platform connection is active before executing.
5. **Execution logging**: All execution commands must log results via `execution-tracker.py --action log-execution`.

### Memory Layer Conventions

When adding or modifying memory/knowledge commands:

1. **Layer selection**: Reference `skills/context-engine/memory-architecture.md` for which memory layer to use for each data type.
2. **Metadata requirements**: All stored items must include brand slug, timestamp, data type, and source.
3. **No raw credential storage**: Never store API keys, tokens, or secrets in memory layers.

### Agency Credential Conventions

When working with credential profiles:

1. **Credential profiles store references, not secrets**: `~/.claude-marketing/credentials/{slug}.json` maps brand slugs to environment variable names, never to actual credential values.
2. **Brand isolation**: Never allow operations that could leak one brand's credentials to another brand's context.
3. **Validation before execution**: Always validate credential profile completeness before attempting platform operations.

### Context Engine Reference Files

The 13 core reference files in `skills/context-engine/` are shared across all modules:

| File | Purpose | Update Frequency |
|------|---------|-----------------|
| `industry-profiles.md` | 22 industry profiles with benchmarks | Annually |
| `compliance-rules.md` | 16 geographic + 10 industry regulations | When laws change |
| `platform-specs.md` | 20+ platform character limits, specs | Quarterly |
| `scoring-rubrics.md` | 7 scoring frameworks (0-100 scale) | Rarely |
| `intelligence-layer.md` | Adaptive learning system docs | When architecture changes |
| `guidelines-framework.md` | Brand guidelines structure and enforcement | When guidelines system changes |
| `execution-workflows.md` | 8 execution type SOPs | When execution patterns change |
| `approval-framework.md` | 4 risk levels + industry gates | When approval rules change |
| `platform-publishing-specs.md` | Platform API write specs | Quarterly |
| `memory-architecture.md` | 5-layer memory system docs | When architecture changes |
| `crm-integration-guide.md` | CRM field mapping + sync patterns | When CRM integrations change |
| `agency-operations-guide.md` | Multi-client management patterns | When agency features change |
| `team-roles-framework.md` | Role definitions + permissions | When team features change |

When updating these files, ensure all modules that reference them still work correctly.

## Testing Your Changes

### Manual Testing

1. **Skill changes**: Run the modified skill command and verify output includes brand context, compliance checks, and proper formatting
2. **Script changes**: Run the script directly with `--brand test-brand` and verify JSON output
3. **Hook changes**: Validate `hooks.json` is valid JSON: `python -c "import json; json.load(open('hooks/hooks.json'))"`
4. **Reference file changes**: Verify no broken markdown formatting and that modules referencing the file still produce correct output

### Verification Checklist

- [ ] `hooks.json` is valid JSON
- [ ] All SKILL.md files have valid YAML frontmatter
- [ ] Scripts exit with code 0 (even on missing optional deps)
- [ ] Brand context loading path is explicit in all command skills
- [ ] No hardcoded file paths (use `~/.claude-marketing/` or `${CLAUDE_PLUGIN_ROOT}`)
- [ ] File count hasn't changed unexpectedly (currently ~291 files including docs)

## Code of Conduct

Be respectful, constructive, and professional. Marketing advice in this plugin affects real businesses — ensure all guidance is accurate, ethical, and compliant with applicable laws.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
