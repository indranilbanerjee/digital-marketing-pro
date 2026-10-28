#!/usr/bin/env python3
"""Framework for checking brand mentions in AI responses (manual or API mode).

Model selection: scripts/model_router.py picks each leg's model from the
provider's own live list (GET /v1/models) for a job in scripts/model_hints.json,
never by name:
  * Anthropic (`ai-visibility.probe.anthropic`): the newest active, generally
    available model in the job's line, at least 14 days old.
  * OpenAI (`ai-visibility.probe.openai`): the highest version in the job's
    family pattern that is listed for the key, has no shutdown date (from the
    list or the hint book's deprecations record), is no preview, snapshot or
    fine-tune, and is at least 14 days old.
One list call per provider per 7 days per key name, cached in
model-router-cache.json; MODEL_ROUTER_OFFLINE=1 makes no call and uses the
registry aliases `latest-balanced-anthropic` / `latest-balanced-openai`.
--anthropic-model / --openai-model ask for a model by name: kept if current,
kept with a warning if deprecated, refused (exit 2) if retired, naming the
replacement.
"""

import argparse
import json
import os
import sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402
import model_router  # noqa: E402

ANTHROPIC_JOB = "ai-visibility.probe.anthropic"
OPENAI_JOB = "ai-visibility.probe.openai"

# Curator: the registry alias each job falls back to offline
try:
    from resolve_model import resolve as _resolve_model, get_registry as _get_registry
except ImportError:  # pragma: no cover — curator should always be present
    _resolve_model = lambda alias_or_id, **_: alias_or_id  # type: ignore
    _get_registry = lambda: None  # type: ignore


def no_redirect_http_client(sdk, **kwargs):
    """An HTTP client for a vendor SDK that never follows a redirect. The openai and anthropic SDKs
    follow redirects by default, and httpx strips only Authorization when a redirect leaves the
    origin: Anthropic's x-api-key header would go to the new host. API endpoints don't redirect, so
    a 3xx comes back as an error instead."""
    factory = getattr(sdk, "DefaultHttpxClient", None)
    if factory is None:  # an SDK older than the pinned one: treated like a missing SDK
        raise ImportError(f"{sdk.__name__} is too old to turn redirects off; install the version in "
                          f"_common.PINNED_DEPENDENCIES")
    return factory(follow_redirects=False, **kwargs)


def _route(job, provider, credential_name, override, api_key, anthropic_version=None, fetch=None, now=None):
    """The model for one leg, chosen from the provider's live list by
    scripts/model_router.py. Raises model_router.RouterError when no request
    should be sent (a rejected key, an empty list, a retired model asked for).
    Offline, the shipped registry stands in for the list's lifecycle data."""
    hints_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_hints.json")
    with open(hints_path, encoding="utf-8-sig") as f:
        hints = json.load(f)
    return model_router.route(
        job, hints, provider=provider, credential_name=credential_name, api_key=api_key,
        default_model=_resolve_model(hints["jobs"][job]["default_alias"]), requested=override,
        fetch=fetch, cache_path=_common.workspace_root() / "model-router-cache.json", now=now,
        anthropic_version=anthropic_version, registry=_get_registry())


def route_anthropic(override, api_key, anthropic_version, fetch=None, now=None):
    return _route(ANTHROPIC_JOB, "anthropic", "ANTHROPIC_API_KEY", override, api_key,
                  anthropic_version=anthropic_version, fetch=fetch, now=now)


def route_openai(override, api_key, fetch=None, now=None):
    return _route(OPENAI_JOB, "openai", "OPENAI_API_KEY", override, api_key, fetch=fetch, now=now)


def _report(provider, routing):
    for warning in routing["warnings"]:
        print(f"WARNING ({provider}): {warning}", file=sys.stderr)
    if routing["offline"]:
        print(f"NOTE ({provider}): {routing['reason']}; using the shipped default {routing['model']}",
              file=sys.stderr)

