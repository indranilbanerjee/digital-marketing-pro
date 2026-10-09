# Privacy

**No telemetry.** Digital Marketing Pro sends nothing to its author or to any analytics service. There is no account, no sign-up and no tracking code in the plugin.

**Your AI host does the model calls.** Digital Marketing Pro is a set of instructions and local scripts that run inside the agent you already use (Claude Code, Cowork, Codex, Cursor, Copilot CLI, Antigravity, Hermes Agent, OpenClaw or Grok). Prompts and outputs go to that host's model provider under that provider's own terms and privacy policy.

**Where your data lives.** Brand profiles, engagement state, memory and run artifacts are written on your machine under `~/.claude-marketing/` (or the folder in `CLAUDE_MARKETING_HOME`, or your host's plugin data folder). Deliverables are written to `~/Documents/DigitalMarketingPro/`. On Cowork with Google Drive connected, the folders you set up through `cowork-setup` live in your own Drive.

**Connections you choose.** The plugin ships with no connector switched on. When you connect a service yourself (for example an analytics, CRM, ad-platform or email connector), the data you ask it to send goes to that service under its own terms. API keys you configure stay on your machine or in your host's credential store.

**Web access.** Research, fact-checking and audit steps read public web pages you or the task point at, mostly through your host's own web tools. The plugin's own fetch scripts identify themselves by name. The competitor scraper also obeys robots.txt; the SEO and agent-readiness audits fetch only the pages you name, as a browser visit would.

## Network endpoints and credentials

Nothing connects on install: there are no hooks and `.mcp.json` ships empty. A script opens a network connection only when you, or a skill you invoked, run it, and only to the endpoints below.

| What | When | Endpoint | Credential |
|---|---|---|---|
| `scripts/connector_executor.py` (`/digital-marketing-pro:execute-action`) | reads with `--execute`; writes only with `--execute` and a matching approved approval record (see below) | the official APIs of Slack, HubSpot, Klaviyo, SendGrid, Brevo, Customer.io, Mailchimp and Ahrefs | the environment variable named for that service in `commands/execute-action.md` |
| `scripts/ai-visibility-checker.py` (API mode) | when you run AI-visibility probes and a key is set | OpenAI and Anthropic APIs | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` |
| `scripts/refresh_models.py` | when you refresh the model registry | the model-list endpoints of api.anthropic.com, api.openai.com, generativelanguage.googleapis.com and direct.evolink.ai | the matching key; a provider without one is skipped |
| `scripts/competitor-scraper.py`, `scripts/tech-seo-auditor.py`, `scripts/agent-readiness-audit.py` (`--fetch` only) | when you pass a URL | the site you name, and its robots.txt | none |
| `scripts/setup.py` | when you run setup and accept | PyPI, through `pip install` of the packages in `scripts/requirements.txt` | none |
| `scripts/embed-c2pa.py` (`/digital-marketing-pro:c2pa-metadata`) | every time it signs an asset (not in `--verify` mode) | `http://timestamp.digicert.com`, plain HTTP: an RFC 3161 timestamp request carrying a hash of the claim, not the asset | none |
| `scripts/brand-voice-scorer.py`, `scripts/content-scorer.py`, `scripts/setup.py` | the first run on a machine without the NLTK tokenizer and tagger data | NLTK's data index and packages on raw.githubusercontent.com (nltk/nltk_data) | none |
| Opt-in MCP connectors | only after you copy an entry into `.mcp.json` yourself | the provider's endpoint, listed in `.mcp.json.connectors-reference` | OAuth or an API key with that provider |

The competitor scraper identifies itself as `DigitalMarketingPro-CompetitorScraper` with a link to this repository, obeys robots.txt for that name, and treats an unreachable robots.txt as a disallow.

No script installs Python packages on its own. When one is missing, the script prints the exact install command and stops; `scripts/setup.py` installs only after you accept.

## Approvals for live writes

- **Writes this plugin sends itself** (`scripts/connector_executor.py`) fire only against a matching approval record: approved, inside its window (30 minutes to review, 15 to fire), unused, and bound by a sha256 to the exact request (brand, connector, action, credential name, URL, body). The record is created by the approval step the skill runs after you type `yes`. It proves that step ran for this exact request, once; it cannot prove who typed `yes`, because the agent runs every command and can edit files you can edit. Every fire is logged with a full copy of the record.
- **Writes through an MCP server tool** (Google Ads, Meta, LinkedIn, TikTok, Amazon and other connected servers) are outside that code check. They rely on the skill's typed `yes` and on your host's permission prompt for the tool.
- **The one check the agent cannot fake is your host's permission prompt.** Keep `connector_executor.py --execute` and your MCP write tools out of the host's allowlist, so the host asks you every time. Bypass or auto-approve modes remove that check.

## Actions under a standing approval

Campaign autopilot (`skills/context-engine/self-healing-ops-guide.md`) proposes every correction and waits for your typed `yes` by default (`allowed_actions` is empty). You can pre-authorise specific guardrailed corrections (pause an ad or ad set, lower a bid by up to 15%, lower a daily budget by up to 20%, pause or resume a campaign whose landing page is down) only through `set-guardrails` with a standing approval you approved: scoped to those actions, capped per day, at most 30 days, every use logged; at the cap, autopilot goes back to proposing. Budget increases, targeting and bidding-strategy changes, creative swaps and pausing an account always need your approval. These corrections run through the ad platform's MCP tools, so the cap is kept by the agent and logged by `campaign-health-monitor.py`, not enforced by the platform. Guardrails written before 3.35.0 that already list actions keep working as written; to return to propose-only, run `python scripts/campaign-health-monitor.py --action set-guardrails --brand {slug} --guardrails '{"allowed_actions": []}'`.

**Deleting your data.** Remove the folders listed above. Uninstalling the plugin through your host removes the plugin's own files.

**Questions.** Open an issue at https://github.com/indranilbanerjee/digital-marketing-pro/issues or use a private security advisory for anything sensitive.

The code is MIT-licensed; see [LICENSE](LICENSE) for the terms of use.
