# Model Curator

`scripts/model_registry.json` is the single source of truth for every AI model id that the plugin's scripts hand to a provider SDK. The resolver `scripts/resolve_model.py` reads the registry and answers three questions for the rest of the plugin:

1. "What's the current best model for X?" → `resolve("latest-fast-anthropic")` returns the concrete id.
2. "Is this model id still good?" → `check("claude-sonnet-4-5-20250929")` returns `("deprecated", "claude-sonnet-5-5")`.
3. "What's available?" → `list_models(vendor="google", modality="image-gen")` returns the matching catalog.

This means a single edit to `model_registry.json` propagates to every script the next time it runs — no grep-and-replace across the plugin when a model is deprecated.

---

## Why it exists

Hardcoding model strings like `claude-sonnet-4-5-20250929`, `gemini-2.0-flash`, or `veo-2.0-generate-001` across dozens of scripts means that when a provider deprecates a model the script silently returns 404, the user blames the plugin, and the maintainer has to grep three repos to fix it. The curator removes that failure mode.

---

## How the plugin picks a model

The only DMP script that calls a model provider itself is `scripts/ai-visibility-checker.py` (API mode). Both of its legs now take their model from the router below; the registry is their offline fallback. The resolver (`resolve_model.py`) remains the registry's API: `resolve`, `check` and `list_models`, used offline and by the sibling plugins.

```bash
# Default: each leg's model is chosen from the provider's live list
python scripts/ai-visibility-checker.py --brand acme --mode api

# The registry: what's curated, and what an alias or a deprecated id resolves to offline
python scripts/ai-visibility-checker.py --list-models
python scripts/resolve_model.py --list --vendor anthropic --status current
```

---

## The model router (both legs of the AI-visibility checker, plus a Google adapter)

`scripts/model_router.py` stops depending on model names for the decision. A job in `scripts/model_hints.json` names a provider and a model **line** or **family**, plus the capabilities it needs, never an id; every rule carries the page it was read from and the date. At run time the router lists the models the key can use (GET `/v1/models` at Anthropic and OpenAI, GET `/v1beta/models` at Google) and picks the newest model in the line or family that is current, generally available (no preview, exp, beta, alpha or rc id, no moving `latest` alias, no dated snapshot, no fine-tune) and at least 14 days old. The registry alias (`default_alias`) is the fallback, used only offline.