# Query templates organized by category
QUERY_TEMPLATES = {
    "recommendation": [
        "What is the best {industry} {product_type}?",
        "Can you recommend a good {product_type}?",
        "What {product_type} should I use for {use_case}?",
        f"Top {{product_type}} for {{industry}} in {datetime.now().year}",
    ],
    "comparison": [
        "{brand} vs competitors",
        "Is {brand} any good?",
        "What are alternatives to {brand}?",
        "{brand} compared to other {product_type}",
    ],
    "informational": [
        "What does {brand} do?",
        "Tell me about {brand}",
        "How does {brand} work?",
        "{brand} features and pricing",
    ],
    "problem_solving": [
        "How to solve {pain_point}?",
        "Best tools for {use_case}",
        "How do I {use_case}?",
    ],
}

SCORING_TEMPLATE = {
    "mentioned": {"score": 1, "label": "Brand was mentioned"},
    "recommended": {"score": 3, "label": "Brand was recommended or suggested"},
    "first_mentioned": {"score": 5, "label": "Brand was the first mentioned"},
    "detailed_description": {"score": 4, "label": "Brand received a detailed positive description"},
    "not_mentioned": {"score": 0, "label": "Brand was not mentioned at all"},
    "mentioned_negatively": {"score": -2, "label": "Brand was mentioned negatively"},
}

AI_PLATFORMS = [
    {"name": "ChatGPT", "url": "https://chat.openai.com", "note": "Test with the default model chatgpt.com shows when you sign in (it changes; read the model picker)"},
    {"name": "Claude", "url": "https://claude.ai", "note": "Anthropic's AI assistant"},
    {"name": "Perplexity", "url": "https://perplexity.ai", "note": "AI search engine with citations"},
    {"name": "Google AI Overview", "url": "https://google.com", "note": "Look for AI-generated summaries in search results"},
    {"name": "Microsoft Copilot", "url": "https://copilot.microsoft.com", "note": "Microsoft's AI assistant"},
]


def generate_queries(brand, queries=None, industry="", product_type="", use_case="", pain_point=""):
    """Generate a comprehensive list of queries to test."""
    if queries:
        return [q.strip() for q in queries if q.strip()]

    generated = []
    fill = {
        "brand": brand,
        "industry": industry or "[your industry]",
        "product_type": product_type or "[your product type]",
        "use_case": use_case or "[your use case]",
        "pain_point": pain_point or "[customer pain point]",
    }

    for category, templates in QUERY_TEMPLATES.items():
        for template in templates:
            try:
                query = template.format(**fill)
                generated.append({"query": query, "category": category})
            except KeyError:
                pass

    return generated


def build_manual_checklist(brand, queries, competitors=None):
    """Build a manual testing checklist with scoring template."""
    checklist = {
        "brand": brand,
        "instructions": (
            "Run each query below on each AI platform. For every response, "
            "record the scoring outcome using the scoring_guide. Track results "
            "in the results_template spreadsheet format."
        ),
        "ai_platforms": AI_PLATFORMS,
        "scoring_guide": SCORING_TEMPLATE,
        "queries_to_test": queries,
        "results_template": {
            "columns": ["query", "platform", "brand_mentioned", "position",
                        "sentiment", "competitors_mentioned", "score", "notes"],
            "example_row": {
                "query": queries[0]["query"] if queries and isinstance(queries[0], dict) else queries[0] if queries else "",
                "platform": "ChatGPT",
                "brand_mentioned": True,
                "position": "1st",
                "sentiment": "positive",
                "competitors_mentioned": competitors or [],
                "score": 5,
                "notes": "Brand was recommended first with detailed description",
            },
        },
        "competitor_tracking": {
            "competitors": competitors or ["[competitor 1]", "[competitor 2]", "[competitor 3]"],
            "note": "Track how often competitors appear vs your brand",
        },
        "summary_metrics": {
            "visibility_score": "Sum of all scores / (number of queries x platforms x max score per query) x 100",
            "mention_rate": "Queries where brand mentioned / total queries x 100",
            "first_position_rate": "Queries where brand is first / queries where brand mentioned x 100",
            "sentiment_breakdown": "Count of positive / neutral / negative mentions",
        },
    }
    return checklist


