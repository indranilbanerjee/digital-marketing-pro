#!/usr/bin/env python3
"""Framework for checking brand mentions in AI responses (manual or API mode).

Model selection: pass --openai-model and --anthropic-model to override the
defaults pulled from scripts/model_registry.json via the curator. If those
flags are omitted, the curator's `latest-balanced-openai` and
`latest-balanced-anthropic` aliases are used so newer models propagate
automatically when the registry is refreshed.
"""

import argparse
import json
import os
import sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

# Curator: resolve model aliases / validate user-supplied model ids
try:
    from resolve_model import resolve as _resolve_model, check as _check_model
except ImportError:  # pragma: no cover — curator should always be present
    _resolve_model = lambda alias_or_id, **_: alias_or_id  # type: ignore
    _check_model = lambda model_id: ("unknown", None)  # type: ignore


def _negotiate_model(user_value: str | None, alias: str) -> tuple[str, str | None]:
    """Pick the model id to actually pass to the SDK. If the user supplied
    --xxx-model, validate it; otherwise resolve the alias. Returns
    (model_id, warning_string_or_None)."""
    if user_value:
        status, replacement = _check_model(user_value)
        if status == "deprecated" and replacement:
            return replacement, f"{user_value} is deprecated, using {replacement} instead"
        if status == "unknown":
            return user_value, f"{user_value} is not in the curated registry — proceeding but no deprecation safety net"
        return user_value, None
    return _resolve_model(alias), None

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
    {"name": "ChatGPT", "url": "https://chat.openai.com", "note": "Test with the current default ChatGPT model (GPT-5.6 family as of July 2026)"},
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

    # Resolve model ids via the curator (auto-falls-forward on deprecation)
    openai_model, openai_warn = _negotiate_model(openai_model_override, "latest-balanced-openai")
    anthropic_model, anthropic_warn = _negotiate_model(anthropic_model_override, "latest-balanced-anthropic")
    if openai_warn:
        print(f"WARNING (openai): {openai_warn}", file=sys.stderr)
    if anthropic_warn:
        print(f"WARNING (anthropic): {anthropic_warn}", file=sys.stderr)

    # Check for OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            import openai
            client = openai.OpenAI(api_key=openai_key)
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
            pass

    # Check for Anthropic
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
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
            pass

    if not api_available:
        return {
            "error": "No AI API keys found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variables.",
            "fallback": "Use --mode manual to generate a manual testing checklist instead.",
        }

    # Compute summary
    total = len(results)
    mentioned_count = sum(1 for r in results if r.get("brand_mentioned"))
    return {
        "brand": brand,
        "mode": "api",
        "total_queries_run": total,
        "mention_rate": f"{round(mentioned_count / max(total, 1) * 100, 1)}%",
        "mentions": mentioned_count,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Check brand visibility in AI responses")
    parser.add_argument("--brand", type=_common.path_component, required=False, default="", help="Brand name to check (required unless --list-models)")
    parser.add_argument("--queries", help="Comma-separated queries to test")
    parser.add_argument("--mode", choices=["manual", "api"], default="manual",
                        help="manual = checklist, api = run queries via APIs")
    parser.add_argument("--competitors", help="Comma-separated competitor names")
    parser.add_argument("--industry", default="", help="Industry for query generation")
    parser.add_argument("--product-type", default="", help="Product type for query generation")
    parser.add_argument("--use-case", default="", help="Use case for query generation")
    parser.add_argument("--pain-point", default="", help="Customer pain point for query generation")
    parser.add_argument("--openai-model", default=None,
                        help="Override OpenAI model (default: registry alias `latest-balanced-openai`). "
                             "Deprecated ids auto-fall-forward to their replacement.")
    parser.add_argument("--anthropic-model", default=None,
                        help="Override Anthropic model (default: registry alias `latest-balanced-anthropic`).")
    parser.add_argument("--list-models", action="store_true",
                        help="Print the curated model registry and exit")
    args = parser.parse_args()

    if args.list_models:
        try:
            from resolve_model import list_models, get_registry
            reg = get_registry()
            print(f"Registry last_updated: {reg.get('last_updated')}  "
                  f"(re-validate quarterly; run `python scripts/refresh_models.py` to check drift)")
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
        result = run_api_mode(args.brand, queries, competitors,
                              openai_model_override=args.openai_model,
                              anthropic_model_override=args.anthropic_model)

    _common.finish(result)


if __name__ == "__main__":
    main()
