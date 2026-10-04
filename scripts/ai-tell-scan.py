#!/usr/bin/env python3
"""
ai-tell-scan.py — Tier-1 surface AI-tell proxies for marketing copy.

The companion to structural-tell-scan.py. That one measures the SHAPE of a
document; this one measures its SURFACE — the word choices, sentence openings
and rhetorical tics that mark unedited model prose.

It exists because the content-engine's `humanize_passed` gate used to ask for
"AI-pattern density below the brand threshold (under 10% of paragraphs
flagged)" with nothing in the repo defining what a flag was. A gate whose
measurement is undefined does not fail; it passes on vibes. This script is the
missing definition: it produces the flags, per paragraph, deterministically.

What it counts:

    llm_favored_words     — delve, leverage, seamless, tapestry, testament...
    significance_markers  — sentences whose only job is to tell the reader what
                            a neighbouring sentence means ("here's the thing",
                            "that's the part that got me", "let that sink in").
                            DELETE these; do not reword them
    soft_adverb_tags      — honestly/genuinely/truly/literally/actually/basically
                            attaching feeling instead of meaning, in clusters
    connective_openers    — So/Moreover/Furthermore/Additionally at the start
    participial_openers   — "Building on this, ...", "Leveraging the platform, ..."
    em_dashes             — the famous one; humans use 2-3, models use 20+
    aphorism_candidates   — short polished ungrounded one-liners with no number,
                            name, date or source

Every count is reported per 1000 words AND as a paragraph-level flag rate, so
the gate has a real number. The right fix for a flag is almost always a
specific from the verified fact-check file, never a synonym swap — and never
an invented fact.

ADVISORY thresholds and the whole lexicon live in THIS script, deliberately
outside every eval/scoring config, exactly like structural-tell-scan.py. The
scan measures visible text; it cannot see and has no relationship to any
statistical watermark. No part of this tool detects or removes a watermark,
and none will be added.

CALIBRATION (measured 2026-08-15 — read this before changing any threshold)
--------------------------------------------------------------------------
Corpus: 39 documents published BEFORE 2022-11-01, i.e. before ChatGPT was
public, so human authorship is guaranteed by publication date rather than
assumed. Four registers (marketing blog, personal/technical essay, journalism
and institutional reports, academic/standards prose), cut into 272 chunks of
~1000 words so both classes are compared at equal length. Negative class: 18
default-LLM documents written with no anti-tell guidance.

  humanize gate (flagged_paragraph_pct <= 10)
      false positives on human prose ....... 0/272 chunks, 0/39 documents
      un-humanized LLM prose caught ........ 0/18 documents

  The gate is SAFE and, on this corpus, INERT. It is a density floor that
  catches egregious tell-stuffing; it is NOT evidence that a piece was
  humanized, and it would not catch a humanizer that silently did nothing.
  Do not describe it as more than that.

  Per-signal, at the strictest threshold with ZERO false positives on human
  prose, the best single signal catches 11% of LLM prose. Accepting a 5%
  false-positive rate, em-dash density catches 94% — but thresholds computed
  per register diverge sharply (em-dash 95th percentile: 1.47 in standards
  prose, 9.90 in essays), so any single pooled threshold high enough to spare
  essayists catches nothing. Composite K-of-N rules were tested too: at
  register-robust thresholds every combination catches 0%.

  CONCLUSION: surface tells cannot carry a fair blocking gate. Discrimination
  that does exist lives in the advisory rating (human 62.5% LOW / 8.8% HIGH
  vs LLM 0% LOW / 83.3% HIGH) and in the structural scan (human 34.6% OK vs
  LLM 0% OK) — both of which route a human editor's attention rather than
  blocking a publish.

  Limits of this measurement, stated plainly: the negative class is prose from
  one model family, so the vocabulary findings may not transfer to other
  models; and 18 negative documents is a small sample. The human class is the
  strong half of the corpus.

Usage:
    python ai-tell-scan.py --file draft.md
    python ai-tell-scan.py --file draft.md --paragraph-flags
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")

_LLM_FAVORED_WORDS = frozenset((
    "delve", "delves", "delving", "underscore", "underscores", "underscored",
    "harness", "harnessing", "illuminate", "illuminates", "facilitate",
    "facilitates", "bolster", "bolsters", "intricate", "seamless", "seamlessly",
    "showcase", "showcasing", "leverage", "leverages", "leveraging", "tapestry",
    "realm", "beacon", "cacophony", "testament", "pivotal", "landscape",
    "navigate", "navigating", "myriad", "plethora", "robust", "transformative",
    "unparalleled", "meticulous", "meticulously", "multifaceted", "elevate",
    "empower", "unlock", "unleash", "streamline", "streamlining",
))
# 'landscape' and 'navigate' have literal uses; the scan is advisory end to end.

_SIGNIFICANCE_MARKERS = (
    "here's the thing", "here is the thing", "the thing is,",
    "here's the kicker", "here is the kicker",
    "here's where it gets interesting", "here is where it gets interesting",
    "here's what's interesting", "that's the part that", "that is the part that",
    "that's the part where", "what got me was", "what struck me was",
    "and that's the point", "and that is the point", "that's the whole point",
    "that is the whole point", "which is exactly the problem", "let that sink in",
    "that's what kills me", "that is what kills me", "the best part?",
    "and here's why that matters", "and here is why that matters", "read that again",
)

_SOFT_ADVERB_TAGS = frozenset((
    "honestly", "genuinely", "truly", "literally", "actually", "basically",
    "quietly", "frankly", "remarkably", "interestingly",
))

_CONNECTIVE_OPENERS = ("so", "because", "moreover", "furthermore", "additionally",
                       "however", "indeed", "ultimately", "in fact", "the reason is")

# Personal and anaphoric pronouns. A sentence carrying one is context-dependent
# — it points at a speaker, a reader, or an earlier sentence — so it cannot be
# the self-contained general claim the aphorism proxy targets.
_PRONOUN_RE = re.compile(
    r"\b(?:i|me|my|mine|we|us|our|ours|you|your|yours|he|him|his|she|her|hers|"
    r"they|them|their|theirs|it|its|this|that|these|those)\b", re.I)

# Advisory bands: (high, moderate). Higher is worse for every metric here.
_BANDS = {
    "llm_favored_words_per_1000": (4.0, 2.0),
    "significance_markers_per_1000": (1.5, 0.75),
    "soft_adverb_tags_per_1000": (4.0, 2.0),
    "em_dashes_per_1000": (6.0, 3.0),
    # Short declaratives are ordinary in marketing copy; this band is set where
    # a RUN of ungrounded one-liners shows, not where two appear.
    "aphorism_candidates_per_1000": (8.0, 5.0),
    "connective_openers_pct": (15.0, 7.5),
    "participial_openers_pct": (8.0, 4.0),
}
# Absolute floors: in a short piece a single legitimate "actually" normalizes
# to a large per-1000 figure. One earned use is not a tell, and the scan must
# not manufacture one out of arithmetic.
_FLOORS = {"significance_markers_per_1000": 2, "soft_adverb_tags_per_1000": 3,
           "aphorism_candidates_per_1000": 4}

# Only these tells count toward the paragraph flag rate that gates the pipeline.
#
# A gate may only be built from signals precise enough to gate on. Connective
# openers ("So,", "However,") and short declaratives are ordinary human
# writing — measured against real hand-written marketing copy, the aphorism
# heuristic alone flagged half the paragraphs of a good piece. Gating on those
# would fail human work and send the pipeline into pointless rewrite loops,
# which is worse than the undefined gate this scan replaced. They stay in the
# report as advisory context for an editor, where a false positive costs two
# seconds instead of a rewrite.
#
# llm_favored_word was REMOVED from this set on 2026-08-15 after measurement.
# See CALIBRATION below: across 272 chunks of prose published before ChatGPT
# existed, 23 words from _LLM_FAVORED_WORDS fired — every one of them ONLY on
# the human class, none on the LLM class. "robust", "facilitate", "harness",
# "landscape" and "leverage" are ordinary in technical and journalistic
# English, while current models have largely been trained off them. As a
# GATING signal it could therefore only ever produce false positives, which
# disqualifies it under the rule above. It remains in the report and in the
# humanizer's catalog, where it is still sound editorial advice.
_GATING_TELLS = frozenset(("significance_marker", "soft_adverb_cluster"))

# The paragraph-flag rate the content-engine's humanize gate reads.
DEFAULT_MAX_FLAGGED_PARAGRAPH_PCT = 10.0


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


def _paragraphs(md_text):
    """Prose paragraphs only — headings, tables and fenced code excluded."""
    out, para, in_code = [], [], False
    for raw in _strip_frontmatter(md_text).split("\n"):
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if _HEADING_RE.match(line.strip()) or line.strip().startswith("|"):
            continue
        if not line.strip():
            if para:
                out.append(" ".join(para)); para = []
            continue
        cleaned = _inline_to_plain(re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", line)).strip()
        if cleaned:
            para.append(cleaned)
    if para:
        out.append(" ".join(para))
    return out


def is_aphorism_candidate(sentence: str) -> bool:
    """A short, self-contained, ungrounded general claim — "Speed wins the shelf."

    The <=9-word test alone is not enough: measured against a published human
    essay and against this plugin's own generated article, it flagged ordinary
    short prose ("But pick something and get going.") at ~13 per 1000 words and
    pushed both to a HIGH advisory rating. A maxim generalizes; a sentence that
    refers to you, me, or the sentence before it is context-dependent and is not
    the broad over-neutral one-liner this targets.
    """
    s = sentence.strip()
    words = s.split()
    if not s or len(words) > 9 or s.endswith("?"):
        return False
    if any(ch.isdigit() for ch in s):
        return False
    if re.search(r"\((?:[A-Z][\w.]*,?\s*\d{4}|\d+)\)|\[\d+\]", s):
        return False
    if any(w[:1].isupper() for w in words[1:]):
        return False
    if _PRONOUN_RE.search(s):
        return False
    # Opening with a coordinating conjunction continues the previous sentence,
    # which is the same context-dependence the pronoun test rules out.
    if words[0].lower().strip(",") in ("but", "and", "so", "or", "yet", "nor"):
        return False
    return s.endswith(".")


def _band(metric, value, absolute_count=None):
    """Bands use one vocabulary throughout: LOW / MODERATE / HIGH. A metric
    suppressed by its absolute floor reports LOW, not a fourth word."""
    high, mod = _BANDS[metric]
    floor = _FLOORS.get(metric)
    if floor is not None and absolute_count is not None and absolute_count < floor:
        return "LOW"
    return "HIGH" if value >= high else ("MODERATE" if value >= mod else "LOW")


# Opening "-ing" words that are not participles. Without this, "During the
# night..." or "Something changed..." counted as participial openers.
_NON_PARTICIPLE_ING = frozenset({
    "during", "something", "nothing", "anything", "everything", "morning",
    "evening", "spring", "string", "thing", "things", "ceiling", "wedding",
    "sibling", "sterling", "offspring", "pudding", "darling", "notwithstanding",
})


def _connective_matcher(connectives):
    """Whole-word match at the start of a sentence. A bare prefix match let
    "so" fire on "Sometimes", "Soon", "Something" and "Software"."""
    alts = "|".join(r"\s+".join(re.escape(w) for w in c.split())
                    for c in sorted(connectives, key=len, reverse=True))
    return re.compile(rf"^(?:{alts})(?![\w'-])", re.I)


def _is_participial_opener(sentence: str) -> bool:
    words = sentence.strip().split()
    if not words:
        return False
    first = re.sub(r"[^a-z]", "", words[0].lower())
    return len(first) >= 5 and first.endswith("ing") and first not in _NON_PARTICIPLE_ING


_CONNECTIVE_RE = _connective_matcher(_CONNECTIVE_OPENERS)


def scan_sentences(sentences):
    """Per-sentence tells, most specific classification first."""
    flagged, counts = [], {"significance_markers": 0, "aphorism_candidates": 0,
                           "soft_adverb_tags": 0, "soft_adverb_clusters": 0,
                           "connective_openers": 0, "participial_openers": 0}
    for i, s in enumerate(sentences):
        st = s.strip()
        norm = st.lower().replace("’", "'")
        marker = next((m for m in _SIGNIFICANCE_MARKERS if m in norm), None)
        soft_here = sum(1 for w in re.findall(r"[a-z']+", norm) if w in _SOFT_ADVERB_TAGS)
        counts["soft_adverb_tags"] += soft_here
        if soft_here >= 2:
            counts["soft_adverb_clusters"] += 1
        if _CONNECTIVE_RE.match(norm):
            counts["connective_openers"] += 1
        if _is_participial_opener(st):
            counts["participial_openers"] += 1

        if marker:
            counts["significance_markers"] += 1
            flagged.append({"index": i, "tell": "significance_marker",
                            "phrase": marker, "text": st[:200],
                            "fix": "Delete this sentence; do not reword it."})
        elif is_aphorism_candidate(st):
            counts["aphorism_candidates"] += 1
            flagged.append({"index": i, "tell": "aphorism_candidate", "text": st[:200],
                            "fix": "Ground it with a verified specific, or cut it."})
        elif soft_here >= 2:
            flagged.append({"index": i, "tell": "soft_adverb_cluster", "text": st[:200],
                            "fix": "Delete the adverbs; if the line needs force it needs a specific."})
        elif _CONNECTIVE_RE.match(norm):
            flagged.append({"index": i, "tell": "connective_opener", "text": st[:200],
                            "fix": "Open with the subject, the specific, or the data."})
    return flagged, counts


def ai_tell_scan(md_text: str, max_flagged_pct: float = DEFAULT_MAX_FLAGGED_PARAGRAPH_PCT) -> dict:
    paras = _paragraphs(md_text)
    prose = " ".join(paras)
    words_total = max(1, len(re.findall(r"[\w'-]+", prose)))
    per_k = 1000.0 / words_total
    sentences = _split_sentences(prose)
    n = max(1, len(sentences))

    flagged, counts = scan_sentences(sentences)
    banned = sum(1 for w in re.findall(r"[A-Za-z'-]+", prose)
                 if w.lower() in _LLM_FAVORED_WORDS)
    em_dashes = prose.count("—") + prose.count(" -- ")

    metrics = {
        "llm_favored_words_per_1000": round(banned * per_k, 2),
        "significance_markers_per_1000": round(counts["significance_markers"] * per_k, 2),
        "soft_adverb_tags_per_1000": round(counts["soft_adverb_tags"] * per_k, 2),
        "em_dashes_per_1000": round(em_dashes * per_k, 2),
        "aphorism_candidates_per_1000": round(counts["aphorism_candidates"] * per_k, 2),
        "connective_openers_pct": round(100.0 * counts["connective_openers"] / n, 1),
        "participial_openers_pct": round(100.0 * counts["participial_openers"] / n, 1),
    }
    absolutes = {
        "significance_markers_per_1000": counts["significance_markers"],
        "soft_adverb_tags_per_1000": counts["soft_adverb_tags"],
        "aphorism_candidates_per_1000": counts["aphorism_candidates"],
    }
    bands = {k: _band(k, v, absolutes.get(k)) for k, v in metrics.items()}
    # Bands that may drive advisory_rating. The aphorism proxy is excluded: it
    # cannot separate a content-free maxim ("Speed wins the shelf.") from a
    # short factual sentence ("The neighbouring region barely moved."), and it
    # rated both a published human essay and this plugin's own generated article
    # HIGH. A signal too imprecise to gate on is too imprecise to headline a
    # rating; its count and sentences stay in the report for the editor.
    rating_bands = {k: v for k, v in bands.items()
                    if k != "aphorism_candidates_per_1000"}

    # Paragraph flag rate — the number the humanize gate reads. Only
    # _GATING_TELLS count toward it; everything else is editor-facing context.
    flagged_paras, para_detail = 0, []
    for pi, p in enumerate(paras):
        p_flags, _ = scan_sentences(_split_sentences(p))
        p_banned = [w for w in re.findall(r"[A-Za-z'-]+", p)
                    if w.lower() in _LLM_FAVORED_WORDS]
        tells = {f["tell"] for f in p_flags}
        if p_banned:
            tells.add("llm_favored_word")
        if not tells:
            continue
        gating = sorted(tells & _GATING_TELLS)
        if gating:
            flagged_paras += 1
        para_detail.append({
            "paragraph": pi,
            "tells": sorted(tells),
            "counts_toward_gate": bool(gating),
            "gating_tells": gating,
            "words": sorted(set(w.lower() for w in p_banned))[:8],
            "excerpt": p[:160],
        })

    total_paras = max(1, len(paras))
    flagged_pct = round(100.0 * flagged_paras / total_paras, 1)
    order = {"LOW": 0, "MODERATE": 1, "HIGH": 2}
    overall = max(rating_bands.values(), key=lambda b: order[b]) if rating_bands else "LOW"

    return {
        "words_analyzed": words_total,
        "sentences": len(sentences),
        "paragraphs": len(paras),
        "per_1000_words": metrics,
        "bands": bands,
        "counts": counts,
        "flagged_sentences": flagged[:25],
        "flagged_paragraphs": para_detail[:25],
        "flagged_paragraph_pct": flagged_pct,
        "max_flagged_paragraph_pct": max_flagged_pct,
        "humanize_passed": flagged_pct <= max_flagged_pct,
        "advisory_rating": overall,
        "advisory_note": (
            "Surface AI-tell proxies — deterministic, and the measurement behind the "
            "content-engine's humanize_passed gate. `flagged_paragraph_pct` vs "
            "`max_flagged_paragraph_pct` IS that gate; every other number here is advisory "
            "context for a human editor. Fix a flag with a verified specific, never a synonym "
            "swap and never an invented fact. "
            "WHAT PASSING MEANS: the gate is a density floor. Measured against 39 documents "
            "published before ChatGPT existed it failed none of them, and against 18 documents "
            "of unedited model prose it caught none — so a pass means no dense cluster of "
            "known tells, NOT that the piece reads as a person wrote it and NOT that the "
            "humanize step did any work. Read the advisory_rating and the structural scan for "
            "that, and read them as an editor's to-do list rather than a verdict. "
            "Measures visible text only; it cannot see and has "
            "no relationship to any statistical watermark."),
    }


def main():
    parser = argparse.ArgumentParser(description="Tier-1 surface AI-tell scan")
    parser.add_argument("--file", required=True)
    parser.add_argument("--max-flagged-pct", type=float,
                        default=DEFAULT_MAX_FLAGGED_PARAGRAPH_PCT,
                        help="Brand threshold for the humanize gate (default 10.0)")
    parser.add_argument("--paragraph-flags", action="store_true",
                        help="Print only the flagged-paragraph list (editor view)")
    args = parser.parse_args()

    path = Path(args.file).expanduser()
    if not path.is_file():
        print(json.dumps({"error": f"file not found: {path}"}))
        sys.exit(1)

    result = ai_tell_scan(path.read_text(encoding="utf-8", errors="replace"),
                          args.max_flagged_pct)
    if args.paragraph_flags:
        result = {k: result[k] for k in
                  ("flagged_paragraphs", "flagged_paragraph_pct",
                   "max_flagged_paragraph_pct", "humanize_passed")}
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