def run_api_mode(brand, queries, competitors=None, openai_model_override=None, anthropic_model_override=None):
    """Attempt to run queries via available AI APIs."""
    results = []
    api_available = False
    missing_sdks = []  # a key is set but its SDK is not installed

    model_routing = {}

    # Check for OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            import openai
            client = openai.OpenAI(api_key=openai_key, http_client=no_redirect_http_client(openai))
            routing = route_openai(openai_model_override, openai_key)
            openai_model = routing["model"]
            _report("openai", routing)
            model_routing["openai"] = routing
            api_available = True
            for q in queries:
                query_text = q["query"] if isinstance(q, dict) else q
                try:
                    response = client.chat.completions.create(
                        model=openai_model,
                        messages=[{"role": "user", "content": query_text}],
                        max_tokens=500,
                    )
                    answer = response.choices[0].message.content
                    brand_lower = brand.lower()
                    mentioned = brand_lower in answer.lower()
                    competitors_found = []
                    if competitors:
                        for comp in competitors:
                            if comp.lower() in answer.lower():
                                competitors_found.append(comp)

                    results.append({
                        "query": query_text,
                        "platform": f"OpenAI {openai_model}",
                        "brand_mentioned": mentioned,
                        "competitors_mentioned": competitors_found,
                        "response_excerpt": answer[:300] + ("..." if len(answer) > 300 else ""),
                    })
                except Exception as e:
                    results.append({
                        "query": query_text,
                        "platform": f"OpenAI {openai_model}",
                        "error": str(e),
                    })
        except ImportError:
            missing_sdks.append("openai")

    # Check for Anthropic
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key, http_client=no_redirect_http_client(anthropic))
            # The list call carries the same anthropic-version as the generation call.
            version = (getattr(client, "default_headers", None) or {}).get("anthropic-version")
            routing = route_anthropic(anthropic_model_override, anthropic_key, version)
            anthropic_model = routing["model"]
            _report("anthropic", routing)
            model_routing["anthropic"] = routing
            api_available = True
            for q in queries:
                query_text = q["query"] if isinstance(q, dict) else q
                try:
                    response = client.messages.create(
                        model=anthropic_model,
                        max_tokens=500,
                        messages=[{"role": "user", "content": query_text}],
                    )
                    answer = response.content[0].text
                    brand_lower = brand.lower()
                    mentioned = brand_lower in answer.lower()
                    competitors_found = []
                    if competitors:
                        for comp in competitors:
                            if comp.lower() in answer.lower():
                                competitors_found.append(comp)

                    results.append({
                        "query": query_text,
                        "platform": f"Anthropic {anthropic_model}",
                        "brand_mentioned": mentioned,
                        "competitors_mentioned": competitors_found,
                        "response_excerpt": answer[:300] + ("..." if len(answer) > 300 else ""),
                    })
                except Exception as e:
                    results.append({
                        "query": query_text,
                        "platform": f"Anthropic {anthropic_model}",
                        "error": str(e),
                    })
        except ImportError:
            missing_sdks.append("anthropic")

    sdk_note = None
    if missing_sdks:
        sdk_note = (f"{' and '.join(missing_sdks)} not installed, so that key was not used. "
                    f"Install the tested version with: {_common.install_command(missing_sdks)}")

    if not api_available:
        return {
            "error": sdk_note or "No AI API keys found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variables.",
            "fallback": "Use --mode manual to generate a manual testing checklist instead.",
        }

    # Compute summary. The rate counts answered queries only: before 3.40.0 a run whose 15 requests
    # all failed reported "0.0%" with exit 0, which a client report could quote as real visibility.
    total = len(results)
    failed = sum(1 for r in results if r.get("error"))
    answered = total - failed
    mentioned_count = sum(1 for r in results if r.get("brand_mentioned"))
    summary = {
        "brand": brand,
        "mode": "api",
        "total_queries_run": total,
        "answered": answered,
        "errors": failed,
        "mention_rate": f"{round(mentioned_count / answered * 100, 1)}%" if answered else None,
        "mention_rate_formula": "runs whose answer names the brand / runs answered (failed requests excluded)",
        "metric_definitions": "skills/context-engine/ai-visibility-metrics.md",
        "mentions": mentioned_count,
        "results": results,
    }
    if total and not answered:
        first = next((r.get("error") for r in results if r.get("error")), "")
        summary["error"] = (f"every request failed ({failed} of {total}), so no mention rate can be "
                            f"reported. First error: {first}")
    if sdk_note:
        summary["warning"] = sdk_note
    if model_routing:
        summary["model_routing"] = model_routing
    return summary


