---
description: "Open the DMP output folder for a brand, where deliverables are saved. \"where did my deliverables save\""
argument-hint: "[brand] [workflow] (both optional — defaults to active brand, all workflows)"
disable-model-invocation: false
---

# Output Folder

> **Script location.** If your host does not set `${CLAUDE_PLUGIN_ROOT}`, the scripts are in this plugin's `scripts/` folder, next to `skills/`.

Show the user where DMP actually saves the finished workflow deliverables, and (when supported) open that folder in the OS file manager. This is the answer to "where are my 50 engagement files?" — a real question from user-team feedback ("dm pro also taking too long to process" was partly about not knowing whether anything had finished saving).

## Trigger

User runs `/digital-marketing-pro:output-folder`, or asks any variant of "where are my engagement files", "I can't find the campaign plan deliverables", "open output folder", "show me where it saved everything".

## Background

DMP writes two copies of every workflow artifact:

1. **Internal tracking copy** at `~/.claude-marketing/brands/{brand}/output/{workflow}/{run_id}/...` (or `$CLAUDE_PLUGIN_DATA/digital-marketing-pro/brands/{brand}/output/...` when that env var is set). This is the system-of-record for `/digital-marketing-pro:status`, the checkpoint manager, audit history. It lives inside a dotfolder that Windows hides by default.
2. **User-visible published copy** at `~/Documents/DigitalMarketingPro/{brand}/{workflow}/{YYYY-MM}/{filename}` (or wherever `$DIGITAL_MARKETING_PRO_PUBLISH_DIR` points). This is the one to surface.

The published copy was added specifically because users running the 12-Part engagement workflow couldn't find the 50-60 deliverable files it produces. They were saving — just somewhere Explorer hid by default.

## Process

### Step 1: Resolve the path

The published-output directory is:

- `$DIGITAL_MARKETING_PRO_PUBLISH_DIR/{brand}/[{workflow}/]` if the env var is set, or
- `~/Documents/DigitalMarketingPro/{brand}/[{workflow}/]` otherwise.

Default to the active brand if no argument was provided. If neither is available, prompt: "Which brand's output folder? Run `/digital-marketing-pro:output-folder <brand>` or set up a brand with `/digital-marketing-pro:brand-setup`."

If the user supplied a workflow argument (e.g. `engagement`, `campaign-plan`, `seo-audit`), drill down to that subfolder.

### Step 2: Print the path + summary

Use `scripts/output-publisher.py where` to resolve and report — it returns both the visible path AND the internal tracking path AND whether the env var override is active:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/output-publisher.py" where \
    --brand "{brand}" \
    --workflow "{workflow_or_omit}"
```

Show the user:

```
📂 DMP output folder for {brand}{workflow_phrase}:
   {visible_publish_dir}

   Subfolders are organised by workflow (engagement / campaign-plan /
   content-engine / seo-audit / competitor-analysis / campaign-audit /
   launch-campaign) and then by month (YYYY-MM). The newest run is in
   the latest month folder.

   Override the root with $DIGITAL_MARKETING_PRO_PUBLISH_DIR if you want
   outputs going to a shared team drive instead.
```

### Step 3: Open in the OS file manager

Use `scripts/output-publisher.py open` for the actual file-manager invocation (Windows `start` / macOS `open` / Linux `xdg-open`):

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/output-publisher.py" open \
    --brand "{brand}" \
    --workflow "{workflow_or_omit}"
```

If the open fails (headless environment, no associated handler), don't error — the user already has the path from Step 2.

### Step 4: If the folder doesn't exist yet

`~/Documents/DigitalMarketingPro/{brand}/` is created the first time a workflow's artifacts are published. If the folder is missing, say:

```
The output folder doesn't exist yet — that means no workflow has
finished and published for "{brand}" yet. Run a workflow first:

  /digital-marketing-pro:engagement          # full 12-Part Strategy Flow
  /digital-marketing-pro:campaign-plan       # multi-channel campaign
  /digital-marketing-pro:seo-audit           # SEO + AI visibility audit
  /digital-marketing-pro:competitor-analysis # deep-dive

Then come back here. Expected location after the first published run:
  {visible_publish_dir}
```

Do NOT create the folder pre-emptively.

## Configuration

Workspace-wide / agency-wide override:

```bash
# Persistent — add to shell profile
export DIGITAL_MARKETING_PRO_PUBLISH_DIR="$HOME/Dropbox/Marketing/DMP-Outputs"

# Per-run
DIGITAL_MARKETING_PRO_PUBLISH_DIR="/mnt/team-share/DMP" /digital-marketing-pro:engagement ...
```

The internal tracking copy (under `~/.claude-marketing/`) is unchanged — that stays as DMP's system-of-record. The env var only affects the visible publish copy.

## Related

- [`commands/engagement.md`](engagement.md), [`skills/campaign-plan/SKILL.md`](../skills/campaign-plan/SKILL.md), [`skills/content-engine/SKILL.md`](../skills/content-engine/SKILL.md), [`skills/seo-audit/SKILL.md`](../skills/seo-audit/SKILL.md) — the workflows that produce the files this command reveals
- [`commands/resume.md`](resume.md) — pick up an interrupted run
- [`scripts/output-publisher.py`](../scripts/output-publisher.py) — implements the dual-copy save + `where` + `open` subcommands
