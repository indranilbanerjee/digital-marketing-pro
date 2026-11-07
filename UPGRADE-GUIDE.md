# Digital Marketing Pro Upgrade Guide

## Upgrading 3.41.0 → 3.42.0

**Nothing migrates. Four behaviours change, all for safety.**

- **The send, publish, launch and sync skills start only when you run them.** `send-email-campaign`, `send-sms`, `send-notification`, `send-report`, `publish-blog`, `schedule-social`, `launch-ad-campaign`, `launch-campaign`, `crm-sync`, `lead-import`, `pipeline-update`, `segment-audience`, `data-import`, `data-export`, `live-dashboard`, `redirect-manager`, `seo-implement`, `credential-switch` and the `execute-action` command are `disable-model-invocation: true`. Asked in plain words, Claude names the command for you to run, for example `/digital-marketing-pro:send-email-campaign`. Each skill's typed `yes` is unchanged.
- **Claude Code asks before each live-write step.** The plugin now ships one hook, `hooks/gate_live_writes.py`. It runs only for commands that name `approval-manager.py` or `connector_executor.py` and answers "ask" for prepare (`--execute`, `--prepare-batch`), `approve`, `create-standing` and fire (`--approval-id`), so you see a prompt even if you saved "Yes, and don't ask again" for the executor. It needs Python on `PATH` as `python3` or `python`, like the scripts themselves.
- **Fewer commands run without a prompt.** Skills that listed bare `Bash` in `allowed-tools` now pre-approve only the named local scripts they run (`dm-status.py`, `engagement-state.py`, `performance-monitor.py` and the like); anything else prompts. `growth-plan`, `yearly-planner`, `four-core-documents` and `commands/engagement.md` pre-approve no shell command at all.
- **`approval-manager.py` and `connector_executor.py` refuse shortened options.** `--exec` or `--act` now exit 2; write `--execute` and `--action` in full.

New, and backward compatible: every JSON option accepts `@<path>` (a file, UTF-8) or `-` (stdin) as well as inline JSON, and the docs now write the JSON to a file first (`--data "@{data_file}"`). `social-post-formatter.py --text` and `competitor-tracker.py --content` accept `@<path>` too (a value that is not an existing file is kept as text). The connector catalogue marks who runs each endpoint (`_operator`), and its `make-com` entry sends the token as an `Authorization: Bearer` header instead of in the URL; if you copied the old URL form, it still works, but it puts the token in logs.

## Upgrading 3.40.0 → 3.41.0

**Nothing migrates, and one script's output changes.** `social-post-formatter.py` now allows 3 hashtags on a Facebook story, not 5, the same advice as a Facebook post (`scripts/platform_specs.json`, facebook.hashtags_advised). A story's 250-character text limit is unchanged but is now labelled a practice: Meta states no limit for story text.

Everything else is new and opt-in: `goldfish-review.py` (`/digital-marketing-pro:check --goldfish`), `crawler-log-report.py` (step 5 of `/digital-marketing-pro:agent-readiness-audit`; its `--refresh-ranges` is the only network call) and the ad-product watch list `scripts/paid_products.json`.

## Upgrading 3.39.1 → 3.40.0 (audit fixes)

**Nothing migrates, and these behaviours are stricter.** Each one used to fail quietly or overwrite something; now it stops and says why. A wrapper or automation that relied on the old behaviour needs the change named here.

- **An existing brand isn't overwritten.** `setup.py --create-brand` exits 2 with `BRAND_EXISTS` when the brand already exists. Pass `--force` to replace it on purpose. Even with `--force`, a slug that belongs to another brand is refused: pick a different name.
- **Non-ASCII brand names get their own folder.**
  - A name in Devanagari, CJK or emoji keeps its ASCII part plus a six-character tag (`भारत Foods` becomes `foods-` plus six characters; a name with no ASCII becomes `brand-` plus six). Before, every such name became `brand`.
  - Plain ASCII names keep the slug they had.
  - A brand created under the old `brand` slug is still found while its profile is that brand. If two brands shared that folder, the second one wrote over the first, and only a backup can bring the first back.
- **Names that would leave the brand folder are refused**, with exit 2:
  - names containing `../`, a colon, or a Windows device name (`NUL`, `CON`, `COM1` and the like);
  - path components over 200 characters.

  This covers campaign ids, report periods, checkpoint extensions, workflow and panel names. A report period such as `Q3: Jul-Sep` is slugged into the file name.
- **The quality gate can block.**
  - `eval-runner.py` now returns `decision`. BLOCKED exits 3: a CRITICAL issue, or a composite under the brand's auto-reject line. Treat exit 3 as "do not publish".
  - The brand's eval settings (minimum scores, weights, auto-reject line) now apply, so a draft that passed before can come back WARN or BLOCKED.
  - A run missing a dimension is `partial`, and its grade is capped at B, or `incomplete` with fewer than two dimensions.
- **Exit codes:**
  - an error result exits 1 (a dozen of them used to exit 0 with an error payload);
  - bad input exits 2;
  - the text scorers exit 4 for nothing to score (`--text ""`) and for a brand with no voice profile;
  - a fallback still exits 0.

  Check the exit code, not only the JSON.
- **JSON options are shape-checked** (`--data`, `--*-json`, `--scenarios`, `--key-points` and the rest). A value of the wrong shape, such as `null`, a list where an object goes, or a bare string, exits 2 naming the option. Before, it ended in a traceback.
- **Connector keys:** the key is refused before any request is made when:
  - a Mailchimp key doesn't end in a data centre (`-us21` and the like);
  - `MAILCHIMP_DC` isn't letters then digits;
  - `SALESFORCE_INSTANCE_URL` isn't `https://<org>.my.salesforce.com` with nothing after the host.

  A request whose host isn't the vendor's is never sent. No key follows a redirect to another host, whether it belongs to a connector, a model provider (the router), the registry refresh or the AI-visibility checker. A vendor endpoint that redirects now gets an unauthenticated request at the new address (expect a 401 there rather than a leaked key), and the checker's SDK calls report the redirect as an error.
- **`agent-readiness-audit --path`** must start with `/`. In Git Bash, set `MSYS_NO_PATHCONV=1` so `/products/` isn't rewritten to a Windows path.
- **`build_skills_index.py`** checks by default and exits non-zero on drift. Pass `--write` to regenerate.

`SECURITY.md` now lists 3.40.x as supported, 3.39.x for trivially backportable fixes, and older minors as unsupported.
