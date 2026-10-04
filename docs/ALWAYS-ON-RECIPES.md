# Always-On Recipes

These are recurring jobs you can schedule today. Each recipe below is one self-contained prompt, plus notes on how each scheduler runs it. Platform facts were **checked 2026-10-04** against the source linked next to them. They describe research previews and betas that change often, so re-check before relying on a limit.

## Ground rules for every recipe

1. **Unattended runs report; they never write.**
   - DMP's write actions (launching ads, sending email, CRM updates) require a human to type `yes` at an execution gate.
   - A scheduled run cannot supply that approval. Claude Code's docs say a fired routine prompt "is not live user input and can't act as approval or consent" ([routines](https://code.claude.com/docs/en/routines)).
   - Every recipe below is read-and-report. If a finding needs action, the report says which skill to run *with a human present*.
2. **Remove write-capable connectors from the job.**
   - Claude Code routines include all your connectors by default. Their docs warn that Claude "can use every tool from an included connector, including writes, without asking for permission during a run".
   - Cursor automations likewise give agents "access to every tool exposed by" a connected MCP server ([automations](https://cursor.com/docs/cloud-agent/automations)).
   - Keep ad-account and CRM servers (for example `meta-ads`, `amazon-ads-mcp`, `hubspot`) out of scheduled jobs. Read-only ones such as `google-ads-mcp` are fine.
3. **Cloud runners don't see your laptop.**
   - DMP keeps brand profiles under `~/.claude-marketing/` on the machine where you set it up.
   - A cloud scheduler (Claude Code routines, Cursor automations, Grok Bot, Gemini Spark, Claude Tag) only sees what you give it: a repository, connectors, or files you upload.
   - Either put the inputs (exports, a brand-profile copy) in the repository the job clones, or run the job locally (Claude Code Desktop scheduled tasks, Hermes on your own machine).
4. **Same input, same output.** Point each recipe at dated export files or connector queries with fixed date ranges, so two runs of the same week give the same answer.

---

## The recipes

### R1 — Weekly rank / SEO drift (Mondays)

**Prompt:**
> Compare last week's Google Search Console performance export with the week before using `/digital-marketing-pro:seo-drift` (`scripts/seo_drift.py --baseline <prev.csv> --current <this.csv> --top 30 --noise 5 --format json`). Report the quality scorecard first; if any gate fails, stop and say which. Otherwise list the 10 biggest losers and 10 biggest gainers by clicks and by position, each with a one-line hypothesis, and flag queries that moved more than 3 positions. Do not change anything on the site or in any account. End with: "Next step with a human: /digital-marketing-pro:seo-audit or /digital-marketing-pro:aeo-geo for <the losing pages>."

**Inputs:** two GSC Performance exports for adjacent, non-overlapping weeks, from the same property and with the same columns. For AI-surface drift, run it a second time on two exports of the Search Console *generative AI* report. That report has page, country, device and date dimensions and **no queries**, so compare pages.

### R2 — Competitor alerts digest (daily or weekly)

**Prompt:**
> Using `/digital-marketing-pro:competitor-alerts` and the saved baselines from `/digital-marketing-pro:competitor-monitor`, produce today's digest. Summarize alerts since the last run (`scripts/competitor-tracker.py --brand <slug> --action alert-summary --since <YYYY-MM-DD>`), grouped critical / warning / info. Quote the evidence for each alert (URL, date, what changed); drop anything you cannot evidence. No outreach, no ad changes. If nothing crossed a threshold, say "No competitor changes above threshold" and stop.

**Inputs:** competitor baselines already saved by `/digital-marketing-pro:competitor-monitor` (local brand data). On a cloud scheduler, commit a copy of the baseline files to the job's repository, or run the job locally.

### R3 — Content-decay scan (first Monday of the month)

**Prompt:**
> Run `/digital-marketing-pro:content-decay-scan` on the attached 6-month per-URL performance export (traffic, positions, last-updated date). Score decay with `scripts/creative-fatigue-predictor.py --action decay-scan --data <json>`, rank refresh candidates by recoverable traffic, and write refresh briefs for the top 5 only. Label every recovery estimate as an estimate. Do not publish or edit content.

**Inputs:** a GA4 / GSC export by URL covering the last 6 months, or analytics connectors with read-only access.

### R4 — AI-visibility snapshot (monthly)

**Prompt:**
> Build this month's AI-visibility snapshot with one row per surface and each number in its own units — never add them together:
> 1. **Google AI Overviews / AI Mode**: impressions by page from the Search Console generative AI report export (`/digital-marketing-pro:gsc-ai-performance`). State that the report has no clicks, CTR or queries.
> 2. **Copilot / Bing**: citations, Citation Share and top grounding-query intents from the Bing Webmaster Tools AI Performance export.
> 3. **ChatGPT / Perplexity / Gemini / Copilot answers**: probe scores from `/digital-marketing-pro:geo-monitor` (`scripts/geo-tracker.py --brand <slug> --action diff`), labeled as probes.
> 4. **AI-referred traffic**: GA4 AI Assistant channel sessions, noting that this channel excludes Google's AI Overviews and AI Mode, which GA4 counts as Organic Search.
>
> Flag any surface where the trend disagrees with the others. No recommendations to add llms.txt.

**Inputs:** the Search Console generative AI export, the Bing Webmaster Tools AI Performance export, the GA4 channel report, and last month's geo-tracker data.

### R5 — Agent-readiness regression check (weekly)

`scripts/agent-readiness-audit.py` is deterministic and exits `1` when a check fails, so it can run without a model at all and alert only on failure:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/agent-readiness-audit.py" \
    --site https://example.com --fetch --page https://example.com/products/best-seller \
    --expect "Best Seller" --format text
```

It fails when an answer-engine crawler gets blocked, when key content drops out of the server HTML, or when JSON-LD breaks. Run `/digital-marketing-pro:agent-readiness-audit` with a human to interpret and fix.

---

## Where to schedule them

| Platform | How a recurring job is defined | Limits worth knowing | Source |
|---|---|---|---|
| **Claude Code routines** | `/schedule` in the CLI (alias `/routines`), or claude.ai/code/routines. Presets are hourly, daily, weekdays and weekly; `/schedule update` sets a custom cron | Research preview. Pro, Max, Team and Enterprise plans. Minimum interval one hour. Runs in the cloud against the repositories you select; uses skills committed to those repositories and the connectors you include | [code.claude.com/docs/en/routines](https://code.claude.com/docs/en/routines) |
| **Claude Code Desktop scheduled tasks** | Desktop app → Routines → New routine → **Local** | Runs on your machine with access to local files, so DMP's `~/.claude-marketing/` brand data is reachable | [routines page, "Related resources"](https://code.claude.com/docs/en/routines) |
| **Claude Tag (Slack)** | Tag @Claude in a channel and ask for the recurring job. Anthropic says it "can also schedule tasks for itself" | Beta for Claude Enterprise and Team. Admins pair it with Slack, grant tool access, and set a monthly spend limit | [anthropic.com/news/introducing-claude-tag](https://www.anthropic.com/news/introducing-claude-tag) (23 Jun 2026) |
| **Grok Bot** | In chat, ask the Bot to run a skill on a schedule, e.g. "Every weekday at 8:00 AM, run …". Manage it under the conversation's **Routines** (pause, test, edit, history) | Results post in the conversation where the routine was defined. Event triggers depend on connected accounts | [docs.x.ai — skills and routines](https://docs.x.ai/grok-bot/skills-routines-and-automations) |
| **Gemini Spark** | Tell Gemini when to run the task ("Schedules") | Google AI Pro or Ultra. 18+. Not in the EEA, Nigeria, Switzerland or the UK. Gemini mobile app, Mac app, or web. Up to 15 tasks running at once | [Gemini Apps Help](https://support.google.com/gemini/answer/17094507) |
| **Cursor automations** | Cloud agents on a schedule (preset or cron expression) or on events (GitHub, GitLab, Slack, webhooks, Linear, Sentry, PagerDuty) | Cron/Slack-triggered automations default to no repository; pick one if the job needs files. MCP servers you attach expose all their tools | [cursor.com/docs/cloud-agent/automations](https://cursor.com/docs/cloud-agent/automations) |
| **Hermes cron** | `hermes cron create "every monday 9am" "<prompt>" --skill <skill>` or `/cron add …`. Cron expressions (`"0 9 * * 1"`) also work | Deliver to `origin`, `local`, `telegram`, `discord`, `slack`, `email` or `all`. `--no-agent --script` runs a script with zero LLM involvement: stdout is delivered, empty output sends nothing, a non-zero exit raises an error alert | [hermes-agent docs — cron](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron) |

### Per-platform notes for these recipes

- **Claude Code routines.**
  - Pick a repository that holds the inputs (dated exports, a copy of the brand profile).
  - Remove every write-capable connector in the form's **Connectors** section.
  - Schedule a few minutes past the hour; the docs note on-the-hour runs "can start several minutes late".
  - The routine page doesn't document whether installed plugins load in cloud runs. If `/digital-marketing-pro:*` isn't available in a run, have the prompt call DMP's scripts from a repository that contains the plugin.
- **Claude Code Desktop (local).** The simplest home for R2 and R3, because they read local brand data.
- **Claude Tag.** Paste the recipe prompt into the channel that should receive the digest. Give Claude Tag read-only tool access for these jobs.
- **Grok Bot.**
  - DMP ships a `.grok-plugin/` manifest. If DMP's skills are installed for your Bot, name them in the routine; otherwise paste the full recipe prompt.
  - Keep event triggers narrow. xAI asks for "a narrow matching rule and a clear response".
- **Gemini Spark.** Nothing on the help page says Spark can load DMP's skills. Use it for prompt-only versions of R1 and R4 with exports from Google Drive, and expect no local brand data.
- **Cursor automations.**
  - DMP ships a `.cursor-plugin/` manifest, but the automations page doesn't say whether plugins load in cloud agents.
  - Point the automation at a repository containing the plugin and the inputs, and call the scripts directly.
- **Hermes.**
  - R5 fits `--no-agent` mode exactly. Wrap the command so it prints only on failure. For example: `python …/agent-readiness-audit.py … --format text > /tmp/ara.txt || cat /tmp/ara.txt`, run as the job's `--script`. A clean week then sends nothing, and a regression posts the findings.
  - Use agent mode with `--skill` for R1–R4.
