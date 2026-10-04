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
| `scripts/connector_executor.py` (`/digital-marketing-pro:execute-action`) | only with `--confirm`; write actions also need the skill's typed approval | the official APIs of Slack, HubSpot, Klaviyo, SendGrid, Brevo, Customer.io, Mailchimp and Ahrefs | the environment variable named for that service in `commands/execute-action.md` |
| `scripts/ai-visibility-checker.py` (API mode) | when you run AI-visibility probes and a key is set | OpenAI and Anthropic APIs | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` |
| `scripts/refresh_models.py` | when you refresh the model registry | the model-list endpoints of api.anthropic.com, api.openai.com, generativelanguage.googleapis.com and direct.evolink.ai | the matching key; a provider without one is skipped |
| `scripts/competitor-scraper.py`, `scripts/tech-seo-auditor.py`, `scripts/agent-readiness-audit.py` (`--fetch` only) | when you pass a URL | the site you name, and its robots.txt | none |
| `scripts/setup.py` | when you run setup and accept | PyPI, through `pip install` of the packages in `scripts/requirements.txt` | none |
| Opt-in MCP connectors | only after you copy an entry into `.mcp.json` yourself | the provider's endpoint, listed in `.mcp.json.connectors-reference` | OAuth or an API key with that provider |

The competitor scraper identifies itself as `DigitalMarketingPro-CompetitorScraper` with a link to this repository, obeys robots.txt for that name, and treats an unreachable robots.txt as a disallow.

**Deleting your data.** Remove the folders listed above. Uninstalling the plugin through your host removes the plugin's own files.

**Questions.** Open an issue at https://github.com/indranilbanerjee/digital-marketing-pro/issues or use a private security advisory for anything sensitive.

The code is MIT-licensed; see [LICENSE](LICENSE) for the terms of use.
