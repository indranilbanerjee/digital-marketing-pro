#!/usr/bin/env python3
"""Cluster keywords by semantic similarity and search intent using word overlap."""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Intent classification modifiers
INTENT_MODIFIERS = {
    "transactional": [
        "buy", "purchase", "order", "shop", "deal", "discount", "coupon", "price",
        "cheap", "affordable", "sale", "subscribe", "download", "hire", "book",
        "get", "free trial", "pricing", "cost", "quote",
    ],
    "commercial": [
        "best", "top", "review", "reviews", "comparison", "compare", "vs",
        "versus", "alternative", "alternatives", "recommended", "ranking",
        "rated", "pros and cons", "benchmark", "which",
    ],
    "informational": [
        "how", "what", "why", "when", "where", "who", "guide", "tutorial",
        "tips", "learn", "example", "examples", "definition", "meaning",
        "does", "can", "is", "are", "ways to", "ideas", "steps",
    ],
    "navigational": [
        "login", "sign in", "website", "official", "app", "contact",
        "support", "account", "dashboard", "portal", "homepage",
    ],
}

# Common stop words to ignore during clustering
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "as", "be", "was", "are",
    "this", "that", "these", "those", "i", "you", "he", "she", "we", "they",
    "my", "your", "his", "her", "our", "their", "me", "him", "us", "them",
    "do", "does", "did", "will", "would", "could", "should", "can", "may",
    "not", "no", "so", "if", "about", "up", "out", "just", "into", "also",
}


def tokenize(text):
    """Split text into lowercase tokens, removing stop words."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def classify_intent(keyword):
    """Classify a keyword's search intent based on modifier presence."""
    kw_lower = keyword.lower()
    scores = {}
    for intent, modifiers in INTENT_MODIFIERS.items():
        score = sum(1 for mod in modifiers if mod in kw_lower)
        scores[intent] = score

    max_score = max(scores.values())
    if max_score == 0:
        # Default heuristic: questions -> informational, otherwise informational
        if any(kw_lower.startswith(q) for q in ["how", "what", "why", "when", "where", "who"]):
            return "informational"
        return "informational"

    # Return the intent with the highest score
    for intent in ["transactional", "commercial", "navigational", "informational"]:
        if scores[intent] == max_score:
            return intent
    return "informational"


def compute_similarity(tokens_a, tokens_b):
    """Jaccard similarity between two token sets."""
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def cluster_keywords(keywords, threshold=0.25):
    """Cluster keywords using single-linkage clustering with word overlap."""
    if not keywords:
        return []

    # Tokenize all keywords
    tokenized = [(kw, tokenize(kw)) for kw in keywords]

    # Assign each keyword to a cluster
    clusters = []  # Each cluster is a list of (keyword, tokens)

    for kw, tokens in tokenized:
        best_cluster = None
        best_score = 0.0

        for i, cluster in enumerate(clusters):
            # Compare against all keywords in the cluster, take max similarity
            for _, cluster_tokens in cluster:
                sim = compute_similarity(tokens, cluster_tokens)
                if sim > best_score:
                    best_score = sim
                    best_cluster = i

        if best_score >= threshold and best_cluster is not None:
            clusters[best_cluster].append((kw, tokens))
        else:
            clusters.append([(kw, tokens)])

    return clusters


def label_cluster(cluster_keywords_list):
    """Generate a topic label from the most common non-stop words."""
    word_freq = defaultdict(int)
    for kw in cluster_keywords_list:
        for token in tokenize(kw):
            word_freq[token] += 1

    sorted_words = sorted(word_freq.items(), key=lambda x: -x[1])
    top_words = [w for w, _ in sorted_words[:3]]
    return " + ".join(top_words) if top_words else "misc"


def main():
    parser = argparse.ArgumentParser(description="Cluster keywords by similarity and intent")
    parser.add_argument("--keywords", help="Comma-separated keywords")
    parser.add_argument("--file", help="File with one keyword per line")
    parser.add_argument("--threshold", type=float, default=0.25,
                        help="Similarity threshold for clustering (0.0-1.0, default 0.25)")
    args = parser.parse_args()

    if not args.keywords and not args.file:
        parser.error("Provide --keywords or --file")

    keyword_list = []
    if args.keywords:
        keyword_list = [k.strip() for k in args.keywords.split(",") if k.strip()]
    elif args.file:
        path = Path(args.file)
        if not path.exists():
            print(json.dumps({"error": f"File not found: {args.file}"}))
            sys.exit(1)
        keyword_list = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    if not keyword_list:
        print(json.dumps({"error": "No keywords provided"}))
        sys.exit(1)

    raw_clusters = cluster_keywords(keyword_list, threshold=args.threshold)

    output_clusters = []
    intent_summary = defaultdict(int)

    for cluster in raw_clusters:
        kw_list = [kw for kw, _ in cluster]
        intents = [classify_intent(kw) for kw in kw_list]
        primary_intent = max(set(intents), key=intents.count)
        topic = label_cluster(kw_list)

        for intent in intents:
            intent_summary[intent] += 1

        output_clusters.append({
            "topic_label": topic,
            "primary_intent": primary_intent,
            "keyword_count": len(kw_list),
            "keywords": [
                {"keyword": kw, "intent": classify_intent(kw)}
                for kw in kw_list
            ],
        })

    # Sort clusters by size descending
    output_clusters.sort(key=lambda c: -c["keyword_count"])

    result = {
        "total_keywords": len(keyword_list),
        "total_clusters": len(output_clusters),
        "intent_distribution": dict(intent_summary),
        "similarity_threshold": args.threshold,
        "clusters": output_clusters,
    }

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
