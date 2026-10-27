# Model Curator

`scripts/model_registry.json` is the single source of truth for every AI model id that the plugin's scripts hand to a provider SDK. The resolver `scripts/resolve_model.py` reads the registry and answers three questions for the rest of the plugin:

1. "What's the current best model for X?" → `resolve("latest-fast-anthropic")` returns the concrete id.
2. "Is this model id still good?" → `check("claude-sonnet-4-5-20250929")` returns `("deprecated", "claude-sonnet-4-6")`.
3. "What's available?" → `list_models(vendor="google", modality="image-gen")` returns the matching catalog.

This means a single edit to `model_registry.json` propagates to every script the next time it runs — no grep-and-replace across the plugin when a model is deprecated.

---

## Why it exists

Hardcoding model strings like `claude-sonnet-4-5-20250929`, `gemini-2.0-flash`, or `veo-2.0-generate-001` across dozens of scripts means that when a provider deprecates a model the script silently returns 404, the user blames the plugin, and the maintainer has to grep three repos to fix it. The curator removes that failure mode.

---

## How users override the model

Every script that calls a provider model accepts `--model` (or `--openai-model` / `--anthropic-model` for scripts that hit two providers). Pass any id from the registry — or any id, even one the registry doesn't know about. The resolver will:

- **Current id** → pass it through unchanged.
- **Deprecated id** → print a `WARNING` to stderr and silently substitute the registered `replacement_id`.
- **Unknown id** → print a `WARNING` and pass the id through (the call may still work; you just lose the deprecation safety net).
- **No `--model`** → resolve via the script's default alias (e.g. `latest-balanced-anthropic`).

```bash
# Default — uses the registry's latest-balanced-anthropic alias (claude-sonnet-4-6 today)
python scripts/ai-visibility-checker.py --brand acme --mode api

# Override to a specific id
python scripts/ai-visibility-checker.py --brand acme --mode api --anthropic-model claude-opus-4-7

# Pass a deprecated id — script warns and substitutes claude-sonnet-4-6
python scripts/ai-visibility-checker.py --brand acme --mode api --anthropic-model claude-sonnet-4-5-20250929
# WARNING (anthropic): claude-sonnet-4-5-20250929 is deprecated, using claude-sonnet-4-6 instead

# See what's curated
python scripts/ai-visibility-checker.py --list-models
python scripts/resolve_model.py --list --vendor anthropic --status current
```

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

This table is generated from `scripts/model_registry.json`; `tests/test_model_registry_dates.py` fails if it drifts. `latest-video-google` is Veo 3.1 on **Vertex AI only**; the Gemini API's video model is `latest-video-gemini-api` (Gemini Omni, a different call shape: see `param_compatibility_notes.veo_backend`).

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

**Keeping the registry fresh:** `refresh_models.py` calls Evolink's `GET /v1/models` when `EVOLINK_API_KEY` is set.

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
