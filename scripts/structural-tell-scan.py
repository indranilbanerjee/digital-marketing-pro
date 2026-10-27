#!/usr/bin/env python3
"""
structural-tell-scan.py — Tier-2 structural AI-tell proxies for marketing copy.

StoryScope (arXiv 2604.03136) showed AI text stays detectable on document
STRUCTURE even after a perfect surface-style pass (93.9% F1 after stylistic
stripping — structure is "largely orthogonal to surface prose artifacts").
This scan measures deterministic proxies for the structural tells that
transfer to marketing prose, each with the spans that fired it, so a human
editor knows exactly where to work:

    moralizing           — spelled-out takeaways ("in conclusion, the key
                           takeaway...") instead of trusting the reader
    section_symmetry     — near-identical H2 section lengths (filled template)
    parallel_headings    — every heading cut to the same grammatical shape
    specificity          — low density of numbers/proper nouns/citations/quotes
                           (the generic AI center; humans name checkable things)
    stance               — hedged positionless evenness vs a real point of view
    paragraph_evenness   — uniform paragraph rhythm (machine fingerprint)
    entity_development   — specifics name-dropped once and abandoned (a machine
                           establishing a setting) vs developed (an expert
                           making a case). FIX BY DEVELOPING, NEVER BY DELETING

ADVISORY ONLY, never a scored gate: bands (OK/NOTE/ATTENTION) and thresholds
live in THIS script, deliberately outside every eval/scoring config. The scan
measures visible structure; it cannot see and has no relationship to any
statistical watermark. Consumed by /digital-marketing-pro:check (advisory
section) and the content-engine's revision guidance.

Usage: python structural-tell-scan.py --file draft.md
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys

for _stream in (sys.stdout, sys.stderr):  # UTF-8 output, even where a Windows pipe defaults to cp1252
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from pathlib import Path

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")

_MORALIZING_PHRASES = (
    "in conclusion", "ultimately", "the key takeaway", "the bottom line",
    "it's important to remember", "it is important to remember",
    "this matters because", "at the end of the day", "in short", "simply put",
    "what this means for you", "the lesson here", "in today's world",
    "it's crucial to", "it is crucial to", "remember that", "the takeaway is",
)
_HEDGING_WORDS = frozenset((
    "may", "might", "can", "could", "often", "typically", "generally",
    "usually", "tends", "potentially", "possibly", "somewhat", "relatively",
))
_STANCE_RE = re.compile(r"\b(?:I|we|our|my|us)\b|\bin my experience\b", re.I)
_CITATION_RE = re.compile(r"\[\d+\]|\((?:[A-Z][\w.]*,?\s*)?\d{4}\)|https?://")
_QUOTE_RE = re.compile(r"[\"“][^\"”]{6,}[\"”]")

_BANDS = {
    "moralizing_per_1000": (6.0, 3.0),
    "section_symmetry_cv": (0.20, 0.35),      # LOWER is worse
    "parallel_heading_share": (0.75, 0.55),
    "specificity_per_1000": (5.0, 10.0),      # LOWER is worse
    "hedging_per_1000": (18.0, 12.0),
    "paragraph_evenness_cv": (0.25, 0.40),    # LOWER is worse
    "mentions_per_entity": (1.25, 1.60),      # LOWER is worse (churn, not dwell)
}
_LOWER_IS_WORSE = ("section_symmetry_cv", "specificity_per_1000", "paragraph_evenness_cv",
                   "mentions_per_entity")

# Entity extraction for the development proxy. Capitalized runs are merged so
# "European Medicines Agency" counts as one entity, not three.
_ENTITY_TOKEN_RE = re.compile(r"^[A-Z][\w'’.&-]*$")
_NUMERIC_RE = re.compile(r"^[$€£¥]?\d[\d,.]*%?$")
_ENTITY_STOPWORDS = frozenset((
    "the", "a", "an", "this", "that", "these", "those", "it", "its", "they",
    "their", "there", "and", "but", "or", "if", "when", "while", "however",
    "moreover", "furthermore", "additionally", "because", "so", "then",
    "in", "on", "at", "for", "with", "by", "from", "to", "of", "as", "after",
    "before", "during", "since", "until", "each", "every", "both", "most",
    "many", "some", "no", "not", "we", "our", "you", "your", "he", "she",
    "his", "her", "i", "my", "one", "two", "three", "first", "second", "third",
))


def _band(metric, value):
    att, note = _BANDS[metric]
    if metric in _LOWER_IS_WORSE:
        return "ATTENTION" if value <= att else ("NOTE" if value <= note else "OK")
    return "ATTENTION" if value >= att else ("NOTE" if value >= note else "OK")


def _cv(values):
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    if mean == 0:
        return None
    return round(statistics.pstdev(values) / mean, 3)


def _strip_frontmatter(text):
    if text.startswith("---"):
        parts = text.split("\n---", 2)
        if len(parts) >= 2:
            return parts[-1]
    return text


def _inline_to_plain(s):
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    return re.sub(r"[*_`]+", "", s)


def _split_sentences(text):
    raw = re.split(r"(?<=[.!?])\s+", text)
    return [s for s in (x.strip() for x in raw) if s]


def _extract_entities(sentences):
    """Distinct named/numeric specifics and how often each recurs.

    The first token of a sentence is skipped because English capitalizes it
    regardless of whether it names anything — the same simplification the
    specificity proxy makes.
    """
    counts = {}
    for s in sentences:
        tokens = s.split()
        run = []
        for tok in tokens[1:]:
            bare = tok.strip("([{\"'“”’,;:.!?)]}")
            if not bare:
                continue
            if _NUMERIC_RE.match(bare):
                counts[bare.lower()] = counts.get(bare.lower(), 0) + 1
                if run:
                    key = " ".join(run).lower()
                    counts[key] = counts.get(key, 0) + 1
                    run = []
                continue
            if _ENTITY_TOKEN_RE.match(bare) and bare.lower() not in _ENTITY_STOPWORDS:
                run.append(bare)
                continue
            if run:
                key = " ".join(run).lower()
                counts[key] = counts.get(key, 0) + 1
                run = []
        if run:
            key = " ".join(run).lower()
            counts[key] = counts.get(key, 0) + 1
    return counts


def structure_scan(md_text: str) -> dict:
    md_text = _strip_frontmatter(md_text)
    sections, paragraphs, para = [], [], []
    current = ["(before first heading)", []]
    in_code = False
    for raw in md_text.split("\n"):
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = _HEADING_RE.match(line.strip())
        if m and len(m.group(1)) == 2:
            sections.append(current)
            current = [_inline_to_plain(m.group(2)).strip(), []]
            if para:
                paragraphs.append(" ".join(para)); para = []
            continue
        if m or line.strip().startswith("|"):
            continue
        if not line.strip():
            if para:
                paragraphs.append(" ".join(para)); para = []
            continue
        cleaned = _inline_to_plain(re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", line)).strip()
        if cleaned:
            current[1].append(cleaned)
            para.append(cleaned)
    sections.append(current)
    if para:
        paragraphs.append(" ".join(para))
    sections = [(t, " ".join(ls)) for t, ls in sections if ls]

    prose = " ".join(text for _, text in sections)
    words_total = max(1, len(re.findall(r"[\w'-]+", prose)))
    per_k = 1000.0 / words_total
    sentences = _split_sentences(prose)
    findings = {}

    moral_hits = []
    for i, s in enumerate(sentences):
        low = s.lower()
        for ph in _MORALIZING_PHRASES:
            if ph in low:
                moral_hits.append({"index": i, "text": s.strip()[:160], "phrase": ph})
                break
    val = round(len(moral_hits) * per_k, 2)
    findings["moralizing"] = {
        "per_1000_words": val, "band": _band("moralizing_per_1000", val),
        "spans": moral_hits[:15],
        "meaning": "Spelling the takeaway out instead of trusting the reader — AI states the theme far more often than human writers do.",
    }

    counts = [len(re.findall(r"[\w'-]+", text)) for _, text in sections]
    cv = _cv(counts) if len(counts) >= 4 else None
    findings["section_symmetry"] = {
        "section_word_counts": {t[:60]: c for (t, _), c in zip(sections, counts)},
        "coefficient_of_variation": cv,
        "band": _band("section_symmetry_cv", cv) if cv is not None else "OK",
        "meaning": "Near-identical section lengths read as a filled template; human structure is asymmetric — sections take the length their content earns.",
    }

    h2s = [t for t, _ in sections if t != "(before first heading)"]
    share = None
    if len(h2s) >= 4:
        first_words = [t.split()[0].lower() for t in h2s if t.split()]
        gerund_share = sum(1 for w in first_words if w.endswith("ing")) / len(first_words)
        top_share = max(first_words.count(w) for w in set(first_words)) / len(first_words)
        share = round(max(gerund_share, top_share), 2)
    findings["parallel_headings"] = {
        "headings": h2s, "max_identical_pattern_share": share,
        "band": _band("parallel_heading_share", share) if share is not None else "OK",
        "meaning": "Every heading cut to the same grammatical shape is a template tell; vary the syntax where the content allows.",
    }

    numbers = len(re.findall(r"\b\d[\d,.%]*\b", prose))
    proper = sum(1 for s in sentences
                 for w in s.split()[1:] if w[:1].isupper() and w[1:2].islower())
    cites = len(_CITATION_RE.findall(prose))
    quotes = len(_QUOTE_RE.findall(prose))
    val = round((numbers + proper + cites + quotes) * per_k, 2)
    findings["specificity"] = {
        "per_1000_words": val, "band": _band("specificity_per_1000", val),
        "components_per_1000": {"numbers": round(numbers * per_k, 2),
                                "proper_nouns": round(proper * per_k, 2),
                                "citations_urls": round(cites * per_k, 2),
                                "quoted_strings": round(quotes * per_k, 2)},
        "meaning": "Generic prose is the AI center-of-mass; human expert writing names specific, checkable things — sources, numbers, products, people.",
    }

    hedges = sum(1 for w in re.findall(r"[A-Za-z'-]+", prose) if w.lower() in _HEDGING_WORDS)
    stance = len(_STANCE_RE.findall(prose))
    hval = round(hedges * per_k, 2)
    findings["stance"] = {
        "hedging_per_1000_words": hval,
        "stance_markers_per_1000_words": round(stance * per_k, 2),
        "band": _band("hedging_per_1000", hval),
        "meaning": "Hedged, positionless prose reads machine-made; a human expert takes a stance and owns a judgment somewhere in the piece.",
    }

    plens = [len(p.split()) for p in paragraphs if len(p.split()) >= 10]
    pcv = _cv(plens) if len(plens) >= 6 else None
    findings["paragraph_evenness"] = {
        "paragraphs_measured": len(plens), "coefficient_of_variation": pcv,
        "band": _band("paragraph_evenness_cv", pcv) if pcv is not None else "OK",
        "meaning": "Uniform paragraph rhythm is a machine fingerprint; human writing has short punches and long developments.",
    }

    ents = _extract_entities(sentences)
    distinct = len(ents)
    mentions = sum(ents.values())
    depth = round(mentions / distinct, 2) if distinct else None
    singletons = sum(1 for c in ents.values() if c == 1)
    top = sorted(ents.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    # A short piece names things once because it has no room to develop them —
    # that is brevity, not churn. Only speak where development was possible.
    measurable = words_total >= 600 and distinct >= 12
    findings["entity_development"] = {
        "distinct_entities": distinct,
        "distinct_per_1000_words": round(distinct * per_k, 2),
        "mentions_per_entity": depth,
        "single_mention_share": round(singletons / distinct, 2) if distinct else None,
        "most_developed": [{"entity": e, "mentions": c} for e, c in top if c > 1],
        "band": _band("mentions_per_entity", depth) if measurable else "OK",
        "measurable": measurable,
        "measurable_note": ("Banded only at >=600 words and >=12 distinct entities; below that a "
                            "single mention each is brevity, not churn."),
        "meaning": ("A new name or number in almost every sentence, each mentioned once, reads as a "
                    "machine establishing a setting; human experts return to the few specifics that "
                    "carry the argument. FIX BY DEVELOPING, NEVER BY DELETING: give an existing "
                    "specific a second, substantive mention from the verified fact-check file. "
                    "Cutting specifics to raise this number would lower the specificity finding "
                    "above and is the wrong move — and inventing a mention is forbidden outright."),
    }

    order = {"OK": 0, "NOTE": 1, "ATTENTION": 2}
    overall = max((f["band"] for f in findings.values()), key=order.get, default="OK")
    return {
        "words_analyzed": words_total,
        "sections": len(sections),
        "findings": findings,
        "overall": overall,
        "advisory_note": ("Structural-tell proxies (StoryScope-derived) — advisory only, never a "
                          "scored gate. These measure visible structure; they cannot see and have "
                          "no relationship to any statistical watermark."),
    }


def main():
    parser = argparse.ArgumentParser(description="Tier-2 structural AI-tell scan (advisory)")
    parser.add_argument("--file", required=True)
    args = parser.parse_args()
    path = Path(args.file).expanduser()
    if not path.is_file():
        print(json.dumps({"error": f"file not found: {path}"}))
        sys.exit(1)
    print(json.dumps(structure_scan(path.read_text(encoding="utf-8-sig", errors="replace")),
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