- **Anthropic** (`ai-visibility.probe.anthropic`, line `sonnet`): the list reports each model's `lifecycle`, `line`, `created_at`, `retires_at` and capabilities, so lifecycle is fully automatic.
- **OpenAI** (`ai-visibility.probe.openai`, family `gpt-<version>-sol`): the list gives only `id`, `created`, `owned_by` and, when announced, `shutdown_date`. Selection is by family pattern over ids, highest version first. Lifecycle comes from that `shutdown_date` plus the `deprecations.openai` record an agent read from OpenAI's deprecations page into the hint book, with its source and date. The router names the record in its warnings once it is more than 30 days old. Fine-tuned models (`ft:BASE:org::id`) follow their base model's schedule, as OpenAI states, and are never picked or cached.
- **Google** (no DMP job; this file is the canonical copy that [SocialForge](https://github.com/indranilbanerjee/socialforge) copies byte for byte for `index-assets`): `models.list` gives each model's `name` (`models/<id>`), `version`, token limits and `supportedGenerationMethods`, with no lifecycle and no release date. Previews, experimental ids and moving `latest` aliases are mixed in. A Google job names a family pattern and must list the generation methods it calls as its `capabilities` (for example `generateContent`), which the list must report for the model. The key goes only in the `x-goog-api-key` header. Google's own curl examples put it in the URL as `?key=`, where proxies and server logs keep it.
  - Lifecycle **and** release dates come from the `deprecations.google` record, read from [Google's deprecations page](https://ai.google.dev/gemini-api/docs/deprecations), with its source and date. One entry per model row, every field optional:

    | Field | From the page |
    |---|---|
    | `released` | Release date, `YYYY-MM-DD`; `YYYY-MM` when the page gives only a month (counted from the month's last day) |
    | `shutdown` | The page's shutdown date, which it defines as the **earliest possible** one |
    | `shut_down` | `true` for the rows the page greys out as already shut down |
    | `replacement` | Recommended replacement |
    | `redirects_to` | The model an endpoint now routes its requests to ("the endpoint is not shutting down and automatically routes API requests to …") |

  - The router reads those fields like this:
    - `shut_down`: retired, and refused if asked for by name.
    - `redirects_to`: never picked. Asked for by name, it is sent with a warning that the answer comes from the other model.
    - A `shutdown` date still in the future: deprecated. Asked for by name, it is kept with a warning.
    - A `shutdown` date already past on a row the page doesn't grey out: kept with a warning that it may stop at any time, not refused.
    - A listed model missing from the record has no known release date, so the 14-day rule can't clear it. A newer one held back this way is named in a warning until the record is re-read.
- One list call per provider per 7 days per key name serves every job; the cache (`model-router-cache.json`) is keyed by the environment variable's name and holds chosen ids, lifecycle dates and counts, never the key, the list or a fine-tune's name. `MODEL_ROUTER_OFFLINE=1` makes no call.
- A model asked for by name (`--anthropic-model`, `--openai-model`) is kept if current, kept with a warning if deprecated, and refused with exit 2 if retired, naming the replacement. Nothing is swapped silently.
- A rejected key or an empty list stops the run before any probe is sent (exit 2). A timeout, provider trouble, an Anthropic list without lifecycle fields, or a list still going after 20 pages falls back to the registry alias and tags the output `offline`. A partial list is never used: it would make a listed model look unlisted.
- Offline, a model asked for by name is checked against two local sources instead of the live list: the shipped registry and the hint book's deprecations record for that provider.
  - Each is read as the live path reads it. Deprecated warns with its retirement date and replacement. Past its shutdown (OpenAI), or `shut_down` on Google's page, it is refused (exit 2). A Google `redirects_to` warns that the answer comes from the other model.
  - Where the two disagree, the stricter one wins, and the message names its source: "according to the shipped registry", or "according to the hint book's google deprecations record (read 2026-10-27)".
  - An undated id such as `claude-sonnet-4-5` matches its one dated snapshot in the registry.
  - The router's CLI resolves the job's `default_alias` in the registry when `--default-model` is omitted.
- When the record describes a different service than the call goes to, the caller passes `record_applies=False` (CLI: `--ignore-deprecations-record`). [SocialForge](https://github.com/indranilbanerjee/socialforge)'s Vertex AI runs do this, because Vertex retires Gemini models on its own schedule. The record is then ignored for that call, live and offline, and no cache is read or written.
- The run's output carries `model_routing.anthropic` and `model_routing.openai`: the model asked for, the model sent, where the answer came from (`live`, `cache`, `requested` or `offline`) and when.

```bash
# Ask for deprecated models by name: kept, with a warning naming the replacement
python scripts/ai-visibility-checker.py --brand acme --mode api --anthropic-model claude-sonnet-4-5-20250929
# WARNING (anthropic): claude-sonnet-4-5-20250929 is deprecated and retires 2026-11-30; the router would choose claude-sonnet-5-5. Keeping claude-sonnet-4-5-20250929 because it was asked for by name.
python scripts/ai-visibility-checker.py --brand acme --mode api --openai-model gpt-4o-2024-08-06
# WARNING (openai): gpt-4o-2024-08-06 is deprecated and retires 2027-01-14; openai's deprecations page names gpt-6-luna as its replacement. Keeping gpt-4o-2024-08-06 because it was asked for by name.
```

A replacement taken from a deprecations record is the vendor's recommendation and is named as such. It can differ from the router's own pick: for `gpt-4o-2024-08-06` OpenAI recommends GPT-6 Luna, while the job's family pick is GPT-6.1 Sol. Before 3.39.0 both cases read "the router would choose".

When Sonnet 4.5 retires on 2026-11-30, a job with no model named keeps working without a registry edit, and a run that names Sonnet 4.5 stops with the replacement in the message.

---

## Aliases (the public API for "give me the latest X")

| Alias | Resolves to (registry, 2026-10-27) |
|---|---|
| `latest-text-anthropic` | `claude-opus-5-5` (Claude Opus 5.5) |
| `latest-balanced-anthropic` | `claude-sonnet-5-5` (Claude Sonnet 5.5) |
| `latest-fast-anthropic` | `claude-haiku-5-5` (Claude Haiku 5.5) |
| `latest-text-openai` | `gpt-6-astra` (GPT-6 Astra) |
| `latest-balanced-openai` | `gpt-6.1-sol` (GPT-6.1 Sol) |
| `latest-fast-openai` | `gpt-6-luna` (GPT-6 Luna) |
| `latest-image-openai` | `gpt-image-2.5-sunburst` (GPT Image 2.5 Sunburst) |
| `latest-text-google` | `gemini-4-argon` (Gemini 4 Argon) |
| `latest-balanced-google` | `gemini-3.8-flash` (Gemini 3.8 Flash) |
| `latest-fast-google` | `gemini-3.5-flash-lite` (Gemini 3.5 Flash-Lite) |
| `latest-vision-google` | `gemini-3.8-flash` (Gemini 3.8 Flash) |
| `latest-multimodal-google` | `gemini-omni-1.1-flash` (Gemini Omni Flash 1.1) |
| `latest-image-google` | `gemini-3-pro-image` (Nano Banana Pro (Gemini 3 Pro Image)) |
| `latest-image-balanced-google` | `gemini-nano-banana-2.1` (Nano Banana 2.1) |
| `latest-image-edit-google` | `gemini-3-pro-image` (Nano Banana Pro (Gemini 3 Pro Image)) |
| `latest-image-photoreal-google` | `gemini-3-pro-image` (Nano Banana Pro (Gemini 3 Pro Image)) |
| `latest-video-google` | `veo-3.1-generate-001` (Veo 3.1) |
| `latest-video-gemini-api` | `gemini-omni-1.1-flash` (Gemini Omni Flash 1.1) |
| `latest-video-wavespeed` | `kwaivgi/kling-v3.0-pro/image-to-video` (Kling v3.0 Pro (image-to-video)) |
| `latest-image-character-higgsfield` | `higgsfield-soul-v2` (Higgsfield Soul v2) |
| `latest-text-evolink` | `gpt-5.2` (GPT-5.2) |
| `latest-balanced-evolink` | `deepseek-chat` (DeepSeek Chat (V3)) |
| `latest-fast-evolink` | `deepseek-v4-flash` (DeepSeek V4 Flash) |
| `latest-tts-openai` | `gpt-realtime-2.1-mini` (GPT-Realtime-2.1 mini) |
| `latest-stt-openai` | `gpt-transcribe` (GPT Transcribe) |
| `latest-tts-elevenlabs` | `eleven_v4` (Eleven v4) |
| `latest-stt-elevenlabs` | `scribe_v2` (Scribe v2) |
| `latest-tts-sarvam` | `bulbul:v3` (Bulbul v3) |
| `latest-stt-sarvam` | `saaras:v4` (Saaras v4) |

This table is generated from `scripts/model_registry.json`; `tests/test_model_registry_dates.py` fails if it drifts. `latest-video-google` is Veo 3.1 on **Vertex AI only**; the Gemini API's video model is `latest-video-gemini-api` (Gemini Omni, a different call shape: see `param_compatibility_notes.veo_backend`).

**Speech kinds are pins with an expiry.** No vendor list endpoint tells a speech model from a chat model, so the `text-to-speech` and `speech-to-text` entries are not discovered: each carries `pinned_on` and `pin_expires` (at most 92 days apart), and the weekly dated check fails once a pin expires, so someone re-reads the vendor page and re-pins. Three facts from the 2026-10-27 read change how callers work, not just which id they send:

- OpenAI shuts down every `/v1/audio/speech` model (`tts-1`, `tts-1-hd`, `gpt-4o-mini-tts`) on **2027-01-06**. Its replacement, `gpt-realtime-2.1-mini`, runs only on the Realtime API, so OpenAI text-to-speech needs a Realtime client.
- OpenAI's `whisper-1` and `gpt-4o-transcribe` shut down on **2027-02-26**; `gpt-transcribe` takes the same `/v1/audio/transcriptions` call.
- Sarvam's `/speech-to-text` accepts only `saaras:v4` and `saaras:v3` now; `saarika:v2.5` is deprecated. Send `mode="transcribe"` for a plain transcript.

Run `python scripts/resolve_model.py --aliases` to list the live mappings.

---

## ⚠ Parameter compatibility — every Anthropic model (API version 2026-10-21)

**From Anthropic API version 2026-10-21, `temperature`, `top_p` and `top_k` are removed for every model:** a request that sends any of them returns HTTP 400, even at the default value. On the older 2023-06-01 version, Claude 4.7 and later (Opus 4.7, 4.8, 5, 5.5, Sonnet 5, 5.5, Fable 5, 5.1, Haiku 5.5) already reject a non-default value.

Omit all three on every Anthropic call; use prompting (and on Claude 5, the `effort` parameter) to guide behaviour. Plugins call current Anthropic models through aliases such as `resolve_model("latest-text-anthropic")`. Run `python scripts/resolve_model.py --check-params script.py` to scan a file: it flags `temperature` / `top_p` / `top_k` anywhere in a file that names a Claude model id or a `latest-*-anthropic` alias.

**Claude Fable 5 refusal handling:** Fable 5's safety classifiers can decline a request with `stop_reason: "refusal"` returned as a **successful HTTP 200** — not an error. Handle it explicitly: pass the server-side `fallbacks` parameter (or retry client-side on another Claude model, e.g. `claude-opus-5`); refused requests aren't billed, and fallback credit refunds the prompt-cache cost of switching.

Sources: [Claude model deprecations — API parameter deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations) · [Introducing Claude Fable 5](https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5-and-claude-mythos-5).

---

## Evolink vendor

[EvoLink](https://evolink.ai) is a multi-provider API gateway that aggregates models from OpenAI, Anthropic, Google, DeepSeek, Doubao, MiniMax, and more through a single API key. The `evolink` vendor entries in the registry cover models that are **primarily or exclusively accessible through Evolink** — DeepSeek, Doubao, MiniMax families — plus Evolink's own `evolink-auto` smart router.

**API compatibility:** OpenAI-compatible (`https://direct.evolink.ai/v1/chat/completions`). Set `EVOLINK_API_KEY` in your environment. Models from other vendors (GPT-5, Claude, Gemini) already tracked under `openai`/`anthropic`/`google` are also proxied by Evolink — use the existing vendor entries and configure the Evolink endpoint as the base URL for those SDKs.

**Keeping the registry fresh:** `refresh_models.py` calls Evolink's `GET /v1/models` when `EVOLINK_API_KEY` is set. Evolink's docs don't describe that endpoint; it answers in OpenAI's shape, so the script reads one page, or follows `has_more`/`last_id` if it ever sends them.

```bash
# See all Evolink-curated models
python scripts/resolve_model.py --list --vendor evolink

# Resolve an Evolink alias
python scripts/resolve_model.py --alias latest-text-evolink

# Poll Evolink's live model catalog
EVOLINK_API_KEY=... python scripts/refresh_models.py
```

---

## Keeping the registry fresh

Frontier model landscape shifts roughly every 6 weeks. Treat any entry older than 3 months as suspect.

```bash
# Check how stale the registry is
python scripts/resolve_model.py --registry-age
# -> last_updated: 2026-07-12. next_review_due: 2026-09-10

# Poll the provider catalogs and report drift (no writes)
ANTHROPIC_API_KEY=... OPENAI_API_KEY=... GEMINI_API_KEY=... EVOLINK_API_KEY=... python scripts/refresh_models.py

# After a manual curation pass, bump the timestamp
python scripts/refresh_models.py --bump-timestamp
```

The drift report reads every page of each list (Anthropic's default page is 20 models, Google's 50) with the model router's own readers. A list still going after 20 pages is reported as skipped, never as a short list. Each key goes only in its provider's header, never in a URL, and a refused call is reported by its HTTP status alone, never with the provider's error message, which can echo part of the key. Before 3.39.0 the Gemini call put the key in the URL, and a model on page two of a list was reported STALE.

The drift report shows:
- **NEW** — model ids the provider lists that are not in your registry (triage and add).
- **STALE** — model ids in your registry marked `current` that the provider no longer lists.

The script never auto-rewrites entries; curation is a human decision.

---

## Adding a new model

Edit `scripts/model_registry.json`. Minimum fields:

```json
{
  "id": "claude-opus-4-8",
  "vendor": "anthropic",
  "family": "claude",
  "display_name": "Claude Opus 4.8",
  "tier": "frontier",
  "modality": ["text", "vision"],
  "status": "current",
  "released": "2026-07",
  "best_for": ["complex reasoning", "agentic workflows"]
}
```

Then either point the relevant alias at the new id, or leave the alias alone and let users opt in via `--model`.

## Deprecating a model

Change `status` to `"deprecated"` and add `replacement_id`. The resolver will auto-fall-forward for any script that resolves through an alias OR through `--model` validation.

```json
{
  "id": "claude-sonnet-4-5-20250929",
  "vendor": "anthropic",
  "status": "deprecated",
  "replacement_id": "claude-sonnet-4-6"
}
```
