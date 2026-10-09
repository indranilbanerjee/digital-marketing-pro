# Changelog

All notable changes to the Digital Marketing Pro plugin are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This project uses [Semantic Versioning](https://semver.org/).

---

## [3.35.0] - 2026-10-10

### Live writes need a matching approval record, and the Hermes review is answered point by point

A maintainer review of the Hermes catalog listing (NousResearch/hermes-agent#132571, against 3.33.3) asked for changes before listing. Every point is fixed below, with tests that fail if the fix is undone (each test was run against the old code and failed there).

**Changed (behaviour) — approvals for live writes (review item 2)**

- **Writes sent by `connector_executor.py` fire only against a matching approval record.** `--execute` without an id builds the exact request, writes a pending record holding its sha256 and a preview rendered by the script, sends nothing and exits 2. After the user types `yes`, the skill runs `approval-manager.py --action approve`. The fire step rebuilds the request and must match the hash (brand, connector, action, credential name, URL, body); the record must be approved, inside its window (30 minutes to review, 15 to fire) and unused. It is consumed once the request is sent, whatever the HTTP status, and released if nothing was sent. `--confirm` no longer fires anything.
- What this proves is stated as such everywhere: the approval step ran for this exact request, once, in its window. Code cannot tell the user from the agent, which runs every command, and writes through MCP server tools (Google Ads, Meta, LinkedIn, TikTok, Amazon) are outside this check; they rely on the skill's typed `yes` and the host's permission prompt. The docs now say to keep `connector_executor.py --execute` out of the host's allowlist, the one check the agent cannot fake. Every fire is logged with a full copy of the record.
- Batches: `--prepare-batch` writes one record with an itemised preview; each item is consumed on its own and a changed item fails alone. Standing approvals (`approval-manager.py --action create-standing`) are scoped to a connector and actions, capped per day and expire within 7 days (executor) or 30 (autopilot), with every use logged.
- `approval-manager.py` no longer stamps `approved_by: "user"`; it records `approved_via: "approval-step"` and the time. The 23 skill calls that sent fields the approval step rejected now send `type`, `platform` and `content_summary`, and every execution skill says to stop and report if the approval step errors. Slack and other internal messages are no longer auto-confirmed.
- **Autopilot proposes by default.** `allowed_actions` now defaults to empty, so every correction waits for a typed `yes`. Pre-authorising corrections needs `set-guardrails --approval-id` with an approved autopilot standing approval; automatic corrections stop at its daily cap. Guardrails written before 3.35.0 that already list actions keep working as written.
- Fixed a bypass the red-team found: `resolve_action` ran local actions (arm-watchdog writes a file) during resolution, so even a dry run had a side effect before any gate. Resolving is now side-effect free; local actions run only under `--execute`.

**Fixed — review item 1 (C2PA install)**

- `embed-c2pa.py` never installs packages. A missing package prints the exact pinned command (`c2pa-python==0.38.0`, `cryptography==46.0.3`) and exits 2. The c2pa-metadata skill no longer claims anything is auto-installed.
- **Found while pinning:** with c2pa-python 0.38.0, the version an unpinned install pulls today, signing failed ("c2pa.created action must have a digitalSourceType"). The created action now carries the IPTC digital-source-type URI; all three AI claims sign and verify, with and without `--ai-disclosure`.
- New `embed-c2pa.py --verify ASSET` (exit 0 valid, 6 no manifest, 7 invalid, 2 not installed), the presence check the pre-publish gate already described but no script provided.

**Fixed — review item 3 (path containment)**

- `_common.safe_child()` and `child_or_error()`: every model- or user-supplied ID that reaches a file path (run, member, content-hash, guideline, template, SOP, journey, schedule, approval ids and raw brand names) must be a single plain component and resolve directly inside its folder. Applied at 26 sites in 7 managers, `discard_run`, the raw-brand legacy branch, `auto-save-insight`, three run-id entry points, and the guideline, template and SOP save paths.
- Every `--brand`, `--slug`, `--run-id` and `--client` argument in 44 scripts uses the new `type=_common.path_component` (one allow-listed name, with its reason); `tests/test_cli_path_args.py` keeps it that way.

**Fixed — review item 4 (PRIVACY.md)**

- New rows: the `timestamp.digicert.com` request on every C2PA signature (plain HTTP, a hash of the claim only) and NLTK data downloads. New sections on approvals for live writes and on actions under a standing approval. The dev C2PA signing key is now deleted when the script exits (review note).

**Fixed — smaller review notes**

- Fetchers: one URL guard (`_common.public_url_error`) checked on every redirect hop in `tech-seo-auditor.py`, `competitor-scraper.py` and `agent-readiness-audit.py` (which keeps a standalone copy, tested to agree): http/https only, no loopback, private, link-local or cloud-metadata addresses.
- `connector_executor.py` substitutes only the connector's own environment variables into a request.
- 104 skills, reference files and commands that run `${CLAUDE_PLUGIN_ROOT}/scripts/...` now say where the scripts are when a host does not set that variable (same line as ContentForge and SocialForge; guarded).
- Doc drift: the pre-publish gate's C2PA verify mode now exists (above); `execute-action` and README no longer list Brevo and Customer.io send endpoints the resolver never built (both are read-only from Python).
- Also found: the autopilot guide documented guardrail keys and a path the script never read, and its default limits (bids 20%, budget 25%) did not match the published ones (15%, 20%); all now match. `guidelines-manager.py` ignored `CLAUDE_MARKETING_HOME` / `PLUGIN_DATA` for SOPs; it now uses the workspace, falling back to an existing `~/.claude-marketing/sops` so saved SOPs stay reachable.

**Tests**

- New: `test_approval_gate.py` (23), `test_approval_honesty.py` (6), `test_path_containment.py` (15), `test_cli_path_args.py` (6), `test_url_guard.py` (9), `test_script_root_fallback.py` (5). Suite: 575 tests.

## [3.34.0] - 2026-10-10

### Every description fits the listing budget, and the model finds the right skill more often

**Changed — descriptions**

- **All 164 skill, 5 command and 1 workflow descriptions now fit Claude Code's
  skill-listing budget.** The budget is characters, not tokens: the context
  window x 4 x `skillListingBudgetFraction` (default 1%), so 8,000 characters
  on a 200k window and 40,000 on 1M, shared by every installed plugin. Every
  listed name counts and is never dropped. DMP's listing needed about 126,600
  characters, so on a 1M window every description was cut to about 195
  characters and its trigger phrases never reached the model. It is now
  25,974 (median description 109 characters), which leaves room for other
  plugins inside a 1M window's 40,000. On a 200k window DMP's 170 names alone
  take about 6,900 of the 8,000 characters, so the model sees names only (a
  few most-used skills keep their text once there is usage history). To see
  descriptions there, set `skillListingBudgetFraction` to 0.05 in
  `settings.json`.
- Each description says what the skill does and one phrase a user would
  type; where the skill runs a script, has an approval gate or reads the
  brand profile, it says so, which is the model's reason to load it rather
  than answer in chat. Slash aliases and "Triggers on"
  lists are gone from the listing and remain in the skill bodies.
- `tests/test_description_density.py` enforces the rule: 60-150 characters,
  median <= 110, one owner per quoted phrase, 24 registered near-miss pairs
  with a pointer on one side only, and the listing formula with a
  26,000-character ceiling. Its docstring records why, so the descriptions are
  not made "denser" again.
- **Workflows count too.** `workflows/*.js` descriptions are listed alongside
  skills and commands; the guard now reads them (planted). The after-eval
  found the competitor-sweep workflow, whose 183-character description named
  exactly the dimensions of a competitor question, taking requests meant for
  competitor-analysis. Rewritten, with a pointer to competitor-analysis.

**Measured with trigger evals** (`claude plugin eval`, listing budget pinned
so the comparison measures wording rather than truncation, first action
graded, 3 runs per case and 5 for near-miss pairs):

- Same 45 cases before and after: 136/169 runs pass before, 153/169 after
  (80.5% to 90.5%), and 159/169 (94.1%) with the two cases fixed below
  re-run on the shipped text. ab-test-plan, check, funnel-audit and seo-audit went
  from 0 or 1 of 3 to 3 of 3. "Should not trigger" cases stay
  quiet (12/12), and every near-miss pair holds at 4/5 or better except
  translate-content.
- Two cases got worse in the first after-run and were fixed before release:
  competitor-analysis (the workflow above) and verify-claims ("against
  supplied evidence" sent the model looking for a file first; the skill also
  works without one, and now says what it does then). Both pass 3/3 on
  re-run.
- Each fix was checked against a second, differently worded request, and
  counts only if that passes too. It holds for ab-test-plan, budget-tracker,
  check, funnel-audit, seo-audit, competitor-analysis and verify-claims (3/3
  each). paid-advertising passes its original case (Performance Max or AI
  Max?) 3/3 but its reworded twin, a broad account-restructure question, 0/3
  (the model answers in chat), so that fix is not counted.
- Not fixed, reported as is: translate-content (the model translates a
  one-line request itself, 0/5 before and after) and hreflang-check (its test
  prompt never attaches the page it asks about; the same request with the
  page's tags attached routes 3/3; recorded in `evals/README.md` as a case
  defect, kept unchanged so the comparison stays paired).
- Without the pin, at Claude Code's default budget on the eval machine, 42 of
  45 cases routed as in the pinned run. That was measured on the first
  after-run text, before the two fixes above, so competitor-analysis's miss
  there predates its fix.

## [3.33.3] - 2026-10-04

### Fixed — Hermes refused to install the plugin

- **Hermes Agent's install-time security scan rated the plugin "dangerous"**
  (`hermes plugins install` refuses that verdict), on harmless lines written
  the way an attack would be: recursive-delete one-liners aimed at the home
  folder in the README and testing guide, realistic-looking example tokens in the integrations guide,
  a constant named `ROBOTS_TOKEN`, an "upload this file to a URL" step in
  the C2PA guide, and "share of conversation" phrasing the scanner reads as a request
  to leak the chat. All reworded or renamed (`CRAWLER_NAME`); the docs now
  say to delete the cache folder, and to move brand data aside rather than
  delete it before a fresh test. Hermes's own validator (main branch) now
  passes with a "safe" scan.
- New `tests/test_host_scanner_compat.py` applies the scanner's patterns to
  every shipped text file (planted against the pre-fix tree).

## [3.33.2] - 2026-10-04

### Fixed

- **A test assumed `.mcp.json` exists.** It is gitignored, so an installed
  copy has none, and the shipped-empty test errored when run from an install
  (verify-from-installed caught it). An absent file now passes — it connects
  nothing — a present one must still be empty, and the test now also requires
  `.gitignore` to keep listing `.mcp.json`, which is what actually keeps
  servers out of every install (planted). Test-only change.

## [3.33.1] - 2026-10-04

### Fixed

- **`agent-readiness-audit --fetch` hid an unreachable robots.txt.** A 5xx or
  a network error on robots.txt was reported as a skipped check. RFC 9309
  section 2.3.1.4 tells crawlers to assume complete disallow in that case, so
  the robots check now fails with every crawler blocked and a first finding
  that explains why (a 4xx is still allow-all). Found while extracting the
  audit into the standalone `digital-marketing-pro-agent-readiness` skill,
  which stays byte-identical. Two tests; the docstring no longer claims link
  names are checked (only buttons are), and the crawler-token test now covers
  all 11 tokens.
- The Hermes `__init__.py` docstring no longer quotes a skill count.

## [3.33.0] - 2026-10-04

### Added — AI surfaces, agent readiness, official ad servers

- **`/digital-marketing-pro:agent-readiness-audit`** (new skill + stdlib
  `scripts/agent-readiness-audit.py`, offline on exported files; network only
  with `--fetch`). Checks whether AI agents and AI crawlers can use a site:
  robots.txt rules for the AI crawler tokens parsed per RFC 9309 (search and
  user-fetch bots blocked = fail; training bots reported as a policy choice),
  JSON-LD structured data, main content present without JavaScript,
  accessibility basics, Merchant Center feed completeness including
  `native_commerce` and conversational attributes, the agentic-commerce feed,
  and WebMCP as an optional experiment. It never recommends llms.txt for
  Google, citing Google's AI optimization guide. 43 tests.
- **AI-visibility measurement map** in `gsc-ai-performance`, `geo-monitor`
  and `analytics-insights`, primary-sourced 2026-10-04: Search Console's
  generative AI report has impressions only (no clicks, CTR or Queries
  dimension) and reached all sites worldwide on 31 Aug 2026; GA4's AI
  Assistant channel (medium `ai-assistant`) *excludes* AI Overviews and AI
  Mode, which GA4 files under Organic Search; Bing Webmaster Tools AI
  Performance covers Copilot citations and grounding queries. Every
  deliverable states what no first-party tool reports instead of inferring it.
- **Ads inside AI answers** (`paid-advertising/ads-in-ai-answers.md`,
  `media-plan`): ChatGPT ads (Advertiser, Conversions and Reporting APIs,
  pixel, delta feeds) and Google AI Mode ads through AI Max / Performance Max.
- **Official ad-platform MCP servers in the connector catalog**: Meta Ads AI
  Connectors (read-write, open beta), Google Ads MCP (open source,
  **read-only** — the resolver never picks it for a write), Amazon Ads MCP
  (partner open beta; endpoint comes from your API onboarding). Every write
  runs behind `launch-ad-campaign`'s typed approval gate, and new ad objects
  are created PAUSED. MCP-only connectors return an `mcp_tool_hint` instead
  of an HTTP request. HubSpot moves to its GA remote server URL; Asana,
  Webflow and Make entries move to Streamable HTTP. Registry-backed HTTP
  connectors: 10 → 13.
- **Meridian 2.x** (JAX backend, experiment-calibrated priors, declarative
  holdouts) in `marketing-scientist` and the MMM docs.
- **`docs/ALWAYS-ON-RECIPES.md`**: scheduled rank/SEO drift, competitor
  alerts and content-decay jobs for Claude routines, Claude Tag, Grok Bot,
  Gemini Spark, Cursor automations and Hermes cron, each with its approval
  boundary.
- **Workflow `/digital-marketing-pro:competitor-sweep`** (`workflows/`):
  per-competitor research in parallel, then one synthesis. Read-only.
- **`evals/`**: a trigger suite for `claude plugin eval` (10 cases plus a
  stay-quiet case).
- **Directory listing fields**: `displayName`, `icon`, `documentationUrl`,
  `supportUrl`, `privacyPolicyUrl`, `termsOfServiceUrl`, a new `PRIVACY.md`
  (no telemetry; what is stored where), and `assets/icon.png`. The root
  `plugin.json` gains `extensions["com.openai"].interface` for OpenAI's
  ChatGPT + Codex directory. Guarded.

### Changed — context cost

- **13 commands folded into their same-named skills** (`backlink-gap`,
  `brand-setup`, `campaign-plan`, `check`, `competitor-analysis`,
  `content-engine`, `cowork-setup`, `email-sequence`, `keyword-cluster`,
  `performance-report`, `seo-audit`, `seo-drift`, `status`). Each loaded
  twice; command-only instructions moved into supplement files beside the
  skill, and every slash name works as before. Five standalone commands
  remain. Always-on cost measured with `claude plugin details`: ~47,079 →
  ~46,656 tokens, with one new skill added.
- **`triggers:` removed from 16 skills.** It is not a skill frontmatter field
  and was never loaded; a guard rejects it.

### Fixed

- **Opener matching in `ai-tell-scan.py`**: connectives now match as whole
  words ("so" no longer matched "Sometimes") and the participial-opener check
  skips non-participles ("During", "Something"). On a human sample the two
  rates went from 60% / 60% to 0% / 0%.
- **The doc-count guard missed qualified counts.** "18 top-level commands"
  and "24 specialist agents" escaped its regex, so 30+ lines stayed stale
  after the command fold. Qualifiers now chain; every stale line fixed.
- **Issue #6's promised guard was never written.** Its resolution said a test
  would keep all 18 execution skills gated and model-invocable; none existed.
  `tests/test_execution_gates.py` now does, and also fails if any skill that
  records an approval is missing from the execution list.
- **`competitor-scraper.py` disguised itself as a browser.** It sent a random
  browser User-Agent, which hid it from any robots.txt rule written for it, and
  treated an unreachable robots.txt as permission. It now sends
  `DigitalMarketingPro-CompetitorScraper/1.0` with this repo's URL, checks
  robots.txt for that token with the standard-library parser (agent groups and
  Allow lines count), and follows RFC 9309: a 4xx means no restrictions, a 5xx
  or network error means do not fetch. `PRIVACY.md` now lists every network
  endpoint the scripts can call and the credential each needs.

### Not changed, on purpose

- **Execution skills stay model-invocable.** Setting
  `disable-model-invocation: true` would trim their descriptions from the
  listing, but a plain request such as "send the campaign" could then not load
  the skill, and the model can still reach the same MCP write tools freehand.
  That routes around the typed approval gate instead of through it.

## [3.32.0] - 2026-10-04

### Fixed — install paths

- **Codex listed zero suite plugins.** The shared marketplace's
  `.agents/plugins/marketplace.json` used the `{"source": "github"}` shorthand,
  which Codex silently drops (marketplace adds cleanly, lists nothing,
  `codex plugin add` → "not found"). Fixed in neels-plugins 3.52.0 (url
  sources), reproduced and verified against a live codex-cli 0.145 install.
- **The README's Codex command did not exist.** `codex plugin install …` →
  `codex plugin add digital-marketing-pro@neels-plugins`; the install-command
  guard now also asserts the old form is absent.
- **`requiredMinimumVersion` removed from `.claude-plugin/plugin.json` and the
  Grok manifest.** It is a Claude Code *managed setting*, not a manifest field;
  Claude Code stripped it at load and `claude plugin validate --strict` failed
  on it. The README's promise that older builds "will be told to upgrade" was
  never true and is corrected; `settings.json.example` now explains the managed
  setting honestly and its `fallbackModel` chain moves to the current
  generation (dated). New guard: plugin.json may carry only documented fields.

### Fixed — model registry (canonical; distributed to CF + SF)

- Re-verified 2026-10-04 against Anthropic, OpenAI and Google models +
  deprecations pages (`next_review_due` had passed on 2026-09-10). Added
  `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-fable-5-1`, `gpt-6-astra`,
  `gpt-6.1-sol`, `gpt-6-luna`, `gpt-image-2.5-sunburst`,
  `gpt-image-2.5-flare`, `gemini-3.8-flash`, `gemini-omni-1.1-flash`.
- Retired: `gemini-2.5-flash-image` (was marked *supported*; Google shut it
  down 2026-10-02), `imagen-4` (shut 2026-08-17), `claude-opus-4-1` (retired
  2026-08-05). Deprecated with fall-forward: `claude-sonnet-4-5` (retires
  2026-11-30), `veo-3.1-generate-preview` (shutdown 2026-10-22), `gpt-5.4-nano`,
  `gemini-omni` (preview endpoint shut 2026-09-30), `gemini-3-pro` (no longer
  listed).
- `latest-*` aliases moved to the current generation. `latest-video-google`
  moved to the GA-format `veo-3.1-generate-001` (its Vertex listing could not
  be verified — noted in the entry; SocialForge's video chain falls forward on
  a 404). `gemini-omni-1.1-flash` is registered but deliberately NOT aliased
  for video: its SDK call shape is undocumented and the Veo rung calls
  `generate_videos()`.
- **`sync_model_registry.sh` bug:** it copied refreshed alias values into the
  subset sibling registries without the entries they name — every new alias
  dangled in CF and SF. The sync now pulls the alias/replacement closure and
  the shared top-level metadata (sampling-param rules), and stamps
  `last_updated`. New guards: no alias targets a retired model, every
  `replacement_id` resolves, and sibling aliases resolve locally.

### Changed — world changes, each from a primary source

- **EU AI Act Article 50** (`context-engine/eu-code-of-practice.md`): the
  Commission's three icons (Basic / Fully AI-Generated / Partially
  AI-Modified), "optional icons, mandatory labelling", label visible at first
  exposure and when reshared/downloaded, enforcement live since 2 Aug 2026; the
  "AI-generated vs AI-assisted taxonomy is dropped" line corrected (it was
  dropped from the *obligation*, not the *label*).
- **Paid:** AI Max auto-upgrade (from Sep 2026) and the DSA sunset moved to
  Feb 2027; Google Ads Limited Ad Serving on all surfaces; LinkedIn API
  `202608`/`202609` changes and the `202510`/`202511` sunsets; Amazon Ads
  Agent + Ads MCP Server (Lite); ChatGPT Ads noted as secondary-sourced.
- **Privacy Sandbox:** Topics, Protected Audience, Attribution Reporting and
  friends are under "Intent to Deprecate and Remove" — the programmatic
  checklist had told users to *invest* in them.
- **Search:** expired "valid until ~2026-08" blocks in `seo-audit` and
  `tech-seo-audit` replaced with update-agnostic triage plus a dated status
  (May core update; Aug + Sep spam updates; **no** Sep core update; site
  reputation abuse EEA split; VideoObject `creator`). `gsc-ai-performance`
  gains the September multimodal measurement-break caveat.
- Distribution bundle: the Anthropic directory moved to the developer portal
  (`claude.ai/directory/manage`); DMP's 567 tracked files exceed the 512-file
  review-hold threshold — noted. ChatGPT directory ZIP rules noted.

Tests: 402 → 407.

---

## [3.31.1] - 2026-08-17

### Fixed — all five open community issues, each verified by reproduction first

- **#10 `claim-verifier.py`: percent regex matched only when a word character
  followed "%".** `%\b` requires a word char AFTER the non-word "%" — so
  "98%x" was a claim while "98% of customers", "98%." and end-of-line
  percentages extracted nothing. Fixed with `%(?!\w)`; new
  `tests/test_claim_verifier.py` (7 tests) pins the corrected behavior through
  the real CLI, including that "98%x" is now correctly NOT a claim.
- **#11 `keyword_cluster.py`: `[a-z0-9]+` tokenizer split every non-ASCII
  letter; German compounds scored 0.00.** "bürohaftpflicht" tokenized as
  "rohaftpflicht"; Jaccard("betriebshaftpflichtversicherung",
  "betriebshaftpflicht") = 0.00, leaving the cannibalisation gate and internal
  link map blind in compounding languages. Fixed: Unicode tokenizer
  (`[^\W_]+`) + `_lexical_similarity` with compound-aware containment matching
  (6-char floor) used at the three lexical call sites; SERP-URL overlap keeps
  pure `_jaccard`. New `tests/test_keyword_cluster.py` (9 tests) includes an
  English-parity bound and proof that English sets without containment pairs
  score exactly as before.
- **#13 `engagement-workflow`: `allowed-tools` lacked `Task` while the body
  mandates Task dispatch in Parts 2/9/10/11 and the parallel-dispatch rules.**
  `Task` added to the declaration. New `TestSkillToolDeclarations` guard fails
  any skill whose body references Task dispatch without declaring it
  (detection regex plant-checked against the real phrasing). A sweep confirmed
  engagement-workflow was the only offender.
- **#12 `plugin.yaml` said "158 skills" against 163 shipped.** The Hermes
  manifest was the one description outside the count guards. Fixed to 163;
  the auto-register comment and two test-message literals made count-free;
  new guard pins the plugin.yaml description to the derived skill count.
- **#9 `hooks/hooks.json` carried a `_readme` field that Cowork plugin
  validation rejects.** The rationale text moved to `hooks/README.md`;
  hooks.json is now exactly `{"hooks": {}}`. The same defect existed in
  ContentForge and SocialForge — fixed and guarded in all three repos
  (`TestHooksManifestSchemaClean`).

Reported by @jurazerr (#10, #11, #12, #13) and @theepicsaxguy (#9) — thank you
for precise, reproducible reports. Tests: 381 → 402.

---

## [3.31.0] - 2026-08-17

### Added — Grok (xAI Build CLI) native support

- New `.grok-plugin/plugin.json` (mirrors the Claude manifest + the
  `"skills": "./skills/"` pointer Grok's loader uses) and
  `.grok-plugin/marketplace.json` (single-plugin marketplace source), so
  `grok plugin install indranilbanerjee/digital-marketing-pro` works directly.
  Grok also reads the Claude Code manifests for compatibility
  ([Grok Build docs](https://docs.x.ai/build/features/skills-plugins-marketplaces));
  the native pair is the first-class lane.
- Both files version-locked in `tests/test_release_consistency.py`
  (`PLATFORM_MANIFESTS_JSON` grows to 8; a dedicated test pins the marketplace
  entry's version and source URL). Grok added to the install-command guard,
  the README troubleshooting platform-name guard, and the AGENTS.md surfaces
  guard. Shared manifest description now lists Grok in the platform run.
- README: platforms 8→9 native across the compare table, surfaces table
  (new Grok row + install commands), troubleshooting (new Grok section),
  FAQ, and the harnesses lede; AGENTS.md surfaces line updated.

### Fixed — four stale counts that escaped the doc-count guard, and the guard taught to see them

- "DMP's 158 `SKILL.md` files" (backticks broke the guard's adjacency match),
  "all 158 marketing skills" and "All 158 DMP skill names" (qualifier words
  between number and noun), and "All 209 tests" (tests was never a guarded
  noun — 170 stale against the real 379). All four corrected to derived truth.
- `tests/test_doc_counts.py`: `SKILL_MD_RE` now tolerates backticks, new
  `QUALIFIED_SKILLS_RE` catches the qualifier phrasings, new `TESTS_RE` makes
  "N tests" a guarded noun with ground truth derived from `def test_` counts.
  Each new pattern plant-checked against the exact phrasing it previously
  missed.

Tests: 379 → 381.

---

## [3.30.2] - 2026-08-16

### Fixed — the documentation truth pass

A from-zero audit of every live document found the doc-count guard pattern-blind: it
required a number directly before one of three nouns, and every stale count in the
repo was phrased some other way.

- **README** — the "How does this compare?" table said "Skills count **158**" (the repo
  ships 163), "All 158 SKILL.md files" (163), and a "### 86 Python scripts" section
  heading (93).
- **AGENTS.md** — the file every non-Claude runtime auto-loads — pinned "Supported
  surfaces (v3.17.0)", thirteen releases stale. It now carries the current version.
- **docs/architecture.md** and **docs/claude-interfaces.md** quoted "86 Python scripts"
  in five places and "The 158 SKILL.md files" — all now 93 and 163.
- **TESTING-GUIDE.md**'s versioning checklist pinned v3.17.0 and "~86 scripts"; it is
  now version-agnostic and points at the sources of truth instead of restating them.
- **docs/distribution/submission-bundle.md** pinned a release version in its
  release-notes section; made version-agnostic so it cannot rot.

### Changed — the guard can now see what rotted

`tests/test_doc_counts.py` grew the patterns the audit proved necessary: script counts
(including "N Python scripts"), "N SKILL.md files", comparison-table "Skills count"
rows, and AGENTS.md currency (version = manifest, all 8 surfaces named).
Release-narrative sections keep their ship-time numbers via heading-aware exemptions,
and each new pattern is plant-checked against the exact phrasing that previously
escaped. Tests 376 → 379.

## [3.30.1] - 2026-08-16

### Changed — richer Agent Plugins 1.0 listing metadata + submission bundle

The root `plugin.json` now carries the official schema's full optional set —
`homepage`, `repository`, `license`, `keywords` — verified against the
published schema at agent-plugins.org (closed schema, 10 permitted fields).
Schema guards widened to the official field list. Added
`docs/distribution/submission-bundle.md`: listing metadata, starter prompts,
and the 5-positive + 3-negative test cases both official directories require —
ready for the owner to submit.

## [3.30.0] - 2026-08-16

### Added — the content-engine run auditor

`scripts/run-audit.py` re-derives a run's gate claims from its artifacts, using
the plugin's own scripts. "status: ready" now requires the audit: the humanize
verdict is re-measured with a fresh ai-tell-scan run rather than read off the
scorecard; scan JSON embedded in the measured file (the corruption class that
once flipped `may_claim_authored`) is a violation; the authorship record must
match a fresh measurement; recorded voice distances must actually sit inside the
0.15 gate a ready-declaration claims they do; publish-ready copy must be free of
production placeholders. Missing inputs are reported-N/A, never silent-pass.
12 new tests with plants for every guard.

## [3.29.0] - 2026-08-16

### Added — Agent Plugins 1.0 packaging

- Root `plugin.json` on the closed AP1.0 schema (OpenAI standard, 2026-08-06;
  ChatGPT, Codex, Cursor, GitHub Copilot, VS Code, Kiro), version-synced with
  the Claude manifest and guarded by `tests/test_agent_plugins_manifest.py`.
- `${PLUGIN_DATA}` (the standard's data-dir name) accepted wherever
  `CLAUDE_PLUGIN_DATA` was read — a compliant non-Claude host previously
  resolved no data directory at all.

## [3.28.0] - 2026-08-15

A `brand-setup` → `content-engine` run on a fresh brand, following the instructions
literally, surfaced five contract defects that no unit test could see — each is about what
an instruction MEANS rather than whether code runs.

### Fixed — `brand_voice_match` was unfailable as written

The gate asked for "≤ 1.5 point deviation on each axis" while `brand-voice-scorer.py` emits
`distance` bounded at 1.0. Read literally it could never fail — the same hollow-gate defect
as a gate with no measurement behind it, sitting in the scorecard passing everything. Now
stated in the scorer's own 0–1 unit at **`distance` ≤ 0.15**, which is the threshold the
scorer already used internally, with a test that fails if the two ever diverge. The gate also
now says plainly what it does not measure: the target axis values come from `brand-setup`'s
descriptor→number mapping, and there is no rubric for descriptors it has not seen.

### Fixed — `seo_complete` contained one impossible and one vacuous criterion

"≥ 3 internal links" cannot be met by a pre-launch brand's first article, and "all images
have alt text" passed at zero images — a pass verifying nothing. Both now take an explicit
`N/A` that must name its reason; a bare `N/A` is a FAIL, so the exemption cannot become a way
to skip any gate.

### Fixed — `brand-setup` produced a profile its own validator rejected

The generator writes `brand_voice` / `target_markets` and no `guardrails`; `validate-profile`
demanded `voice.*`, `target_jurisdictions` and `guardrails.*` as BLOCKERs. A freshly created
brand therefore failed the plugin's own validator. `content-engine` and `brand-voice-scorer.py`
both read the generator's keys, which made the validator the outlier — it now accepts them,
and missing guardrails is a WARNING for unregulated brands rather than an unsatisfiable BLOCKER.

### Fixed — the voice remediation message inverted its own diagnosis

Copy scoring humor 0.00 against a target of 0.20 was told it "reads as too serious" **and**
that the brand "calls for more serious tone". The remedy direction pivoted on an absolute 0.5
instead of the direction of the gap, so following the advice moved the score further out of
tolerance.

### Fixed — two instructions wrote incompatible things to `05-scans.json`

One said save, the other said append; appending a second JSON document to a file holding one
yields a file `json.load` rejects. The file now has one specified shape —
`{"surface": …, "structure": …}` — is listed in the numbered-output convention it was missing
from, and carries the Windows note that the documented redirect writes cp1252 and breaks
parsing without `PYTHONIOENCODING=utf-8`.

### Fixed — creating a brand silently repointed every skill at it

`create_brand` set the global active brand with nothing printed, and `_active-brand.json`
stores one value with no history, so the previous brand was unrecoverable. It now announces
the change, records `previous_slug`, and prints the command to undo it. `--slug` is also
finally exposed on the CLI: `create_brand()` always accepted one, the storage path IS the
slug, and callers who needed a specific slug had to import the module to get it.

Suite: 340 -> 358.

---

## [3.27.0] - 2026-08-15

The humanize gate got measured against writing that predates ChatGPT, and lost a signal
that was pointing the wrong way.

### Fixed — `llm_favored_word` was gating, and it fires on human prose, not model prose

A calibration corpus was built from **39 documents published before 2022-11-01** — before
ChatGPT was public, so human authorship is guaranteed by publication date rather than
assumed — across four registers (marketing blog, personal and technical essay, journalism
and institutional reports, academic and standards prose), cut into **272 chunks of ~1000
words** so both classes are compared at equal length. Negative class: 18 documents of
default model prose written with no anti-tell guidance.

Result: of the 45 words in `_LLM_FAVORED_WORDS`, **23 fired — every one of them only on the
human class, none on the model class.** "robust", "facilitate", "harness", "landscape" and
"leverage" are ordinary technical and journalistic English, while current models have
largely been trained off them. As a **gating** signal it could therefore only ever produce
false positives, which disqualifies it under the rule this scan already followed. It stays
in the report and in the humanizer's catalog, where it remains sound editorial advice.

### Changed — the gate now says what it actually proves

Measured: the gate fails **0 of 39** documents of published human prose and catches **0 of
18** documents of unedited model prose. It is a density floor that catches egregious
tell-stuffing; it is not evidence a piece was humanized, and it would not catch a humanize
step that did nothing. `advisory_note`, the content-engine skill, and `/check` now say so
plainly instead of implying more. The discrimination that does exist lives in the advisory
rating (human 62.5% LOW / 8.8% HIGH vs model 0% LOW / 83.3% HIGH) and the structural scan
(human 34.6% OK vs model 0% OK) — both editor-facing, neither a publish gate.

The full calibration, including per-register thresholds and the composite rules that were
tested and rejected, is recorded in the `ai-tell-scan.py` docstring so no future threshold
edit can be made without re-measuring.

### Fixed — scan output was being appended to the file `authorship.py` measures

The content-engine said "append the scan JSON to `05-humanize.md`" while also running
`authorship.py --draft 05-humanize.md` against that same file. Measured on a real run:
appending a report and scan JSON moved `author_word_share` 0.253 -> 0.206 and flipped
`may_claim_authored` true -> false. Scan output now goes to **`05-scans.json`**; the draft
file stays the draft. `violations` stayed clean throughout, which is exactly why this was
invisible.

Suite: 335 -> 340.

---

## [3.26.2] - 2026-08-14

Load-test corrections, mirroring ContentForge 3.23.3.

### Fixed — the authorship matcher was quadratic

`classify()` was all-pairs: 11.43s at 500 sentences, and its difflib prefilter
pruned nothing when the draft genuinely contained the author's sentences. A long
piece would have hung the humanize step. Rewritten as a hash-indexed pass for
verbatim survivors plus fuzzy matching over the remainder only, bounded by a
length test derived from difflib's ratio formula. **5000 sentences: 0.07s.**

### Verified — adversarial inputs and determinism

The same 28-case battery (empty, 50k words, RTL, CJK, null bytes, unclosed
fences, HTML injection, Windows newlines) runs through `ai-tell-scan.py`,
`structural-tell-scan.py` and `authorship.py` without a crash, with every band
inside its declared vocabulary and every metric finite and non-negative. Scan
output is byte-identical across repeated runs. Exit codes confirmed: 0 / 1 / 3.
The cases are now regression tests, including an explicit non-quadratic
assertion on the matcher.

331 -> 335 tests.

## [3.26.1] - 2026-08-14

Field-test corrections to the new `ai-tell-scan.py`, measured against a
published human essay and against this plugin's own generated article.

### Fixed — the aphorism proxy was too blunt to headline a rating

`is_aphorism_candidate` flagged ordinary factual sentences ("The neighbouring
region barely moved.", "Net, the office is down seven people.") and rated both
a human essay and DMP's own 1081-word article HIGH.

- The heuristic now excludes sentences carrying a personal or anaphoric pronoun
  or opening with a coordinating conjunction — context-dependent sentences are
  not the self-contained general claims this targets.
- `aphorism_candidates_per_1000` is computed, banded and reported, but no longer
  contributes to `advisory_rating`. It was already excluded from the gate for
  the same reason; excluding it from the rating applies that logic one level up.

### Verified in the field (no change needed)

The gate itself held under real conditions. DMP's own generated article passes
its own gate at 0% flagged paragraphs; the published human essay passes at 0%;
the AI-shaped fixture still fails at 66.7%. `entity_development` read OK on the
real article (18 distinct entities, 1.67 mentions each, measurable) — the proxy
behaves correctly on genuine long-form content, not just synthetic fixtures.

327 -> 331 tests.

## [3.26.0] - 2026-08-14

**The humanize gate stops being a vibe, and the author stays in the piece.**

### Fixed — `humanize_passed` had no implementation behind it

The content-engine's quality scorecard gated on "`05-humanize.md` shows AI-pattern density below the brand-specific threshold (default: under 10% of paragraphs flagged)". There was no pattern catalog, no humanizer agent, and no script anywhere in the repo that produced a flag. A gate whose measurement is undefined does not fail — it passes on impression, every time.

- **`scripts/ai-tell-scan.py`** (new) is that missing measurement. Deterministic, self-contained, lexicon in-script: LLM-favored vocabulary, significance markers, soft-adverb clusters, connective openers, participial openers, em-dash density, and ungrounded one-liners — each per 1000 words, with flagged sentences and a per-paragraph flag rate. `humanize_passed` now reads a number the script computes.
- **The gate counts only three tells**, and that restraint is the point. Measured against real hand-written marketing copy, the short-declarative heuristic alone flagged 50% of paragraphs — gating on it would fail good human writing and spin the pipeline into rewrite loops, which is worse than the undefined gate it replaced. Only `llm_favored_word`, `significance_marker`, and `soft_adverb_cluster` gate; the rest are reported as editor-facing context where a false positive costs two seconds instead of a rewrite.
- **Absolute floors** stop small samples from manufacturing tells: one legitimate "actually" in a 150-word excerpt normalizes to a per-1000 figure well over threshold, and is not a pattern.
- The fix for any flag is a verified specific from `04-fact-check.md` — never a synonym swap, never an invented fact.

### Added — significance markers

A sentence whose only job is to tell the reader what a neighbouring sentence means: "here's the thing", "the thing is,", "that's the part that got me", "which is exactly the problem", "let that sink in". The scan returns these with `"fix": "Delete this sentence; do not reword it."` — softening a marker into a gentler marker is not a fix; the specific it points at already does the work. Phrases are scoped to their marker senses so ordinary prose ("that's the part of the regulation that changed", "the thing is broken") is not flagged.

### Added — bring your own words (`--source-draft`)

- **`scripts/authorship.py`** (new) measures sentence-level provenance between the author's own rough draft and the finished piece: which sentences are theirs verbatim, which were **rewritten**, which were **dropped**. Matching is greedy and one-to-one, so repeating an author's line cannot inflate their share.
- The author's draft is saved verbatim as `00-source-draft.md` and carried into the draft **unchanged** — typos, run-ons, lowercase and all. **Their sentences are exempt from every tell**: if the author wrote "here's the thing", it stays, because a pattern describes what a model writes unprompted, not what a person chose to say.
- **This check blocks; it does not advise.** Every tell scan here stays advisory because a detector signal is a probabilistic opinion. "The author wrote this sentence and it is no longer here" is a checkable fact about a promise the pipeline made, so `authorship.py` exits 3 until the sentence is restored *verbatim* — never resolved by editing their words further.
- **Their claims are their voice, not verified facts.** Anything factual the pipeline adds still comes from `04-fact-check.md`; a claim of theirs that contradicts the research is flagged for the human editor, never silently corrected.
- **Provenance-accurate disclosure**, gated on the record: `may_claim_authored` requires both a 25% author-word floor and zero outstanding violations. The direction is one-way by design — an authorship record may only ever make a disclosure MORE specific about human involvement that demonstrably happened. Overclaiming human authorship is the one form of this statement a reader cannot check.

### Added — entity development (structural scan)

A seventh proxy in `structural-tell-scan.py`: specifics introduced once and abandoned read as a machine establishing a setting; an expert returns to the few that carry the argument. **Fixed by developing, never by deleting** — cutting specifics would lower the `specificity` finding in the same scan, which matters more, and inventing a mention is forbidden outright. Silent below 600 words or 12 distinct entities, because a short piece names things once for lack of room.

### Changed

- `/digital-marketing-pro:check` now reports **both** tell tiers in one advisory section, and still **NEVER** lets either affect the PASS/WARN/BLOCKED decision.
- Both scans keep their thresholds inside their own scripts, deliberately outside every eval config — guard-tested.

### Notes

- **No watermark detection or removal exists anywhere in DMP, and none will be added.** Both scans measure visible text only. A guard fails the suite if evasion vocabulary (zero-width characters, homoglyphs, watermark stripping, "pass as human") appears in the files this release touched.
- Both new scripts are fully self-contained — no sibling-plugin delegation, guard-tested.
- 294 → **327 tests**. New: `tests/test_ai_tell_and_authorship.py` (33).

## [3.25.0] - 2026-08-13

Honest provenance + the structural tier — the disclosure-and-structure layer
proven in the suite's content pipeline (CF v3.22.0), mirrored into DMP's
content surface. Context: Anthropic now statistically watermarks Claude text
output (models ≥ 2026-08-02; a mark proves *processed by*, not *authored by*),
and StoryScope (arXiv 2604.03136) showed AI text stays detectable on document
STRUCTURE even after a perfect surface-style pass. DMP's answer is
transparency and genuinely human-shaped structure — no watermark detection or
removal exists in this plugin, permanently.

### Added

- **`scripts/detect_surface.py`** — classifies the running harness
  (claude / non-claude / uncertain) from affirmative env fingerprints, with
  the fail-safe pinned in tests: uncertain ⇒ disclose; skipping the
  disclosure requires an AFFIRMATIVE non-Claude fingerprint.
- **AI-assistance disclosure** (brand-setup + content-engine): profile.json
  gains `ai_disclosure` — `{"mode": "claude-surfaces"|"always"|"off",
  "text": null|custom, "author": null|name}`. Default wording is
  author-optional, vendor-neutral (guard-tested), and claims only the review
  the pipeline performs. Applied inside the `09-publish-ready.md` body so it
  survives `/digital-marketing-pro:publish-blog`; the decision is recorded
  in handoff metadata either way. Complements (never replaces) the existing
  `eu_disclosure_if_ai` gate.
- **`scripts/structural-tell-scan.py`** — Tier-2 structural AI-tell proxies
  with spans (moralizing/over-explained takeaways, template section symmetry,
  parallel heading syntax, specificity density, stance absence,
  paragraph-rhythm evenness). Bands OK/NOTE/ATTENTION with thresholds in the
  script, deliberately outside every eval/scoring config (guard-tested).
- **content-engine structural pass**: after `05-humanize.md`, the scan runs
  and NOTE/ATTENTION findings get fact-grounded structural edits (cut the
  spelled-out takeaway, break unearned symmetry, add verified specifics,
  take a defensible stance); the band lands in the quality scorecard as
  ADVISORY and never gates `status: ready`.
- **/check advisory section**: the structural findings report alongside the
  eval scorers but NEVER affect the PASS/WARN/BLOCKED decision.
- `tests/test_disclosure_and_structure.py` (13 tests): decision matrix incl.
  the uncertain⇒disclose pin, vendor-neutral default wording, AI-shaped
  fixture fires / human-shaped fixture stays quiet, advisory-never-a-gate,
  and the skill wiring. **Tests 281 → 294.**

## [3.24.0] - 2026-08-12

The timing ladder — the last "shipped table pretending to be timeless" in the
plugin. posting-time-analyzer and send-time-optimizer were static best-times
lookup tables: population averages describing everyone's audience (which is no
one's audience), with no path to the brand's own data and no expiry.

### Changed

- **Both timing scripts rebuilt on the measurement ladder.**
  - **Rung 1 — first-party (`--history`)**: the brand's own post/send log,
    aggregated into ranked day × hour-block windows with honest statistics —
    minimum sample floors (30 posts / 12 sends overall, 5 / 3 per bucket),
    sample sizes in every recommendation, and an explicit refusal to rank what
    the data cannot support. First-party is the ONLY path to "high" confidence.
  - **Rung 2 — dated population baseline**: the curated tables remain as test
    starting points, stamped `baseline_as_of` (re-verified against current
    published studies 2026-08-12), with absolute confidence renamed
    `relative_strength` and capped at medium — a population average can never
    be high-confidence for a specific audience. The stamp AGES: >180 days
    warns in every output; >540 days the baseline REFUSES (exit 3) and
    instructs a live refresh or `--history`.
  - **2026 mechanics in every output**: per-platform `algorithm_note` (feeds
    use recency to seed early velocity, but interest-ranked distribution means
    content strength dominates timing — TikTok least time-sensitive, X/Twitter
    most); email outputs always carry the STO doctrine — per-recipient
    send-time optimization from the connected ESP outperforms ANY global
    window (current reports: 5-15% open-rate lift); A/B segment windows 4-6
    weeks, then layer STO.
  - Baseline rows that current published data clearly moved were refreshed
    (TikTok's evening windows → weekday-afternoon; Instagram gains the
    early-morning velocity window).
- **Consumers updated to the ladder**: schedule-social and send-email-campaign
  steps, social-media-manager and email-specialist tool entries,
  execution-workflows, team-roles-framework — which was also documenting
  `--brand/--region` flags the script never had (doc↔script contract bug,
  fixed to the real interface).

### Added

- **`tests/test_timing_ladder.py`** (12): first-party finds a synthetic
  engagement peak and reports sample sizes; thin history falls back WITH the
  explanation attached; baseline outputs carry stamp + ceiling +
  relative_strength (never absolute confidence); every platform has an
  algorithm note; STO doctrine always present; timezone adjustment regression;
  and self-aging release gates that fail the suite when a shipped baseline
  stamp exceeds its window. Suite: 269 → 281.

---

## [3.23.0] - 2026-08-12

Translation goes capability-first — the last hardcoded-vendor surface in the
plugin, verified in code (not from notes) and reworked. The localization
cluster shipped a four-vendor routing table ("Indic → product A, European →
product B") plus a closed enum in language-config: a bet on the 2026 vendor
landscape baked into a plugin that runs at arbitrary future dates.

### Changed

- **`language-router.py --action route` rebuilt.** The route result names a
  CAPABILITY KIND per language family (translation.indic / .european / .cjk /
  .semitic / .sea / .general) with selection criteria — native script-aware
  models, formality registers, segmentation, RTL integrity — and resolves a
  concrete service only at run time: the brand's recorded
  `translation_preferences` first (free-form, honored even for servers no
  shipped list knows), then translation-capable MCP servers discovered live in
  `.mcp.json` (one candidate → resolved; several → judged against the
  criteria). Nothing connected → `basis: unresolved` plus a resolution ladder:
  the harness's own multilingual capability with mandatory scoring, tools the
  user already has, or ask-and-record. Every payload carries `basis`. Detection
  and scoring are untouched.
- **`language-config`**: `set-translation-pref` accepts any server-name slug —
  the closed four-vendor enum is gone; unknown-but-recorded preferences warn
  instead of being rejected.
- **`translate-content` / `localize-campaign`**: execution steps rewritten
  around the resolved service's capabilities (register control, glossaries,
  script handling) with the harness-translation path as a legitimate,
  score-gated route — vendor-specific step instructions removed.
- **`localization-specialist` agent**: routes capability-first; judges
  connected candidates against criteria; never instructs installing a
  commercial product.
- **`multilingual-execution-guide`**: the vendor comparison table (whose rate
  limits and prices rot like all shipped market facts) replaced by a
  capability checklist and per-family requirements; routing tree redrawn as
  the resolution ladder; Indic guidance reframed as what an Indic specialist
  must provide. `india-market-context` and `docs/architecture.md` aligned.
- Deliberately unchanged: the connector CATALOG (CONNECTORS.md, registry
  tables, per-connector setup in docs/) — enabling connectors the USER chose
  is the "already-connected tools" rung of the ladder, not an endorsement.

### Added

- **`tests/test_language_router.py`** (10): resolution ladder, free-form
  preference ("my-own-translator" resolves — unknown ≠ unusable), candidate
  handling, missing-preference warning, no vendor names inside the capability
  profiles, detection/scoring regression pins.
- **`tests/test_vendor_neutrality.py`** (6): no commercial translation vendor
  named on the skills/agents instruction surface (catalog exemptions by name),
  no sign-up/install instructions, the language-config enum pinned free-form,
  and the router's unresolved payload verified vendor-free. Plant-checked.
  Suite: 253 → 269.

---

## [3.22.0] - 2026-08-12

The Routing Layer — all 163 skill descriptions rewritten to the trigger-dense
house pattern, because for a model-invoked skill the frontmatter description
IS the routing layer: it is the only thing the model reads when deciding
whether a skill applies, and 163 skills with one-line descriptions meant wrong
routing, not just thin docs.

### Changed

- **Every skill description (163/163) rewritten**: states what the skill does
  and produces, then "Triggers on" with ≥4 quoted phrases a user would
  actually type (the `/digital-marketing-pro:<name>` slash alias always
  first), then what it reads or pairs with. Median length grew from a
  one-liner to ~720 characters of routing signal.
- **The rewrite doubled as an honesty audit.** Every description was written
  against the full SKILL.md, and capabilities the file does not deliver were
  deliberately NOT claimed — each agent-pass reported its refusals. Real
  overclaims caught in the OLD descriptions: campaign-orchestrator advertised
  "launching, managing" (it plans only); client-proposal advertised an SLA
  document (the file has a terms outline); lead-magnet-ideas' alias was not
  namespaced. Plan-only skills now say so ("it publishes nothing", "it sends
  nothing"); every approval-gated execution skill names its gate in the
  description; heuristic scripts are called heuristics (posting-time and
  send-time suggestions are static heuristics, not engagement-learned).
- **language-config description** no longer bakes in the four translation
  vendor names (body enum unchanged pending the localization-cluster
  vendor-neutrality rework, tracked as the next open item).

### Added

- **`tests/test_description_density.py`** — the guard that keeps the routing
  layer dense: single-line double-quoted descriptions, ≥300 and ≤900 chars,
  "Triggers on" + ≥4 quoted phrases + the namespaced slash alias per skill,
  and a median floor (≥350) so the surface cannot slide back toward
  one-liners one lazy rewrite at a time. Suite: 248 → 253.

---

## [3.21.1] - 2026-08-12

Patch caught by the ship ritual's verify-from-installed-copy step, minutes
after 3.21.0.

### Fixed

- **`build_skills_index.py` measured environment, not content.** The index's
  per-skill `bytes` came from on-disk file size, which git's LF↔CRLF
  conversion changes per checkout — so `--check` reported DRIFT on an
  installed copy of the very commit that generated the index. Byte counts are
  now computed from newline-normalized text; the depth contract compares
  content, never checkout configuration.

---

## [3.21.0] - 2026-08-12

The Flagship Contract — three invisible risks made visible and machine-enforced:
market benchmarks that rot silently, skill depth nobody could verify from the
outside, and model resolutions that look identical whether the registry was
reviewed yesterday or abandoned a year ago.

### Added

- **`scripts/benchmark_book.py` — market benchmarks with provenance.** The
  price-book contract applied to market data: a benchmark enters only via
  `record` with a source URL and as-of date (no seed table ships — a fresh
  workspace has zero entries, and a test pins that); `quote` returns a status,
  never a bare number — fresh (≤90d) quotes cleanly, aging (≤365d) carries a
  warning the caller must surface, stale or absent REFUSES (exit 3) and names
  the lookup to run. Keyed metric × channel × segment, because LinkedIn CPM
  for B2B is not Meta CPM for DTC. 13 tests (`tests/test_benchmark_book.py`).
- **Benchmark provenance banners across 28 skill docs** (every paid-advertising
  platform doc, the industry-profiles tables, influencer rate cards, tool
  pricing tables). Each banner carries an as-of stamp that AGES OUT in
  `tests/test_benchmark_provenance.py`: stamps older than 6 months warn at test
  time, older than 15 months fail the suite — benchmark rot becomes a red build
  instead of a confident lie in a doc nobody rereads. The scanner is
  mechanical (metric-token + $, subscription prices, creator rate cards), with
  named exemptions for worked examples and regression pins so it cannot
  quietly weaken. 8 tests.
- **`skills-index.json` — the depth contract.** Generated by
  `scripts/build_skills_index.py`, committed, and machine-verified: every
  skill's tier (E executes real scripts — 108; M output measured through the
  quality machinery — 12; G structured guidance — 43), its scripts, gates,
  and cross-references. `tests/test_skills_index.py` (9 tests) fails on drift,
  on any referenced script that does not exist, and on the executable tier
  dipping below 100. "163 skills" is now a verifiable claim, not a count.
- **`resolve_model.py --for-execution` — the execution ladder.** Resolution
  that carries its own provenance: basis, registry age, and a staleness
  warning attached to every payload once the registry is older than 7 days;
  unknown aliases are REFUSED (exit 3) with the lookup ladder named instead of
  letting a caller fall back to a memorized literal. 5 tests.
- **`/help --intent "<goal>"` — intent-first routing.** Goals route to at most
  3 skill CHAINS read from skills-index.json (entry skill → cross-referenced
  handoffs → the gate), each step tier-badged with one line of why; chains
  producing publishable output must end at a gate. `--skills` listings now
  carry the depth-tier badges.
- **`tests/test_engagement_smoke.py` — the capstone.** A synthetic brand runs
  the executable spine end to end in one workspace: engagement intake (stone
  facts + opinions with evidence) → benchmark record/quote → ROI math on the
  QUOTED numbers → campaign persistence → provenance-carrying model
  resolution → coherent engagement status. The flagship assertion: the
  benchmark's source URL survives every joint into the stored campaign record.
  Plus the negative twin: with nothing recorded, the chain refuses to run on
  remembered numbers.

### Changed

- **Live-verification pass over the benchmark surface** (2026-08 sources, two
  or more per area): WhatsApp Business API pricing rewritten from the retired
  per-conversation model to per-message billing (category × recipient country
  × volume tier, marketing ~$0.01–$0.14/msg, service replies free); TikTok
  TopView CPM corrected $50–$80 → $11–$19 and creator-tier rates recalibrated;
  LinkedIn CPL floor raised $30 → $50 (2026 average ≈ $75); Amazon DSP CPM
  widened to $3–$15; Heepsy ($49–$269 → $89–$369) and Modash ($99–$399 →
  $199–$599) repriced — both had dropped their old entry plans entirely.
  Influencer rate cards, podcast CPMs, and LinkedIn CPM/CPC verified current
  and left untouched.
- **`media-planning.md`** now routes every rate assumption through
  `benchmark_book.py --action quote` before it enters a plan; a refusal means
  research-and-record first, never carry-forward from memory or from the doc.
- **`campaign-planning.md`** SMART example now sources its CPL benchmark from
  brand history or a recorded benchmark-book entry — never from memory.

### Fixed

- **README what's-new history**: the v3.17.1 registry-reconciliation entry had
  been relabeled "v3.20.0" by a wholesale version bump, and the real
  v3.18.0–v3.20.0 releases were missing from the narrative. History restored.

---

## [3.20.0] - 2026-08-12

Video ad scripting, campaign linkage, and the unified quality gate — video
scripts were a standalone content skill with no connection to the campaign
machinery or to /check, and no ad-format craft at all.

### Changed

- **`/video-script` step 2.4 — organic or ad, and campaign context first.**
  Organic content earns its audience; ads buy theirs, so the craft is what
  happens inside a paid, often skippable slot. Campaign scripts read the
  campaign brief from the brand workspace so they inherit the objective,
  funnel stage, audience, and offer instead of inventing parallel ones — a
  mid-funnel retargeting ad and a cold-audience awareness ad are different
  scripts for the same product, and the campaign brief decides which this is.
  Per-format structural rules: **6s bumper** — one message, no arc, brand by
  second 2, two messages means two bumpers; **15s skippable** — the skip
  button at 5s is the real deadline, hook and core message land before it, and
  a script that saves its point for second 9 was a 5-second logo exposure for
  most of its audience; **30s spot** — one front-loaded arc, pay off early and
  again late; **UGC-style** — native-feeling is a style, not a disclosure
  exemption (FTC/ASA rules apply in full).
- **`/video-script` step 11 — the unified gate.** Every finished script's
  narration and on-screen text routes through /digital-marketing-pro:check,
  the same hallucination + brand-voice + claims gate every other deliverable
  passes. For ad scripts it is non-negotiable: paid distribution multiplies
  whatever the script gets wrong, and platforms adjudicate claims complaints
  against the advertiser.
- **`/ad-creative`** routes video ad scripts to video-script's format rules
  and keeps ownership of the copy layer around the video — headlines,
  descriptions, CTAs.

---

## [3.19.0] - 2026-08-12

Video discovery and packaging craft, extracted from the same 17-skill reference
study as 3.18.0 — the YouTube-specific skills were initially set aside as
"wrong surface", then quarried properly: the craft transfers even where the
surface does not.

### Added

- **`/video-packaging`** (163rd skill) — generate or critique title +
  thumbnail-text pairs under the pairing principle: the title carries context
  and keywords (what the platform's systems read), the thumbnail text carries
  the tension (what a human reacts to), and they never say the same thing —
  any thumb word already in the title is rejected as wasted real estate,
  checked word by word. Every package is tagged with its discovery intent
  (search / browse / both), because the two are found differently and reward
  different structures. Critique mode gives PASS/FIX/FAIL on an existing
  video's packaging with three fixed pairs — the "strong content nobody
  clicks" entry point a channel audit produces. Packaging never outpromises
  the video; titles pass the same claims gate as any other copy.

### Changed

- **`/video-script`**: declares discovery intent before structure (a video
  with no search or browse logic has no discovery reason — the topic goes back
  to development rather than into production); long-form body sections carry
  the payoff rule (no section ends on setup — that is where viewers leave);
  the output gains **retention notes** naming the 2-3 likely drop points and
  the hold at each; the thumbnail step adopts the pairing rule and tightens
  overlay text to 1-3 words.
- **`/content-repurpose`**: gains the standalone test — every derivative piece
  works for someone who will never see the source, with its own hook and
  payoff. Not every section of a source is repurposable; what fails the test
  is cut and listed, and the cut list ships as evidence the filter ran. The
  10+ pieces target no longer overrides quality — eight strong beat twelve
  where four are filler.

---

## [3.18.0] - 2026-08-12

Four skills (158 → 162) closing a shared gap: DMP could execute any marketing
plan but had nothing that filtered work against the objective, and nothing that
turned lived experience or raw industry material into brand-safe content
angles. Patterns extracted from a study of 17 third-party creator skills —
taken as reference, reimplemented fresh against DMP's brand-profile and
compliance machinery, nothing copied.

### Added

- **`/goal-filter`** — locks ONE primary goal per brand
  (`goal-lock.json` in the brand workspace) and judges any idea, draft, or
  plan against it: ON GOAL / PARTIAL / OFF GOAL, always with the fix or the
  sharper version, never just a grade. Verdict history is kept and patterns
  are named across checks — three OFF verdicts in a week is a drift, not three
  ideas. Inside a 12-Part engagement it locks Part 1's primary objective
  rather than inventing a parallel one.
- **`/story-mine`** — a real experience in, 3-5 distinct content angles out
  (the lesson, the contrarian take, the framework, the proof, the relatable
  moment), each with format, pillar, and a draft opening that leads with the
  interesting part. `--client-safe` anonymisation defaults ON for client
  stories; fabricating story details is banned outright; a strong proof angle
  routes to case-study-plan.
- **`/signal-mine`** — a raw dump of news, threads, competitor moves, or call
  notes in; only the angles the brand has *standing* to make out, each mapped
  to a pillar with a timeliness window. The dropped list always ships, with
  reasons — authority beats relevance, and pasted claims stay unverified until
  routed through verify-claims.
- **`/lead-magnet-ideas`** — topic or campaign in, specific lead-magnet ideas
  out, each cut from IP the brand already owns and graded on **lead-gen power
  × build effort** with reasons. Every idea names what it qualifies the lead
  for; power-C × effort-C ideas are flagged as not worth building.

---

## [3.17.1] - 2026-07-30

### Fixed

- **Model registry reconciled with current truth.** The canonical registry lagged the sibling ContentForge registry that was corrected in its July-29 audit: `latest-fast-openai` still pointed at `gpt-5.4-nano` (now `gpt-5.6-luna`), `latest-balanced-openai` at `gpt-5.4-mini` (now `gpt-5.6-terra`), and `latest-balanced-anthropic` at `claude-sonnet-4-6` (now `claude-sonnet-5`). The GPT-5.5/5.4 family moved `current` -> `supported` with `replacement_id`s targeting GPT-5.6 (GA 2026-07-09), and the `balanced-video` tier was added. Caught by this repo's own cross-registry drift tests — which is exactly what they exist for.
- **Source-anonymity guard test added** (`tests/test_source_anonymity.py`). The rule that the methodology's source organization is never named anywhere in the repo was previously enforced only by hand; the guard scans every text file on every run, with the forbidden strings assembled at runtime so the test itself keeps the repo grep-clean. Verified to fire on a planted needle. Tests 209 -> **210**.
## [3.17.0] — 2026-07-29

### Changed — The Line-by-Line Audit

Every file in the repo (530 files, ~162K lines — all 158 skills, 24 agents, 18 commands, 86 scripts, tests, docs, manifests) was read end-to-end by a 16-reader audit fleet, cross-checked against primary-source July-2026 ground truth and against the code itself, then fixed by an 8-worker fix fleet with disjoint file ownership. ~250 corrections in ~150 files:

- **Truth pass on the long tail.** Dead or retired products removed from live recommendations: Google Podcasts, Stitcher, Chartable/Podsights, Google Assistant Actions, Instagram Live Shopping/Guides, Starbucks Odyssey, Oracle BlueKai/MOAT/Contextual, Amazon Freevee, Netflix-via-Xandr, CareDash, HARO, giropay/SOFORT, Curalate, Hootsuite Insights, GARM (wound down), Zapier NLA, GSC legacy tools (robots.txt Tester, crawl-rate limiter, sitemap ping, International Targeting), FID, ZestMoney, JioCinema/Disney+ Hotstar (→ JioHotstar), E3, TrueView. Chrome third-party-cookie deprecation corrected to CANCELLED across 5 files; ePrivacy Regulation marked withdrawn (Feb 2025); COPPA amended rule (2025); LinkedIn Ad Library documented; WhatsApp per-message pricing aligned; Meta Special Ad Audiences removal noted; platform video limits updated (Shorts/Reels 3 min).
- **EU compliance currency.** All remaining draft-guidance and pre-22-July language moved to final-Code, post-deadline state; Article 50 applicability (2 Aug 2026) called out at every disclosure decision point.
- **Doc↔script contract repair.** Every documented flag, payload shape, storage path, threshold, and taxonomy now matches the code (validate-profile storage layout, approval-manager/quality-tracker/memory-manager/crm-sync/team-manager payloads, creative-health weights+risk levels, churn tiers, eval run-quick scope, --schema vs --custom-schema, connector counts 10 registry-backed + catalog-only extras, and more).
- **Script hardening.** Trustworthy exit codes (revenue-forecaster, pdf-generator, gsc-ai-performance), atomic writes everywhere, storage split-brain fully closed (adaptive-scorer, eval-runner, eval-config-manager, brand-voice-scorer, journey-engine, narrative-mapper now on `_common`), real quality gates (keyword-cluster cannibalisation, calendar gap dedup), input sanitization (prompt-ab-tester), sentinel/zip/formula bugs fixed (intelligence-graph --min-confidence, audience-simulator Van Westendorp, ad-budget-pacer exhaustion math, growth-loop-modeler sustainability), embed-c2pa now stamps the live plugin version, eval-runner scores by actual content type, subset-safe registry sync, thread-splitter no longer drops words, Bluesky tag facets supported.
- **Statistical integrity.** A/B and personalization sample-size tables regenerated from `sample-size-calculator.py` (previous tables were ~5× inflated); absolute-vs-relative MDE factor corrected (~200×, not 40×); test-velocity math fixed.
- **Discoverability.** Reference-file indexes completed — context-engine now indexes all 56 reference docs (grouped), and 14 other skills list every reference file they ship.
- **Self-containment, everywhere.** Guard test extended beyond skills/agents/commands to docs/, scripts/, and root docs (cross-promo and shared-registry infra allowlisted); remaining leaks in AGENTS.md, engagement-methodology, the C2PA cert guide, and output-publisher removed. Retired `competitor-intelligence` agent references renamed to `competitive-intel` across 6 skills.
- Tests 208 → **209**; suite green.

## [3.16.0] — 2026-07-12

### Changed — July 2026 Market Refresh

All claims below verified against primary sources on 2026-07-12 (vendor docs, EU Commission, platform changelogs).

- **EU AI Act — FINAL Code of Practice adopted.** `context-engine/eu-code-of-practice.md` rewritten from "second draft, final not yet published" to the **final Code of Practice on Transparency of AI-Generated Content (published 10 June 2026)**: official PDF cited, standardized EU disclosure icons now published (use them), initial-signatory window closes **22 July 2026**, Commission confirms the Code as an adequate voluntary compliance tool, and the **final Article 50 Guidelines** are adopted (`compliance-rules.md` §1.1b.i updated draft→final). Article 50 applies 2 Aug 2026.
- **Model registry: Claude 5 + GPT-5.6 families added** (`model_registry.json` 62→68 entries, mirrored to the ContentForge registry): `claude-fable-5` (Mythos-class, $10/$50, refusal/fallback semantics documented), `claude-opus-5` ($5/$25, May-2026 knowledge cutoff — Anthropic's new recommended default), `claude-sonnet-5` (intro $2/$10 through Aug 31), `gpt-5.6-sol` / `-terra` / `-luna` (GA July 9; $5/$30, $2.50/$15, $1/$6). Aliases re-pointed: `latest-text-anthropic` → claude-opus-5, `latest-text-openai` → gpt-5.6-sol. `claude-opus-4-8` → supported/legacy (context corrected to 1M); `claude-opus-4-1` flagged **retires 2026-08-05**.
- **`docs/MODEL-CURATOR.md`**: alias table re-dated, parameter-compatibility section extended to the Claude 5 family, new **Fable 5 refusal handling** guidance (`stop_reason: "refusal"` as HTTP 200 + `fallbacks` parameter + fallback credit).
- **Meta Marketing API v25 truth pass**: `meta-ads.md`, `paid-advertising/SKILL.md`, `execution-workflows.md`, `ai-marketing-tools.md` now state that standalone Advantage+ Shopping/App campaigns can no longer be created via the API (all versions since 19 May 2026; v26 pauses remaining ones Sept 2026 — unified Advantage+ is the go-forward path) and that the **Page Viewer metric** replaces legacy reach metrics.
- **Google Ads API v25** (July 2026 major: legacy lifecycle-goal resources removed → unified `Goal`/`CampaignGoalConfig`; loyalty-retention goal; Shorts social metrics) documented with a deliberate-adoption note; v24.2 remains the stable target. **LinkedIn 202607** documented (auto Not-Interested CTA on Message Ads; `SHA256_IP_ADDRESS` in Conversions API).
- **`gsc-ai-performance`**: report family now covers **Discover** generative surfaces; data backfilled from 18 May 2026; access expanded July 2026; API surface still unpublished.
- **README rotation**: hero/cost/examples reference Opus-class models (measured on 4.8, Opus 5 current at the same price); What's-new intro reframed to the July 2026 state.
- **Test suite 207 → 208** — new self-containment guard test locks the v3.15.1 rule (no cross-plugin capability references in the skill surface).

## [3.15.1] — 2026-07-12

### Changed — plugin self-containment

- **Removed every cross-plugin capability reference.** Skills no longer point users at SocialForge or ContentForge for any activity — DMP is fully standalone. Affected skills: `ad-creative` (visual production handoff is now tool-agnostic), `engagement-workflow` (Part 11 asset rendering no longer requires another plugin), `c2pa-metadata`, `launch-campaign` (C2PA signing + resume are DMP-native paths), `content-engine` (AI-detection guidance is self-contained; repurposing routes to `content-repurpose`), `keyword-cluster`, `campaign-audit`, `validate-profile` (now checks DMP's own publish dir `$DIGITAL_MARKETING_PRO_PUBLISH_DIR` / `~/Documents/DigitalMarketingPro/` instead of ContentForge's), `context-engine/eu-code-of-practice.md`, `context-engine/compliance-rules.md`.
- README suite table and "other plugins" links are unchanged — cross-promotion stays; capability delegation is gone.

## [3.15.0] — 2026-07-07

**The Reliability & Truth release — a full-repo audit (orchestration, agents, skills/commands, Python scripts, configs/docs/manifests) surfaced ~200 findings; this release fixes them in one coordinated pass.** The theme is honesty: every fabricated capability, fictional package, phantom script flag, stale count, and unsafe gate is either fixed or explicitly labeled. Mirrors ContentForge v3.16.0 (same release class, same day).

### Added

- **`scripts/_common.py`** — one shared workspace-root resolver (`$CLAUDE_PLUGIN_DATA/digital-marketing-pro/brands/{slug}/` → `~/.claude-marketing/brands/{slug}/`), one `slugify_brand`, atomic JSON writes, safe JSON loads, a UTF-8 stdout guard, and a `finish()` exit helper — adopted across the script layer to kill the storage split-brain and the four-different-slugify bug.
- **`scripts/check_skill_contracts.py`** — a doc-vs-argparse linter that parses every fenced script call in SKILL.md/commands/agents and validates flags/actions against each script's real argparse. Wired into the test suite so contract rot can't silently return.
- **C2PA 2.4 AI-disclosure** — `embed-c2pa.py` gains `--ai-disclosure`, embedding the `c2pa.ai-disclosure` assertion (the EU AI Act **Article 50** machine-readable pathway, applicable 2026-08-02) alongside the existing IPTC digital-source-type claim.
- **Tessl CLI review workflow** — `.github/workflows/skill-review.yml` moves off the retired `tesslio/skill-review@main` Action to the `tessl review` CLI, with scoring dimensions encoded in the new `.github/tessl-rubric.yml` (closes issue #8).
- **Uniform execution gate** — all 18 execution skills now carry an explicit `## Execution gate` (typed approval, cancel-on-anything, never proceed on ambiguous input) and `disable-model-invocation: false` so Codex's validator stops erroring (closes issue #6).
- **State-layer + release-consistency tests** — engagement/checkpoint/execution state machines, `_common`, the contract scanner, and AGENTS/README/manifest count locks. Test suite grows from 123 to 207 passing.

### Changed

- **Agents 25 → 24.** `competitor-intelligence` merged into `competitive-intel` (with a `mode: snapshot|monitoring` input, keeping its evidence-discipline rules); `memory-manager` reduced to a thin storage agent while `intelligence-curator` owns intake/interpretation. All 9 manifest descriptions, AGENTS.md (now with the explicit 24-agent roster), and docs updated.
- **Connector truth.** The `connect` skill's "13 HTTP connectors are already pre-configured" fiction is gone — connectors are an opt-in catalog (the shipped `.mcp.json` is empty `{"mcpServers":{}}`). `.mcp.json.example` gains a verification `_warning` enumerating verified-real vs known-fictional npm packages; memory-architecture and skill/registry text demote Graphiti/Supermemory/Qdrant/Notion npm backends to "only if you have a working server connected".
- **Script-contract rot fixed** across compliance/intel/agency/memory/eval skills: real `eval-config-manager` actions (no `--value`/`set-content-type`/`reset-config`), agency CLI drift (`list`→`list-campaigns`/`get-history`, `metrics`→`get-campaign`, `list-assignments`→`get-assignments`, required `--brand` added), `intelligence-graph`/`narrative-mapper`/`geo-tracker`/`growth-loop-modeler`/`macro-signal-tracker`/`competitor-tracker` positional calls → `--action`/`--brand` forms, correct six eval dimensions (`content_quality, brand_voice, hallucination_risk, claim_verification, output_structure, readability`), and `--file` vs `--text` for eval inputs.
- **Manifests hardened.** Dropped the dangling `mcpServers` key from `.cursor-plugin/plugin.json` and `.github/plugin/plugin.json` (they pointed at the gitignored `.mcp.json`); confirmed `repository` is a string URL and no `$schema` key in plugin/marketplace manifests; `plugin.yaml` `.hooks/`→`hooks/`; `settings.json.example` OTEL var moved under `env`; `.gitignore` bare-directory ignores anchored to repo root.
- **Docs re-snapshotted to truth.** AGENTS.md (phantom `references/` dir removed — reference files live inside `skills/<name>/`, 169 of them; surfaces heading → v3.15.0), architecture.md (removed the false `$schema` claim, empty-`.mcp.json`/empty-hooks truth, package-verification caveat), claude-interfaces/getting-started (counts → 158 skills / 24 agents / 18 commands / 169 refs), CONNECTORS.md ("pre-configures" → shipped-empty), TESTING-GUIDE section 7 (hooks ship `{}` since v3.1.0), SUBMISSION.md (marked historical + phantom `config/`+`examples/` paths and fabricated agent list removed).
- **Compliance currency.** `eu-code-of-practice.md` moved to a July verification pass (June passed without the final Code confirmed published; second draft remains operative), with FTC May-2026 endorsement guidance, the NY synthetic-performer law, and the standardized EU disclosure icon flagged for verification. `region-config` onboarding gains India DPDPA + EU AI Act Article 50.

### Fixed

- Uncited "93% of consumers" stat in `reputation-management/review-strategy.md` delabeled to a verify-before-citing note; `what-if` gains a simulated-output disclosure; hardcoded "Opus 4.7 / Sonnet 4.6 / Haiku 4.5" + unexecutable `/usage --since 7d` in `agency-dashboard` made registry-driven and user-data-gated; `sync-memory` checkpoint path corrected to `memory/_last_sync.json`; `memory-architecture` phantom `--entity-type`/no-op `--type` flags fixed; C2PA spec link v1.3 → 2.4.
- `python3` → `python` and bare `scripts/` → `python "${CLAUDE_PLUGIN_ROOT}/scripts/…"` across the touched compliance/intel/agency skills (Windows-first). `validate-profile`'s connector probe softened to the honest local env-var/`.mcp.json` check it actually performs.

---

## [3.14.1] — 2026-06-28

**README sync patch + test-coverage extension. Catches the drift class v3.14.0 shipped with.**

After v3.14.0 shipped, the user flagged that the README still showed `## Supported surfaces (v3.13.1)`, a stale Cowork badge anchor pointing at `#supported-surfaces-v3131`, a second internal anchor with the same problem, and a "What's new" section whose latest entry was still v3.13.0 — three releases out of date. The release-consistency test suite covered most cross-manifest drift but had test-coverage gaps on these three specific README facets (CF + SF tests already had the section-heading lock; DMP didn't).

### Fixed (DMP README)

- `## Supported surfaces (v3.13.1)` → `(v3.14.1)` (line 246)
- Cowork badge anchor `#supported-surfaces-v3131` → `#supported-surfaces-v3141` (line 17)
- Second internal anchor in FAQ section, same fix (line 708)
- Added 3 missing What's new entries to README: **v3.14.1**, **v3.14.0**, **v3.13.1**

### Added (DMP `tests/test_release_consistency.py`, +3 tests)

- **`test_readme_supported_surfaces_heading_matches_canonical`** — locks `## Supported surfaces (vX.Y.Z)` heading to the canonical version. Mirrors what CF + SF tests already had.
- **`test_readme_supported_surfaces_anchor_links_match_canonical`** — verifies any `#supported-surfaces-v…` anchor link in the README matches the slugified canonical version. Catches the Cowork-badge-anchor class of drift.
- **`test_readme_whats_new_section_includes_canonical_version`** — verifies the README "What's new" section actually mentions the currently-shipping version. Catches the "shipped 3 versions, forgot to update the section" class of drift.

Test count: 120 → **123**. All passing.

### Changed

- All 9 DMP version declarations 3.14.0 → 3.14.1
- README test badge bumped 120 → 123
- README hero callout updated for v3.14.1
- README "What's new" gains a v3.14.1 entry

### Notes

- Pre-flight: ran the new tests against the v3.14.0 README state — confirmed they would have caught all 4 staleness issues. So the regression is now structurally prevented.
- Zero runtime change.

---

## [3.14.0] — 2026-06-28

**June 2026 market-refresh sweep — model registry rebuilt, Meta API bumped, Google Ads v24.1+v24.2 documented, EU Code of Practice second draft incorporated.**

Triggered by user request: *"do a proper cross-check of what's new in the market and what new or old things in the digital marketing plugin need to be updated or upgraded… check what might have degraded in our skills, plugins, or other technologies."* All findings verified against primary sources (platform.claude.com, developers.openai.com, ai.google.dev, developers.google.com, blog.google, digital-strategy.ec.europa.eu).

### Fixed — broken integrations users would have hit today

- **Meta Graph API bumped v20.0 → v24.0** across `scripts/connector_resolver.py` (4 callsites: `/campaigns`, `/posts`, `/feed`, campaign updates). Per Meta's deprecation policy all pre-v24 Marketing API calls were scheduled to fail by 2026-06-09 — our v20 hits would have started returning HTTP 400/410.
- **Retired Gemini preview models routed to GA replacements** (these endpoints stopped responding 2026-06-25):
  - `gemini-3-pro-image-preview` → `gemini-3-pro-image` (Nano Banana Pro GA 2026-05-28)
  - `gemini-3.1-flash-image-preview` → `gemini-3.1-flash-image` (Nano Banana 2 GA 2026-05-28)
- **Veo 2.0 / Veo 3.0 / Veo 3.0-Fast routed to Veo 3.1 preview** ahead of their 2026-06-30 shutdown — handled automatically via the `latest-video-google` alias.
- **Gemini 2.0 Flash family marked `retired`** (shutdown 2026-06-01, already past).
- **Imagen 4 marked `deprecated`** with replacement `gemini-3-pro-image` (Google announced deprecation 2026-06-15).

### Added — resolver now handles `retired` status

`scripts/resolve_model.py` previously only fell forward for `deprecated` models. The new logic unconditionally rewrites `retired` model IDs to their `replacement_id` — even when `allow_deprecated=True` — because retired models no longer respond at the API layer. New test `test_retired_falls_forward_unconditionally` covers this.

### Added — `--check-params` scanner for Anthropic param 400 protection

Claude Opus 4.7 and Opus 4.8 reject `temperature`, `top_p`, and `top_k` with HTTP 400 when set to a non-default value. New `python scripts/resolve_model.py --check-params <file>` scans a Python file for these kwargs near Opus 4.7+ targets (explicit IDs or `latest-text-anthropic` alias use) and exits 1 if found. Pre-flight scanned all 3 plugins' `scripts/*.py` — clean.

### Added — model registry rebuilt against Anthropic / OpenAI / Google primary docs

Net registry growth: 27 → 47 entries. Notable additions:

- **Anthropic active:** `claude-opus-4-8` (now recommended frontier), `claude-opus-4-6`, `claude-opus-4-5-20251101`; corrected `claude-sonnet-4-5-20250929` from mis-marked deprecated → still active per [Anthropic deprecations page](https://platform.claude.com/docs/en/about-claude/model-deprecations).
- **Anthropic deprecated:** `claude-opus-4-1-20250805` (deprecated 2026-06-05, retiring 2026-08-05), `claude-sonnet-4-20250514` + `claude-opus-4-20250514` (retired 2026-06-15).
- **OpenAI new flagships:** `gpt-5.5`, `gpt-5.5-pro`, `gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-image-2`.
- **OpenAI deprecated:** entire GPT-5 family + o3 / o3-pro (announced 2026-06-11, shutdown 2026-12-11).
- **Google new actives:** `gemini-3-pro-image` (GA), `gemini-3.1-flash-image` (GA, with video-to-image), `gemini-3.1-pro-preview`, `gemini-3.1-flash-lite`, `veo-3.1-generate-preview`.
- **Google deprecated:** Gemini 2.5 Pro / Flash / Flash-Lite (shutdown 2026-10-16).
- **Removed:** speculative `claude-sonnet-4-7` entry that was never in Anthropic's active list.

All 18 aliases re-pointed to current models. Notable: `latest-text-anthropic` now → `claude-opus-4-8` (was 4.7), `latest-text-openai` now → `gpt-5.5` (was gpt-5), `latest-image-photoreal-google` now → `gemini-3-pro-image` (was deprecated `imagen-4`).

Registry `last_updated` bumped to 2026-06-28; `next_review_due` 2026-09-28.

### Added — Google Ads API v24.1 + v24.2 documentation

`skills/paid-advertising/google-ads.md` now covers all three v24.x releases:

- **v24.0** (2026-04-22) — original breaking changes (videos/logo_images required on Demand Gen + Video responsive ads)
- **v24.1** (2026-05-13) — 4 new experiment types (`ADOPT_AI_MAX` / `ADOPT_BROAD_MATCH_KEYWORDS` / `OPTIMIZE_ASSETS` / `PMAX_REPLACEMENT_SHOPPING`) + `mobile_device_platform` segment for iOS/Android reporting
- **v24.2** (2026-06-24) — `GENERATE_LANDING_PAGE_TEXT` asset automation enum + first-class Local Services Ads (LSA) support via `AssetGroup.google_local_services_info` + beta `MultiPartyAuthReview` for regulated verticals

Adoption recommendation section added — recommends `ADOPT_AI_MAX` experiment as the canonical lift-measurement path before any AI Max rollout.

### Added — EU Code of Practice second-draft refresh

`skills/context-engine/eu-code-of-practice.md` rewritten against the [European Commission second draft (5 March 2026)](https://digital-strategy.ec.europa.eu/en/library/commission-publishes-second-draft-code-practice-marking-and-labelling-ai-generated-content). The second draft made two material changes from the first:

1. **Section 1 (Providers)** consolidated around **two-layered marking** (secured metadata required + watermarking required; fingerprinting/logging optional). C2PA explicitly satisfies the metadata layer.
2. **Section 2 (Deployers)** **dropped the AI-generated-vs-AI-assisted taxonomy** in favor of design + placement requirements for icons/labels/disclaimers on deepfakes + text publications on matters of public interest. Simplified exemptions for artistic / satirical / fictional / editorially-controlled content.

Added an **operational readiness checklist** for the **2026-08-02 Article 50 applicability date** (5 weeks away): brand profile review, c2pa_auto_sign enablement, disclosure-language drafting in EU languages, platform-roundtrip verification, signatory decision.

### Added — Google I/O 2026 announcements surfaced in SEO/AEO skills

- `skills/aeo-audit/SKILL.md` — added callout for **Google Information Agents** (AI Pro/Ultra subscriber feature launching summer 2026) as the 7th probe target once live.
- `skills/local-seo/SKILL.md` — added **2026 priority section** for **Google Agentic Booking expansion** to 4 new verticals (local services, home repair, beauty, pet care). Three opt-in requirements documented: GBP scheduling integration, `AvailabilityFeed` structured data, Service-catalog price transparency.

### Added — Suite-wide `docs/MODEL-CURATOR.md` refresh

All 3 plugins (DMP/CF/SF) ship the same updated `docs/MODEL-CURATOR.md`:

- Aliases table refreshed to show current resolutions
- New § **Parameter compatibility — Claude Opus 4.7 and later** explains the HTTP 400 risk and points to the new `--check-params` scanner
- Notes which Google models were retired June 25/30 with replacement IDs

### Tests

- DMP: 114 → **115 passing** (new `test_retired_falls_forward_unconditionally`)
- CF: 53/53 passing (model registry distribution validated)
- SF: 54/54 passing (resolver still routes `latest-video-google` correctly)
- Suite total: 222 tests across the 3 plugins

### Changed

- All 9 DMP version declarations bumped 3.13.1 → 3.14.0 (.claude-plugin, .codex-plugin, .cursor-plugin, .github/plugin, gemini-extension, openclaw.plugin, plugin.yaml, __init__.py, package.json)
- README test badge bumped 114 → 115
- README "Just shipped" callout rewritten for v3.14.0

### Notes

- `model_registry.json` schema unchanged; new fields (`deprecation_date`, `shutdown_date`, `tentative_retirement`) are additive and ignored by older callers.
- Meta Graph version `v24.0` hardcoded for now — future refactor to extract a `META_GRAPH_API_VERSION` constant would simplify the next bump.

---

## [3.13.1] — 2026-06-09

**Test infrastructure hardening + user-friendliness polish — no runtime changes.**

Triggered by user push-back: "you have the testing infrastructure, so test everything properly and make sure everything works awesomely. Also make sure the documentation and problem decisions are properly updated so you are friendly, discoverable, and user-friendly."

### Added — Tests (70 → 114, all passing)

Three new test modules expand the safety net so cross-manifest drift, README staleness, and Hermes/OpenClaw edge cases get caught at CI rather than in production:

- **`tests/test_release_consistency.py`** (25 new tests) — the highest-leverage addition. Tests fail when:
  - The 7 platform manifests (5 Claude-family + Hermes + OpenClaw) get out of version sync
  - The Hermes `plugin.yaml` version disagrees with `__init__.py`'s `PLUGIN_VERSION` constant
  - The README version badge falls behind plugin.json
  - The CHANGELOG's latest entry doesn't match the current plugin version (caught a stale entry during this release)
  - The test-count badge in the README is stale (caught and fixed 3 times during this release as new tests were added)
  - All Claude-family manifests' descriptions don't match each other verbatim
  - The skill-count claim in any description doesn't match `ls skills | wc -l`
  - An install command for any of the 8 native platforms goes missing from the README
  - A critical section (Who this is for, Compare table, Real workflows, Supported surfaces, Agent Skills 40+, What's new, FAQ, **Get started in 5 minutes**, **Troubleshooting**) goes missing
  - A README internal anchor link points at a non-existent heading
  - The Troubleshooting section fails to cover all 8 native platforms by name
- **`tests/test_hermes_edge_cases.py`** (10 new tests) — Hermes adapter resilience under adverse conditions:
  - Missing `skills/` directory entirely → adapter logs and returns cleanly
  - Empty `skills/` directory → no skills registered, no crash
  - Skill directory present but no `SKILL.md` inside → silently skipped
  - Skills with no YAML frontmatter → falls back to dirname + empty description
  - Skills with broken YAML → adapter doesn't propagate the parse failure
  - `ctx.register_skill` itself raises on one skill → others still register
  - `ctx` is `None` → adapter returns without crashing (Hermes API drift insurance)
  - Two skills with the same `name:` in frontmatter → both register (Hermes namespaces them)
  - The live production adapter's `audit()` returns all expected fields
  - `audit()` first-5 skills all have populated name + description
- **Hardening to `tests/test_openclaw_manifest.py`** (6 new tests) — deeper schema validation:
  - `configSchema.type` is `"object"`
  - `configSchema.additionalProperties` is `false` (lockdown)
  - `configSchema.properties` block is present (so JSON Schema validators don't treat undefined as "any")
  - `id` is kebab-case (matches OpenClaw URL-slug requirement)
  - `id` matches `.claude-plugin/plugin.json`'s `name` field (cross-manifest consistency)
  - Every entry in `skills` array is a relative path AND exists on disk

### Added — README polish (user-friendliness pass)

- **New "Get started in 5 minutes (non-developer path)"** section at the top of the README. For marketers, agency owners, content leads who don't live in a terminal: 5-step path through Cowork — no installation, no command line, no Git. From "I clicked a marketplace link" to "Claude is producing a full 12-Part Strategy Flow" in 5 minutes.
- **New "Troubleshooting"** section above Updating. Covers the 8 common install + first-run issues for each native platform: Claude Code + Cowork (slash command unavailable, slash commands not showing, brand profile vanishing, doctor stale), Codex / Cursor / Copilot CLI / Antigravity (slash commands not invoking, Codex regex failure, Cursor `/add-plugin` URL form), Hermes Agent (`enable` step, register_skill error), OpenClaw (manifest-not-found, Claude bundle vs native), plus general (test failures, doctor reporting stub_unconfigured, "where do my files go?"). Each issue has the exact command to fix it.

### Changed

- All 5 platform manifests + `plugin.yaml` + `__init__.py` `PLUGIN_VERSION` + `openclaw.plugin.json` bumped to v3.13.1 in lock-step (every step is now verified by the release-consistency test suite).
- README badges: version 3.13.0 → 3.13.1, tests 70/70 → **114/114**.
- README hero "Just shipped" callout rewritten to highlight test-infra hardening.
- Supported surfaces anchor: `v3130` → `v3131`.
- AGENTS.md test count: 70 → 114.

### Why no breaking changes

Zero runtime files touched. Only tests + docs + manifest version strings. Claude Code + Cowork behavior is byte-identical to v3.13.0. Same multi-manifest coexistence pattern; same skills, same agents, same scripts.

### Test results
- `python tests/run_all.py` — **114/114 passing**
- All 6 JSON manifests + 1 YAML manifest + Python adapter constant agree on version `3.13.1`
- All 9 critical README sections present
- All 8 platform install commands present in README
- All 8 platforms covered in Troubleshooting section
- All README internal anchors resolve
- No description drift across the 5 Claude-family manifests

## [3.13.0] — 2026-06-09

**Multi-harness expansion: native Hermes Agent + OpenClaw + 40+ Agent Skills platforms documented.**

Triggered by user push-back: "how can I make this plugin compatible with Hermes agents or OpenClaw agents, or something like that? Is there any possibility?"

Research first, then build. Verified every claim against primary sources before any code shipped:
- [Hermes Agent plugin spec (Nous Research)](https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin) — confirmed `plugin.yaml` + `__init__.py` at repo root, `ctx.register_skill(name, path)` signature, Hermes Desktop v0.15.2 public preview June 2 2026
- [OpenClaw native manifest spec](https://docs.openclaw.ai/plugins/manifest) — confirmed `id` + `configSchema` required, `skills` field accepts paths relative to plugin root, OpenClaw also auto-detects Claude-compatible bundles
- [Agent Skills open standard client showcase](https://agentskills.io) — confirmed 41 platforms officially adopted (up from ~32 in March 2026)

### Added — Native Hermes Agent plugin

- **`plugin.yaml`** at repo root — Hermes-native manifest. Fields: `name`, `version`, `description`, `author`, `license`, `homepage`, `provides_tools: []`, `provides_hooks: []`, `requires_env: []`. Zero env vars required, zero global hooks (matches our policy on every other platform).
- **`__init__.py`** at repo root — Python adapter exposing `register(ctx)` that Hermes calls at plugin load. The function walks our `skills/` directory, parses YAML frontmatter for `name` + `description`, and registers each of the 158 skills via `ctx.register_skill(name, path_to_SKILL_md)`. **Defensive coding throughout** — stdlib only, no third-party Python dependencies; if Hermes' API surface differs from the documented spec, the adapter logs and degrades gracefully rather than crashing (Hermes guarantees "crashes disable the plugin but don't crash Hermes" — we go further and never raise). Includes an `audit()` introspection function so a Hermes user can sanity-check the adapter before installing: `python __init__.py` prints the discovered skill count + first 5 skill names.
- Install command: `hermes plugins install indranilbanerjee/digital-marketing-pro`.
- Verified: registers all 158 skills against a mock Hermes context in the test suite.

### Added — Native OpenClaw manifest

- **`openclaw.plugin.json`** at repo root — minimal-but-complete OpenClaw native manifest. Required fields: `id` (`digital-marketing-pro`) + `configSchema` (empty object with `additionalProperties: false`). Optional fields populated: `name`, `description`, `version`, `skills: ["./skills"]`. The `skills` field tells OpenClaw to walk our `./skills` directory for SKILL.md files — same directory every other platform uses.
- Install command: `openclaw plugins install git:github.com/indranilbanerjee/digital-marketing-pro`.
- Backward-compatibility note: OpenClaw also auto-detects our existing `.claude-plugin/plugin.json` as a Claude-compatible bundle, so we'd work without `openclaw.plugin.json` — but shipping the native manifest enables ClawHub marketplace eligibility + first-class discoverability.

### Added — "Works on 40+ agent harnesses" README section

Documentation of explicit compatibility with **35 additional platforms** via the Agent Skills open standard (no platform-specific manifest needed; agents discover SKILL.md by walking a directory tree). Tier-1 list: Goose · OpenHands · OpenCode · Junie · Gemini CLI · Roo Code · Cline / Windsurf · Kiro · Amp · Letta · Mux · Factory · Workshop · Tabnine · Mistral Vibe · Emdash · Superconductor · Ona · VT Code · Qodo · Piebald · Autohand Code CLI · pi · Command Code · TRAE · Firebender · bub · fast-agent · nanobot · Vita · Snowflake Cortex Code · Databricks Genie Code · Laravel Boost · Spring AI · Agentman · Google AI Edge Gallery.

### Added — Tests (49 → 70)

- **`tests/test_hermes_adapter.py`** — 13 new tests covering: `plugin.yaml` exists at repo root + has required fields (name / version / semver / description), `provides_tools` block explicit, `provides_hooks: []` enforces zero-hooks policy, `requires_env: []` enforces zero install-time env vars, adapter `__init__.py` imports without error, `register()` function exists + is callable, `audit()` works + discovers 158 skills, `register()` against mock ctx registers all 158 skills, `register()` degrades gracefully when ctx is missing `register_skill` method, plugin version matches between `plugin.yaml` and `__init__.py`.
- **`tests/test_openclaw_manifest.py`** — 8 new tests covering: manifest exists at repo root, `id` field is canonical, `configSchema` required with `additionalProperties: false`, `skills` field points at `./skills` AND that directory has 100+ SKILL.md files, version matches the canonical Claude Code manifest, name + description present + substantive, no hooks declared, no unexpected top-level fields.
- All 70 tests passing: `python tests/run_all.py`.

### Changed

- All 5 platform manifests bumped to v3.13.0 with description: "Open-source AI marketing plugin for agencies & in-house teams — 158 skills, 25 agents, 12-Part Strategy Flow, Cowork team-persistent, EU AI Act Article 50 ready. Runs on Claude Code, Codex, Cursor, Copilot CLI, Antigravity, Hermes Agent, OpenClaw + 40+ Agent Skills platforms."
- README "Supported surfaces" table now has 8 rows (Claude Code · Cowork · Codex · Cursor · Copilot CLI · Antigravity · **Hermes Agent** · **OpenClaw**), up from 6.
- Recent-release callout at top of README updated.
- Version badge: 3.12.1 → 3.13.0.
- New "Platforms" badge: "8 native + 35 Agent Skills".
- Test badge: "49/49" → "70/70".
- AGENTS.md updated with new surfaces + repo root file inventory.

### Why no breaking changes

`plugin.yaml`, `__init__.py`, and `openclaw.plugin.json` sit at the repo root but are isolated to their respective platforms:

| File | Read by | NOT read by |
|---|---|---|
| `plugin.yaml` | Hermes Agent | Claude Code, Cowork, Codex, Cursor, Copilot CLI, Antigravity, OpenClaw |
| `__init__.py` | Hermes Agent (calls `register(ctx)`) | Everyone else (Claude Code doesn't auto-execute Python files) |
| `openclaw.plugin.json` | OpenClaw native install path | Everyone else (Claude Code only reads `.claude-plugin/plugin.json`) |

The three new files add ~10KB to the install bundle. Auto-connecting MCPs unchanged (still empty `.mcp.json`). Global hooks unchanged (still empty `hooks/hooks.json`). Skill descriptions unchanged. Claude Code + Cowork behavior is byte-identical to v3.12.1.

### Verified

- `python tests/run_all.py` — 70/70 passing
- `python scripts/skill-line-check.py` — all 158 skills under 500-line threshold
- `python __init__.py` — Hermes adapter audit shows 158 skills discovered
- Mock Hermes `ctx` test — all 158 skills register successfully
- Bad-ctx test — adapter degrades gracefully without crashing
- All 8 platform manifest files (5 DMP + native Hermes + native OpenClaw) parse as valid JSON / YAML

Skill count: 158 unchanged. Test count: **49 → 70**. Native platforms: **6 → 8**. Documented Agent Skills coverage: **6 → 41+**.

## [3.12.1] — 2026-06-08

**Documentation + discoverability polish — no runtime changes.**

Triggered by user push-back: "have you done audits properly? marketing copies have to be beautiful, proper, and worthy. We get a lot of searches, and our plugin gets visible through searches on Google, GitHub, etc., so harden it more properly so that our plugin can be much more visible."

### Added
- **README "Who this is for"** — audience-segmented use cases for marketing agencies, in-house teams, automation builders (n8n / Zapier / Make / Pipedream), solo consultants, growth / product marketers, and compliance-led marketers. Each row shows the exact slash command to start with and the concrete outcome.
- **README "How does this compare?"** — comparison table vs Anthropic Marketing (official), Composio Marketing, and claude-seo. Columns: skills count · methodology · multi-brand · EU AI Act · real API execution · Cowork persistence · cross-platform install · tests · license · maintainer responsiveness.
- **README "Real workflows you'd actually run"** — 6 concrete copy-paste workflow examples (new-client onboarding, quarterly business review, SEO sprint, marketing automation flow, pre-publish compliance gate, AI creative brief with EU disclosure) showing exact slash command sequences and expected outputs.
- **README "Recent releases" callout** at the top — surfaces the latest version + 1-line description + links to "What's new" anchor and full CHANGELOG. Updated on every release so visitors see freshness at a glance instead of scrolling 180 lines.
- **Two new FAQ entries**: (1) Cowork brand state persistence — explains the `${CLAUDE_PLUGIN_DATA}` Cowork bug and the cowork-setup fix; (2) Model freshness — explains the curator + fallbackModel chain and why users don't need to update DMP when new models ship.
- **Tests badge** on the README (49/49 passing).
- **GitHub repo description** updated: was claiming 150 skills, now 158 with "Cowork team-persistent" + audience callout ("for agencies & in-house teams") for Google search snippet.
- **GitHub topics refreshed** with SEO-targeted additions: `claude-skills`, `marketing-agency`. Dropped less-searched `ai-agents` and broad `compliance` (kept `eu-ai-act` which is more specific).

### Changed
- README "Supported surfaces" version anchor fixed (was pointing at the stale v3.8.0 ID).
- Version badge bumped to v3.12.1.

### Why no runtime version bump
All 158 skills + 25 agents + 84 scripts unchanged. Only docs + manifest metadata + GitHub-side description / topics changed. Patch-level (3.12.0 → 3.12.1) follows SemVer convention for documentation-only updates that ship with the plugin bundle.

## [3.12.0] — 2026-06-08

**Cowork persistence, fallback models, model-freshness, tests — research-grounded hardening pass.**

Triggered by user push-back on a self-audit-only recommendation: actual web research surfaced that `${CLAUDE_PLUGIN_DATA}` is NOT persistent across Cowork sessions (GitHub issue #51398, April 2026). The earlier planned path-migration would NOT have fixed the bug. Solution: route brand state through a Drive MCP, mirroring ContentForge's `cf-cowork-setup` pattern.

### Added

- **`/digital-marketing-pro:cowork-setup` skill + command.** New `skills/cowork-setup/SKILL.md` walks through a 6-step Cowork team-setup: detect sandbox → verify Drive MCP → create canonical Drive folder (`<root>/_brands/`, `_runs/`, `_plans/`) → store per-team config → confirm routing expectations → optionally chain into `brand-setup`. Multi-team isolation via per-team folder names. Falls back to local-only mode on Claude Code.
- **`scripts/plugin-metadata.py`** — environment + asset probes. Detects Cowork vs local Claude Code, reports plugin version + skill / agent / command / script counts + connector availability.
- **`scripts/drive-sync-state.py`** — Cowork+Drive routing ledger. Manages three concerns: per-team Drive root config (`~/.claude-marketing/_cowork-config.json`), per-brand profile sync state (SHA-256 hash compare to detect drift), per-run checkpoint sync pending lists. Agent reads pending lists after each phase and uses Drive MCP for actual transfers.
- **`scripts/skill-line-check.py`** — CI guard for the documented 500-line SKILL.md guideline. Default warn at 400, error at 500. All 158 skills currently under threshold (heaviest: `four-core-documents` at 368).
- **`settings.json.example`** — recommended user settings with `fallbackModel` 3-model resilience chain (Sonnet 4.7 → Sonnet 4.6 → Haiku 4.5), `requiredMinimumVersion`, `skillOverrides`, OTel resource attrs.
- **`tests/` directory** — 49 stdlib-unittest tests covering `resolve_model.py`, `drive-sync-state.py`, `plugin-metadata.py`, `skill-line-check.py`, `connector_resolver.py`. Drive-sync tests run against a tempdir HOME so they never touch the real `~/.claude-marketing/`. Run with `python tests/run_all.py`. **All 49 passing.**

### Changed

- **`.claude-plugin/plugin.json`** — bumped to v3.12.0, added `"requiredMinimumVersion": "2.1.157"` (Claude Code refuses to load DMP on older builds; landed in CC v2.1.163 June 4 2026). Updated description from 157 to 158 skills + "Cowork-ready" badge.
- **`/digital-marketing-pro:doctor`** now reports two additional sections beyond the per-action readiness map: **Model curator status** (registry age + severity bands: `ok` <60d, `warn` 60-119d, `urgent` >=120d, with the exact `refresh_models.py` invocation when stale), and **Cowork+Drive routing status** (flags `urgent` when Cowork is detected but `cowork-setup` hasn't run, so users see the brand-state-vanishes-at-session-end risk before it bites).
- **`disable-model-invocation: true`** added to the 5 true side-effect commands: `execute-action`, `cowork-setup`, `resume`, `check`, `output-folder`. Their descriptions no longer load into the model's per-session description listing, saving context budget. `brand-setup`, `doctor`, `status` deliberately left open — those are natural-language entry points users expect Claude to be able to invoke.
- **Fixed 3 "Read all" eager-load anti-patterns** in `skills/growth-plan/SKILL.md`, `skills/client-validation-document/SKILL.md`, `skills/continuous-improvement-loop/SKILL.md`. Replaced with explicit grep-first + targeted Read with offset+limit guidance that respects the per-skill 5K-token auto-compaction budget.
- **Added `## Context efficiency` sections** to 3 more top-heaviest SKILL.md files (`seo-plan`, `content-engine`, `analytics-insights`), bringing the total to 16 / top-16 heaviest skills with explicit context-efficiency guidance.
- **All 5 platform manifests bumped** to v3.12.0 with consistent "Cowork-persistent" badge and 158-skills count.
- **README + AGENTS.md updated** with v3.12.0 release block, Cowork-specific routing note, and corrected counts (158 skills / 18 commands / 84 scripts).

### Verified against primary sources

- [Claude Code changelog May–Jun 2026](https://code.claude.com/docs/en/changelog) for `fallbackModel` (v2.1.152), `requiredMinimumVersion` (v2.1.163), `disable-model-invocation` semantics, `/reload-skills`, `SessionStart` hook `reloadSkills: true`, per-skill `usage` breakdown
- [Claude Code Skills docs](https://code.claude.com/docs/en/skills) for the 500-line SKILL.md guideline, the 1,536-char description+when_to_use cap, the 5K-token / 25K-budget auto-compaction rules
- [GitHub issue #51398](https://github.com/anthropics/claude-code/issues/51398) confirming `${CLAUDE_PLUGIN_DATA}` is NOT persistent across Cowork sessions
- [GitHub issue #39686](https://github.com/anthropics/claude-code/issues/39686) (silently-injected skills) confirming that users penalize plugins that waste tokens
- [build-to-launch Claude Code plugins review](https://buildtolaunch.substack.com/p/best-claude-code-plugins-tested-review) confirming that reviewers KEEP plugins with multi-skill chains (DMP's pattern) and SKIP plugins with always-on hooks (we ship zero) or "wrong data presented as polished" (our connector-resolver + executor guards against this)

### Test results

- `python tests/run_all.py` — **49 / 49 passing**
- `python scripts/skill-line-check.py` — **158 / 158 skills under 500-line threshold** (heaviest `four-core-documents` at 368)
- `python scripts/action-doctor.py` — clean readiness map + new model + Cowork sections work end-to-end on Windows

Skill count: 157 → **158** (`cowork-setup` added). 192/192 skills still pass Codex `[a-z0-9-]+` regex. Script count: 81 → **84**.

## [3.11.0] — 2026-06-04

**SEO skill expansion + workflow discipline — 3 new skills, dispatcher orchestration, numbered-output convention, quality scorecards, Tips & caveats.**

### Added — 3 new skills + 3 supporting Python scripts

- **`/digital-marketing-pro:keyword-cluster`** — build pillar+spokes content architecture from seed keywords with SERP-overlap clustering (Jaccard ≥ 0.4 default) or lexical fallback. Four-gate quality scorecard (cannibalisation / orphan / coverage / anchor_diversity) plus a fragmentation-warning soft signal. New `scripts/keyword_cluster.py` (stdlib only) — tested end-to-end with synthetic SERP data + edge cases.
- **`/digital-marketing-pro:backlink-gap`** — find domains linking to your competitors but not to you, prioritised by DR + link-overlap count + traffic + topical relevance. Four-gate scorecard (data_freshness / sample_size / competitor_coverage / link_overlap_signal). New `scripts/backlink_gap.py` — handles Ahrefs / Semrush / SE Ranking / Moz export formats via column auto-detection.
- **`/digital-marketing-pro:seo-drift`** — compare two SEO snapshots (GSC classic, GSC AI Performance Report, rank tracker, AEO probe) and surface biggest movers per metric with auto-classification (growth / decline / reshuffle / stable / new / lost). Four-gate scorecard. New `scripts/seo_drift.py` — handles GSC-shape data + arbitrary join keys via `--join-on`.

Skill count: 154 → **157**. 194/194 skills still pass Codex `[a-z0-9-]+` regex.

### Changed — dispatcher pattern + numbered output convention

- **`/digital-marketing-pro:seo-plan` upgraded with Confirm-Then-Dispatch + pillar scoring**:
  - Step D0: auto-detect fresh specialist outputs in `${CLAUDE_PLUGIN_DATA}/{brand}/seo/` (≤30 days)
  - Step D1: never silently re-runs specialists — single Y/N prompt (default N) with cost estimate before fan-out
  - Step D2: scores 4 pillars (Technical / Content / Topical / AI Search) 1-10 from specialist outputs
  - Step D3: the **lowest-scoring pillar drives the lead theme** of the next quarter's roadmap
- **Numbered intermediate-file output convention** applied to: `seo-plan`, `seo-audit`, `aeo-audit`, `gsc-ai-performance`, `content-engine`. Each skill writes `00-input.md`, `01-...md`, …, `PLAN.md` under `${CLAUDE_PLUGIN_DATA}/{brand}/seo/{workflow}/{date}/` — downstream skills consume the numbered files (not the endpoint), enabling resumable workflows and auditable intermediate state.
- **Quality scorecards** added to `seo-plan`, `seo-audit`, `aeo-audit`, `gsc-ai-performance`, `content-engine` — every output passes named gates before being declared `status: ready`.
- **Tips & caveats sections** added to 10 SEO skills total: the 5 above plus `tech-seo-audit`, `keyword-research`, `local-seo`, `content-decay-scan`, `aeo-geo`.
- **README — new "How the SEO skills chain together" section** documents 4 canonical workflows: agency onboarding, quarterly review, content production, backlink campaign.

### Unchanged

- 25 specialist agents
- 14+3 = **17 commands** (the 3 new skills add the same number of commands)
- All v3.10.x platform manifests (icon, composerIcon) untouched aside from version bump
- All v3.10.0 platform-refresh content (GSC AI Performance Report skill, EU Code of Practice doc, C2PA 2.3/2.4, Google Ads API v24, GA4 AI Assistant channel) preserved
- Zero global hooks, zero auto-connecting MCPs (`.mcp.json` remains gitignored)

### How to update

```bash
/plugin update digital-marketing-pro@neels-plugins
/reload-plugins
```

If on Cowork / claude.ai / Desktop: Plugins panel → Update.

## [3.10.1] — 2026-06-04

**Plugin icon + Codex composerIcon — preps DMP for awesome-codex-plugins listing.**

### Added

- `assets/icon.svg` — 512×512 SVG plugin icon (~0.9KB, well under the 50KB limit; clean bar chart with growth trend arrow on indigo background). Renders cleanly at 32×32 thanks to bold geometric shapes.
- `.codex-plugin/plugin.json` `interface.composerIcon: "./assets/icon.svg"` — required field for the OpenAI Codex composer UI and for inclusion in the [awesome-codex-plugins](https://github.com/hashgraph-online/awesome-codex-plugins) curated list (375★, hashgraph-online org).

### Changed

- All 5 platform manifests bumped 3.10.0 → 3.10.1 (icon-only change; no skill content changes; existing installs work unchanged because `composerIcon` is additive).

### Why this release exists

Closes [#4](https://github.com/indranilbanerjee/digital-marketing-pro/issues/4) — community suggestion from @internet-dot to list DMP in the awesome-codex-plugins curated marketplace. The awesome-list's bundle structure requires `interface.composerIcon` + `assets/icon.svg` (or .png), neither of which DMP shipped previously. v3.10.1 adds both so the upstream PR to the awesome-list can reference real published assets.

### How to update

```bash
/plugin update digital-marketing-pro@neels-plugins
/reload-plugins
```

## [3.10.0] — 2026-06-04

**June 2026 platform refresh — GSC AI Performance Report, Google Ads API v24, GA4 AI Assistant channel, C2PA 2.3/2.4, EU Code of Practice.**

Six discrete updates triggered by genuine platform changes that shipped April–early June 2026. Cross-referenced against primary sources before any code change (workflow notes in CHANGELOG appendix).

### Added

- **New skill: `/digital-marketing-pro:gsc-ai-performance`** — query and interpret Google Search Console's new AI Performance Report (rolled out 3 June 2026, UK first). Combined AI Overviews + AI Mode impressions/pages/countries/devices/dates. No click data (use GA4 AI Assistant channel for attribution). New `scripts/gsc-ai-performance.py` reads exported CSV; API path returns a structured "not yet supported by Google" message with a recheck date stamp. Skill count 153 → **154**. Sources: [SEL 3 Jun 2026](https://searchengineland.com/google-search-console-ai-performance-reports-and-controls-to-block-your-content-in-ai-responses-479298).
- **New reference doc: `skills/context-engine/eu-code-of-practice.md`** — voluntary EU Code of Practice on AI-generated content (page dated 22 May 2026). WG1 (providers, machine-readable marking) + WG2 (deployers, disclosure). Final publication targeted May–June 2026, applicable for AI Act Article 50 from 2 August 2026. Pairs with C2PA 2.4 `c2pa.ai-disclosure` assertion as the canonical deployer-side compliance path. Source: [EU Digital Strategy 22 May 2026](https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content).

### Changed

- **`skills/aeo-geo/SKILL.md`** — added Google's official position (no `llms.txt` needed, no special schema needed, standard Search eligibility = AI Features eligibility; Google AI Optimization Guide updated 15 May 2026), plus AI Overview → AI Mode follow-up flow, Personal Intelligence to ~200 countries / 98 languages, AI Information Agents for Pro/Ultra summer 2026 (all from [Google I/O 19 May 2026](https://blog.google/products-and-platforms/products/search/search-io-2026/)). Added Google-Extended user-agent for non-Search Google AI opt-out and noted the new in-Search-Console opt-out toggle.
- **`skills/aeo-audit/SKILL.md`** — added cross-reference to new GSC AI Performance Report + GA4 AI Assistant channel; noted Google's official "no llms.txt / no AI-specific schema" position.
- **`skills/c2pa-metadata/SKILL.md`** — added C2PA Content Credentials 2.3 expanded format support (live video, plain text, OGG Vorbis, large AVI, EXIF) and C2PA Spec 2.4 `c2pa.ai-disclosure` assertion (April 2026). Trust List now via the public C2PA Conformance Program.
- **`skills/paid-advertising/SKILL.md` + `skills/paid-advertising/google-ads.md`** — Google Ads API **v24** (22 April 2026) breaking changes: `videos` + `logo_images` mandatory in `DemandGenVideoResponsiveAdInfo` + `VideoResponsiveAdInfo`; `Campaign.video_brand_safety_suitability` removed (moved to Customer level); `CallAd`/`CallAdInfo` fully removed. v23.1 (25 Feb 2026) added `text_guidelines.term_exclusions` + `messaging_restrictions` for AI-generated PMax/Search assets.
- **`skills/analytics-insights/SKILL.md` + `skills/attribution-report/SKILL.md`** — GA4 added **AI Assistant** default channel group on 13 May 2026; `Medium=ai-assistant` for ChatGPT/Gemini/Claude referral traffic. Pair with GSC AI Performance Report (impressions, no clicks) for full AEO attribution picture.
- **`.mcp.json.connectors-reference`** — Google Ads connector entry now flags v24 minimum.

### Research workflow note

Findings backed by direct WebFetch of primary sources after the deep-research workflow's adversarial-verification phase failed infrastructurally (subagent schema-call failures, not actual refutations). Each finding traced to a primary source on `developers.google.com`, `blog.google`, `support.google.com`, `digital-strategy.ec.europa.eu`, or `c2pa.org` / `spec.c2pa.org`. No third-party claim was accepted without primary verification — the user's "wrong claim wastes user time on a bad patch" constraint shaped the verification bar.

### How to update

```bash
/plugin update digital-marketing-pro@neels-plugins
/reload-plugins
```

If on Cowork / claude.ai / Desktop: Plugins panel → Update.

## [3.9.0] — 2026-05-27

**Distribution & context-efficiency polish — discoverability + leaner skill loads.**

### Changed

- **Plugin descriptions trimmed to ~150 chars across all 5 manifests** (`.claude-plugin/`, `.codex-plugin/`, `.cursor-plugin/`, `.github/plugin/`, `gemini-extension.json`). The install-UI shown across Claude Code's Plugins panel, Codex marketplace browser, Cursor's `/add-plugin` listing, Copilot CLI, and Antigravity now reads as a single clear sentence rather than a multi-paragraph spec dump. Long-form positioning lives in README + `interface.longDescription` (Codex only). Inspired by the Understand-Anything distribution pattern (35k★ Mar–May 2026).
- **README hero rewritten pain-first.** Opens with the real scenario the plugin solves ("Your agency just signed a 50-brand client. The previous agency left no playbook…") then states what the plugin does. The feature/spec sections immediately follow.
- **GitHub repo topics curated to the 20-max with platform-skill topics added**: `cursor-plugin`, `copilot-cli-plugin`, `gemini-cli-extension`, `google-antigravity` joined `claude-code` / `claude-plugin` / `openai-codex` / `agent-skills` for cross-platform discoverability via GitHub's topic browser.
- **Context-efficiency callout added to the 10 heaviest skills** (`four-core-documents`, `engagement-workflow`, `client-validation-document`, `continuous-improvement-loop`, `check`, `campaign-audit`, `growth-plan`, `local-seo`, `status`, `technical-seo`). Tells the agent to grep-before-read referenced files and use `offset` + `limit` on partial reads of brand state under `${CLAUDE_PLUGIN_DATA}/<brand>/` — preserves context window for the actual work.

### Unchanged

- 153 skills (frontmatter intact, names match folders, all pass Codex `[a-z0-9-]+` regex, all descriptions ≤ 1024 chars)
- 25 specialist agents
- 14 commands
- 77 Python scripts (`connector_resolver.py`, `connector_executor.py`, shared model curator, etc.)
- All v3.8.0 native platform manifests untouched aside from version bump + description trim
- Zero global hooks, zero auto-connecting MCPs (`.mcp.json` remains gitignored — never published)

### How to update

```bash
/plugin update digital-marketing-pro@neels-plugins
/reload-plugins
```

If on Cowork / claude.ai / Desktop: Plugins panel → Update.

## [3.8.1] — 2026-05-27 (version bump; published state unchanged)

**Correction (also 2026-05-27)**: the original v3.8.1 release notes claimed this fixed a Cowork install hazard from a populated `.mcp.json`. That was wrong. Re-checking after the release: **`.mcp.json` is gitignored in this repo** (see `.gitignore`) — it has never been committed and is not part of the published install bundle. My local copy had drifted to a populated state, but Cowork / Claude Code installs only see the published files, not my local dev artifacts. **The published v3.8.0 install state was already Cowork-safe** (plugin manifest references `.mcp.json` but the file is absent from the published bundle, which Claude Code/Cowork treats as "no auto-connecting MCPs"). v3.8.1 therefore ships zero functional change for installed users. The version bump remains so the suite-wide marketplace v3.7.1 + SF v1.9.1 (which DID add real new files) ship as a coordinated patch.

### What actually changed

- Version field bumped to 3.8.1 across all 5 manifests for marketplace coordination
- CHANGELOG entry retained (this one) for the historical record + correction

### What did NOT change

- The published install bundle for DMP v3.8.0 → v3.8.1 is byte-identical for everything users see
- `.mcp.json` was never in the published repo (gitignored since the policy was established)
- Skills (153), agents (25), commands (14), scripts (77), hooks, the 37-entry `.mcp.json.connectors-reference` — all unchanged
- v3.8.0's 5-surface native manifests untouched

### Lesson recorded to memory

`.mcp.json` is gitignored across all 3 plugins so credentials never get committed. Future "Cowork install hazard" checks must inspect the published GitHub artifact, not local dev state.

## [3.8.0] — 2026-05-27

**Real native manifests for 5 verified agent surfaces.** Ships verified-real manifests for OpenAI Codex, Google Antigravity 2.0, Cursor 2.5+, and GitHub Copilot CLI — replacing the v3.6/v3.7 era invented manifests that were correctly removed in v3.7.13.

### Per-surface manifest (verified-real schemas)

| Surface | Manifest path | Schema source |
|---|---|---|
| Claude Code (CLI + IDE extensions) + Anthropic Cowork | `.claude-plugin/plugin.json` | Claude Code published format (unchanged from v3.7.13) |
| OpenAI Codex (CLI + IDE + App) | `.codex-plugin/plugin.json` | `developers.openai.com/codex/plugins/build` |
| Cursor 2.5+ | `.cursor-plugin/plugin.json` | `cursor.com/schemas/cursor-plugin/plugin.json` (JSON Schema draft-07) |
| GitHub Copilot CLI | `.github/plugin/plugin.json` | `docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-creating`. Copilot also recognizes `.claude-plugin/plugin.json` as documented fallback path |
| Google Antigravity 2.0 (CLI + IDE) | `gemini-extension.json` (at repo root, not `.antigravity/`) | Per Google's `gemini-cli-extensions/data-agent-kit-starter-pack` reference repo + `agy plugin import gemini` |

### Added

- **`gemini-extension.json`** at repo root — Antigravity manifest with `contextFileName: "AGENTS.md"` so Antigravity auto-loads the shared agent-context file. Same `skills/` directory shared with Claude Code + Codex + Cursor + Copilot via the Agent Skills open standard.
- **`.codex-plugin/plugin.json`** — OpenAI Codex manifest with `interface` block (displayName, shortDescription, longDescription, category, capabilities, defaultPrompt list), points at shared `./skills/`.
- **`.cursor-plugin/plugin.json`** — Cursor 2.5+ manifest per the published Cursor JSON Schema; declares skills + agents + commands + mcpServers pointing at the shared directories. Strict `additionalProperties: false` schema honored (no `$schema` field, repository as string URL).
- **`.github/plugin/plugin.json`** — GitHub Copilot CLI manifest at the primary path. Plus the existing `.claude-plugin/plugin.json` works as 4th-priority Copilot fallback per Copilot's documented manifest search order.
- **`AGENTS.md`** at repo root — auto-loaded by Codex + Antigravity + Copilot CLI + Cursor agent context chains. Mirrors what `CLAUDE.md` does for Claude Code: explains how to discover skills by description, lists canonical entry points, documents the file layout.

### Verified

- **190/190 skills across the suite pass the Codex `[a-z0-9-]` regex** (no underscores, no capitals; folder names match SKILL.md `name:` frontmatter; descriptions ≤ 1024 chars). 153 DMP + 21 CF + 16 SF.
- **All 4 new JSON manifests parse cleanly** under `python3 -c "import json; json.load(open(F))"`.
- **Test harnesses still pass**: `_shared/dmp_action_test_harness.py` (27/27) + `_shared/dmp_executor_test_harness.py` (17/17) = 44/44 combined, no regressions.

### Not changed

- Zero changes to `skills/`, `commands/`, `agents/`, `scripts/`, `hooks/hooks.json`, `.mcp.json`, `.mcp.json.connectors-reference`. Plugin behavior in Claude Code + Cowork **byte-identical** to v3.7.13.
- 153 skills + 25 agents + 14 commands + 77 Python scripts + 14 HTTP MCP connectors + 167 reference files all unchanged.
- Shared model curator (`scripts/model_registry.json` + `resolve_model.py` + `refresh_models.py`) unchanged.
- Historical v3.6.0 / v3.7.0 (invented manifests) and v3.7.13 (honest cleanup) entries are intact below.

### Caveats per platform

- **Codex subagents** are TOML at `~/.codex/agents/*.toml`, not markdown — our `agents/*.md` are Claude-only as static files. On Codex use the `/agent` ad-hoc spawn or convert your most-used agents to TOML.
- **Copilot CLI custom slash commands not yet supported** (open issues `github/copilot-cli#618` and `#1113`) — our `commands/*.md` files won't be discovered. Users invoke skills by natural-language intent on Copilot.
- **Copilot CLI subagents** want `agents/*.agent.md` extension; our `agents/*.md` files are not auto-discovered.
- **Antigravity slash commands** fold into skills during `agy plugin import gemini` — users invoke by intent.
- **MCP env-var syntax differs**: Claude uses `${user_config.VAR}`, Codex/Antigravity use `$VAR`, Copilot requires per-server `type` field. Our `.mcp.json` ships empty so none of these bite.

## [3.7.13] — 2026-05-26

**Honest positioning: removed invented multi-platform manifests. Zero functional change for Claude Code + Cowork users.**

A May 2026 deep research pass (saved at `memory/antigravity-plugin-spec-may-2026.md` and `memory/codex-plugin-spec-may-2026.md`) confirmed that the v3.6 / v3.7 era `.codex-plugin/`, `.cursor-plugin/`, `.antigravity/` manifests and the GitHub Copilot CLI auto-discovery claim were all invented or unverified. They did not match the platforms' actual install specs:

- **Antigravity** uses `gemini-extension.json` at repo root — not `.antigravity/plugin.json`. Google's reference repo (`gemini-cli-extensions/data-agent-kit-starter-pack`) and the `agy plugin import gemini` migrator both confirm this.
- **OpenAI Codex** uses the `.codex-plugin/plugin.json` path (that part was right), but the schema we hand-rolled was invented. The real schema is published at `developers.openai.com/codex/plugins/build` and proven by `schuettc/codex-reviewer`.
- **Cursor** plugin format we shipped was not a real Cursor manifest path.
- **GitHub Copilot CLI** auto-discovery of `.claude-plugin/plugin.json` was unverified.

Honest position from v3.7.13 onwards: **Claude Code (CLI + IDE extensions) + Anthropic Cowork.** Real OpenAI Codex / Cursor / GitHub Copilot CLI / Google Antigravity 2.0 support is on the roadmap with research complete — build deferred.

### Removed

- `.antigravity/plugin.json` — wrong path entirely. Real Antigravity manifest is `gemini-extension.json` at repo root.
- `.codex-plugin/plugin.json` — path was right, schema was invented and would fail real Codex install.
- `.cursor-plugin/plugin.json` — invented format.
- `docs/cross-platform-install.md` — documented install commands that did not work.

### Changed

- `.claude-plugin/plugin.json` — description rewritten to advertise Claude Code + Cowork only. Misleading keywords dropped (`openai-codex`, `cursor-plugin`, `github-copilot`, `antigravity`). Version bumped to 3.7.13.
- `README.md` — hero, badge row, quick start, "Installs on 5 coding-agent surfaces" matrix, "What's new" entries, FAQ entries, and "Release notes" entries all updated to reflect supported surfaces (Claude Code + Cowork). The "5 platforms" badge is gone.
- `.github/PULL_REQUEST_TEMPLATE.md` — platform checkbox list reduced to Claude Code + Cowork.
- `SECURITY.md` — scope and reporting fields updated to Claude Code + Cowork only.

### Not changed

- Zero changes to `skills/`, `commands/`, `agents/`, `scripts/`, `hooks/hooks.json`, `.mcp.json`, `.mcp.json.connectors-reference`. Plugin behavior in Claude Code + Cowork is byte-identical to v3.7.12.
- 153 skills, 25 agents, 14 commands, 77 Python scripts, 14 HTTP MCP connectors, 167 reference files, shared model curator — all unchanged.
- Historical CHANGELOG entries for v3.6.0, v3.7.0, v3.7.1 are intact below — they describe what was shipped at the time. v3.7.13 is the correction.

### Verified

- `.claude-plugin/plugin.json` parses cleanly (`python3 -c "import json; json.load(open('.claude-plugin/plugin.json'))"`).
- Both DMP test harnesses still pass: `_shared/dmp_action_test_harness.py` (27/27) + `_shared/dmp_executor_test_harness.py` (17/17). 44/44 combined, no regressions from v3.7.12.
- Shreea's beta-test flows (brand-setup, doctor, execute-action, validate-profile, campaign-audit, launch-campaign) untouched.

## [3.7.12] — 2026-05-26

**Code hygiene pass: eliminates the connector-registry duplicate + removes dead imports.** Zero behavior change — purely structural cleanup that prevents future drift between `connector-status.py` and the v3.7.10 `_connector_registry.py`.

### Changed

- **`scripts/connector-status.py`** refactored from 973 → 342 lines. The 600-line inline `CONNECTOR_REGISTRY` is gone; the file now imports `CONNECTOR_REGISTRY`, `_load_mcp_json`, `is_connector_configured`, and `redact_secrets` from `_connector_registry.py`. The local `_is_configured(name, info, servers)` adapter preserves the old (bool-returning) call-site signature on top of the new tuple-returning `is_connector_configured`. Adding a connector now means editing ONE file (`_connector_registry.py`) instead of two — the previous duplication was a 100% drift risk.
- **`scripts/connector_resolver.py`** — removed 3 unused imports (`os`, `CONNECTOR_REGISTRY`, `PLUGIN_ROOT`) flagged by static analysis.
- **`scripts/seo-executor.py`** — removed pre-existing unused `hashlib` import.
- **`_shared/backfill_releases.py`** — removed unused `json` import.

### Verified

- Both DMP test harnesses still pass: `_shared/dmp_action_test_harness.py` (27/27 resolver scenarios) + `_shared/dmp_executor_test_harness.py` (17/17 mock-HTTP-server tests). Combined: 44/44, no regressions from v3.7.11.
- All 4 `connector-status.py` actions (`status`, `list-available`, `check`, `setup-guide`) + `--probe-only` path verified working end-to-end after refactor.
- `/digital-marketing-pro:doctor` returns the same readiness map as v3.7.11 (1 real / 8 manifest-ready / 5 stub-unconfigured = 14 total).

## [3.7.11] — 2026-05-26

**Closes the resolver loop: actions can now actually fire HTTP requests from Python.** v3.7.10 introduced a resolver that returned a manifest of "what would be sent" when a connector was configured. v3.7.11 introduces `scripts/connector_executor.py` (stdlib `urllib.request`, no third-party deps) that takes that manifest and actually executes the request against the real API, with credential substitution, write-op gates, audit logging, and per-endpoint success-code handling.

### What can execute end-to-end from Python (8 connectors, verified docs)

Verified against current vendor docs (May 2026 research pass — see CHANGELOG source citations below):

| Connector | Env var | Auth pattern | Endpoint examples |
|-----------|---------|--------------|---------------------|
| Slack | `SLACK_BOT_TOKEN` | `Authorization: Bearer xoxb-...` | `POST /api/chat.postMessage` (HTTP 200 + body.ok=true required) |
| HubSpot | `HUBSPOT_PRIVATE_APP_TOKEN` | `Authorization: Bearer pat-...` | `GET /automation/v4/flows`, `POST /marketing/v3/campaigns` (201) |
| Klaviyo | `KLAVIYO_PRIVATE_KEY` | `Authorization: Klaviyo-API-Key ...` + revision `2026-04-15` | `GET /api/flows`, `PATCH /api/flows/{id}` (vnd.api+json) |
| SendGrid | `SENDGRID_API_KEY` | `Authorization: Bearer SG.xxx` | `POST /v3/mail/send` (202 + empty body) |
| Brevo | `BREVO_API_KEY` | `api-key:` header (lowercase, NOT Authorization) | `POST /v3/smtp/email` (201) |
| Customer.io | `CUSTOMERIO_APP_API_KEY` | `Authorization: Bearer <App-API-key>` (App key, NOT Site/Track) | `POST /v1/send/email` |
| Mailchimp | `MAILCHIMP_API_KEY` | `Authorization: Basic <base64(anystring:key)>`, dc from key suffix | `GET /3.0/automations` |
| Ahrefs | `AHREFS_API_KEY` | `Authorization: Bearer ...` | `GET /v3/site-explorer/metrics` (not `/overview`) |

### What requires the MCP path (25 OAuth-only connectors)

Cannot execute from Python because OAuth flows require a browser redirect. The resolver still returns `manifest_ready` with the exact request shape, and the executor returns `execute_blocked_reason: "use MCP path"` with an `alternative` field pointing to the MCP route:

Google Ads, Meta Marketing, LinkedIn Marketing, LinkedIn Publishing, TikTok Ads, Twitter/X (OAuth 1.0a HMAC), Gmail, Google Calendar, Google Analytics, Google Search Console, Meta Graph (organic), Salesforce, Pipedrive, Zoho CRM, Buffer, Hootsuite, Cision, Muckrack, Amplitude, Similarweb, SEMrush, Moz, Intercom, Canva, Figma.

### Safety gates (all 6 tested)

1. **No `--execute`** -> dry-run, returns resolver manifest, no HTTP fired
2. **Write op without `--confirm`** -> blocked with reason naming the action
3. **OAuth-only connector** -> blocked with `alternative` MCP path hint
4. **Missing env var credential** -> blocked with `setup_hint_credential` naming the var
5. **Unconfigured connector** -> blocked at resolver level (`stub_unconfigured`)
6. **Unresolved `{VAR}` placeholder** -> request NEVER sent (prevents leaking placeholder text to APIs)

Every executed call is logged to `~/.claude-marketing/{brand}/executions/exec-{connector}-{action}-{ts}.json` with HTTP status, elapsed_ms, success/failure, and any error reason.

### Manifest corrections from research pass

The May 2026 doc verification surfaced 6 errors in the v3.7.10 manifests, now fixed:

1. **Klaviyo `revision` header** — bumped from `2024-10-15` (18 months stale) to `2026-04-15`
2. **Klaviyo PATCH `Content-Type`** — was `application/json` (rejected by API), now `application/vnd.api+json` per JSON:API spec
3. **Ahrefs site-explorer URL** — was `/v3/site-explorer/overview` (doesn't exist), now `/v3/site-explorer/metrics`
4. **Brevo auth note** — clarified custom lowercase `api-key:` header, NOT `Authorization: Bearer`
5. **SendGrid success code** — documented that 202 is success (not 200) per async-queue behavior
6. **Slack success check** — documented that HTTP 200 with `body.ok=false` is logical failure (chat.postMessage returns 200 even on `channel_not_found` errors); executor now does the body.ok check

### Added

- **`scripts/connector_executor.py`** — stdlib HTTP executor. Public API: `execute_manifest(http_request, env, data, timeout, connector)` for direct manifest execution; `execute_action(action_id, brand, execute, confirm, data, timeout, log_to_tracker, env, **kwargs)` for resolve+execute orchestration. `EXECUTE_PROFILES` table holds per-connector env var + auth handler + success codes + post-checks. CLI mode supports dry-run / execute / confirm / data flags.
- **`commands/execute-action.md`** — `/digital-marketing-pro:execute-action` slash command. Wraps `connector_executor.py` with full safety-gate documentation, executable-vs-OAuth-only matrix, and 6 worked examples covering dry-run, read-op execute, write-op execute, blocked-without-confirm, OAuth-only, missing-credential.
- **`_shared/dmp_executor_test_harness.py`** — 17 tests against a stdlib `http.server` mock HTTP server in a daemon thread. Coverage:
  - 8 connector-specific tests (Slack incl. body.ok check + logical-failure variant, HubSpot read + write, Klaviyo list + PATCH with vnd.api+json, SendGrid 202, Brevo lowercase header, Mailchimp Basic auth)
  - 6 safety-gate tests (OAuth-only blocks, write requires confirm, missing credential, unconfigured connector, 404 = failure, network error = clean status, unresolved placeholder NEVER fires)
  - 1 utility test (data-substitution from `{plan.field}` placeholders)

### Changed

- Plugin command count: 13 -> 14 (`/digital-marketing-pro:execute-action` added)
- Script count: 76 -> 77 (`connector_executor.py` added)
- Manifest builders in `connector_resolver.py` updated with the 6 corrections above

### Anthropic submission readiness

- 17/17 mock-server tests pass (covers actual HTTP send-and-receive against a real local server, not just request shape inspection)
- 27/27 resolver tests still pass (no regressions from v3.7.10)
- Every executable endpoint cited to its current vendor documentation
- OAuth-only connectors honestly flagged with explicit MCP fallback path
- All safety gates tested

### Source citations for executable endpoints

- Slack `chat.postMessage` — https://docs.slack.dev/reference/methods/chat.postMessage
- HubSpot `/marketing/v3/campaigns` — https://developers.hubspot.com/docs/reference/api/marketing/campaigns
- HubSpot `/automation/v4/flows` — https://developers.hubspot.com/docs/guides/api/automation/create-manage-workflows (BETA flag)
- Klaviyo `/api/flows` (list) — https://developers.klaviyo.com/en/reference/get_flows
- Klaviyo `/api/flows/{id}` (PATCH) — https://developers.klaviyo.com/en/reference/update_flow
- SendGrid `/v3/mail/send` — https://www.twilio.com/docs/sendgrid/api-reference/mail-send/mail-send
- Brevo `/v3/smtp/email` — https://developers.brevo.com/reference/sendtransacemail
- Customer.io `/v1/send/email` — https://docs.customer.io/api/app/#operation/sendEmail
- Mailchimp `/3.0/automations` — https://mailchimp.com/developer/marketing/api/automation/list-automations/ (Classic Automations — flag for new tenants)
- Ahrefs `/v3/site-explorer/metrics` — https://docs.ahrefs.com/api/reference/site-explorer/get-metrics

## [3.7.10] — 2026-05-26

**Replaces 14 unconfigured-only action stubs with a connector-aware three-mode resolver.** The v3.7.5–v3.7.7 stubs always returned `status: stub_implementation` no matter what connectors the user had configured. They were honest about being scaffolds but they could not graduate to real calls. v3.7.10 introduces a resolver layer that probes the live connector state and chooses one of three modes per action, every call:

| mode | when it applies |
|------|----------------|
| `real` | The action runs end-to-end with no external API. Currently only `arm-watchdog` (writes a watchdog config to `~/.claude-marketing/{brand}/watchdogs/`). |
| `manifest_ready` | A matching connector is configured. The response includes the exact HTTP request manifest (method, URL, headers, body template, auth pattern) for the orchestrator (Claude via MCP) to execute. For write/launch ops the response sets `approval_required: true`. |
| `stub_unconfigured` | No matching connector is configured. The response includes the manual fallback PLUS copy-paste setup hints with `.mcp.json` snippets, env vars, and a Cowork-compatibility warning. |

### Added

- **`scripts/_connector_registry.py`** — single source of truth for the connector catalog (33 connectors, 11 categories). Imported by both `connector-status.py` and the new resolver. Includes `is_connector_configured(name)` (probes `.mcp.json` membership + env-var presence), `redact_secrets()` for credential-safe response filtering.
- **`scripts/connector_resolver.py`** — the resolver layer. `ACTION_SPECS` table maps each of the 14 actions (`inventory`, `automations`, `cadence`, `diagnostic`, `arm-watchdog`, `audit-workflows`, `create-campaign`, `enable-automation`, `schedule-posts`, `notify-influencers`, `pr-send`, `internal-kickoff`, `launch-ads`, `audit-current`) to its candidate connectors, manifest builder (concrete HTTP request shapes for Google Ads / Meta Marketing / LinkedIn / TikTok / HubSpot / Salesforce / Klaviyo / Mailchimp / Brevo / Customer.io / SendGrid / Gmail / Cision / Muckrack / Slack / Google Calendar / Ahrefs / Similarweb / SEMrush / Google Search Console), and operation type (`read` / `write` / `local`). `arm-watchdog` is fully implemented as a local executor that writes a real watchdog config; the remaining 13 return either `manifest_ready` (one of the candidates is configured) or `stub_unconfigured` (none are).
- **`scripts/action-doctor.py`** — per-action readiness diagnostic. Resolves every action against the live `.mcp.json` + env-var state and reports the mode (`real` / `manifest_ready` / `stub_unconfigured`) for each one, with a one-step unlock guide for the blocked ones. Defensive UTF-8 stdout reconfigure for Windows cp1252 consoles.
- **`commands/doctor.md`** — `/digital-marketing-pro:doctor` slash command. Wraps `action-doctor.py`. The canonical pre-flight check before running `campaign-audit` or `launch-campaign`. Output options: full readiness table, `--summary` one-liner, `--action <id>` drill-in, `--json`.
- **`_shared/dmp_action_test_harness.py`** — comprehensive test harness. For every non-local action, exercises (1) unconfigured mode — empty `.mcp.json` → expects `stub_unconfigured` with `setup_hint.setup_options` populated; (2) configured mode — temporarily writes a single matching connector entry to `.mcp.json` → expects `manifest_ready` with a complete `http_request` shape (method + url + headers/body/params + auth_pattern). For `arm-watchdog`, runs an end-to-end execution test and verifies the watchdog file is written to disk and matches the response. Backs up + restores the user's real `.mcp.json` around every scenario. 27 total scenarios; all pass.

### Changed

- **`scripts/performance-monitor.py`** — `inventory`, `automations`, `cadence`, `diagnostic`, `arm-watchdog` actions now delegate to `connector_resolver.resolve_action()`. The inline `_stub_action()` helper from v3.7.6 is removed.
- **`scripts/crm-sync.py`** — `audit-workflows`, `create-campaign` actions now delegate to the resolver. Inline `_stub_action()` removed.
- **`scripts/execution-tracker.py`** — `enable-automation`, `schedule-posts`, `notify-influencers`, `pr-send`, `internal-kickoff`, `launch-ads` actions now delegate to the resolver. Inline `_stub_action()` removed.
- **`scripts/seo-executor.py`** — `audit-current` action now delegates to the resolver. Inline stub block removed.

### Cross-platform verification

- All new scripts run clean on Windows cp1252 console (UTF-8 stdout reconfigure where needed; otherwise pure ASCII output).
- No Windows-only paths (`pathlib.Path` everywhere, `Path.home()` for user dirs, no hardcoded drive letters).
- No `os.system()` / `shell=True` calls (subprocess uses argv lists).
- HTTP connectors work in Claude Code CLI + IDE + Anthropic Cowork. npx connectors (Salesforce, Google Ads, Meta Marketing, etc.) work in Claude Code only; the resolver flags this in `setup_hint.platforms_warning` so Cowork users know to use the Pipedream/Composio/Zapier aggregator alternatives.

### Anthropic submission readiness

- 27/27 test scenarios pass.
- Every action has a documented purpose, manual fallback, fields-returned schema, and live status (real / manifest_ready / stub_unconfigured) — no silent stubs anywhere.
- Every stub response is self-documenting about how to upgrade itself.

## [3.7.9] — 2026-05-25

**Corrects an inaccuracy in the v3.7.8 README callout.** v3.7.8 said the `/plugin isn't available in this environment` error applies to **claude.ai web chat**. User correction: it also applies to the **Claude Desktop app**. The actual rule: `/plugin` slash commands are supported only in **Claude Code** (CLI / IDE at claude.com/code) and **Anthropic Cowork** — not in the standard Claude chat app, whether browser OR installed desktop.

### Changed

- **`README.md`** — re-worded the "/plugin isn't available" callout in the Updating section + the Quick start install note (line 74) to name both environments accurately.

## [3.7.8] — 2026-05-25

**README fix for the "claude.ai web" gotcha.** User-team report from a CF v3.12.2-cycle WhatsApp screenshot: `/plugin update ...` produces `"/plugin isn't available in this environment"` when used in claude.ai web chat. The plugin is installed (skills show up correctly), but the `/plugin` slash command is not supported in claude.ai web — only in Claude Code CLI / Desktop / Cowork. Same gotcha applies to DMP and to the marketplace.

### Changed

- **`README.md`** — added a prominent "If you see /plugin isn't available in this environment" callout at the top of the Updating section. Recovery paths: (1) **Plugins** UI button at the bottom of the web chat → **Manage plugins** → Remove + Add for a re-pull, OR (2) switch to Claude Code CLI / Desktop / Cowork for the management commands.

## [3.7.7] — 2026-05-25

**Direct fix for "dm pro also taking too long to process" (user-team feedback from the v3.12.2-cycle WhatsApp transcript) + an audit pass that caught 4 additional broken refs missed by v3.7.6.**

### Audit pass — 4 newly-found gaps fixed

Full audit across all 153 SKILL.md + 25 agent + 10 command files (broader than v3.7.6's "just the 3 new skills" audit):

- 2 more missing actions: `execution-tracker.py --action launch-ads`, `seo-executor.py --action audit-current` (called from the v3.7.5 skills, missed in v3.7.6). Both added as stub-implementation handlers.
- 2 broken slash refs in v3.7.5 SKILL.md docs: `/digital-marketing-pro:performance-monitor` (no such skill — corrected to `/digital-marketing-pro:performance-check`) and `/digital-marketing-pro:setup` (no such command — corrected to `/digital-marketing-pro:add-integration`).
- 2 broken internal file refs: `docs/custom-mcp-guide.md` (corrected to `skills/context-engine/custom-mcp-guide.md`) and `skills/context-engine/industry-benchmarks.md` (replaced with the existing `industry-profiles.md` + `channel-families.md` fallback chain).
- Re-audit after fixes: **0 broken slash refs, 0 missing script actions, 0 broken internal file refs**.

### Added — resumable workflows (Shreea's "too long" fix)

- **`scripts/checkpoint-manager.py`** — per-step checkpoint storage for every long DMP workflow. Supports `engagement` (the 12-Part Strategy Flow), `campaign-plan`, `content-engine`, `seo-audit`, `competitor-analysis`, `campaign-audit`, `launch-campaign`, plus a `custom` slot for any other long flow. Subcommands: `init`, `save`, `status`, `load`, `list`, `resume`, `finalize`, `discard`. Atomic writes; stdlib only; works in headless / cron contexts. Ported from the ContentForge v3.12.3 pattern, adapted for DMP's multi-workflow surface (CF was content-only; DMP has 8 distinct long workflows).
- **`commands/resume.md`** — `/digital-marketing-pro:resume [workflow] [run-id]`. Picks the run to resume (auto-pick latest in_progress, or filter by workflow, or explicit run-id), reloads every saved part as context, hands control to the agent/sub-flow that owns the next un-checkpointed part. Warns if `last_updated` > 7 days (market data drifts). Lists all in-progress runs when there's ambiguity.

### Added — dual-copy save (visible output folder)

- **`scripts/output-publisher.py`** — dual-copy publisher. Every artifact a workflow produces now lands in TWO locations: internal tracking copy under `~/.claude-marketing/{brand}/output/{workflow}/...` (system-of-record) AND user-visible copy under `~/Documents/DigitalMarketingPro/{brand}/{workflow}/{YYYY-MM}/{filename}` (visible in Explorer / Finder by default). Override the visible root with `DIGITAL_MARKETING_PRO_PUBLISH_DIR` env var or `--publish-dir`. Subcommands: `publish` (single file), `publish-run` (bulk-publish every artifact in a checkpoint-manager run), `where` (print both paths without copying), `open` (print + open in OS file manager via Windows `start` / macOS `open` / Linux `xdg-open`).
- **`commands/output-folder.md`** — `/digital-marketing-pro:output-folder [brand] [workflow]`. Direct answer to "where did my 50 engagement files save?" Prints the absolute visible path and opens it in the OS file manager. Configuration section documents the env-var override for Dropbox / shared-drive setups.

### Changed

- **`commands/engagement.md`** — added a "Checkpointing (v3.7.7+)" section explaining the per-part `checkpoint-manager.py save` cadence + the `output-publisher.py publish-run` finalize step. The `start` subcommand description now mentions that it opens a checkpoint run automatically.
- **README** — new "Resumable workflows + visible output folder (v3.7.7+)" section above the Model Curator section; new entries in the slash command list for `/resume` + `/output-folder`.
- **plugin.json count fields** — none change (the 3 v3.7.5 skills are still counted; the 2 new commands bring the total from 10 → 12).

### Honesty disclosure

The 12 stub-implementation action handlers added in v3.7.6 are unchanged in v3.7.7 — they still return structured `stub_implementation` contracts, not live API calls. The checkpoint-manager and output-publisher are **fully implemented** (no stubs there).

The /engagement workflow itself is unchanged in runtime — Opus 4.7 still takes ~60 minutes for the full 12-Part Strategy Flow. What's new is that a single interruption no longer means losing 30+ minutes of work. That's the direct addressing of "dm pro also taking too long to process" — the workflow can't be made faster (LLM latency is the dominant cost), but it can be made resilient to interruption.

### Verification

- Full e2e simulation `_shared/dmp_engagement_simulation.py` — 5 scenarios: (A) clean 12-part engagement → dual-copy publish → finalize, (B) interrupt at Part 5 → /resume → continue to Part 12, (C) 3 parallel workflows (engagement + campaign-plan + seo-audit) preserved state independently, (D) Part 7 quality-gate fail leaves run in_progress, (E) all 8 workflows accept the checkpoint contract. **5/5 PASS in 5.8 seconds.**
- 12 visible deliverables landed in `~/Documents/DigitalMarketingPro/EngagementSim/engagement/2026-05/` (the user-visible folder) — verified by directory listing.
- All **73 DMP scripts** (was 71, added 2) pass `--help` smoke test; **0** scripts take > 2 seconds on import.
- Sweep across 188 SKILL.md / 25 agents / 167 references files clean.

## [3.7.6] — 2026-05-25

**Wires the v3.7.5 skill surface to actual script implementations.** The 3 new skills shipped in v3.7.5 (`/validate-profile`, `/campaign-audit`, `/launch-campaign`) referenced ~15 script actions that **did not exist** in the underlying Python scripts. The skills were documented but uncallable end-to-end — the orchestrator would dispatch an action and the script would error with `argparse: invalid choice`. Caught by an audit pass mirroring the ContentForge v3.12.3 → v3.12.4 production-simulation fix.

### Added — script action surface that the v3.7.5 skills actually need

- **`scripts/performance-monitor.py`** — 5 new actions: `inventory`, `automations`, `cadence`, `diagnostic`, `arm-watchdog`. Plus new flags `--channel`, `--campaign-id`, `--kpis`, `--read-only`.
- **`scripts/crm-sync.py`** — 2 new actions: `audit-workflows`, `create-campaign`. Plus new flag `--plan` for the approved-plan JSON path.
- **`scripts/execution-tracker.py`** — 5 new actions: `enable-automation`, `schedule-posts`, `notify-influencers`, `pr-send`, `internal-kickoff`. Plus new flags `--plan`, `--automation-id`.
- **`scripts/connector-status.py`** — 2 new flags: `--probe-only` (credential-safe reachability probe used by `/validate-profile`) and `--no-secrets` (walks the response object and redacts any token/secret/password/api_key field before printing). New `_redact_secrets()` and `_probe_only()` helpers.

### Honesty disclosure

Each of the 12 new action handlers in `performance-monitor.py` / `crm-sync.py` / `execution-tracker.py` is a **stub implementation** that returns a structured contract with a `status: "stub_implementation"` field, a `purpose` description, the `data_source` connector that would back it, a `manual_fallback` procedure, and the `fields_returned_when_implemented` schema. The orchestrator gets a clean JSON response it can surface to the user as "this part of the workflow is the design, here is what it would do, here is the manual fallback for now." Live implementation is staged across subsequent releases. The action contract is stable; what's marked `stub_implementation` today will become a live API call as the underlying connectors are integrated.

The `connector-status.py` flags (`--probe-only`, `--no-secrets`) are **fully implemented** — they're a thin wrapper over the existing `check_connector()` function plus a recursive secret-redactor for the response.

### Quality

- All 14 new action invocations return valid structured JSON (`14/14 PASS`).
- All **71 DMP scripts** still pass `--help` smoke test after the additions (no regressions).
- End-to-end `/validate-profile` simulation against a deliberately-broken brand profile correctly produces 1 BLOCKER + 1 WARN + 6 PASSED checks, with credential-safe `--probe-only --no-secrets` connector probes verifying no credential values leak into output.
- Only one DMP script calls LLM APIs at runtime (`ai-visibility-checker.py`) and it correctly uses the model curator from v3.7.4 — no hidden hardcoded model ids elsewhere.

## [3.7.5] — 2026-05-25

**Three new skills shipped to close gaps from the v3.7.4 audit.** No breaking changes.

### Added — 3 new skills (`skills/`)

- **`validate-profile/SKILL.md`** — `/digital-marketing-pro:validate-profile`. The canonical "is this brand ready to ship work?" gate. Validates the brand profile is complete enough for production AND that every connector / MCP / credential it references is actually reachable — without ever printing credential values. Ten validation dimensions: required identity, voice profile, audience profile, guardrails (upgraded to BLOCKER for regulated industries), compliance-jurisdiction cross-check against `compliance-rules.md`, connector reachability (`--no-secrets` probes), MCP server health, credential storage, output-path writeability, model-curator currency. Emits both a human report and a machine-readable JSON summary. **Pre-requisite for `/engagement`, `/campaign-plan`, `/launch-campaign`.**
- **`campaign-audit/SKILL.md`** — `/digital-marketing-pro:campaign-audit`. Cross-channel current-state audit covering paid search, paid social, retail media, email, organic social, content/SEO, AEO/GEO across the 6 AI surfaces (Google AI Mode + Perplexity + ChatGPT search + Claude search + Copilot + Gemini App), CRM/automation, web analytics, influencer/PR, compliance posture. Scores every item across four tiers (🟢 healthy / 🟡 quick win / 🟠 strategic gap / 🔴 red flag) with a configurable spend threshold for waste detection. Produces a single audit document with executive summary, per-channel inventory, cross-channel observations, compliance posture, AEO/GEO snapshot, quick-wins backlog, strategic gaps, red flags, and channels-not-running-that-should-be. Dual-copy save (internal tracking + user-visible `~/Documents/DigitalMarketingPro/{brand}/audits/`) mirroring the ContentForge v3.12.3 pattern.
- **`launch-campaign/SKILL.md`** — `/digital-marketing-pro:launch-campaign`. Multi-channel launch orchestrator — broader than `launch-ad-campaign` (paid-ads only). Takes an approved campaign plan and walks the full 14-step activation in dependency order: CRM Campaign object → landing-page verify → email automation enable → paid search → paid social → retail media → organic social → influencer notification → PR send → internal kickoff → UTM tracking → attribution confirmation → day-1 watchdog → launch record. Refuses to start unless every prerequisite passes (`validate-profile` clean, plan status `approved`, assets reachable, conversion tracking live, EU AI Act Article 50 disclosure verified for EU launches). Dry-run preview mandatory before execution; per-step checkpoint after each action; no auto-retry on failure (day-1 retries create duplicate campaigns / doubled emails); dual-copy launch record.

### Changed — context-engine guides reverted to real skill refs

- **`skills/context-engine/agency-operations-guide.md`** step 8 now points at `/digital-marketing-pro:campaign-audit` directly (v3.7.4 used a workaround chain of `competitor-analysis` + `performance-check` because the skill didn't exist yet).
- **`skills/context-engine/agency-operations-guide.md`** credential-rotation guidance now points at `/digital-marketing-pro:validate-profile --connectors ...` instead of the v3.7.4 workaround of `check` + `status`.
- **`skills/context-engine/crm-integration-guide.md`** Campaign-object creation now references `/digital-marketing-pro:launch-campaign` (with `launch-ad-campaign` cited as the paid-ads-only subset).

### Changed — counts

- `150 skills` → `153 skills` across `README.md` hero + Architecture section + `docs/architecture.md` + `docs/getting-started.md` + `docs/claude-interfaces.md` + `.claude-plugin/plugin.json`. Reality matches: `ls skills/ | wc -l` returns 153.

### Quality

- Per-file content sweep (`_shared/sweep_skill_quality.py`) — **188 SKILL.md + 43 agents + 69 reference docs** clean. Zero issues across frontmatter, slash refs, deprecated model ids, dead MCP URLs, hardcoded paths.

## [3.7.4] — 2026-05-25

**Model curator + correctness sweep.** Adds the model-selection infrastructure the suite was missing, plus a 13-finding correctness pass across scripts, skills, agents, and reference docs.

### Added

- **Model curator (`scripts/model_registry.json` + `scripts/resolve_model.py` + `scripts/refresh_models.py`)** — single source of truth for every model id the plugin hands to a provider SDK. Aliases like `latest-balanced-anthropic`, `latest-fast-anthropic`, `latest-text-openai`, `latest-vision-google`, `latest-image-google`, `latest-video-google`, `latest-video-wavespeed` resolve to concrete ids at call time. Deprecated ids auto-fall-forward to their `replacement_id`. Catalog covers Claude Opus 4.7 / Sonnet 4.7 preview / Sonnet 4.6 / Haiku 4.5; GPT-5 / 5-mini / 5-nano (and supported-but-older 4o / 4o-mini with replacements); Gemini 3 Pro / 3.5 Flash / Omni; Nano Banana Pro / 2 / 3.1 Flash Image; Imagen 4; Veo 3.1; Kling v3.0 Pro via WaveSpeed; Higgsfield Soul v2. `refresh_models.py` reports drift against live provider catalogs (Anthropic / OpenAI / Google list endpoints). See [`docs/MODEL-CURATOR.md`](docs/MODEL-CURATOR.md).
- **`--openai-model` + `--anthropic-model` + `--list-models` flags** on `scripts/ai-visibility-checker.py`. Defaults pull from curator aliases; user overrides validated against the registry with deprecation warnings.

### Changed

- **`scripts/ai-visibility-checker.py`** — replaced the hardcoded deprecated `claude-sonnet-4-5-20250929` and stale `gpt-4o-mini` defaults with curator-resolved `latest-balanced-anthropic` and `latest-balanced-openai`. Per-call model now shown in the result `platform` field (e.g. `Anthropic claude-sonnet-4-6`).
- **Gmail / Calendar / Drive MCP endpoints** — replaced the dead `*.mcp.claude.com` URLs (all returning HTTP 404 as of May 2026) with the Google-hosted equivalents in `.mcp.json.connectors-reference`, `scripts/connector-status.py`, and `TESTING-GUIDE.md`. New endpoints respond with HTTP 405 to GET probes (alive; POST-only as expected for MCP).
- **Slash-command refs in Python error messages** — swept 51 shorthand `/dm:X` references and rewrote to the canonical `/digital-marketing-pro:X` namespace. Claude Code's auto-namespacing does NOT accept the short form, so the previous error messages pointed users at slash commands that wouldn't actually invoke.
- **`skills/context-engine/compliance-rules.md` § 1.11 India — DPDPA** — replaced the stale "rules pending finalization as of early 2025" line. Section now reflects the **Digital Personal Data Protection Rules 2025** (notified by MeitY 3 Jan 2025; phased commencement through 2025-2026), the live Consent Manager framework under Rule 4, the children's targeted-advertising ban, and the Significant Data Fiduciary obligations.
- **`docs/c2pa-production-cert-guide.md`** — replaced the broken `contentauthenticity.org/community/cr-cli` URL with the working `opensource.contentauthenticity.org/docs/c2patool/` and corrected the framing (open-source `c2patool` CLI, not an Adobe-only program).
- **`skills/status/SKILL.md`** — removed hardcoded `/Users/indra/.claude-marketing` example, replaced with `~/.claude-marketing` and a note about `$CLAUDE_PLUGIN_DATA`.
- **`skills/influencer-brief/SKILL.md`** — added Sora deprecation note (consumer Sora app discontinued 26 Apr 2026; Sora API ends 24 Sep 2026) to the AI-tool clauses, with Veo 3.1 / Kling v3.0 Pro / Runway Gen-4 as the recommended set.
- **`agents/seo-specialist.md` + CHANGELOG entries + `skills/page-seo-analysis/SKILL.md` + `skills/sitemap-manager/SKILL.md`** — fixed broken slash refs `/digital-marketing-pro:page-analysis` (skill is named `page-seo-analysis`) and `/digital-marketing-pro:sitemap` (skill is named `sitemap-manager`).
- **`skills/context-engine/agency-operations-guide.md`** — replaced references to non-existent `/digital-marketing-pro:campaign-audit` and `/digital-marketing-pro:validate-profile` with concrete chains of existing skills (`competitor-analysis` + `performance-check`; `check` + `status`).
- **`skills/context-engine/crm-integration-guide.md`** — `launch-campaign` → `launch-ad-campaign` (the actual skill name).

### Quality

- Smoke-tested every Python script via `--help` — **102 of 103 scripts** return valid usage (1 timeout on first-run pip auto-install of `pyairtable`; pre-existing UX issue, not a regression).
- Per-file content sweep across **185 SKILL.md + 43 agent files + 69 reference docs** for: frontmatter validity, slash-shorthand refs, deprecated model ids, dead MCP URLs, hardcoded local paths. **Zero issues** after the sweeps.
- License compliance: MIT across all 4 manifests; zero GPL-licensed Python imports detected.

## [3.7.3] — 2026-05-24

**Community-standards + Star History.** Patch bump — no functional changes.

### Added

- **`CODE_OF_CONDUCT.md`** — Contributor Covenant v2.1, adapted with project-specific scope (Neelverse Marketing Suite, related repositories, Discussions, Issues, PRs). Five-step enforcement ladder (Correction → Warning → Temporary Ban → Permanent Ban). Reporting routed through the maintainer contact at [indranil.in](https://indranil.in) or GitHub Private Security Advisories.
- **`SECURITY.md`** — Supported-versions table, private vulnerability reporting via GitHub Private Security Advisories (no public Issues for security), coordinated-disclosure timeline (Day 0 ack → Day 7 assessment → Day 30 patch → Day 45 public advisory), scope boundaries (in scope vs upstream-vendor scope), hardening recommendations for operators (don't commit `.mcp.json`, treat `~/.claude-marketing/` as sensitive, rotate API keys quarterly, review SKILL.md PRs as production code, pin version in agency environments).
- **`.github/PULL_REQUEST_TEMPLATE.md`** — checklist covering platform coverage (5 surfaces), version-bump-in-all-sibling-manifests reminder, compliance-source requirement (primary source only — Wikipedia / blog posts NOT acceptable), AI-content disclosure clause.
- **Star History chart** in README — live SVG via star-history.com showing 112-star trajectory. Visual social proof for first-time visitors.
- **`Contributing` section in README** now references CoC + PR template + SECURITY.md explicitly so contributors land on the right artefacts.

### Why this matters

GitHub computes a "Community Standards" score under the repo's Insights tab. Repos with all four (Description, README, Code of Conduct, Contributing, License, Issue templates, PR template, Security policy) get a green checklist that increases organic discovery and contributor trust. v3.7.3 closes the three gaps DMP still had (CoC, SECURITY, PR template).

### Compatibility

- No functional changes. No new commands, skills, agents, scripts, or MCP connectors.
- All 4 sibling manifests bumped 3.7.2 → 3.7.3.
- Plugin version: 3.7.2 → 3.7.3 (patch — community-standards files + Star History).

---

## [3.7.2] — 2026-05-24

**Personal-handles correction.** Patch bump — README only.

### Fixed

- The v3.7.1 "Star + share" CTA at the bottom of the maintainer section used `@neelverse` as a social-handle suggestion. That's the **product/suite brand name**, not Indranil's personal handle. Corrected to use Indranil's actual handles across LinkedIn and X:
  - **LinkedIn:** [linkedin.com/in/askneelnow](https://www.linkedin.com/in/askneelnow)
  - **X / Twitter:** [@askneelnow](https://x.com/askneelnow)

### Changed

- "About the maintainer" links block now includes LinkedIn and X rows alongside Website, GitHub, Other plugins, Discussions, and Issues — so readers can one-click follow Indranil on the platform they prefer.
- The keyword `"neelverse"` in `plugin.json` stays — it's a brand/marketplace-search keyword, not a social handle.
- "Neelverse Marketing Suite" branding throughout the README is preserved — that's the correct name for the bundle of DMP + ContentForge + SocialForge.

### Compatibility

- No functional changes. No new commands, skills, agents, scripts, or MCP connectors.
- All 4 sibling manifests bumped 3.7.1 → 3.7.2.
- Plugin version: 3.7.1 → 3.7.2 (patch — README + branding correction only).

---

## [3.7.1] — 2026-05-24

**Polish + discoverability pass.** No functional changes; no new commands, skills, agents, or scripts. Patch bump for a comprehensive README rewrite and a sweep of stale asset counts across the docs.

### Changed

#### README rewrite for organic GitHub + AI-engine discoverability

- **Hero section rewritten** — leads with a tweet-worthy one-liner positioning DM Pro as "the most comprehensive open-source AI marketing plugin" and the only one installable on 5 coding-agent surfaces. Adds GitHub stars / forks / issues / last-commit badges (live counts from shields.io), Cowork-compatible badge, EU AI Act Article 50 badge, and a "5 platforms" badge. Install command moved to the top of the document.
- **New "Why Digital Marketing Pro" section** — explicit differentiator vs ad-hoc prompts. Six-row comparison table covering canonical 12-Part Flow, Two-Views Model, Decision Matrix, Living Project Instruction File, EU AI Act readiness, 6-platform AEO/GEO audit.
- **New "What you get in 60 minutes" section** — outcome-focused list of the ~50–60 canonical files produced by `/digital-marketing-pro:engagement` with explicit API-spend range ($15–40 on Opus 4.7) and time estimate.
- **New "Installs on 5 coding-agent surfaces" matrix** — install commands per platform (Claude Code, Codex, Cursor, Copilot CLI, Antigravity) with status per platform and a one-sentence "why this works without code duplication" (Agent Skills became an open standard in Dec 2025).
- **Compliance section restructured** — adds flag emojis per jurisdiction for visual scannability, hoists EU AI Act Article 50 readiness as a sub-section with explicit C2PA + pre-publish-gate + production-cert-guide references.
- **AEO/GEO section restructured** — "6-platform audit standard" called out (was 5 before AI Mode added in v3.5). Lists exact platforms (ChatGPT, Perplexity, Google AI Mode, Google AI Overviews, Gemini, Microsoft Copilot).
- **New "About the maintainer" section** — author block with website link ([indranil.in](https://indranil.in)), GitHub, other Neelverse plugins, Discussions, Issues, and the "why this plugin exists" story.
- **New FAQ entries** — comparison vs LangChain marketing templates / CrewAI marketing crews, per-engagement API cost ($15–40), cross-platform support clarification, "is this an Anthropic product?" disambiguation.
- **⭐ Star CTAs** added at hero, maintainer section, and footer. Footer "Made with care by Indranil Banerjee · Powered by Anthropic Claude · MIT-licensed" line at bottom.
- **SEO keyword density** improved throughout — "AI marketing plugin", "Claude Code marketing", "Google AI Mode", "EU AI Act Article 50", "C2PA content provenance", "OpenAI Codex marketing", "GitHub Copilot CLI marketing", "agency operations", "multi-brand marketing", "agent skills standard".

#### Stale asset counts swept across docs

| File | Before | After |
|---|---|---|
| `docs/claude-interfaces.md` | "13 specialist agents" | "25 specialist agents" |
| `docs/claude-interfaces.md` | "117 reference files" | "167 reference files" |
| `docs/claude-interfaces.md` | "34 Python scripts" | "69 Python scripts" |
| `docs/claude-interfaces.md` | "42 commands" | "10 commands" |
| `docs/claude-interfaces.md` | "18 MCP integrations" | "14 HTTP MCP connectors" |
| `docs/architecture.md` | "149 skills total" | "150 skills total" |
| `docs/getting-started.md` | "149 skills" (×3 places) | "150 skills" |
| `docs/competitor-intelligence.md` | "117 reference knowledge files" | "167 reference knowledge files" |
| `docs/cross-platform-install.md` | "71 Python scripts" (×4 places) | "69 Python scripts" |
| `skills/context-engine/memory-architecture.md` | "All 13 agents" | "All 25 agents" |
| `.claude-plugin/plugin.json` description | "71 Python scripts, 16 industry profiles, 16 privacy-law jurisdictions" | "69 Python scripts, 16 privacy-law jurisdictions" (industry-profiles claim removed pending re-count) |

Audit method: JSON-validated all 6 manifest/config files (`.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.antigravity/plugin.json`, `.mcp.json`, `hooks/hooks.json`). Smoke-tested all 69 Python scripts via `python3 <script> --help` (69 pass, 0 fail). Verified all 150 SKILL.md files have valid `name:` + `description:` frontmatter. Checked all internal markdown links in README.md for broken references (none found).

#### Plugin manifest keywords expanded for GitHub + marketplace search

Added: `marketing-automation`, `marketing-plugin`, `ai-marketing`, `ai-mode`, `ai-overviews`, `generative-engine-optimization`, `answer-engine-optimization`, `google-ai-mode`, `performance-max`, `advantage-plus`, `content-strategy`, `brand-guidelines`, `gdpr`, `ccpa`, `eu-ai-act`, `article-50`, `c2pa`, `content-provenance`, `synthid`, `deepfake-disclosure`, `claude-code-plugin`, `claude-skills`, `agent-skills`, `anthropic-claude`, `openai-codex`, `cursor-plugin`, `github-copilot`, `antigravity`, `mcp`, `model-context-protocol`, `gemini`, `nano-banana-pro`, `veo-3`, `gemini-omni`, `neelverse`. Total keyword count: 26 → 61.

### Compatibility

- No breaking changes. All previous v3.7.x commands, skills, agents, scripts, and MCP connectors continue to work unchanged.
- Plugin version: 3.7.0 → 3.7.1 (patch bump — docs + branding only).
- All 4 sibling manifests bumped to 3.7.1 (`.claude-plugin/`, `.codex-plugin/`, `.cursor-plugin/`, `.antigravity/`).
- Skills count, agents count, commands count, scripts count: unchanged from v3.7.0.

---

## [3.7.0] — 2026-05-24

**Install-surface expansion: GitHub Copilot CLI (auto-discovered) + Google Antigravity 2.0 (experimental).** DM Pro now installs cleanly on five coding-agent surfaces from a single source repository — Claude Code (canonical), OpenAI Codex, Cursor (added v3.6), GitHub Copilot CLI, and Google Antigravity 2.0 (experimental). No new core dependencies; same 150 skills, same scripts, same MCP catalog.

### Added

- **GitHub Copilot CLI compatibility — no new manifest needed.** Copilot CLI's plugin discovery explicitly checks `.claude-plugin/plugin.json` as one of its accepted manifest paths (alongside `.plugin/plugin.json`, `plugin.json`, and `.github/plugin/plugin.json`). DM Pro's existing Claude Code manifest is therefore directly readable by Copilot CLI. Install: `copilot plugin install indranilbanerjee/digital-marketing-pro`. The MCP catalog (`.mcp.json`), hooks (`hooks/hooks.json`), and SKILL.md auto-discovery all work natively.
- **`.antigravity/plugin.json`** — Experimental manifest for Google Antigravity 2.0 CLI (launched 19 May 2026 at Google I/O, replacing Gemini CLI). Mirrors the Gemini-CLI-extensions format that Antigravity's `agy plugin import gemini` converter accepts. Includes a `_status` field flagging the experimental nature. Will be updated against the v2-native plugin spec when Google publishes it.
- **`docs/cross-platform-install.md` — expanded** to cover all 5 platforms with: install commands, what works natively per platform, the Antigravity caveat (spec not yet public — Gemini-extensions importer is the most reliable current path), `agy plugin import gemini` workflow, update commands per platform, and where to file platform-specific bugs.

### Why Copilot CLI works without a new manifest

GitHub Copilot CLI plugin discovery (May 2026 Public Preview) is intentionally inclusive — it accepts `.claude-plugin/plugin.json`, `.plugin/plugin.json`, `plugin.json`, and `.github/plugin/plugin.json` interchangeably. The manifest format (name, version, description, skills, mcpServers, hooks fields) is a near-superset of Claude Code's, so the existing DM Pro manifest is directly readable. Skills, MCP, and hooks all auto-load without modification.

### Why Antigravity ships as experimental

Antigravity CLI (announced 19 May 2026) preserves Gemini CLI's plugin concepts but has not yet published an open v2-native plugin manifest spec. Third-party plugin libraries (e.g., antigravity-awesome-skills) currently distribute via Antigravity's Gemini-CLI-extensions importer (`agy plugin import gemini`). DM Pro ships an experimental `.antigravity/plugin.json` against the same format the importer accepts; when Google publishes the v2-native spec, this will be updated and the experimental flag removed.

### Compatibility

- No breaking changes for existing Claude Code, Codex, or Cursor users.
- Plugin version: 3.6.0 → 3.7.0 (minor bump — new install surfaces, no breaking changes).
- Files added: 1 (`.antigravity/plugin.json`); 1 expanded (`docs/cross-platform-install.md`).
- Skills count, agents count, commands count, scripts count: unchanged from v3.6.0.

---

## [3.6.0] — 2026-05-24

**Cross-platform compatibility pack.** Digital Marketing Pro now installs cleanly on three coding-agent surfaces from a single source repository — Claude Code (canonical), OpenAI Codex, and Cursor — by adding platform-native manifest files alongside the existing Claude Code manifest. No skill duplication: all three platforms read the same `skills/` directory, the same `scripts/`, the same `.mcp.json`, and the same `hooks/hooks.json`.

### Added

- **`.codex-plugin/plugin.json`** — OpenAI Codex plugin manifest. Includes the `interface` block (displayName, shortDescription, longDescription, category, capabilities, defaultPrompt) Codex uses to render the plugin in its install surfaces. Points at `./skills/`, `./.mcp.json`, `./hooks/hooks.json` — same directories Claude Code reads.
- **`.cursor-plugin/plugin.json`** — Cursor plugin manifest. Minimal manifest (Cursor only requires `name`) plus author, repository, license, keywords, and skills path. Cursor auto-discovers `skills/` via the open SKILL.md frontmatter standard.
- **`docs/cross-platform-install.md`** — Full install guide covering all three platforms with: install commands per platform, what works natively vs what requires platform-specific configuration (notably Cursor's global mcp.json paste step), portability matrix, update commands per platform, and where to file platform-specific bugs.

### Why this works without code duplication

Agent Skills became an open standard (donated to the Agentic AI Foundation, Dec 2025; adopted by 32+ tools by May 2026). All three target platforms — Claude Code, Codex, Cursor — parse the same `name:` + `description:` SKILL.md frontmatter the same way. DM Pro's 150 skills are platform-portable as written; the v3.6.0 manifests are thin platform-specific wrappers around shared content.

### Platform-specific gotchas (documented in cross-platform-install.md)

| Gotcha | Affects | Workaround |
|---|---|---|
| Cursor reads MCP from global `mcp.json` (no leading dot), not from plugin-scoped `.mcp.json` | Cursor only | One-time paste of `.mcp.json` contents into Cursor → Settings → MCP Servers (documented step) |
| Codex slash-command syntax differs (`/cmds` vs Claude Code's `/<plugin>:<command>`) | Codex only | Skills are invoked via natural-language intent on Codex; outputs are equivalent |
| Sub-agent format differs across platforms | Codex, Cursor | DM Pro skills embed agent instructions inline so outputs are equivalent on platforms without Claude Code sub-agent support |

### Compatibility

- No breaking changes for Claude Code users.
- No new dependencies — the new manifests are sibling JSON files; existing tooling untouched.
- Plugin version: 3.5.0 → 3.6.0 (minor bump — new platform surfaces, no breaking changes)
- Files added: 3 (2 manifests + 1 docs)
- Skills count, agents count, commands count, scripts count: unchanged from v3.5.0

---

## [3.5.0] — 2026-05-24

A May-2026-ecosystem modernisation pass covering Google I/O 2026, the active broad core algorithm update, EU AI Act draft implementing guidelines, Meta platform expansions, and Claude Code's new cost-attribution capability. No breaking changes. No new commands or skills — six discrete content updates applied across 14 existing files + 1 script.

### Changed — Six discrete content updates

#### 1. Google AI Mode added as a first-class AEO/GEO surface (5 files)

Google AI Mode (default conversational search since Google I/O on 19 May 2026, ~1B MAUs, Gemini 3.5 Flash backbone) is now tracked as a distinct platform separate from AI Overviews. The 5-platform AEO/GEO testing protocol is now 6-platform. Files updated:

- `skills/aeo-audit/SKILL.md` — Purpose section now explains the AI Mode vs AI Overviews distinction (citations diverge 40–60% for the same query)
- `skills/aeo-geo/SKILL.md` — Module trigger phrases + testing protocol updated to 6 platforms; AI Mode treated as a distinct surface in process steps
- `skills/aeo-geo/ai-visibility-audit.md` — Scoring rubric updated (max per query = 30, not 25), platform-specific notes added for AI Mode (Gemini 3.5 Flash, captures conversational follow-ups), monitoring cadence updated, baseline-normalisation guidance for pre-vs-post May 2026 score comparisons
- `skills/geo-monitor/SKILL.md` — Input "platforms to monitor" now includes AI Mode by default; output scorecard exposes the 6th surface
- `scripts/geo-tracker.py` — `PLATFORMS` list updated to include `ai-mode`; docstring clarifies the AI Mode vs AI Overviews separation. Smoke-tested via `--help`.

#### 2. May 2026 broad core algorithm update triage guidance (2 files)

Google began a broad core update on 21 May 2026 (still in the typical ~2-week deployment window when this ships). Reactive changes during/immediately after a Core Update tend to make things worse — both SEO audit skills now lead with explicit triage guidance:

- `skills/seo-audit/SKILL.md` — Purpose section adds "May 2026 Core Update context" subsection: wait for the rollout + 7–14 days settling before drawing conclusions; segment Search Console data pre/in/post rollout; Core Updates re-weight existing signals (E-E-A-T, content quality) rather than introducing new ones
- `skills/tech-seo-audit/SKILL.md` — Adds the parallel note: run the technical audit anyway (Core Updates surface pre-existing technical debt), but technical "fixes" sold as Core Update remedies won't undo a quality-driven hit

#### 3. EU AI Act Article 50 draft implementing guidelines (1 file, major addition)

The European Commission published draft Article 50 implementing guidelines on **8 May 2026**; public consultation closes **3 June 2026**; final guidelines expected July 2026 ahead of the **2 August 2026** enforcement date. Added as new sub-section §1.1b.i in `skills/context-engine/compliance-rules.md`:

- Six-row clarification table covering: "substantial AI manipulation" definition, "matters of public interest" scope, machine-readable marking (C2PA = presumption of compliance), deepfake visible-disclosure requirements (perceivable at normal viewing distance), editorial-responsibility carve-out conditions, and enforcement priorities
- Five-point action list: audit EU AI-asset inventory now, file consultation comment by 3 June if materially affected, lock in C2PA signing-cert procurement (Adobe approval = 2–4 weeks; start by 1 July), update Definition of Done so creative is C2PA-signed at production time, treat the human-review carve-out as conditional (named accountability required)

#### 4. Meta platform updates — Advantage+ Leads global, Threads ads global, brand-safety controls (1 file)

Three May 2026 Meta updates added to `skills/context-engine/execution-workflows.md` Section 3 (Ad Campaign Workflow):

- **Advantage+ Leads** — now globally available; only works well with Conversions API + CRM-quality feedback; not compatible with Special Ad Categories (housing/credit/employment)
- **Threads ads** — global rollout completing May 2026; image-only formats only; cheap-to-moderate inventory; best for younger / news-adjacent / B2B-thought-leadership; cap at <10% of Meta budget until account-level CPA proves out
- **Brand-safety inventory filters** — three tiers (Expanded/Moderate/Limited); default Moderate; move to Limited only for regulated industries or after a documented incident (Limited costs ~30% reach); Brand Suitability dashboard now exposes Reels topic adjacencies

#### 5. Gemini Omni + Nano Banana Pro + Veo 3.1 in AI creative briefs (4 files)

Added an "AI image & video generation guidance (May 2026)" sub-section to four creative-production skills, with consistent C2PA-by-default and Article 50 disclosure clauses:

- `skills/ad-creative/SKILL.md` — Asset-type-to-model table (Nano Banana Pro for stills with on-image text, Veo 3.1 for short-form video, Gemini Omni for connected multimodal packages); workflow recommendation to hand visual spec to SocialForge `/sf:image` and `/sf:video`
- `skills/content-brief/SKILL.md` — Visual/media spec requires explicit model, provenance marking, deepfake flag, and editorial-responsibility owner for YMYL topics
- `skills/creative-testing-framework/SKILL.md` — AI creative variant production note: cost-per-variant becomes the new floor for minimum-budget math; EU-targeted ad sets blocked unless C2PA-signed
- `skills/influencer-brief/SKILL.md` — Three explicit AI-tool clauses for creator contracts: permitted AI use, required platform disclosures, EU deepfake clause (mandatory for EU placements)

#### 6. Claude Code v2.1.149+ `/usage` per-model breakdown (2 files)

Claude Code v2.1.149 (May 2026) exposes per-model token consumption and projected USD cost via `/usage`. For agencies, this is the cleanest brand-attributable AI-cost source.

- `docs/claude-interfaces.md` — New "Cost tracking" section under Claude Code (Full Support) documenting `/usage`, `/usage --since 7d`, per-directory scoping, and the operational implications for 12-Part engagement billing and Opus-1M context tradeoffs
- `skills/agency-dashboard/SKILL.md` — Process step 8 (team utilization) now pulls `/usage --since 7d` per brand directory; output adds "Claude Code consumption (per brand)" line flagging brands at >2× portfolio median for retainer-tier rate review

### Compatibility

- No breaking changes. All previous v3.4.x commands, skills, agents, scripts, and MCP connectors continue to work unchanged.
- `geo-tracker.py` now accepts `ai-mode` as a platform argument (previously: rejected with argparse error).
- Historical GEO scores baselined pre–May 2026 should be normalised ×1.2 OR rerun against the 6-platform set before comparison. See `skills/aeo-geo/ai-visibility-audit.md`.

### Auditor notes

- Plugin version: 3.4.2 → 3.5.0 (minor bump — new feature surface for AI Mode + Article 50 draft + Gemini Omni; no breaking changes)
- Files modified: 15 (14 SKILL/docs + 1 script)
- Skills count, agents count, commands count: unchanged from v3.4.2

---

## [3.4.2] — 2026-05-17

### Added — Three documentation expansions (no code changes; no breaking changes)

#### 1. Opus 4.7 1M-context guidance in `skills/engagement-workflow/SKILL.md`

The full 12-part engagement (50–60 documents, 250K–600K tokens) now fits in a single conversation when running on Opus 4.7 with the 1M context window (generally available to Max, Team, and Enterprise users as of May 2026). New section documents:

- When 1M context is available: skip LIF re-load between parts, run Parts 1–8 sequentially in one conversation, dispatch Part 9 channel families in parallel, complete Parts 10–12 in the same conversation
- When 1M context is NOT available (Pro tier, third-party API access, batch mode): use the existing engagement-state.py persistence pattern; chunk by Part; re-load LIF at each transition
- The local persistence pattern stays the default — it's correct in both worlds and the only one that works for multi-day / multi-author engagements

#### 2. WhatsApp Business voice calling in `skills/context-engine/india-market-context.md`

WhatsApp Business now supports brand-to-customer voice calls in/out of WhatsApp (May 2026 launch). Use cases: high-AOV consult (real estate, automotive, financial services), post-purchase support, B2B account management. Practical guidance: pilot with a single use case rather than treating it as a broadcast channel; voice calls preserve the 24-hour customer-care window for the next 24 hours after the call ends.

#### 3. May 2026 platform updates in `skills/context-engine/execution-workflows.md` Section 3 (Ad Campaign Workflow)

- **Google Performance Max 2026:** brand exclusion lists first-class, per-network placement reporting exposed, first-party audience exclusions, 15 videos per asset group (was 5), PMax experiments. The old "black box" criticism is mostly addressed.
- **Meta Advantage+ shopping 2026:** in-app checkout, AI product overlays on hover, retailer integrations standard. Creative at product-tile scale, not full-frame. Catalog quality dominates performance.
- **LinkedIn Ads:** March 2026 algorithm shift carries into ad relevance — ads with external links score lower than in-platform formats (lead gen forms, document ads, conversation ads).
- **TikTok Ads (post-USDS Jan 2026):** US-served ads run through USDS LLC infrastructure; AI-generated creative requires AI disclosure label.
- **Retail media (Amazon, Walmart, Instacart):** combined US spend ~$60B+/year in 2026. Worth a campaign track for DTC + CPG brands.

#### 4. New `docs/roadmap-multiagent-sessions-api.md`

Planning document for v3.5 / v4.0 — how DMP would adopt Anthropic's Multiagent Sessions API + Memory for Managed Agents API (both in public beta under the `managed-agents-2026-04-01` Messages API beta header). Three-phase plan: (A) v3.5 dual-write opt-in path, (B) v4.0 flip default to managed-agents with local-file fallback, (C) v4.1+ long-running engagements as managed sessions. Open questions documented: pricing, Cowork compatibility, cross-API-provider availability, migration story. No code in v3.4.2 implements any of this — it's a planning artifact.

### Rationale

User asked what's worth doing next from the May 2026 reality. These three documentation expansions are the small, low-risk content adds; the multi-agent roadmap is the longer-term direction setter. Bundled into one patch release rather than three separate ones because none of them ship code.

---

## [3.4.1] — 2026-05-17

### Fixed — Audit & corrections pass on v3.4.0

User explicitly asked whether the v3.4 work had been audited. Answer: no. Ran a real audit. Found four issues, fixed all four.

#### (1) C2PA script — actually works now

**Problem:** v3.4.0 `scripts/embed-c2pa.py` called `c2pa.create_signer(...)` and `c2pa.sign_file(...)` as top-level module functions. Neither exists in c2pa-python 0.32.6 (the current library). Script would have failed at runtime the first time a user invoked `/digital-marketing-pro:c2pa-metadata`.

**Fix:**
- Rewrote against the real API: `c2pa.Signer.from_info(C2paSignerInfo(...))` → `c2pa.Builder(manifest_json)` → `builder.sign_file(source, dest, signer)`.
- Fixed `C2paSignerInfo` field types (`c_char_p` ctypes — alg=b"es256", cert_bytes, key_bytes, b"http://timestamp.digicert.com").
- Switched manifest assertions label from `c2pa.actions` to `c2pa.actions.v2` (current spec).
- Bound `digital_source_type` via `builder.set_intent(C2paBuilderIntent.CREATE, C2paDigitalSourceType.{TRAINED_ALGORITHMIC_MEDIA|COMPOSITE_WITH_TRAINED_ALGORITHMIC_MEDIA|HUMAN_EDITS})` rather than embedding raw IPTC URIs in the manifest.
- Fixed the self-signed dev cert to include the certificate extensions C2PA requires: BasicConstraints(ca=false, critical), KeyUsage(digital_signature=true, critical), ExtendedKeyUsage(EMAIL_PROTECTION), SubjectKeyIdentifier, AuthorityKeyIdentifier. Without these the C2PA library rejects with "the certificate is invalid".
- Fixed the read-back verification to use `c2pa.Reader(format, stream)` context manager — the prior `Reader.from_file` API doesn't exist either.

**Verified end-to-end:** 75-byte test PNG → 42,818-byte signed PNG. Read-back confirms `active_manifest` ID, title, signer ("Digital Marketing Pro"), cert algorithm "Es256", assertions `["c2pa.actions.v2", "stds.schema-org.CreativeWork"]`, action `c2pa.created (Test Generator)`, CreativeWork.author `[{"@type": "Organization", "name": "Test Brand"}]`. `manifest_embedded_and_verified: true`. Validation state shows "Invalid" only because self-signed certs aren't in C2PA's trust list — production CAI-issued certs validate as "Valid".

#### (2) Unified ads MCP entries — corrected endpoints + coverage

Prior research agent told me Synter endpoint was `https://mcp.synter.com/sse` covering 14 platforms, and Ryze was `https://mcp.ryze.ai/mcp`. Neither matches reality.

**Fix:**
- **Synter (real name: Synter Media AI):** corrected endpoint `https://mcp.syntermedia.ai/mcp/` with `X-Synter-Key` header auth. Platform coverage corrected from claimed 14 to actual 7: Google Ads, Meta Ads, LinkedIn Ads, Microsoft Ads, Reddit Ads, TikTok Ads, X. Source: `github.com/Synter-Media-AI/mcp-server`. Renamed entry from `synter` to `synter-media-ai`.
- **Ryze AI:** corrected entry — it's primarily a managed OAuth connector service at `app.get-ryze.ai/mcp-connector`, not a generic self-serve HTTP MCP. The Google Ads per-platform endpoint is `https://ryze-google-ads-mcp-kyfjuf4chq-uc.a.run.app/mcp`. Coverage clarified: Google Ads primary; separate per-platform connectors for Meta and Google Analytics via the managed OAuth service. Renamed entry from `ryze-ai` to `ryze-ai-google-ads`.
- **Northbeam:** corrected GitHub URL to `github.com/mattcoatsworth/Northbeam-MCP-Server` (community-maintained, NOT first-party from Northbeam Inc — the prior reference implied otherwise). Platform coverage (Google + Meta + LinkedIn + TikTok) verified. Renamed entry from `northbeam-selfhosted` to `northbeam-mcp-selfhosted`.
- Added explicit caveat at top of `_section_unified_ads_mcps`: "Endpoint URLs and platform-coverage claims below were verified May 2026 — re-verify before production use as these are early-stage services."
- `CONNECTORS.md` "Unified ads MCPs" table updated with the corrected URLs, auth, and source-repo links.

#### (3) Parallel-dispatch speedup claim — softened from overstated to honest

**Problem:** v3.4.0 claimed flat "~6× wall-clock speedup" across multiple surfaces (CHANGELOG, README, plugin.json, marketplace.json, engagement-workflow SKILL, competitor-analysis command, seo-audit command). Published Anthropic guidance is more nuanced: 4–6× parallelism with 50–80% wall-clock reduction for 3–8 concurrent subagents; past 8 you queue against rate limits and the win drops; under 3 there's nothing to parallelize.

**Fix:**
- `skills/engagement-workflow/SKILL.md`: replaced overclaim with "4–6× parallelism with roughly 50–80% wall-clock reduction for 3–8 concurrent subagents" + cost note ("total token usage is broadly similar; billed-per-turn input costs trend up slightly because each parallel subagent re-loads its context") + the queue-after-8 caveat.
- `commands/competitor-analysis.md`: changed "parallel → ~6 min wall-clock" to "parallel dispatch reduces this by 50–80% wall-clock per Claude Code's April 2026 parallel-subagent initialization — typical run lands at ~7–17 min (rate-limit dependent)".
- `commands/seo-audit.md`: changed "parallel ~5 min wall-clock" to "parallel dispatch typically lands at ~5–12 min wall-clock (rate-limit dependent) — roughly 50–80% reduction".

#### (4) Submission URLs — removed unverified URL

**Problem:** `SUBMISSION.md` referenced two submission URLs: `https://claude.ai/settings/plugins/submit` (consumer) and `https://platform.claude.com/plugins/submit` (Console). Only the second is verifiable in Anthropic's public docs as of May 2026.

**Fix:** Removed `claude.ai/settings/plugins/submit` references from SUBMISSION.md introduction and the 12-step submission flow. Sole submission URL is now `https://platform.claude.com/plugins/submit`.

### Rationale

User explicitly pushed back on the previous turn's "ship-fast, verify-later" pattern. Audit found exactly the kind of issues that pattern produces: a Python script that won't run, MCP endpoint URLs that don't resolve, performance claims that misrepresent published Anthropic guidance, and a submission URL that may not exist. All four fixed in v3.4.1. The C2PA script is now end-to-end empirically tested — signing succeeds, manifest reads back round-trip, all assertion fields verified.

---

## [3.4.0] — 2026-05-16

### Added — The Four Deferred Items from v3.3 audit

User asked why these were deferred. Answer: sequencing — content/regulatory drift was bleeding trust and shipped first. They're now in.

#### 1. C2PA content provenance (EU AI Act Article 50 compliance)

- **New script** `scripts/embed-c2pa.py` (~250 lines) wrapping `c2pa-python>=0.5.0`. Embeds machine-readable provenance manifests into AI-generated images / video / audio / PDF. Supports `.png .jpg .jpeg .webp .gif .tiff .mp4 .mov .webm .mp3 .wav .pdf`.
- **New skill** `/digital-marketing-pro:c2pa-metadata` at `skills/c2pa-metadata/SKILL.md`. Full doc with usage examples, IPTC digital-source-type vocabulary mapping (ai-generated-content / ai-assisted-edits / ai-no-substantive-changes), signing-certificate guidance (CAI-recognized authority for prod; auto-generated 90-day self-signed cert for dev).
- **Pre-publish gate integration** — `/digital-marketing-pro:check` now treats missing/invalid C2PA manifest on AI-flagged assets in EU-targeted campaigns as a CRITICAL issue (BLOCKED decision). Wired through `commands/check.md`.
- **Compliance rule binding** — new `Section 1.1b EU/EEA — AI Act Article 50 (Generative AI Disclosure)` in `skills/context-engine/compliance-rules.md` documents the regulatory basis, applicability date (2 Aug 2026), penalty (€15M or 3% global turnover), and how the c2pa-metadata skill satisfies the marking requirement.
- **requirements.txt updated** with optional `c2pa-python>=0.5.0` and `cryptography>=42.0` (commented; install only when needed).
- Output is verifiable at https://contentcredentials.org/verify and any C2PA-aware viewer (Photoshop, Lightroom, Truepic).

#### 2. Unified ads-platform MCPs

- **New `_section_unified_ads_mcps` in `.mcp.json.connectors-reference`** documenting three purpose-built MCPs:
  - **Synter** — 14 platforms in one (Google, Meta, LinkedIn, TikTok, Reddit, Pinterest, Snapchat, X, Microsoft, Taboola, Outbrain, Quora, Spotify, Amazon Ads)
  - **Ryze AI** — Google + Meta + GA4 with confirmation patterns
  - **Northbeam (self-hosted)** — Google + Meta + LinkedIn + TikTok, open-source, BYO OAuth
- **CONNECTORS.md updated** with a new "Unified ads MCPs (added v3.4)" section and a callout on the Advertising row in the npx-only table directing users to the unified options.
- All three are HTTP — fully Cowork-compatible. Replaces the per-platform stdio servers in `.mcp.json.example` for teams who want one ads tool surface instead of four.

#### 3. Parallel subagent dispatch

Leverages Claude Code's **April 2026 parallel-subagent initialization**. Realistic speedup: 4–6× parallelism with ~50–80% wall-clock reduction for 3–8 concurrent subagents (past 8 you queue against rate limits). See v3.4.1 entry above for corrected per-command numbers.

- **`skills/engagement-workflow/SKILL.md`** — new "Parallel Dispatch" section identifies Parts 2 (External Research), 4 (Competitive + Customer + Market), 9 (Channel Strategy Fan-out), 10 (Execution Artefacts), 11 (AI Creative Instructions) as parallel-eligible, with explicit subagent-dispatch instructions. Parts 1→2, 3→4, 5→6, 7→8, 8→9 remain sequential (real data dependencies). New Quality Discipline rule #6: "Always parallelize independent work."
- **`commands/competitor-analysis.md`** — 7 dimensions (content, SEO, paid ads, social, AI visibility, pricing, positioning) dispatched in one message with 7 parallel Task calls. ~35 min sequential → ~6 min parallel. Multi-competitor analyses sequence competitors but parallelize dimensions within each.
- **`commands/seo-audit.md`** — 6 dimensions (technical, on-page, content, E-E-A-T, link profile, AEO) parallel; aggregation + impact-to-effort prioritization sequential. ~25 min sequential → ~5 min parallel.
- **`commands/content-engine.md`** — per-format drafting parallel when multiple formats requested from one brief (blog + 3 socials + email + ad copy → 6 parallel Task calls); SME calibration + quality gate + aggregation sequential.
- **`commands/campaign-plan.md`** — per-channel briefs parallel after channel-mix approval; KPI tree + attribution + reporting cadence parallel in the measurement layer; budget allocation sequential.

#### 4. Anthropic Software Directory submission packet

- **New `SUBMISSION.md` at repo root** pre-stages every input the directory form requires: one-line + long description, category, target audience, 4 working use cases, testing-account/sample-data declaration, ownership verification, compliance-with-policy checklist, Cowork compatibility statement, Verified-badge candidacy assessment, screenshot checklist, step-by-step submission instructions.
- Reduces actual submission at https://claude.ai/settings/plugins/submit from a multi-hour task to ~5 minutes.
- Maintained in the repo so it can be refreshed each release before re-submission.

### Changed

- Skill count bumped from 149 → **150** (new c2pa-metadata skill).
- Script count bumped from 70 → **71** (new embed-c2pa.py script).
- Plugin description in plugin.json + marketplace.json updated to lead with the four v3.4 additions.

### Rationale

The four deferred items from the v3.3 audit aren't optional polish — C2PA is a hard regulatory requirement for EU markets in 81 days (2 Aug 2026); unified ads MCPs eliminate connector sprawl that's been the #2 user complaint; parallel dispatch makes the 12-part engagement viable inside a single conversation rather than an hour-long wait; the directory submission packet is the path to discoverability beyond word-of-mouth.

---

## [3.3.0] — 2026-05-15

### Added — May 2026 Modernization Sweep

Comprehensive refresh against current marketing/regulatory/AI-search reality. **Content + documentation release** — no breaking changes to skills, agents, or scripts.

#### Privacy & Compliance updates (16-jurisdiction matrix)

- **EU AI Act Article 50 (applicable 2 Aug 2026)** — generative-AI marketing content must carry machine-readable C2PA-style watermarks; deepfakes must be visibly disclosed; AI-generated text on matters of public interest must be disclosed. Penalty up to €15M or 3% global turnover.
- **DPDP Phase II preparation (effective 13 Nov 2026)** — consent-manager framework registration window opens. Phase III hard enforcement 13 May 2027 with INR 2.5B max penalty.
- **NY synthetic-performer disclosure law (live June 2026)** — $1K–$5K per violation, $10K repeat. Synthetic influencers and AI-generated endorsements flagged.
- **FTC May 2026 endorsement guidance** — covers synthetic influencers, AI testimonials, AI-edited creator content.
- **CJEU March 2026 ruling** — pseudonymized cookie IDs are personal data when re-identification is feasible.
- **CCPA/CPRA Jan 2026 amendments** — neural networks and AI-derived personal data classified as sensitive. ADMT compliance (Jan 1 2027) flagged.

#### Channel guidance updates

- **LinkedIn (March 2026 algorithm shift)** — external links and engagement bait penalized ~60%; new Depth Score measures dwell time. `social-strategy` and content-engine LinkedIn guidance updated.
- **Email** — Apple MPP affects ~64% of B2C opens; open rate dropped as primary KPI. **DMARC + RFC 8058 one-click POST unsubscribe** mandatory; non-compliant bulk mail to Gmail/Yahoo/Microsoft gets permanent 550 rejections. Spam threshold tightened to <0.10%.
- **TikTok (post Jan 22 2026 USDS Joint Venture closing)** — US data and algorithm under USDS LLC. AI-generated creators allowed only with disclosure; AI content excluded from Creator Rewards Program. Daily shoppable-post limits effective May 11 2026.
- **WhatsApp (per-message pricing since 1 July 2025)** — corrected from deprecated conversation-based model in 3 skill files: `skills/context-engine/execution-workflows.md`, `skills/context-engine/india-market-context.md`, `skills/emerging-channels/conversational-commerce.md`. India marketing template ≈ USD 0.0118 per message. 72-hour free service window from CTWA ads or Page CTAs.
- **Schema strategy refresh** — Google's March 2026 core update demoted FAQ/Review/HowTo schema on non-primary pages. Skills now emphasize entity-rich JSON-LD and produce an LLMs.txt companion file.
- **Sora deprecation note** — OpenAI's consumer Sora app discontinues April 26 2026; Sora API September 24 2026. AI creative briefs default to Runway Gen-4 / Veo 3.x / Kling 3.0.
- **Third-party cookies — deprecation cancelled** — Chrome formally abandoned the timeline. The `attribution-model` skill defaults to first-party + MMM + incrementality stack.

#### AEO / GEO modernization

- Google AI Overviews now appear on ~55% of all Google searches. Organic CTR on AI Overview queries dropped ~61%. ~58% of searches are zero-click.
- Citation-tracking guidance updated for ChatGPT, Perplexity, Google AI Overviews, Claude, Bing Copilot, Gemini.
- For ongoing measurement, integrate with **Profound / Otterly / Conductor AgentStack** via the connectors layer.
- **Share of AI Voice** as a first-class metric in `/digital-marketing-pro:performance-report`.

#### README + Top Commands fixes

- **README fully restructured** to ContentForge v3.9.5 pattern: Quick Start at top with install + auto-update toggle as steps 1-2; "Where your files go" section showing the 12-part engagement directory layout; version histories collapsed at the bottom.
- **Top Commands table corrected** — was using bare `/brand-setup` form that conflicts with other plugins. Now uses canonical `/digital-marketing-pro:brand-setup`.
- **Duplicate "Option C" install heading fixed** (was Option C twice instead of A/B/C/D).
- **Top version badge bumped** from 3.2.0 → 3.3.0 (was two patches stale).
- **Auto-update guidance** — explicit two-option flow (toggle vs manual uninstall+reinstall) since third-party marketplaces have auto-update OFF by default.
- **Cowork install correctness** — Cowork is the Anthropic Desktop computer-use product with local filesystem access; full DM Pro pipeline including all 70 Python scripts runs natively. Only Cowork-specific limitation is HTTP MCPs only.
- **Script count corrected** from "68 Python scripts" to actual file count of 70.
- **Two PDF references at repo root** documented (`DM_Strategy_Complete_Learning_Guide.pdf` and `DM_Strategy_Flow_v3_2_Visualization_v1_23Apr26.pdf`).

### Rationale

Marketing tech moves quarterly. A plugin that documents WhatsApp's per-conversation pricing (deprecated July 2025) or treats email open rate as a primary KPI (Apple MPP affects 64% of B2C opens) erodes user trust. v3.3 brings DM Pro's content surface up to the May 2026 reality.

---

## [3.2.2] — 2026-05-09

### Fixed — Slash Command Namespace Consistency

All `/dm:` references in docs and runtime files swept to the canonical `/digital-marketing-pro:` form that Claude Code auto-namespacing actually produces. The `/dm:` shorthand was used in ~600 places across README, getting-started, TESTING-GUIDE, engagement-methodology, multi-brand-guide, brand-guidelines, architecture, v3.2-opt-ins, all agent files, all 149 skill SKILL.md files, command files, and the CHANGELOG. Users can now copy-paste any command from any doc and have it work.

The replacements include agent files (content-creator, email-specialist, social-media-manager, pr-outreach, quality-assurance, seo-specialist) which emit slash command recommendations during execution. Before this release, agents may have been emitting commands that didn't match the documented namespace.

Skill filenames preserved.

No behavioral changes. If `/dm:` shortcuts work in your environment they'll continue to work; this just makes the docs match the documented Claude Code namespace pattern.

---

## [3.2.1] — 2026-05-03

### Fixed — Plugin Manifest Install Format (CRITICAL)

The plugin manifest format that v3.0 inherited (and v3.1.1 / v3.2.0 carried forward) used two fields that Claude Code's plugin schema does not accept, causing `claude plugins install digital-marketing-pro` to fail with "the manifest's `repository` field is an object when Claude Code expects a string." This release fixes both issues so install works.

#### Changes

- **`repository` field**: converted from npm-shorthand object form (`{type: "git", url: "..."}`) to the string URL form Claude Code's plugin schema requires. New value: `"https://github.com/indranilbanerjee/digital-marketing-pro.git"`.
- **`$schema` field removed**: Claude Code's plugin schema parser rejects this top-level key. Editor validation benefit isn't worth a broken install.

Same fixes shipped same-day to ContentForge v3.9.2, SocialForge v1.5.2, and marketplace v2.8.0.

### Migration

Pure manifest fix. No behavioral changes; the v3.2 12-Part Methodology + opt-in safety nets continue to work identically.

---

## [3.2.0] — 2026-05-03

### Added — Closing the v3.1 Hook-Removal Gaps

v3.1 removed all four global hooks for multi-plugin coexistence (the `PreToolUse mcp_.*` matcher in particular was intercepting every MCP call from every installed plugin). That fix was correct, but it left real gaps — most notably, the loss of automatic hallucination detection on every Write/Edit operation. v3.2 closes those gaps with explicit on-demand replacements, agent-embedded safety, and opt-in ambient capture — without bringing back the global-scoping problem.

#### New: `/digital-marketing-pro:check` — explicit pre-publish quality gate

Replaces the `PreToolUse Write|Edit` global hook. Wraps `scripts/eval-runner.py` (the master eval orchestrator) and produces a single PASS / WARN / BLOCKED decision with actionable issues. Three modes:

- `/digital-marketing-pro:check <file>` → quick eval (~2s, no external deps): hallucination + content quality + readability
- `/digital-marketing-pro:check <file> --full --brand <slug>` → full 6-dimension eval including brand voice + claims + structure
- `/digital-marketing-pro:check <file> --compliance --brand <slug> --evidence <facts.json> --schema <name>` → compliance-focused for regulated industries

New files:
- `commands/check.md`
- `skills/check/SKILL.md`

#### New: `/digital-marketing-pro:status` — unified on-demand brand snapshot

Replaces the `SessionStart` global hook (which printed a brand summary banner at every Claude Code launch in every project). Richer than the old banner: brand profile, all engagements with current part + days-since-update + pending decisions + versioned doc count, recent insights with last-save age, recent compliance violations, Python dependency mode. Five subcommand modes:

- `/digital-marketing-pro:status` → full snapshot for active brand
- `/digital-marketing-pro:status --quiet` → one-line compact summary
- `/digital-marketing-pro:status --json` → machine-readable JSON for downstream skills
- `/digital-marketing-pro:status --brand <slug>` → snapshot for a specific brand
- `/digital-marketing-pro:status --section <brand|engagements|insights|compliance|deps>` → single section

New files:
- `commands/status.md`
- `skills/status/SKILL.md`
- `scripts/dm-status.py` (560-line script; reads brand profile + engagement state + insights + violations + deps; never modifies state)

#### Embedded mandatory hallucination check in 4 content-producer agents

Replaces the `PreToolUse Write|Edit` global hook with stronger architectural guarantees. Each agent now runs `hallucination-detector.py` on its final draft before delivering content to the user. Severity-based decision rules:
- `severity: "high"` (placeholder URLs, fabricated stats in headlines, made-up academic citations, unsupported "#1" / "best in industry" / "leading" claims) → DO NOT deliver; return issues + suggested fixes
- `severity: "medium"` (unverified body stats, missing hedging, entities-to-verify) → deliver but include warnings inline
- `severity: "low"` → mention; not blocking
- Overall hallucination_score < 60 → flag for revision (PR content uses stricter < 75 threshold)

This is stronger than the v3.0 hook because (a) the check runs on the actual draft the agent intends to deliver, not on every intermediate Write/Edit; (b) the agent has the context to interpret findings appropriately; (c) the check is part of the agent's deliverable contract, not an external gate.

Agents updated:
- `agents/content-creator.md` — Behaviour Rule 12 added
- `agents/email-specialist.md` — Behaviour Rule 11 added
- `agents/social-media-manager.md` — Behaviour Rule 11 added
- `agents/pr-outreach.md` — Behaviour Rule 10 added (with stricter PR-specific thresholds)

#### New: `auto_save_insights` opt-in flag for ambient learning capture

Replaces the `SessionEnd` global hook (which auto-prompted insight saving on every session end across every project). Opt-in per brand:

```json
{
  "auto_save_insights": true,
  "...": "...rest of brand profile..."
}
```

When enabled, marketing agents call `scripts/auto-save-insight.py` at meaningful checkpoints to persist session learnings. When disabled (default), the helper returns `{"status": "no_op"}` — clean no-op, no surprise side effects, no cross-project noise.

New file: `scripts/auto-save-insight.py` (240-line helper with subcommands: save, save with `--force`, `--dry-run`; falls back to direct `insights.json` write if `campaign-tracker.py` cannot resolve the brand).

Atomic writes; honours `CLAUDE_PLUGIN_DATA` env var; respects the same workspace path as `dm-status.py` and `engagement-state.py`.

#### New: `docs/v3.2-opt-ins.md` — comprehensive opt-in guide

Documents:
- What was lost when v3.1 removed each of the four global hooks
- How to re-enable any hook at the user-level (`~/.claude/settings.json`) or project-level (`.claude/settings.local.json`) — this gives users the v3.0 ambient experience without forcing it on the entire plugin user base
- Why the `PreToolUse mcp_.*` matcher should NOT be re-enabled (it intercepts every MCP call from every plugin)
- How `auto_save_insights` works and when to enable it
- How `/digital-marketing-pro:status` and `/digital-marketing-pro:check` map to the removed hooks
- How the embedded agent check is stronger than the v3.0 hook
- Recommended workflow for minimum / opt-in / power-user / project-scoped configurations

#### Plugin manifest

`.claude-plugin/plugin.json` bumped to v3.2.0 with updated description surfacing the new commands, agent updates, opt-in flag, and hook re-enable pattern.

### Compatibility

- All v2.7 + v3.0 + v3.1 capabilities continue to work unchanged
- New skills and scripts are purely additive
- The `auto_save_insights` flag defaults to `false` — opt-in only; existing brand profiles without the flag get no behavioural change
- Hook re-enabling is documented as a user-side action; the plugin still ships zero global hooks

### Migration

No migration needed. To start using the new compensations:

```
# On-demand status snapshot
/digital-marketing-pro:status

# Pre-publish quality gate
/digital-marketing-pro:check drafts/your-content.md --brand <your-slug>

# Enable ambient insight capture (opt-in per brand)
# Edit ~/.claude-marketing/brands/<your-slug>/profile.json:
#   "auto_save_insights": true

# Re-enable v3.0 SessionStart banner at user level (optional)
# Copy SessionStart block from hooks/hooks-reference.example.json into ~/.claude/settings.json
# (Do NOT re-enable the PreToolUse mcp_.* matcher — see docs/v3.2-opt-ins.md)
```

---

## [3.1.1] — 2026-05-03

### Added — Cowork-Compatible Connectors Reference Catalog

The v3.1.0 audit confirmed DMP runs in Anthropic Cowork, but surfaced a documentation gap: the `.mcp.json.example` file ships ~60 stdio/npx MCP servers (Google Analytics, Google Search Console, Google Ads, Meta Marketing, Mailchimp, LinkedIn, TikTok, Salesforce, etc.) — none of which work in Cowork. Cowork users had no documented HTTP path to these services. v3.1.1 adds a reference catalog of HTTP MCP equivalents.

#### New file: [.mcp.json.connectors-reference](.mcp.json.connectors-reference)

Sectioned catalog of 25+ HTTP MCPs covering DMP's full integration surface:

- **First-party marketing MCPs** (already in active `.mcp.json`): HubSpot, Stripe, Klaviyo, Amplitude, Ahrefs, Similarweb — all OAuth, all Cowork-compatible
- **Collaboration & publishing**: Notion, Slack, Asana, Webflow, Canva, Figma, Gmail, Google Calendar
- **Aggregator MCPs for Cowork** — the critical addition. Pipedream entries for Google Analytics, Google Search Console, Google Ads, Google Sheets, Google Drive, Meta Marketing, Mailchimp, LinkedIn, Salesforce, plus a generic template covering Pipedream's 1000+ services. Composio (`https://connect.composio.dev/mcp`), Zapier (`https://mcp.zapier.com/api/v1/connect`), and Make.com as alternatives
- **Image/video generation**: fal-ai, Replicate (covers Stability, Gemini Imagen, FLUX, Recraft, etc.)

Per-entry `_auth` notes document the OAuth flow or API key requirement. Bottom-of-file `_cowork_compatibility_summary` makes the CLI-vs-Cowork mapping explicit.

#### What this means for users

- **Claude Code CLI users**: nothing changes. `.mcp.json.example` still documents the 60+ stdio/npx options, and the active `.mcp.json` (gitignored) still ships the 14 HTTP MCPs you've already configured.
- **Cowork users**: open `.mcp.json.connectors-reference` instead of `.mcp.json.example`. Every category has a Cowork-compatible HTTP path, either via a first-party MCP or via a Pipedream/Composio/Zapier aggregator.

#### Compliance posture

All listed connectors satisfy the [Anthropic Software Directory Policy](https://support.claude.com/en/articles/13145358-anthropic-software-directory-policy): no financial-transaction processing, no advertising delivery, no safety circumvention. All MCPs use OAuth 2.0 or API key auth via the provider's official endpoint.

### Migration

Pure additive release. No breaking changes. Existing connector setups continue to work. Cowork teams gain a documented path for every category previously only available via npx.

---

## [3.1.0] — 2026-05-03

### Changed — Multi-Plugin Coexistence (Removed All Global Hooks)

Audit of the v3.0 install footprint surfaced the same issue that prompted ContentForge v3.9.0 and SocialForge v1.5.0 the same day: Claude Code plugin hooks fire *globally* when the plugin is enabled. There is no per-directory or per-project scoping. DMP's four prior hooks were particularly problematic because one of them — the `PreToolUse mcp_.*` matcher — intercepted EVERY MCP tool call from EVERY installed plugin (Slack, Notion, GitHub MCP, Stripe, anything), forcing a brand-compliance LLM evaluation on every MCP write regardless of whether it had any connection to marketing work.

#### Removed All 4 Global Hooks

[hooks/hooks.json](hooks/hooks.json) now contains an empty `hooks: {}` object plus a `_readme` explaining the rationale. The four prior hooks are preserved with per-hook rationale notes at [hooks/hooks-reference.example.json](hooks/hooks-reference.example.json):

- **SessionStart** — ran `python3 scripts/setup.py --check-deps --summary` on every Claude Code launch in every project. Now run on demand.
- **PreToolUse Write|Edit** — large brand-compliance + hallucination-check prompt fired on every file edit. Compliance and hallucination checks already run inside the agents responsible for generating the marketing content; the hook was a duplicate execution layer with a SKIP guard that still cost a model invocation per edit.
- **PreToolUse mcp_.\*** — the worst offender. Gated every MCP tool call from every plugin through DMP's brand-compliance prompt. A user installing DMP alongside other MCP-using plugins (which is common) saw this prompt fire on every Slack message, every Notion page write, every GitHub PR creation, etc. — even when those operations had nothing to do with marketing. Per-agent decision flows already require explicit user approval for marketing MCP writes.
- **SessionEnd** — insight-saving prompt for marketing work, fired at every session end. Insight capture should be opt-in (run the engagement orchestrator), not automatic.

#### Why It Matters

The mcp_.* matcher meant DMP was effectively becoming a global gatekeeper for every MCP tool call across the user's entire Claude Code installation. That is far beyond DMP's scope of authority. Removing it fixes the most acute multi-plugin coexistence problem in the marketing plugin family.

#### Behavior Preserved

All compliance checks, brand voice enforcement, MCP write approvals, and dependency setup still run — they were always also encoded in the agent files, the engagement orchestrator, and the per-agent decision flows. The hook layer was a duplicate execution path. Removing it produces identical output quality with zero side-effects on other Claude Code work or other installed plugins.

### Migration

No breaking changes to commands, skills, agents, or production behavior. Brand profiles, engagement state, tracking data, and the v3.0 12-Part Methodology are all preserved. If you specifically want a hook back, copy the relevant entry from `hooks/hooks-reference.example.json` into `hooks/hooks.json` — but be aware that the `mcp_.*` matcher will gate every MCP call from every installed plugin.

---

## [3.0.0] — 2026-05-03

### Added — The 12-Part Engagement Methodology

Major release introducing a sequential engagement workflow that transforms the plugin from a catalog of 141 atomic skills into a methodology-driven engagement system. Every brand engagement now runs through 12 canonical parts producing ~50–60 files in a defined structure.

#### New Methodology Layer

- **12-Part Strategy Flow** — sequential engagement workflow from intake through continuous improvement (`skills/context-engine/engagement-flow-methodology.md`)
- **Four Core Documents** — the strategic spine produced in Part 3 with 61 explicit steps across 3.1 Business & SBU Analysis (18 steps), 3.2 Segmentation Framework (15 steps), 3.3 Brand Positioning & Communications (19 steps), 3.4 DMFlow (9 steps) (`skills/context-engine/four-core-documents-spec.md`)
- **Two-Views Model** — v1 unbiased market view + v2 client-validated view; both kept forever for different decision types (`skills/context-engine/two-views-model.md`)
- **Stone vs Opinion intake** — every Part 1 fact tagged with confidence level; Stone facts treated as ground truth, Opinion hypotheses become research questions (`skills/context-engine/stone-vs-opinion.md`)
- **Decision Matrix for v2 Re-runs** — explicit mapping of client validation responses to which Core Documents need re-running (`skills/context-engine/decision-matrix-rerun.md`)
- **Update-Back Rule** — versioning protocol (v2.1, v2.2 etc.) for in-life corrections after Part 7+ (`skills/context-engine/update-back-rule.md`)
- **Living Project Instruction File** — single source of truth per engagement that all skills read first (`skills/context-engine/living-instruction-file-spec.md`)

#### New Strategic Framework References (15 docs)

- **Five Digital Markets** — Search / Profile / Contextual / Marketplace / Utility taxonomy (`skills/context-engine/five-digital-markets.md`)
- **Channel Families** — 7 families covering 17 channels for Part 9 (`skills/context-engine/channel-families.md`)
- **In-Market vs Out-Market** — 3-5% vs 95-97% audience split, budget allocation logic (`skills/context-engine/in-market-out-market.md`)
- **Multi-Dimensional Decision Framework** — weight + score + weighted total for any consequential decision (`skills/context-engine/decision-framework.md`)
- **Unit Economics Framework** — CAC / LTV / LTV:CAC ≥ 3.0 / payback period; foundation for all recommendations (`skills/context-engine/unit-economics-framework.md`)
- **Actionable Persona Format** — 6-question format replacing biographical narratives (`skills/context-engine/actionable-persona-format.md`)
- **B2B Decision-Making Unit** — User / Influencer / Decision-maker / Gatekeeper roles with role-specific messaging (`skills/context-engine/b2b-decision-making-unit.md`)
- **Three-Scenario Forecasting** — Conservative / Moderate / Aggressive for every projection (`skills/context-engine/three-scenario-forecasting.md`)
- **30 / 60 / 90-Day Framework** — Foundation / Validation / Optimisation phasing (`skills/context-engine/30-60-90-framework.md`)
- **Reporting Cadence** — daily / weekly / monthly / quarterly / annual scopes and audiences (`skills/context-engine/reporting-cadence.md`)
- **Fixed vs Variable Budget** — Fixed monthly + Variable reserve mechanism with monthly recommendation conversation (`skills/context-engine/fixed-vs-variable-budget.md`)
- **Competitor 3-Question Output** — what they do well / poorly / are NOT doing — enforced output for every competitor analysis (`skills/context-engine/competitor-3-question-output.md`)
- **India Market Context** — regional context module (DPDP Act, mobile-first, festive seasonality, WhatsApp, vernacular content, INR pricing benchmarks, tier-1/2/3 differentiation) (`skills/context-engine/india-market-context.md`)
- **Growth Plan Template** — canonical 11-section structure for the Part 8 flagship deliverable (`skills/context-engine/growth-plan-template.md`)
- **Yearly Planner Template** — canonical structure for the 12-month operational companion (`skills/context-engine/yearly-planner-template.md`)
- **Monthly Report Template** — 9-section structure with writing principles enforcing insight over data (`skills/context-engine/monthly-report-template.md`)

#### New Engagement Skills (6)

- `engagement-workflow` — the 12-Part orchestrator that owns engagement lifecycle
- `four-core-documents` — produces all 4 Part 3 documents (61 steps); supports `--view v2` for re-runs
- `client-validation-document` — produces the Part 5 deliverable (the "one true stop")
- `growth-plan` — produces the Part 8 flagship 11-section client deliverable
- `yearly-planner` — produces the Part 8 operational 12-month companion
- `continuous-improvement-loop` — Part 12 quarterly briefs and ad-hoc briefs aggregating market + operating signals into product/offering recommendations

#### New Command

- `/digital-marketing-pro:engagement` — entry point with subcommands: `start`, `status`, `next`, `validate`, `re-run-decision`, `update-back`, `lif-show`, `file-tree`, `list-engagements`, `four-core`, `growth-plan`, `yearly-planner`, `loop`

#### New Persistence Script

- `scripts/engagement-state.py` — manages the engagement state, directory tree, Stone/Opinion intake, Decision Matrix evaluation, Update-Back versioning, Living Project Instruction File. 14 subcommands with JSON I/O for skill consumption. Atomic writes; no hand-editing of `_engagement.json` required.

#### New Engagement Directory Structure

Every engagement now lives at:
```
~/.claude-marketing/brands/{brand-slug}/engagements/{engagement-id}/
```
With a canonical 12-part directory tree, v1/v2 split for Parts 3 and 4, persistent reports directory, and the Living Project Instruction File.

#### Plugin Manifest Modernised to 2026 Spec

`.claude-plugin/plugin.json` updated with:
- `$schema` reference for JSON schema validation
- `homepage` and `repository` URLs
- `license` field
- Expanded `keywords` array for marketplace discovery
- Author URL added

### Compatibility

- **All existing v2.7.0 skills, agents, scripts, hooks remain functional and unchanged.** v3.0 is purely additive at the methodology layer.
- The 12-Part workflow uses existing skills as Part-specific producers (e.g., Part 4 uses existing `competitor-analysis`, `audience-intelligence`, `market-intelligence`).
- Engagements are an opt-in workflow. Single-skill invocations (e.g., `/digital-marketing-pro:content-engine` for a one-off blog post) continue to work without an engagement context.

### Migration

No migration needed. Existing brand profiles at `~/.claude-marketing/brands/{slug}/profile.json` continue to work. Engagements are new directories that sit alongside the existing brand state.

To start using the new methodology:
```
/digital-marketing-pro:engagement start <your-brand-slug> <your-engagement-id>
```

---

## [2.7.0] — 2026-03-31

### Changed — Skill Budget, Agent Safety, Execution Safety

Structural quality release addressing plugin best practice audit. No feature changes — all existing functionality preserved.

#### Skill Description Optimization (141 skills)

- All 141 descriptions trimmed to <130 characters (from 130-400+) to fit within the ~15,500 char skill discovery budget
- Preserves trigger intent: "[Verb] [domain]. Use when: [triggers]." pattern
- Previously 140/141 skills exceeded convention — Claude may not have discovered all skills

#### Agent Safety (25 agents)

- `maxTurns` added to all 25 agents — prevents runaway execution
- 10 turns (5 agents), 15 turns (15 agents), 20 turns (5 agents)

#### Execution Safety

- `disable-model-invocation: true` added to `launch-plan` (total: 18 protected skills)

#### Hook Stability

- SessionStart: `timeout 30` wrapper on setup.py prevents session hang

---

## [2.6.0] — 2026-03-30

### Added — SEO Capability Expansion

Closes the gap with dedicated SEO tools by adding 6 new SEO sub-skills, expanded schema markup support, reference documentation, and a new MCP integration. Inspired by capabilities identified in [claude-seo](https://github.com/AgriciDaniel/claude-seo) — adapted to work within the full marketing system architecture with brand context, execution layer, multi-client support, and quality evaluation.

#### New Skills (6)

- **`/digital-marketing-pro:programmatic-seo`** — Programmatic SEO at scale: data source assessment, template engine planning, URL pattern strategy, internal linking automation, thin content safeguards with quality gates (WARNING at 100 pages, HARD STOP at 500), index bloat prevention, and Google's Scaled Content Abuse policy enforcement (June 2025 / August 2025 escalation context)
- **`/digital-marketing-pro:competitor-pages`** — SEO-optimized competitor comparison page generator: "X vs Y" pages, "alternatives to X" pages, "best tools" roundup pages, feature matrix tables. Includes Product/SoftwareApplication/ItemList schema markup, conversion-optimized CTA layouts, keyword targeting formulas, fairness guidelines, and social proof integration
- **`/digital-marketing-pro:image-seo-audit`** — Dedicated image optimization audit: alt text quality, tiered file size thresholds (thumbnail/content/hero), format analysis (WebP/AVIF/JPEG XL status), responsive images (`srcset`/`sizes`), lazy loading validation (flags `loading="lazy"` on LCP images), `fetchpriority="high"` checks, `decoding="async"`, CLS prevention via dimensions, file naming, CDN usage
- **`/digital-marketing-pro:page-seo-analysis`** — Deep single-page SEO analysis: all ranking dimensions for one URL (title, meta, headings, content depth, E-E-A-T, schema detection with deprecation tracking, images, internal links, technical signals, AI search readiness). More granular than site-wide `/digital-marketing-pro:seo-audit`. Use for landing page optimization, content refresh prioritization, or pre-publish quality checks
- **`/digital-marketing-pro:sitemap-manager`** — XML sitemap analysis and generation: parse existing sitemaps for issues (stale lastmod, 404s, noindex conflicts, missing URLs, protocol limit violations), or generate new sitemaps with industry-specific templates (SaaS, ecommerce, local, publisher, agency). Includes sitemap index strategy, robots.txt registration, and compression recommendations
- **`/digital-marketing-pro:seo-plan`** — Comprehensive SEO strategy planning with industry-specific templates: discovery, competitive analysis, architecture design, content strategy, technical foundation, and 4-phase implementation roadmap (Foundation → Expansion → Scale → Authority). Templates for SaaS, ecommerce, local service, publisher/media, and agency business models

#### New Reference Files (2)

- **`schema-templates.json`** — Ready-to-use JSON-LD template library with 12 schema types: VideoObject, BroadcastEvent (LIVE badge), Clip (key moments), SeekToAction (video seek), SoftwareSourceCode, ProductGroup (e-commerce variants), ProfilePage (E-E-A-T), Certification (replaced EnergyConsumptionDetails), OfferShippingDetails, MerchantReturnPolicy, SoftwareApplication, ItemList. Includes deprecation tracker for HowTo (Sept 2023), FAQ (Aug 2023), SpecialAnnouncement (July 2025), EnergyConsumptionDetails (April 2025)
- **`google-seo-reference.md`** — Concise Google SEO quick reference for agents: Search Essentials, E-E-A-T framework (with December 2025 update extending to all competitive queries), Core Web Vitals (INP current, FID removed), schema markup status table, image SEO best practices, AI search optimization signals, spam policies including Scaled Content Abuse and Site Reputation Abuse

#### Updated — schema-generator.py

- **9 new schema types** added: BroadcastEvent, Clip, SeekToAction, SoftwareSourceCode, SoftwareApplication, ProductGroup, ProfilePage, Certification, ItemList, plus dedicated builder functions for each
- **Deprecation warnings** — Automatic warnings when generating HowTo or FAQPage schemas, citing deprecation dates and recommending alternatives
- Total supported types: 18 (was 9)

#### Updated — seo-specialist Agent

- References new skills (programmatic-seo, competitor-pages, image-seo-audit, page-seo-analysis, sitemap-manager, seo-plan) with invocation guidance
- References new reference files (google-seo-reference.md, schema-templates.json)

#### New MCP Integration

- **DataForSEO** — Live SERP data, keyword research, backlink profiles, on-page analysis, content analysis, competitor domain analysis, AI visibility checking, LLM mention tracking. 9 API modules. Added to `.mcp.json.example` with `DATAFORSEO_USERNAME` and `DATAFORSEO_PASSWORD` environment variables

### Summary

| Metric | Before (v2.5.1) | After (v2.6.0) |
|--------|-----------------|-----------------|
| Skills | 135 | 141 |
| Schema types in generator | 9 | 18 |
| SEO-specific commands | ~14 | ~20 |
| MCP integrations | 67 | 68 |
| Reference files | 146 | 148 |

---

## [2.5.1] — 2026-03-05

### Added — Skill Platform Enhancements

- **`argument-hint`** added to all 55 user-invocable skills — provides autocomplete hints in the Skills UI (e.g., `[URL]`, `[brand-name --full]`, `[competitor1, competitor2, ...]`)
- **`disable-model-invocation: true`** added to 17 execution skills — prevents Claude from auto-triggering skills that write to external platforms (publish, send, launch, import, export). Users must explicitly invoke these via `/digital-marketing-pro:skill-name`
- **`evals/evals.json`** added to 3 key skills (campaign-plan, seo-audit, content-engine) — structured test cases with prompts, expected outputs, and quantitative/qualitative assertions for quality benchmarking
- **Fixed** `/digital-marketing-pro:help` skill — added missing `name: help` field in frontmatter (required by Agent Skills spec for skill registration)

### How it works

**Argument hints** appear as placeholder text when a user types `/digital-marketing-pro:` in the Skills UI, showing what arguments each skill accepts. For example, `/digital-marketing-pro:seo-audit` shows `[URL]` and `/digital-marketing-pro:campaign-plan` shows `[product/service description --budget=N]`.

**Execution safety** ensures that skills which write to external platforms (like `/digital-marketing-pro:publish-blog`, `/digital-marketing-pro:send-email-campaign`, `/digital-marketing-pro:launch-ad-campaign`) cannot be triggered by Claude autonomously — the user must explicitly type the slash command. This is a critical safety layer on top of the existing MCP write approval hook.

**Evals** provide reproducible test cases for key skills. Each eval includes a realistic prompt, expected output description, and assertions that can be verified programmatically. Located at `skills/{skill-name}/evals/evals.json`.

---

## [2.5.0] — 2026-02-26

### Added — Commands & Version Consistency

- **7 command files** in `commands/` directory — visible in the Customize panel "Commands" section:
  - `brand-setup` — Set up a new brand profile with voice, audience, competitors, and compliance rules
  - `campaign-plan` — Generate a multi-channel campaign plan with objectives, audience, budget, and KPIs
  - `seo-audit` — Run a comprehensive SEO audit covering technical, on-page, content, E-E-A-T, and link profile
  - `content-engine` — Draft blog posts, ad copy, emails, social, landing pages, and video scripts
  - `performance-report` — Generate marketing performance reports with KPI tracking and anomaly detection
  - `competitor-analysis` — Multi-dimensional competitive analysis across content, SEO, ads, social, and AI visibility
  - `email-sequence` — Design complete email sequences with subject lines, timing, and deliverability guidance
- **New `/digital-marketing-pro:help` skill** — Quick reference with all commands, examples, and troubleshooting

### Fixed

- Updated stale version references across docs (getting-started.md, architecture.md, integrations-guide.md) from v2.2.0/v2.4.0 to v2.5.0

---

## [2.4.0] — 2026-02-25

### Added — Connector Discovery & Onboarding

- **New `/digital-marketing-pro:integrations` skill** — Status dashboard showing all connected vs available MCP connectors, grouped by category (CRM, SEO, advertising, email, social, etc.), with which skills each connector unlocks and quick-win recommendations
- **New `/digital-marketing-pro:connect` skill** — Guided setup for connecting specific services (e.g., `/digital-marketing-pro:connect google-ads`). Provides platform-specific credential instructions, `.mcp.json` configuration, and post-setup verification. Handles HTTP (OAuth) vs npx (API key) connectors differently
- **New `connector-status.py` script** — Backend for connector discovery. Maintains a registry of 45+ connectors across 17 categories, checks `.mcp.json` and environment variables to report connection status, and generates setup guides
- **Updated `CONNECTORS.md`** — Added "Managing connectors" section linking to `/digital-marketing-pro:integrations`, `/digital-marketing-pro:connect`, `/digital-marketing-pro:add-integration`, and `/digital-marketing-pro:credential-switch` skills

### How it works

Users can now discover and manage integrations interactively:
- `/digital-marketing-pro:integrations` — "What's connected? What can I add?"
- `/digital-marketing-pro:connect salesforce` — "Walk me through connecting Salesforce"
- `/digital-marketing-pro:add-integration` — "I have a custom MCP server to add"

All 14 HTTP connectors auto-load on install (Slack, Canva, Figma, HubSpot, etc.) and authenticate via OAuth on first use. The 45+ npx connectors are discoverable through these skills and require API keys.

Skills that depend on connectors already handle missing connections gracefully — they check for connectivity at startup and guide users to setup if not connected.

## [2.3.1] — 2026-02-25

### Fixed

- Added missing YAML frontmatter to `localization-specialist.md` and `quality-assurance.md` agents — without frontmatter, these agents failed to register during plugin installation, potentially causing installation rollback

## [2.3.0] — 2026-02-25

### Changed — HTTP Connector Architecture

This release rebuilds the MCP integration layer to follow Anthropic's official plugin pattern — HTTP-only connectors that work in both Cowork and Claude Code.

- **New `.mcp.json` with 14 HTTP connectors**: Slack, Canva, Figma, HubSpot, Amplitude, Notion, Ahrefs, Similarweb, Klaviyo, Google Calendar, Gmail, Stripe, Asana, Webflow — all `"type": "http"`, all work through Cowork's VM NAT
- **New `CONNECTORS.md`** documenting 12 connector categories with `~~category` placeholder pattern (matching Anthropic's official convention)
- **`.mcp.json.example` preserved** for Claude Code users who want the full 67-server npx configuration
- **Minimal `plugin.json`** — stripped to 4 fields (name, version, description, author) matching Anthropic's official plugin format. Removed non-standard fields: `author.title`, `author.organization`, `author.email`, `author.work_email`, `homepage`, `repository`, `license`, `keywords`
- **Script path resolution** — `setup.py` now outputs the plugin root and scripts directory path at session start, so Claude can resolve relative script paths in both Cowork and Claude Code

### Environment Compatibility

| Feature | Cowork | Claude Code |
|---------|--------|-------------|
| 115 skills, 25 agents | Full | Full |
| HTTP connectors (14) | Full | Full |
| npx/stdio servers (67) | Not available | Full (via .mcp.json.example) |
| Python scripts (64) | Works (Python 3.10 in VM) | Full |
| Persistent brand data | Per-session | Persistent |

## [2.2.1] — 2026-02-24

### Fixed — CLI Contract & Script Bugs
- **CRITICAL: Removed undefined `${CLAUDE_PLUGIN_ROOT}` env var** from all 22+ SKILL.md files, 23 agent files, hooks.json, and 2 documentation files — replaced with relative `scripts/` paths that work across all environments
- **Fixed CLI argument mismatches in 8 SKILL.md files** where script invocation commands did not match actual argparse definitions:
  - eval-content: `--content`/`--type` → `--text`/`--content-type`, `--composite`/`--dimensions` → `--data '{json}'`
  - verify-claims: removed non-existent `--brand` flag, `--content` → `--text`
  - validate-output: removed non-existent `--brand` flag, `--content` → `--text`, `--action detect-schema` → `--action list-schemas`
  - translate-content: `--content` → `--text`, `--source-lang`/`--target-lang` → `--source`/`--target`/`--original`/`--translated`, removed non-existent `--language`
  - localize-campaign: `--content` → `--text`, removed non-existent `--language`
  - eval-suite: `--content` → `--text`, quality-tracker `--action log --content-label --scores --suite-id` → `--action log-eval --data '{json}'`
  - prompt-test: `--content` → `--text`
  - quality-report: `--type` → `--content-type`
- **Fixed content-scorer.py keyword density bug**: multi-word keywords used substring matching (`str.count()`) instead of word-boundary matching — "AI tools" would match inside "AI toolset". Now uses `re.findall()` with `\b` word boundaries
- **Fixed hallucination-detector.py sentence splitting bug**: `re.split(r'(?<=[.!?])\s+', ...)` split on abbreviation periods (Dr., Inc., U.S.) — now requires uppercase letter after split point: `(?<=[.!?])\s+(?=[A-Z])`
- **Fixed hooks.json SessionStart**: replaced fragile compound shell command with nested subshells and `2>/dev/null` (Unix-only) with simple `python scripts/setup.py --check-deps --summary`
- **Fixed custom-mcp-guide.md**: stale "46 MCP servers" count updated to 67

### Fixed — ContentForge Plugin
- **Added YAML frontmatter** (`name` + `description`) to all 10 agent files for Claude Cowork routing compatibility
- **Replaced 5 invented MCP tool names** in Output Manager agent (`mcp_google-drive_list_folders`, `mcp_google-drive_create_folder`, `mcp_google-drive_upload_file`, `mcp_google-sheets_read_row`, `mcp_google-sheets_update_row`) with adaptive MCP approach that checks available tools at runtime

### Changed
- Updated CONTRIBUTING.md verification checklist to reference `scripts/` instead of `${CLAUDE_PLUGIN_ROOT}`
- Updated docs/architecture.md agent template to reference `scripts/` instead of `${CLAUDE_PLUGIN_ROOT}`

## [2.2.0] — 2026-02-13

### Added — Evaluation/QA Layer
- **8 new scripts**: hallucination-detector.py, claim-verifier.py, output-validator.py, eval-runner.py, quality-tracker.py, eval-config-manager.py, prompt-ab-tester.py, language-router.py
- **1 new agent**: quality-assurance — orchestrates multi-dimensional content evaluation
- **7 new eval commands**: eval-content, verify-claims, validate-output, quality-report, eval-config, prompt-test, eval-suite
- **2 new reference files**: eval-framework-guide.md, eval-rubrics.md
- Hallucination detection: pattern-based detection of fabricated statistics, fake URLs, unsubstantiated claims, made-up entities
- Claim verification: cross-check marketing claims against user-provided evidence data
- Output validation: 8 built-in schemas (blog_post, email, ad_copy, social_post, landing_page, press_release, content_brief, campaign_plan)
- Composite eval scoring: 6-dimension evaluation with A+ through F grading and configurable weights per brand
- Quality regression tracking: 30-day rolling baselines with automatic regression detection
- Prompt A/B testing: compare quality scores across content variations with significance detection
- Eval-before-publish gate: execution-coordinator runs eval-runner before creating approval records
- Hallucination scanning added to Write|Edit PreToolUse hook for real-time content checking

### Added — Multilingual Support
- **4 new MCP servers** (67 total): DeepL, Sarvam AI, Google Cloud Translation, Lara Translate
- **1 new agent**: localization-specialist — translation routing, transcreation, cultural adaptation
- **6 new multilingual commands**: translate-content, localize-campaign, language-audit, language-config, multilingual-score, hreflang-check
- **2 new reference files**: multilingual-execution-guide.md, transcreation-framework.md
- Automatic language detection via Unicode script analysis for 35+ languages
- Translation service routing: Indic → Sarvam AI, European → DeepL, CJK → DeepL, broad → Google Cloud
- Translation quality scoring: length ratio, formatting preservation, key term consistency, placeholder integrity
- Transcreation framework: cultural recreation for emotional content with brief templates and quality rubrics
- Cultural adaptation: Hofstede dimensions applied to marketing (social proof, urgency, trust signals per market)
- Multilingual SEO: hreflang auditing, international sitemaps, Baidu/Yandex/Naver optimization guidance
- RTL support for Arabic, Hebrew, Farsi, Urdu
- Indic language expertise: Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi via Sarvam AI
- Language configuration in brand profile: primary/secondary languages, do-not-translate terms, translation preferences, locale formatting

### Changed
- Updated content-creator agent with language awareness (creates in primary_language by default)
- Updated brand-guardian agent with hallucination detection capability
- Updated execution-coordinator agent with eval-before-execution gate
- Added multilingual scoring rubric to scoring-rubrics.md
- Added language fields to brand profile schema in setup.py
- Enhanced Write|Edit hook with hallucination scanning
- Updated plugin.json to v2.2.0 with eval and multilingual keywords

### Totals
- **~402 files** | 115 commands | 25 agents | 64 scripts | 67 MCP servers | 143 reference files

## [2.1.0] — 2026-02-13

### Added — Intelligence, Monitoring & Execution Gaps (~78 new files, ~11 modified)

**MCP Expansion (46 → 63 servers)**
- 7 new CRM MCPs: Odoo, Freshsales, Monday CRM, Microsoft Dynamics 365, Copper, Close, Keap
- 5 new PM/Design MCPs: Jira, Asana, ClickUp, Canva, Figma
- 3 new SEO/Monitoring MCPs: Moz, Google PageSpeed, Brandwatch
- 2 new Marketing Automation MCPs: Marketo, Pardot

**SEO Execution Layer (4 commands + 1 script + 1 ref)**
- Commands: seo-implement, rank-monitor, serp-tracker, redirect-manager
- Script: seo-executor.py — track and execute SEO changes via CMS MCPs
- Reference: seo-execution-guide.md

**Competitor Monitoring System (3 commands + 1 agent + 1 script + 1 ref)**
- Commands: competitor-monitor, share-of-voice, competitor-alerts
- Agent: competitor-intelligence — ongoing competitive scanning with change detection
- Script: competitor-tracker.py — baselines, diff, mentions, SOV, pricing, ads, win/loss
- Reference: competitive-monitoring-guide.md

**GEO Execution & Monitoring (3 commands + 1 script + 1 ref)**
- Commands: geo-monitor, entity-audit, narrative-tracker
- Script: geo-tracker.py — AI visibility auditing across ChatGPT, Perplexity, Gemini, Copilot
- Reference: geo-execution-guide.md

**Advanced Reporting (4 commands + 1 script + 1 ref)**
- Commands: pdf-report, live-dashboard, attribution-report, cohort-analysis
- Script: pdf-generator.py — report generation and scheduling
- Reference: advanced-reporting-guide.md

**Programmatic Gaps (2 ref)**
- native-advertising.md — Taboola, Outbrain, Nativo, TripleLift, Sharethrough
- audio-programmatic.md — Spotify, Pandora, podcast programmatic

**Inter-System Connectivity (2 commands + 1 ref)**
- Commands: data-import, add-integration
- Reference: custom-mcp-guide.md

**Predictive Intelligence (3 commands + 2 agents + 3 scripts + 2 ref)**
- Commands: simulate, what-if, churn-risk
- Agents: marketing-scientist, market-intelligence
- Scripts: revenue-simulator.py, churn-predictor.py, macro-signal-tracker.py
- References: marketing-science-guide.md, market-intelligence-guide.md

**Creative Intelligence (2 commands + 1 script + 1 ref)**
- Commands: creative-health, content-decay-scan
- Script: creative-fatigue-predictor.py
- Reference: creative-intelligence-guide.md

**Compound Intelligence (2 commands + 1 agent + 1 script + 1 ref)**
- Commands: learn, recall
- Agent: intelligence-curator — cross-agent learning hub with confidence scoring
- Script: intelligence-graph.py
- Reference: compound-intelligence-guide.md

**Journey & Growth (3 commands + 1 agent + 2 scripts + 1 ref)**
- Commands: journey-design, loop-detect, dark-funnel
- Agent: journey-orchestrator — cross-channel journey state machines
- Scripts: journey-engine.py, growth-loop-modeler.py
- Reference: journey-growth-guide.md

**Self-Healing Operations (1 command + 1 script + 1 ref)**
- Command: autopilot-status
- Script: campaign-health-monitor.py
- Reference: self-healing-ops-guide.md

**Competitive Narrative (2 commands + 1 script + 1 ref)**
- Commands: narrative-landscape, counter-narrative
- Script: narrative-mapper.py
- Reference: narrative-warfare-guide.md

**Synthetic Audience (2 commands + 1 script + 1 ref)**
- Commands: focus-group, message-test
- Script: audience-simulator.py
- Reference: synthetic-audience-guide.md

**Additional Commands (3)**
- market-weather, intelligence-report, pricing-test

### Changed
- Updated CRM integration guide with 7 new platform field mappings
- Updated plugin.json description and keywords
- Updated README with all new counts and capability sections
- Updated .gitignore with new data directories

## [2.0.0] - 2026-02-12

### Added — Execution Layer
- **26 new slash commands** bringing the total from 42 to 68 — adding a complete execution layer:
  - **Publishing (5)**: `/digital-marketing-pro:publish-blog`, `/digital-marketing-pro:send-email-campaign`, `/digital-marketing-pro:launch-ad-campaign`, `/digital-marketing-pro:schedule-social`, `/digital-marketing-pro:send-report`
  - **CRM & Data (5)**: `/digital-marketing-pro:crm-sync`, `/digital-marketing-pro:lead-import`, `/digital-marketing-pro:pipeline-update`, `/digital-marketing-pro:segment-audience`, `/digital-marketing-pro:data-export`
  - **Monitoring (4)**: `/digital-marketing-pro:performance-check`, `/digital-marketing-pro:campaign-status`, `/digital-marketing-pro:anomaly-scan`, `/digital-marketing-pro:budget-tracker`
  - **Memory & Knowledge (3)**: `/digital-marketing-pro:save-knowledge`, `/digital-marketing-pro:search-knowledge`, `/digital-marketing-pro:sync-memory`
  - **Communication (2)**: `/digital-marketing-pro:send-sms`, `/digital-marketing-pro:send-notification`
  - **Agency Operations (4)**: `/digital-marketing-pro:agency-dashboard`, `/digital-marketing-pro:client-report`, `/digital-marketing-pro:sop-library`, `/digital-marketing-pro:credential-switch`
  - **Brand Team (3)**: `/digital-marketing-pro:team-assign`, `/digital-marketing-pro:region-config`, `/digital-marketing-pro:exec-summary`
- **5 new specialist agents** bringing the total from 13 to 18:
  - `execution-coordinator` — bridges planning and execution with approval workflow
  - `performance-monitor-agent` — live data monitoring, anomaly detection, campaign health
  - `crm-manager` — cross-CRM operations (Salesforce/HubSpot/Zoho/Pipedrive)
  - `memory-manager` — persistent brand knowledge via RAG, knowledge graphs, cross-session memory
  - `agency-operations` — multi-client portfolio management, SOPs, credential profiles, team management
- **8 new Python scripts** bringing the total from 34 to 42:
  - `approval-manager.py` — approval lifecycle (draft → pending → approved → executed)
  - `execution-tracker.py` — audit trail for all platform executions
  - `performance-monitor.py` — metrics aggregation, anomaly detection, baseline management
  - `memory-manager.py` — vector DB/RAG interface, knowledge graph prep, sync orchestration
  - `crm-sync.py` — CRM data preparation, field mapping, deduplication
  - `report-generator.py` — formatted reports for Slack, email, Google Sheets
  - `credential-manager.py` — per-brand credential profiles for agency multi-client management
  - `team-manager.py` — team roles, permissions, approval chains, capacity management
- **7 new reference knowledge files** bringing the total from 117 to 124:
  - `execution-workflows.md` — standard operating procedures for every execution type
  - `approval-framework.md` — risk classification, approval rules, rollback procedures
  - `platform-publishing-specs.md` — platform API requirements and content format specs
  - `memory-architecture.md` — 5-layer persistent memory system design
  - `crm-integration-guide.md` — CRM connection patterns, field mapping, deduplication
  - `agency-operations-guide.md` — multi-client management, portfolio scoring, SOPs, credential isolation
  - `team-roles-framework.md` — role definitions, permission matrix, approval chains, capacity planning
- **28 new MCP server integrations** bringing the total from 18 to 46: Twitter/X, Instagram, LinkedIn Publishing, TikTok Content, YouTube, Pinterest, SendGrid, Klaviyo, Customer.io, Brevo, Mailgun, Zoho CRM, Pipedrive, Mixpanel, Amplitude, BigQuery, Pinecone, Qdrant, Supermemory, Graphiti, Notion, Google Drive, Webflow, Twilio, Intercom, Linear, Optimizely, Supabase
- **Execution safety hook**: New PreToolUse hook with `mcp_.*` matcher that intercepts all MCP write operations — verifies user approval, compliance, budget limits, and consent before allowing any external platform action
- **Human-in-the-loop approval workflow**: Every execution action classified by risk level (low/medium/high/critical) with industry-specific compliance gates and rollback procedures
- **5-layer memory architecture**: Session context → Vector DB RAG (Pinecone/Qdrant) → Temporal knowledge graphs (Graphiti) → Universal agent memory (Supermemory) → Knowledge base (Notion/Google Drive)
- **Agency multi-client operations**: Per-client credential profiles, portfolio health dashboards, SOP library with compliance tracking, team role management with capacity planning
- **Brand team management**: Team roles and permissions, cross-team workflows, regional/market configuration, executive reporting

### Changed
- `plugin.json` updated to v2.0.0 with execution layer description and updated counts
- `.mcp.json` expanded from 18 to 46 server configurations
- `hooks/hooks.json` extended with MCP write safety interceptor
- All documentation updated with v2.0.0 counts and new sections

## [1.9.0] - 2026-02-12

### Added
- **8 new slash commands** bringing the total from 34 to 42 — closing the agency operations gap:
  - `/digital-marketing-pro:client-onboarding` (`skills/client-onboarding/SKILL.md`) — post-sale onboarding workflow with kickoff meeting agenda, discovery questionnaire, stakeholder mapping, access checklist, 30-60-90 day expectations setting
  - `/digital-marketing-pro:qbr-plan` (`skills/qbr-plan/SKILL.md`) — Quarterly Business Review preparation with performance retrospective, strategic recommendations, upsell opportunities, next quarter roadmap
  - `/digital-marketing-pro:media-plan` (`skills/media-plan/SKILL.md`) — holistic paid media planning across channels with flight dates, budget waves, creative rotation, channel allocation, contingency reserves
  - `/digital-marketing-pro:video-script` (`skills/video-script/SKILL.md`) — video marketing script writing for YouTube, TikTok, Instagram Reels, LinkedIn with hook variants, timestamps, visual direction, accessibility
  - `/digital-marketing-pro:executive-dashboard` (`skills/executive-dashboard/SKILL.md`) — C-suite dashboard design with business-outcome north-star metrics, visualization recommendations, alert thresholds, narrative guidance
  - `/digital-marketing-pro:case-study-plan` (`skills/case-study-plan/SKILL.md`) — structured case study creation workflow with CSR framework, interview questions, format variations (PDF/web/slide/video), distribution strategy
  - `/digital-marketing-pro:attribution-model` (`skills/attribution-model/SKILL.md`) — multi-touch attribution setup with model selection (last-touch/first-touch/linear/time-decay/position-based/data-driven/MMM), credit distribution rules, platform implementation guides
  - `/digital-marketing-pro:creative-testing-framework` (`skills/creative-testing-framework/SKILL.md`) — systematic creative testing strategy with testing matrix, holdout controls, sample size per variant, significance thresholds, iteration cadence
- **2 new reference knowledge files** bringing the total from 115 to 117:
  - `skills/paid-advertising/media-planning.md` — media planning framework, channel allocation methodology, flighting strategies (continuous/pulsing/fighting), budget waves, creative rotation cadence, cross-channel synergy
  - `skills/content-engine/video-scripting.md` — platform-specific video formats (YouTube/TikTok/Reels/Shorts/LinkedIn), script structures (AIDA/PAS), 12 hook formulas, timestamp annotation, visual direction, accessibility, CTA placement

### Fixed
- `scripts/setup.py` `create_brand()` function now initializes `insights.json` file when creating new brands — previously this file was referenced by all 13 agents and context-engine but not auto-created, causing errors on first insight save

### Removed
- `.mcp_new.json` — empty orphan file from development
- `mcp_config.json` — legacy 12-server MCP config (replaced by `.mcp.json` in v1.8.0)

### Changed
- `.claude-plugin/plugin.json` version bumped from 1.8.0 to 1.9.0, command count 34 → 42, reference files 115 → 117
- `README.md` updated: version badge 1.8.0 → 1.9.0, command count 34 → 42, reference files 115 → 117, 8 new command rows in commands table, architecture tree updated
- `docs/getting-started.md` version 1.8.0 → 1.9.0, command count and reference file counts updated
- `docs/architecture.md` version 1.8.0 → 1.9.0, file tree updated, file count 233 → 243, command list updated with 8 new entries

## [1.8.0] - 2026-02-12

### Added
- **Marketing Automation module** (`skills/marketing-automation/`) — new dedicated module covering automation workflow design, lead scoring models, nurture sequences, marketing operations, and MAP platform strategy
  - `skills/marketing-automation/SKILL.md` — module definition with workflow design, lead scoring, nurture sequences, and marketing ops capabilities
  - `skills/marketing-automation/automation-workflows.md` — trigger types, 10+ workflow patterns (welcome, abandoned cart, re-engagement, onboarding, win-back), branching logic, cross-channel orchestration
  - `skills/marketing-automation/lead-scoring.md` — explicit and implicit scoring, negative scoring, score thresholds (cold/warm/MQL/SQL), progressive profiling, decay, sales handoff rules
  - `skills/marketing-automation/nurture-sequences.md` — lifecycle stages, 7 sequence types with cadence and content mapping, multi-channel nurture, timing science, template sequences
  - `skills/marketing-automation/marketing-ops.md` — data hygiene, tech stack management, deliverability (SPF/DKIM/DMARC), compliance automation, MAP comparison matrix (HubSpot/ActiveCampaign/Klaviyo/Mailchimp/Marketo/Pardot)
- **15 new reference knowledge files** across 10 existing modules, bringing reference files from 96 to 115:
  - `skills/paid-advertising/microsoft-ads.md` — Bing Ads, Microsoft Audience Network, LinkedIn profile targeting, Import from Google Ads
  - `skills/paid-advertising/retargeting-audiences.md` — audience segments, platform-specific retargeting, sequential messaging, frequency capping, privacy impact
  - `skills/analytics-insights/dashboard-design.md` — dashboard hierarchy (executive/operational/campaign), visualization best practices, alert thresholds, tool recommendations
  - `skills/analytics-insights/clv-analysis.md` — CLV models (historical/predictive/contractual), CLV:CAC ratio, cohort analysis, industry benchmarks
  - `skills/content-engine/personalization.md` — personalization levels, data requirements, email/website/ad personalization, testing personalization, privacy
  - `skills/content-engine/case-studies.md` — CSR framework, interview questions, data presentation, format variations, distribution strategy, industry templates
  - `skills/campaign-orchestrator/sales-enablement.md` — battle cards, sales content mapping to stages, objection handling, proposal templates, content metrics
  - `skills/growth-engineering/experimentation-frameworks.md` — ICE/RICE/PIE scoring, hypothesis format, experiment types, growth experiment categories, velocity
  - `skills/digital-pr/link-building-tactics.md` — 13 link building methods ranked, outreach templates, anchor text strategy, red flags, competitive gap analysis
  - `skills/cro/personalization-testing.md` — segment-based testing, behavioral targeting, dynamic content, holdout testing, testing roadmap
  - `skills/audience-intelligence/customer-research-methods.md` — quantitative and qualitative methods, survey design, JTBD research, win/loss analysis, VoC programs
  - `skills/funnel-architect/sales-marketing-alignment.md` — shared funnel definitions, SLAs, lead handoff, feedback loops, RevOps, shared metrics
  - `skills/reputation-management/review-management-platforms.md` — review platforms by industry, generation strategies, response framework by rating, monitoring tools, legal considerations
  - `skills/emerging-channels/ai-marketing-tools.md` — AI for content/SEO/ads/email/social/analytics/CRO, prompt engineering for marketers, AI governance, cost-benefit
  - `skills/influencer-creator/micro-influencer-strategy.md` — influencer tiers, micro/nano advantages, discovery, vetting, compensation models, gifting programs, scaling
- **6 new MCP integrations** bringing the total from 12 to 18:
  - `tiktok-ads` — TikTok Ads campaign performance, creative insights, audience analytics, Spark Ads data
  - `shopify` — Shopify eCommerce orders, products, customers, inventory, sales analytics
  - `wordpress` — WordPress content publishing, post management, SEO metadata
  - `salesforce` — Salesforce CRM pipeline, opportunity data, lead management, account insights
  - `google-looker-studio` — Google Looker Studio dashboard data, report embedding, cross-platform visualization
  - `activecampaign` — ActiveCampaign email automation, lead scoring, CRM contacts, automation workflows

### Changed
- `.claude-plugin/plugin.json` version bumped from 1.7.0 to 1.8.0, module count 15 → 16, reference files 96 → 115, MCP integrations 12 → 18
- `.mcp.json` expanded with 6 new server entries
- `README.md` updated: version badge 1.7.0 → 1.8.0, module count 15 → 16, new module row, MCP count 12 → 18, 6 new MCP rows, architecture tree updated
- `docs/getting-started.md` version 1.7.0 → 1.8.0, module count and reference file counts updated
- `docs/architecture.md` version 1.7.0 → 1.8.0, file tree updated, file count 213 → 233, module list updated, MCP server list updated

## [1.7.0] - 2026-02-12

### Added
- **10 new slash commands** bringing the total from 24 to 34:
  - `/digital-marketing-pro:keyword-research` (`skills/keyword-research/SKILL.md`) — guided keyword research with clustering, intent mapping, and content gap analysis
  - `/digital-marketing-pro:roi-calculator` (`skills/roi-calculator/SKILL.md`) — campaign ROI calculation with 5 attribution models and budget efficiency ranking
  - `/digital-marketing-pro:ab-test-plan` (`skills/ab-test-plan/SKILL.md`) — A/B test planning with hypothesis framework, sample size calculation, and test duration estimation
  - `/digital-marketing-pro:content-repurpose` (`skills/content-repurpose/SKILL.md`) — content repurposing strategy with derivative format matrix, effort estimates, and publishing calendar
  - `/digital-marketing-pro:retargeting-strategy` (`skills/retargeting-strategy/SKILL.md`) — retargeting campaign architecture with audience segmentation, frequency capping, and creative sequencing
  - `/digital-marketing-pro:martech-audit` (`skills/martech-audit/SKILL.md`) — marketing technology stack audit across 11 functions with overlap detection and gap analysis
  - `/digital-marketing-pro:budget-optimizer` (`skills/budget-optimizer/SKILL.md`) — data-driven budget reallocation with diminishing returns modeling and efficiency ranking
  - `/digital-marketing-pro:client-proposal` (`skills/client-proposal/SKILL.md`) — agency client proposal generation with situation analysis, strategy, scope, timeline, and pricing
  - `/digital-marketing-pro:review-response` (`skills/review-response/SKILL.md`) — brand-aligned review response drafting with tone templates, escalation detection, and multi-variant output
  - `/digital-marketing-pro:webinar-plan` (`skills/webinar-plan/SKILL.md`) — end-to-end webinar planning with promotion timeline, email sequences, and post-event nurture strategy
- **8 new Python scripts** (all zero-dependency, stdlib-only), bringing the total from 26 to 34:
  - `scripts/roi-calculator.py` — campaign ROI with 5 attribution models (last_touch, first_touch, linear, time_decay, position_based), LTV:CAC ratio, budget efficiency ranking
  - `scripts/budget-optimizer.py` — budget reallocation using diminishing returns model (square-root scaling), efficiency-proportional allocation, minimum spend thresholds
  - `scripts/clv-calculator.py` — customer lifetime value with 3 models (simple, contractual, cohort), LTV:CAC health assessment, segment-weighted analysis
  - `scripts/content-repurposer.py` — 9 source content types mapping to 4-8 derivative formats, auto-generated content calendar, ROI multiplier calculation
  - `scripts/review-response-drafter.py` — 5-tier rating response logic, 4 tone modifiers, escalation detection (health/safety, legal, profanity), 3 response variants per review
  - `scripts/ad-budget-pacer.py` — spend pacing with linear projection, trend analysis (7-day moving average, weekend patterns), per-channel pacing, severity classification
  - `scripts/link-profile-analyzer.py` — domain diversity, authority bucketing (5 DA ranges), follow/nofollow ratio, anchor text classification (6 categories), profile health score 0-100
  - `scripts/revenue-forecaster.py` — linear regression + growth rate models, blended forecast, seasonal multipliers, confidence ranges (±15% widening by 3% per month)

### Changed
- **5 agent files updated** with new script references in "Tools & Scripts" section:
  - `agents/analytics-analyst.md` — added roi-calculator.py, clv-calculator.py, budget-optimizer.py, revenue-forecaster.py, ad-budget-pacer.py
  - `agents/media-buyer.md` — added ad-budget-pacer.py, budget-optimizer.py
  - `agents/content-creator.md` — added content-repurposer.py, review-response-drafter.py
  - `agents/marketing-strategist.md` — added roi-calculator.py, budget-optimizer.py, revenue-forecaster.py
  - `agents/seo-specialist.md` — added link-profile-analyzer.py
- `.claude-plugin/plugin.json` version bumped from 1.6.0 to 1.7.0, command count 24 → 34, script count 26 → 34
- `README.md` updated: version badge 1.6.0 → 1.7.0, command count 24 → 34, script count 26 → 34, 10 new command rows in commands table, architecture tree updated
- `docs/getting-started.md` version 1.6.0 → 1.7.0, command count and script count updated
- `docs/architecture.md` version 1.6.0 → 1.7.0, file tree updated with new scripts, file count 195 → 213, command list updated, agent roster updated, dependency tier table updated

## [1.6.0] - 2026-02-12

### Added
- **Technical SEO module** (`skills/technical-seo/`) — new dedicated module covering Core Web Vitals optimization, crawlability audits, site architecture, indexation management, JavaScript SEO, mobile-first indexing, redirect auditing, structured data, and international technical SEO
  - `skills/technical-seo/SKILL.md` — module definition with 12-step audit process
  - `skills/technical-seo/core-web-vitals.md` — LCP, INP, CLS thresholds, causes, fixes, measurement tools, optimization priority framework
  - `skills/technical-seo/crawlability.md` — robots.txt, XML sitemaps, crawl budget, JavaScript rendering, log file analysis, orphan pages
  - `skills/technical-seo/site-architecture.md` — URL structure, internal linking, pagination, faceted navigation, breadcrumbs, site migration planning
  - `skills/technical-seo/indexation.md` — canonical tags, meta robots, index coverage, duplicate content, index bloat, new content indexation
  - `skills/technical-seo/international-seo.md` — hreflang implementation, ccTLD vs subdomain vs subdirectory, geotargeting, localization vs translation, search engine market share by country
- **Local SEO module** (`skills/local-seo/`) — new dedicated module covering Google Business Profile optimization, NAP consistency, citation management, local pack strategy, location pages, multi-location management, and local schema
  - `skills/local-seo/SKILL.md` — module definition with 10-step local SEO audit process
  - `skills/local-seo/gbp-optimization.md` — GBP completeness checklist, categories, attributes, photos, posts, Q&A, insights, suspension prevention
  - `skills/local-seo/citation-management.md` — NAP consistency, citation sources by industry, data aggregators, audit methodology, multi-location citations
  - `skills/local-seo/local-content.md` — local keyword research, location pages, city pages, "near me" optimization, voice search, seasonal content
  - `skills/local-seo/multi-location.md` — multi-location GBP management, store locators, franchise SEO, location opening/closing checklists, hierarchy
- **2 new slash commands**:
  - `/digital-marketing-pro:tech-seo-audit` (`skills/tech-seo-audit/SKILL.md`) — comprehensive technical SEO audit with Core Web Vitals scorecard, crawlability, indexation, site architecture, security, and prioritized fixes
  - `/digital-marketing-pro:local-seo-audit` (`skills/local-seo-audit/SKILL.md`) — local SEO audit with GBP scorecard, NAP consistency report, citation audit, review analysis, and 90-day action plan
- **2 new Python scripts** (both zero-dependency, stdlib-only):
  - `scripts/tech-seo-auditor.py` — URL-level technical SEO checks using `urllib.request`: HTTP status codes, redirect chain detection, meta tag parsing (title, description, canonical, viewport, robots), security headers (HTTPS, HSTS), TTFB measurement, compression detection, scoring (0-100)
  - `scripts/local-seo-checker.py` — NAP consistency analysis with address normalization (18 abbreviation expansions) and GBP profile completeness scoring across 16 weighted fields with industry-specific recommendations

### Changed
- `agents/seo-specialist.md` — added tech-seo-auditor.py and local-seo-checker.py to Tools & Scripts section; added 9 new reference files (5 technical-seo + 4 local-seo) to Reference Files section
- `.claude-plugin/plugin.json` version bumped from 1.5.0 to 1.6.0, module count 13 → 15, script count 24 → 26
- `README.md` updated: version badge 1.5.0 → 1.6.0, module count 13 → 15, command count 22 → 24, script count 24 → 26, reference file count 87 → 96, 2 new module rows in core modules table, 2 new command rows in commands table, architecture tree updated
- `docs/getting-started.md` version 1.5.0 → 1.6.0, module count and command count updated
- `docs/architecture.md` version 1.5.0 → 1.6.0, file tree updated with new modules/commands/scripts, file count 180 → 195, module list and command list updated, agent roster updated, dependency tier table updated

## [1.5.0] - 2026-02-12

### Added
- **9 new domain-specific Python scripts** (all zero-dependency, stdlib-only), bringing the total from 15 to 24 scripts:
  - **Email domain** (3 scripts for `email-specialist` agent):
    - `scripts/email-subject-tester.py` — Score email subject lines for open-rate effectiveness (length, spam triggers, personalization, power words, emoji usage)
    - `scripts/spam-score-checker.py` — Check email content for spam risk indicators (word density, punctuation, caps ratio, link density)
    - `scripts/send-time-optimizer.py` — Recommend optimal email send times by industry and audience type (built-in benchmark tables)
  - **CRO domain** (3 scripts for `cro-specialist` agent):
    - `scripts/sample-size-calculator.py` — Calculate A/B test sample size and estimated test duration (Z-test based, stdlib math)
    - `scripts/significance-tester.py` — Test A/B results for statistical significance (Z-test for proportions + chi-squared, p-value, confidence intervals)
    - `scripts/form-analyzer.py` — Analyze web forms for conversion optimization (field friction scoring, mobile-friendliness, progressive disclosure)
  - **Social media domain** (3 scripts for `social-media-manager` agent):
    - `scripts/hashtag-analyzer.py` — Analyze hashtags per platform (count, length, broad/niche mix, banned hashtag detection)
    - `scripts/posting-time-analyzer.py` — Recommend optimal posting times per platform and industry (built-in engagement data)
    - `scripts/calendar-validator.py` — Validate content calendar structure (frequency, variety, gap detection, weekend coverage)

### Changed
- **7 SKILL.md files updated** with new agent references:
  - 5 command skills gained new agents in "Agents Used" section: `email-sequence` (+email-specialist), `landing-page-audit` (+cro-specialist), `social-strategy` (+social-media-manager), `content-calendar` (+social-media-manager), `funnel-audit` (+cro-specialist)
  - 2 module skills gained new "Agents Used" section: `cro` (+cro-specialist), `emerging-channels` (+social-media-manager)
- **3 agent files updated** with new script references in "Tools & Scripts" section:
  - `agents/email-specialist.md` — Added email-subject-tester.py, spam-score-checker.py, send-time-optimizer.py
  - `agents/cro-specialist.md` — Added sample-size-calculator.py, significance-tester.py, form-analyzer.py
  - `agents/social-media-manager.md` — Added hashtag-analyzer.py, posting-time-analyzer.py, calendar-validator.py
- `.claude-plugin/plugin.json` version bumped from 1.4.0 to 1.5.0, script count 15 → 24
- `README.md` updated version badge and script counts
- `docs/getting-started.md` version 1.4.0 → 1.5.0
- `docs/architecture.md` version 1.4.0 → 1.5.0, file tree updated with 9 new scripts, script tables updated, file count 171 → 180

## [1.4.0] - 2026-02-11

### Added
- **3 new specialist agents** — Email Specialist, CRO Specialist, and Social Media Manager, bringing the total from 10 to 13 agents
  - `agents/email-specialist.md` — deliverability engineering, automation architecture, lifecycle sequences, A/B testing, list hygiene, CAN-SPAM/GDPR/CASL compliance
  - `agents/cro-specialist.md` — landing page optimization, A/B testing methodology, form optimization, pricing psychology, checkout optimization, statistical analysis
  - `agents/social-media-manager.md` — platform-native strategy (8 platforms), content calendars, algorithm optimization, community management, social commerce, UGC curation

### Changed
- **All 13 agents upgraded** from ~30-37 lines to ~100-120 lines each with 5 new functional sections:
  - **Tools & Scripts** — exact CLI commands for calling the plugin's 15 Python scripts with arguments and usage context
  - **MCP Integrations** — which of the 12 MCP servers each agent should query (all marked optional)
  - **Brand Data & Campaign Memory** — which persistent files to load from `~/.claude-marketing/brands/{slug}/`
  - **Reference Files** — which context-engine reference files to consult for each domain
  - **Cross-Agent Collaboration** — specific handoff recommendations between agents
- 8 agents gained **guideline enforcement behavior rules** (marketing-strategist, seo-specialist, media-buyer, analytics-analyst, competitive-intel, pr-outreach, growth-engineer, influencer-manager) — all 13 agents now enforce brand guidelines
- All 13 agents now reference `campaign-tracker.py` for campaign memory and `guidelines-manager.py` for brand guideline loading
- `brand-guardian.md` gained rule 11 (campaign memory pattern analysis) and expanded tool integration (6 scripts)
- `content-creator.md` gained rule 10 (campaign memory) and expanded tool integration (9 scripts)
- `.claude-plugin/plugin.json` version bumped from 1.3.0 to 1.4.0
- `README.md` updated agent count references (10 → 13), version badge
- `docs/getting-started.md` updated agent count references and version
- `docs/architecture.md` updated to v1.4.0 — agent roster expanded, agent definition structure updated with 5 new sections, file counts updated

## [1.3.0] - 2026-02-11

### Added
- **Brand Guidelines System** — persistent per-brand guidelines that go beyond numeric voice scores to capture detailed rules, restrictions, and styles
  - 5 built-in guideline categories: voice & tone, messaging, restrictions, channel styles, visual identity — plus custom guidelines
  - `_manifest.json` index with rule counts, metadata, and category tracking
  - Channel styles override base voice settings per platform (LinkedIn can be formal while Instagram is casual)
  - Automatic enforcement across all 13 modules, 22 commands, and content review
- **Deliverable Templates** — custom output formats for reports, proposals, briefs, and other deliverables
  - Per-brand template storage at `~/.claude-marketing/brands/{slug}/templates/`
  - Commands check for matching templates before using default formats
- **Agency SOPs** — workflow definitions that apply across all clients
  - Stored at `~/.claude-marketing/sops/` (agency-level, not per-brand)
  - Content approval workflows, campaign checklists, escalation procedures, QA processes
- **Guideline Violation Tracking** — `campaign-tracker.py` now tracks guideline violations with severity, category, and suggestions for pattern analysis
- `scripts/guidelines-manager.py` — new CLI script for guidelines, templates, and SOP CRUD operations (stdlib-only, no new dependencies)
- `skills/context-engine/guidelines-framework.md` — reference file for structuring and applying brand guidelines
- `/digital-marketing-pro:import-guidelines` command — interactive import of brand guidelines, restrictions, and channel styles
- `/digital-marketing-pro:import-sop` command — import agency SOPs and workflow definitions
- `/digital-marketing-pro:import-template` command — import deliverable templates for custom output formats
- `docs/brand-guidelines.md` — comprehensive guide for guidelines, templates, and SOPs with worked examples
- Brand Context point 9 in all 13 module SKILL.md files — automatic guideline checking and enforcement
- Guidelines summary line in SessionStart brand output (rule counts, restriction counts, template counts)

### Changed
- All 22 command SKILL.md files: step 1 extended to load guidelines, templates, and SOPs alongside brand profile
- `hooks/hooks.json` SessionStart: now also runs `guidelines-manager.py --action summary` for guideline context
- `hooks/hooks.json` PreToolUse: now checks `restrictions.md` for banned words and restricted claims in content
- `hooks/hooks.json` SessionEnd: now logs guideline violations via `campaign-tracker.py --action save-violation`
- `agents/brand-guardian.md`: added rules 9-10 for guideline restriction checking and SOP compliance verification
- `agents/content-creator.md`: added rule 9 for applying guidelines, messaging framework, and channel styles before writing
- `scripts/setup.py`: `init_memory_dirs()` now creates `sops/` directory; `create_brand()` now creates `guidelines/` and `templates/` subdirectories; `print_brand_summary()` now outputs guidelines summary line
- `scripts/campaign-tracker.py`: added `save-violation` and `get-violations` actions with severity/category filtering
- `docs/getting-started.md`: added section 5 "Importing Your Brand Guidelines" with walkthrough, updated section numbers, added guidelines to Next Steps
- `README.md`: added 3 new commands to Commands table, updated Key Differentiators, updated architecture tree, added Documentation table entry
- `.claude-plugin/plugin.json` version bumped from 1.2.1 to 1.3.0

## [1.2.1] - 2026-02-11

### Added
- Claude Cowork compatibility documentation — full Cowork section in `docs/claude-interfaces.md` with installation instructions, bonus capabilities (document creation, visual review, app integration), setup guide, and comparison with Anthropic's official marketing plugin
- Cowork installation option (Option C) in `README.md` and `docs/getting-started.md`
- Cowork badge in `README.md`
- Plugin Marketplace section in `docs/claude-interfaces.md`

### Changed
- `docs/claude-interfaces.md` rewritten — expanded from 234 to ~350 lines, added Cowork (full support) section, updated Feature Comparison table with 4 columns (Code, Cowork, Desktop, Web), added document creation and visual review rows
- `README.md` title updated: "Claude Code Plugin" → "Claude Code & Cowork Plugin"
- `README.md` "Which Claude Interface?" table updated with Cowork column
- `docs/getting-started.md` prerequisites and installation updated for Cowork, Next Steps links to Cowork guide
- `plugin.json` version bumped from 1.2.0 to 1.2.1

## [1.2.0] - 2026-02-11

### Added
- Rich brand context injection at session start — Claude receives full brand summary (voice, industry, compliance, goals, competitors) automatically
- `print_brand_summary()` function in `setup.py` with `--summary` CLI flag — outputs 15-line brand context
- `## Brand Context (Auto-Applied)` section in all 13 module SKILL.md files — references context-engine reference files
- Explicit brand loading path (`_active-brand.json` → `profile.json`) in all 17 command SKILL.md files
- SessionEnd hook auto-saves marketing insights via `campaign-tracker.py`
- "How It Works" section in README.md (session lifecycle, brand context flow, multi-client workflow)
- Comprehensive documentation suite (`docs/` folder with 10 guides)
- LICENSE file (MIT)
- CHANGELOG.md
- CONTRIBUTING.md

### Fixed
- `brand-voice-scorer.py` graceful fallback — returns structured JSON and `exit(0)` instead of crashing when NLTK is missing
- `content-scorer.py` graceful fallback — same pattern for missing NLTK and textstat dependencies
- SessionStart hook now uses `--summary` flag (was `--check-brand` which only output the brand name)

### Changed
- `hooks.json` SessionStart command: `--check-brand` replaced with `--summary` for rich context injection
- `hooks.json` SessionEnd prompt: simple reminder replaced with auto-save insights workflow
- `setup.py` no-args fallback: calls `print_brand_summary()` instead of `check_brand()`
- `plugin.json` version bumped from 1.1.0 to 1.2.0

## [1.1.0] - 2026-02-10

### Added
- `campaign-tracker.py` — persistent campaign memory with save/retrieve for campaigns, performance snapshots, and insights (200-entry rolling buffer)
- `adaptive-scorer.py` — brand-context-aware content scoring with industry, business model, and goal-based weight adjustments
- `intelligence-layer.md` — documentation of the adaptive learning system architecture
- `/digital-marketing-pro:switch-brand` command for multi-client brand switching
- Quick setup mode in `/digital-marketing-pro:brand-setup` (5 essential questions vs. 17 full questions)
- 12 MCP server integrations (GA4, Google Search Console, Google Ads, Meta, HubSpot, Mailchimp, LinkedIn, SEMrush, Ahrefs, Stripe, Google Sheets, Slack)
- Threads and Bluesky platform support in `social-post-formatter.py`
- Cross-platform SessionStart hook (works on Windows, macOS, Linux)

### Fixed
- Schema alignment: `brand-voice-scorer.py` `normalize_profile()` now correctly converts setup.py integer scale (1-10) to float scale (0.0-1.0)
- `requirements.txt` stripped from 16 packages (~600 MB) to 4 core packages (~15 MB)
- TikTok character limit updated to 4,000 characters
- PreToolUse hook SKIP logic improved — no longer interferes with non-marketing file edits

### Changed
- `plugin.json` version bumped from 1.0.0 to 1.1.0
- SessionEnd hook uses natural language prompt instead of rigid format
- `requirements.txt` reorganized into core and optional dependencies

## [1.0.0] - 2026-02-09

### Added
- Initial release
- 13 marketing modules: Content Engine, Campaign Orchestrator, Paid Advertising, Analytics & Insights, AEO/GEO Intelligence, Audience Intelligence, CRO, Digital PR, Funnel Architect, Growth Engineering, Influencer & Creator, Reputation Management, Emerging Channels
- 19 slash commands (`/digital-marketing-pro:campaign-plan`, `/digital-marketing-pro:ad-creative`, `/digital-marketing-pro:seo-audit`, etc.)
- 10 specialist agents (Marketing Strategist, Content Creator, SEO Specialist, Analytics Analyst, Brand Guardian, Media Buyer, Growth Engineer, Influencer Manager, Competitive Intel, PR Outreach)
- 14 Python execution scripts (setup, scoring, formatting, analysis, generation)
- Context engine with 5 reference files: industry profiles (22 industries), compliance rules (16 jurisdictions), platform specs (20+ platforms), scoring rubrics (7 frameworks), intelligence layer
- 86 reference knowledge files across all modules
- Brand profiling system with persistent storage at `~/.claude-marketing/`
- SessionStart, PreToolUse, and SessionEnd hooks
- `.mcp.json` configuration template for 12 marketing platforms