def main():
    parser = argparse.ArgumentParser(description="Check brand visibility in AI responses")
    parser.add_argument("--brand", type=_common.path_component, required=False, default=None, help="Brand name to check (required unless --list-models)")
    parser.add_argument("--queries", help="Comma-separated queries to test")
    parser.add_argument("--mode", choices=["manual", "api"], default="manual",
                        help="manual = checklist, api = run queries via APIs")
    parser.add_argument("--competitors", help="Comma-separated competitor names")
    parser.add_argument("--industry", default="", help="Industry for query generation")
    parser.add_argument("--product-type", default="", help="Product type for query generation")
    parser.add_argument("--use-case", default="", help="Use case for query generation")
    parser.add_argument("--pain-point", default="", help="Customer pain point for query generation")
    parser.add_argument("--openai-model", default=None,
                        help="Ask for an OpenAI model by name (default: chosen from OpenAI's live "
                             "model list by scripts/model_router.py). Deprecated: kept with a warning; "
                             "retired: refused, naming the replacement.")
    parser.add_argument("--anthropic-model", default=None,
                        help="Ask for an Anthropic model by name (default: chosen from Anthropic's live "
                             "model list by scripts/model_router.py). Deprecated: kept with a warning; "
                             "retired: refused, naming the replacement.")
    parser.add_argument("--list-models", action="store_true",
                        help="Print the curated model registry and exit")
    args = parser.parse_args()

    if args.list_models:
        try:
            from resolve_model import list_models, get_registry
            reg = get_registry()
            print(f"Registry last_updated: {reg.get('last_updated')}. Re-validate quarterly; "
                  f"to check drift, run: {_common.script_command('refresh_models.py')}")
            print()
            for m in list_models(status="current"):
                print(f"  {m['id']:55s}  {m.get('vendor', '?'):10s}  {m.get('tier', '?')}")
            return
        except ImportError:
            print("Model curator not available (scripts/resolve_model.py missing)", file=sys.stderr)
            sys.exit(2)

    if not args.brand:
        parser.error("--brand is required (unless --list-models is set)")

    if not args.brand.strip():
        print(json.dumps({"error": "Brand name cannot be empty"}))
        sys.exit(1)

    competitors = [c.strip() for c in args.competitors.split(",") if c.strip()] if args.competitors else []

    custom_queries = [q.strip() for q in args.queries.split(",") if q.strip()] if args.queries else None
    queries = generate_queries(
        brand=args.brand,
        queries=custom_queries,
        industry=args.industry,
        product_type=args.product_type,
        use_case=args.use_case,
        pain_point=args.pain_point,
    )

    if args.mode == "manual":
        result = build_manual_checklist(args.brand, queries, competitors)
        result["mode"] = "manual"
    else:
        try:
            result = run_api_mode(args.brand, queries, competitors,
                                  openai_model_override=args.openai_model,
                                  anthropic_model_override=args.anthropic_model)
        except model_router.RouterError as exc:
            # Refused before any probe was sent: nothing was spent.
            _common.ensure_utf8_stdout()
            print(json.dumps({"error": exc.reason, "stage": "model routing"}, ensure_ascii=False))
            sys.exit(2)

    _common.finish(result)


if __name__ == "__main__":
    main()
