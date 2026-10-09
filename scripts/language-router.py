#!/usr/bin/env python3
"""
language-router.py
==================
Language Router — Language detection, translation service routing, and
multilingual quality scoring.

Detects languages from text using Unicode script analysis and common word
frequency matching (stdlib only, no external APIs). Routes source/target
language pairs to a translation CAPABILITY — never to a hardcoded product:
the route action names what the language family needs from a translation
service, then resolves an actual service at RUN TIME from (1) the brand's
recorded preference, (2) translation MCP servers the user has already
connected, or (3) refuses to name one and hands back the resolution ladder
(the harness's own multilingual capability, scored by this script's
`score` action, is always available as the floor). Also scores translated
content across length ratio, formatting preservation, key-term consistency,
and placeholder integrity dimensions.

WHY: a routing table that says "family X → product Y" is a bet on the
2026 vendor landscape shipped inside a plugin that runs at arbitrary future
dates. Capability criteria age well; product endorsements do not.

Dependencies: none (stdlib only)

Usage:
    python language-router.py --action detect --text "यह एक हिंदी वाक्य है"
    python language-router.py --action detect --file content.txt
    python language-router.py --action route --source en --target hi
    python language-router.py --action route --source en --target de --brand acme
    python language-router.py --action score --original "Hello world" --translated "Bonjour le monde" --source en --target fr
    python language-router.py --action score --original "Hi {{name}}" --translated "Hola {{name}}" --source en --target es --do-not-translate "BrandX,TagLine"
    python language-router.py --action supported-languages
"""

import argparse
import io
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

# Force UTF-8 stdout on Windows (avoids cp1252 encoding errors)
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Unicode Script Ranges ──────────────────────────────────────────────────

SCRIPT_RANGES = {
    "Devanagari":  (0x0900, 0x097F),
    "Bengali":     (0x0980, 0x09FF),
    "Tamil":       (0x0B80, 0x0BFF),
    "Telugu":      (0x0C00, 0x0C7F),
    "Gujarati":    (0x0A80, 0x0AFF),
    "Kannada":     (0x0C80, 0x0CFF),
    "Malayalam":   (0x0D00, 0x0D7F),
    "Gurmukhi":    (0x0A00, 0x0A7F),
    "CJK":         (0x4E00, 0x9FFF),
    "Hiragana":    (0x3040, 0x309F),
    "Katakana":    (0x30A0, 0x30FF),
    "Hangul":      (0xAC00, 0xD7AF),
    "Arabic":      (0x0600, 0x06FF),
    "Cyrillic":    (0x0400, 0x04FF),
    "Thai":        (0x0E00, 0x0E7F),
}

# Script-to-language default mapping
SCRIPT_LANGUAGE_MAP = {
    "Bengali":   ("bn", "Bengali",   "Bengali"),
    "Tamil":     ("ta", "Tamil",     "Tamil"),
    "Telugu":    ("te", "Telugu",    "Telugu"),
    "Gujarati":  ("gu", "Gujarati",  "Gujarati"),
    "Kannada":   ("kn", "Kannada",   "Kannada"),
    "Malayalam": ("ml", "Malayalam",  "Malayalam"),
    "Gurmukhi":  ("pa", "Punjabi",   "Gurmukhi"),
    "Hangul":    ("ko", "Korean",    "Hangul"),
    "Cyrillic":  ("ru", "Russian",   "Cyrillic"),
    "Thai":      ("th", "Thai",      "Thai"),
}

# ── Common Words for Latin-Script Detection ────────────────────────────────

LATIN_LANGUAGE_WORDS = {
    "en": {
        "name": "English",
        "words": {"the", "is", "and", "of", "to", "in", "for", "with", "that",
                  "this", "are", "was", "have", "been", "not", "but", "they",
                  "from", "will", "would", "can", "which", "their", "what",
                  "about", "could", "should", "does", "has", "had", "were"},
    },
    "es": {
        "name": "Spanish",
        "words": {"el", "la", "de", "en", "los", "las", "del", "por", "con",
                  "una", "que", "es", "para", "como", "pero", "este", "esta",
                  "sus", "ser", "entre", "cuando", "muy", "desde", "sobre",
                  "tiene", "puede", "donde", "cada", "hasta", "nos"},
    },
    "fr": {
        "name": "French",
        "words": {"le", "la", "de", "les", "des", "en", "un", "une", "du",
                  "est", "dans", "pour", "que", "pas", "sur", "qui", "avec",
                  "sont", "mais", "nous", "vous", "cette", "ces", "aux",
                  "par", "tout", "fait", "peut", "comme", "aussi"},
    },
    "de": {
        "name": "German",
        "words": {"der", "die", "das", "und", "ist", "ein", "eine", "den",
                  "dem", "auf", "mit", "sich", "nicht", "auch", "noch",
                  "nach", "wird", "bei", "einer", "sind", "vom", "kann",
                  "oder", "wie", "aber", "hat", "nur", "werden", "zum"},
    },
    "pt": {
        "name": "Portuguese",
        "words": {"de", "da", "do", "em", "os", "as", "um", "uma", "que",
                  "para", "por", "com", "mais", "dos", "das", "foi", "ser",
                  "como", "seu", "sua", "tem", "mas", "aos", "pelo", "pela",
                  "isso", "pode", "entre", "seus", "quando"},
    },
    "it": {
        "name": "Italian",
        "words": {"di", "il", "la", "in", "che", "un", "una", "per", "del",
                  "della", "non", "con", "sono", "anche", "questo", "questa",
                  "dei", "dal", "alla", "degli", "delle", "hanno", "stato",
                  "tutto", "viene", "dopo", "nella", "essere", "molto"},
    },
    "nl": {
        "name": "Dutch",
        "words": {"de", "het", "een", "van", "en", "in", "is", "dat", "op",
                  "met", "voor", "niet", "zijn", "ook", "aan", "kan", "naar",
                  "maar", "worden", "deze", "door", "werd", "bij", "nog",
                  "wel", "meer", "geen", "moet", "tot", "heeft"},
    },
    "pl": {
        "name": "Polish",
        "words": {"nie", "to", "jest", "na", "do", "jak", "co", "za",
                  "ale", "tak", "od", "te", "czy", "tego", "tym", "po",
                  "przez", "tylko", "ich", "jego", "jako", "lub", "ten",
                  "tym", "bardzo", "jednak", "gdzie", "bez", "wszystko"},
    },
    "tr": {
        "name": "Turkish",
        "words": {"bir", "ve", "bu", "olan", "gibi", "daha",
                  "var", "ama", "hem", "kadar", "sonra", "bunu",
                  "ancak", "olarak", "ise", "her", "yeni", "buna",
                  "olan", "sadece", "tarih", "oldu", "olup", "olan"},
    },
}

# ── Marathi vs Hindi Differentiators ───────────────────────────────────────

MARATHI_WORDS = {
    "आहे", "आणि", "हे", "या", "त्या", "करणे", "होते", "असे", "केले",
    "मध्ये", "त्यांनी", "पण", "तो", "ती", "झाले", "नाही", "काही",
    "सर्व", "कसे", "आमच्या", "त्यांच्या", "असते", "आपल्या", "म्हणजे",
}

HINDI_WORDS = {
    "है", "और", "के", "को", "का", "में", "से", "पर", "यह", "एक",
    "की", "हैं", "कि", "ने", "नहीं", "तो", "भी", "हो", "कर",
    "इस", "जो", "था", "लिए", "वह", "अपने", "साथ", "सकते", "बहुत",
}

# ── Arabic vs Urdu Differentiators ─────────────────────────────────────────

URDU_WORDS = {
    "ہے", "اور", "کے", "کو", "کا", "میں", "سے", "پر", "یہ", "ایک",
    "کی", "ہیں", "کہ", "نے", "نہیں", "تو", "بھی", "ہو", "کر",
    "اس", "جو", "تھا", "لیے", "وہ", "اپنے", "ساتھ",
}

ARABIC_WORDS = {
    "في", "من", "على", "إلى", "هذا", "هذه", "التي", "الذي", "كان",
    "ما", "أن", "عن", "أو", "بعد", "قبل", "بين", "ذلك", "حتى",
    "لكن", "هو", "هي", "كل", "ثم", "أي", "عند", "مع", "قد",
}

# ── Language Families ──────────────────────────────────────────────────────

LANGUAGE_FAMILIES = {
    "indic": {
        "hi": "Hindi", "ta": "Tamil", "te": "Telugu", "bn": "Bengali",
        "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
        "pa": "Punjabi",
    },
    "european": {
        "de": "German", "fr": "French", "es": "Spanish", "it": "Italian",
        "pt": "Portuguese", "nl": "Dutch", "pl": "Polish", "ru": "Russian",
        "sv": "Swedish", "da": "Danish", "fi": "Finnish", "no": "Norwegian",
        "cs": "Czech", "ro": "Romanian", "hu": "Hungarian", "el": "Greek",
        "bg": "Bulgarian", "uk": "Ukrainian",
    },
    "cjk": {
        "ja": "Japanese", "ko": "Korean", "zh": "Chinese",
    },
    "semitic": {
        "ar": "Arabic", "he": "Hebrew", "fa": "Farsi",
    },
    "other": {
        "th": "Thai", "vi": "Vietnamese", "id": "Indonesian", "ms": "Malay",
        "tr": "Turkish", "ur": "Urdu", "en": "English",
    },
}

# Flatten for quick lookup: code -> (family, name)
_LANG_LOOKUP = {}
for _fam, _langs in LANGUAGE_FAMILIES.items():
    for _code, _name in _langs.items():
        _LANG_LOOKUP[_code] = (_fam, _name)

# ── RTL Languages ─────────────────────────────────────────────────────────

RTL_LANGUAGES = {"ar", "he", "fa", "ur"}

# ── Translation Expansion Ratios (from English) ───────────────────────────

EXPANSION_RATIOS = {
    "de": (1.10, 1.35),
    "fr": (1.15, 1.30),
    "es": (1.15, 1.30),
    "it": (1.10, 1.25),
    "ja": (0.50, 0.80),
    "zh": (0.50, 0.80),
    "ko": (0.70, 0.90),
    "hi": (0.90, 1.20),
    "ar": (0.80, 1.10),
}

DEFAULT_EXPANSION = (0.80, 1.50)

# ── Routing Tables ─────────────────────────────────────────────────────────

INDIC_CODES = {"hi", "ta", "te", "bn", "mr", "gu", "kn", "ml", "pa", "ur"}
EUROPEAN_CODES = {
    "de", "fr", "es", "it", "pt", "nl", "pl", "ru", "sv", "da", "fi",
    "no", "cs", "ro", "hu", "el", "bg", "uk",
}
CJK_CODES = {"ja", "ko", "zh"}
SEMITIC_CODES = {"ar", "he", "fa"}
SEA_CODES = {"th", "vi", "id", "ms"}

# What each language family NEEDS from a translation service. These are
# selection CRITERIA, not product names: the agent judges whichever services
# are actually available against them. Criteria age well; endorsements don't.
FAMILY_CAPABILITY_PROFILES = {
    "indic": {
        "capability_kind": "translation.indic",
        "service_criteria": [
            "native model coverage of the target Indic language (trained, not transliterated)",
            "script-aware output (Devanagari conjuncts, Tamil ligatures, Gurmukhi rendering)",
            "handles code-mixed content (English loanwords inside Indic sentences)",
        ],
        "notes": "Indic targets reward Indic-specialist services; judge candidates on native coverage of the SPECIFIC target language, not on brand.",
    },
    "european": {
        "capability_kind": "translation.european",
        "service_criteria": [
            "formality registers (German Sie/du, French vous/tu, Spanish usted/tú)",
            "glossary / do-not-translate term support",
            "idiomatic quality beyond word-level accuracy",
        ],
        "notes": "European targets need register control — a service without formality settings forces a manual pass on every B2B asset.",
    },
    "cjk": {
        "capability_kind": "translation.cjk",
        "service_criteria": [
            "context-aware segmentation (no word boundaries in the source)",
            "correct script mixing for Japanese (kanji/hiragana/katakana)",
            "Simplified vs Traditional Chinese variant control",
        ],
        "notes": "CJK quality varies sharply between services — sample-test before committing a campaign.",
    },
    "semitic": {
        "capability_kind": "translation.semitic",
        "service_criteria": [
            "RTL text integrity (no direction corruption around numerals/Latin embeds)",
            "coverage of the specific target (Arabic dialect awareness where relevant)",
        ],
        "notes": "RTL rendering bugs surface in templates, not in the translation text — score AND visually verify.",
    },
    "sea": {
        "capability_kind": "translation.sea",
        "service_criteria": [
            "genuine coverage of the target (Thai/Vietnamese/Indonesian/Malay quality varies widely)",
        ],
        "notes": "Southeast Asian coverage is the thinnest across the industry — sample-test candidates first.",
    },
    "default": {
        "capability_kind": "translation.general",
        "service_criteria": [
            "broad language coverage with published quality benchmarks",
        ],
        "notes": "General-purpose translation; verify the pair is actually supported before sending a batch.",
    },
}

# Recognition data, NOT endorsement: name fragments that identify a configured
# MCP server as translation-capable so the user's ALREADY-CONNECTED tools can
# be discovered (rung 2 of the capability ladder). A server matching none of
# these can still be used via an explicit brand preference — unknown ≠ unusable.
TRANSLATION_SERVER_HINTS = (
    "translat", "deepl", "sarvam", "lara", "lingo", "lokalise", "crowdin",
    "phrase", "smartling", "weglot", "localiz",
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_text(args):
    """Retrieve text from --text or --file argument."""
    if args.text:
        return args.text
    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(json.dumps({"error": f"File not found: {args.file}"}))
            sys.exit(1)
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            print(json.dumps({"error": f"Cannot read file: {exc}"}))
            sys.exit(1)
    return None


def _classify_char(cp):
    """Return the script name for a Unicode code point, or None."""
    for script, (lo, hi) in SCRIPT_RANGES.items():
        if lo <= cp <= hi:
            return script
    return None


def _is_latin(cp):
    """Check if a code point is in the Latin script (Basic + Extended)."""
    return (0x0041 <= cp <= 0x024F) or (0x1E00 <= cp <= 0x1EFF)


def _word_tokenize(text):
    """Simple whitespace + punctuation tokenizer."""
    return re.findall(r"[a-zA-Z\u00C0-\u024F\u1E00-\u1EFF]+", text.lower())


def _count_words(text):
    """Count words using a broad Unicode-aware split."""
    words = re.findall(r"\S+", text)
    return len(words)


# ── Action: detect ──────────────────────────────────────────────────────────

def _detect_script_distribution(text):
    """Analyse character-level script distribution."""
    counts = Counter()
    latin_count = 0
    total = 0
    for ch in text:
        cp = ord(ch)
        if ch.isspace() or unicodedata.category(ch).startswith("P"):
            continue
        total += 1
        script = _classify_char(cp)
        if script:
            counts[script] += 1
        elif _is_latin(cp):
            latin_count += 1
    return counts, latin_count, total


def _detect_devanagari_language(text):
    """Differentiate Hindi from Marathi within Devanagari text."""
    words = set(re.findall(r"[\u0900-\u097F]+", text))
    marathi_hits = len(words & MARATHI_WORDS)
    hindi_hits = len(words & HINDI_WORDS)
    if marathi_hits > hindi_hits and marathi_hits >= 2:
        return "mr", "Marathi"
    return "hi", "Hindi"


def _detect_arabic_script_language(text):
    """Differentiate Arabic from Urdu within Arabic-script text."""
    words = set(re.findall(r"[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]+", text))
    urdu_hits = len(words & URDU_WORDS)
    arabic_hits = len(words & ARABIC_WORDS)
    if urdu_hits > arabic_hits and urdu_hits >= 2:
        return "ur", "Urdu"
    return "ar", "Arabic"


def _detect_cjk_language(text):
    """Differentiate Chinese from Japanese when CJK characters are present."""
    has_hiragana = bool(re.search(r"[\u3040-\u309F]", text))
    has_katakana = bool(re.search(r"[\u30A0-\u30FF]", text))
    if has_hiragana or has_katakana:
        return "ja", "Japanese"
    return "zh", "Chinese"


def _detect_latin_language(text):
    """Detect which Latin-script language the text is most likely in."""
    tokens = _word_tokenize(text)
    if not tokens:
        return "en", "English", 0.0

    token_set = set(tokens)
    token_count = len(tokens)

    best_code = "en"
    best_name = "English"
    best_score = 0.0

    for code, info in LATIN_LANGUAGE_WORDS.items():
        hits = sum(1 for t in tokens if t in info["words"])
        score = hits / token_count if token_count else 0.0
        if score > best_score:
            best_score = score
            best_code = code
            best_name = info["name"]

    return best_code, best_name, best_score


def action_detect(args):
    """Detect the language of the provided text."""
    text = _get_text(args)
    if not text:
        print(json.dumps({"error": "Provide --text or --file for detection"}))
        sys.exit(1)

    script_counts, latin_count, total = _detect_script_distribution(text)
    if total == 0:
        print(json.dumps({
            "detected_language": "unknown",
            "language_name": "Unknown",
            "script": "Unknown",
            "confidence": 0.0,
            "secondary_detection": None,
            "sample_text": text[:80],
        }))
        return

    # Determine dominant script
    dominant_script = None
    dominant_count = 0
    for script, count in script_counts.items():
        if count > dominant_count:
            dominant_script = script
            dominant_count = count

    # Latin might be dominant
    if latin_count > dominant_count:
        dominant_script = "Latin"
        dominant_count = latin_count

    confidence = dominant_count / total if total else 0.0

    # Resolve language from dominant script
    lang_code = "unknown"
    lang_name = "Unknown"
    script_name = dominant_script or "Unknown"
    secondary = None

    if dominant_script == "Latin":
        lang_code, lang_name, word_conf = _detect_latin_language(text)
        script_name = "Latin"
        # Blend character confidence with word confidence
        confidence = (confidence * 0.4) + (word_conf * 0.6) if word_conf > 0 else confidence * 0.5
        if word_conf < 0.05:
            # Very low word match — could be an unsupported Latin-script language
            secondary = {"note": "Low word-frequency match; language may not be in detection set"}
    elif dominant_script == "Devanagari":
        lang_code, lang_name = _detect_devanagari_language(text)
        # If Marathi detected, note Hindi as secondary possibility
        if lang_code == "mr":
            secondary = {"language": "hi", "language_name": "Hindi",
                         "note": "Marathi and Hindi share Devanagari script"}
    elif dominant_script == "Arabic":
        lang_code, lang_name = _detect_arabic_script_language(text)
        if lang_code == "ur":
            secondary = {"language": "ar", "language_name": "Arabic",
                         "note": "Urdu and Arabic share similar script ranges"}
        else:
            secondary = {"language": "ur", "language_name": "Urdu",
                         "note": "Urdu and Arabic share similar script ranges"}
    elif dominant_script == "CJK":
        lang_code, lang_name = _detect_cjk_language(text)
        script_name = "CJK"
        if lang_code == "zh":
            secondary = {"language": "ja", "language_name": "Japanese",
                         "note": "Japanese also uses CJK characters (kanji)"}
    elif dominant_script in ("Hiragana", "Katakana"):
        lang_code, lang_name = "ja", "Japanese"
        script_name = dominant_script
    elif dominant_script in SCRIPT_LANGUAGE_MAP:
        lang_code, lang_name, script_name = SCRIPT_LANGUAGE_MAP[dominant_script]
    elif dominant_script == "Hangul":
        lang_code, lang_name, script_name = "ko", "Korean", "Hangul"

    if confidence < 0.50:
        lang_code = "unknown"
        lang_name = "Unknown"

    sample = text.strip()[:80]
    if len(text.strip()) > 80:
        sample += "..."

    result = {
        "detected_language": lang_code,
        "language_name": lang_name,
        "script": script_name,
        "confidence": round(confidence, 4),
        "secondary_detection": secondary,
        "sample_text": sample,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


# ── Action: route ───────────────────────────────────────────────────────────

def _get_language_family_for_routing(code):
    """Determine the routing family for a language code."""
    if code in INDIC_CODES:
        return "indic"
    if code in EUROPEAN_CODES:
        return "european"
    if code in CJK_CODES:
        return "cjk"
    if code in SEMITIC_CODES:
        return "semitic"
    if code in SEA_CODES:
        return "sea"
    return "default"


def _special_considerations(target_code, family):
    """Return special considerations for a language/family."""
    considerations = []
    if family == "cjk":
        if target_code == "zh":
            considerations.append("Verify Simplified vs Traditional Chinese variant (zh-CN / zh-TW)")
        if target_code == "ja":
            considerations.append("Japanese uses mixed scripts (kanji, hiragana, katakana); verify script usage")
        if target_code == "ko":
            considerations.append("Korean honorific levels may need to match brand tone")
    if family == "indic":
        considerations.append("Verify script-specific rendering and font support in target platform")
        if target_code in ("hi", "mr"):
            considerations.append("Devanagari script — ensure proper conjunct rendering")
    if target_code in RTL_LANGUAGES:
        considerations.append("RTL layout direction — verify bidirectional text handling in templates")
        considerations.append("Ensure email/web templates support dir='rtl' attribute")
    return considerations


def _connected_translation_servers():
    """Names of translation-capable MCP servers the user has ACTUALLY
    configured (read live from .mcp.json — never assumed)."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from _connector_registry import _load_mcp_json
        servers = _load_mcp_json()
    except Exception:
        servers = {}
    return sorted(n for n in servers
                  if any(h in n.lower() for h in TRANSLATION_SERVER_HINTS))


def _brand_translation_pref(brand, target):
    """The brand's recorded translation preference for a target language, if
    any. Free-form server name — the user's explicit choice outranks routing."""
    if not brand:
        return None
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from _common import brand_dir
        profile_path = brand_dir(brand) / "profile.json"
        if not profile_path.exists():
            return None
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        prefs = (profile.get("language") or {}).get("translation_preferences") or {}
        return prefs.get(target) or None
    except Exception:
        return None


RESOLUTION_LADDER = [
    "Use the harness's own multilingual capability: translate directly, then "
    "score with `--action score`; below 85 flag for human review.",
    "Use any translation tool the user has ALREADY connected (MCP server or "
    "otherwise) — never instruct installing a commercial product.",
    "Ask the user which translation service to use, and record the answer "
    "with /digital-marketing-pro:language-config set-translation-pref so the "
    "next run resolves without asking.",
]


def action_route(args):
    """Route a translation pair to a capability, resolving a concrete service
    only from the brand's recorded preference or the user's connected servers.
    Never names a product from a shipped table."""
    source = args.source
    target = args.target
    if not source or not target:
        print(json.dumps({"error": "Both --source and --target language codes are required"}))
        sys.exit(1)

    family = _get_language_family_for_routing(target)
    profile = FAMILY_CAPABILITY_PROFILES[family]

    display_family = "southeast_asian" if family == "sea" else family
    considerations = _special_considerations(target, family)
    connected = _connected_translation_servers()
    pref = _brand_translation_pref(getattr(args, "brand", None), target)

    result = {
        "source": source,
        "target": target,
        "language_family": display_family,
        "capability_kind": profile["capability_kind"],
        "service_criteria": profile["service_criteria"],
        "notes": profile["notes"],
        "rtl": target in RTL_LANGUAGES,
        "special_considerations": considerations,
        "connected_candidates": connected,
        "brand_preference": pref,
    }

    if pref:
        result["recommended_service"] = pref
        result["basis"] = "brand-preference"
        if connected and pref not in connected:
            result["warning"] = (
                f"Brand prefers {pref!r} for {target!r} but no configured MCP server "
                "matches it — connect it, or update the preference via "
                "language-config set-translation-pref.")
    elif len(connected) == 1:
        result["recommended_service"] = connected[0]
        result["basis"] = "connected-servers"
    elif connected:
        result["recommended_service"] = None
        result["basis"] = "connected-servers"
        result["selection_instruction"] = (
            "Multiple connected candidates — pick the one that best meets "
            "service_criteria for this target; record the choice with "
            "language-config set-translation-pref so future runs resolve directly.")
    else:
        result["recommended_service"] = None
        result["basis"] = "unresolved"
        result["resolution_ladder"] = RESOLUTION_LADDER

    print(json.dumps(result, indent=2, ensure_ascii=False))


# ── Action: score ───────────────────────────────────────────────────────────

def _score_length_ratio(original, translated, source, target):
    """Score the translation length ratio against expected expansion."""
    orig_words = _count_words(original)
    trans_words = _count_words(translated)

    if orig_words == 0:
        return {"score": 100, "original_words": 0, "translated_words": trans_words,
                "ratio": 0.0, "expected_range": list(DEFAULT_EXPANSION)}

    ratio = trans_words / orig_words

    # Get expected range (keyed by EN -> target, but use as default guidance)
    expected = EXPANSION_RATIOS.get(target, DEFAULT_EXPANSION)
    lo, hi = expected

    if lo <= ratio <= hi:
        score = 100
    else:
        if ratio < lo:
            deviation_pct = ((lo - ratio) / lo) * 100
        else:
            deviation_pct = ((ratio - hi) / hi) * 100
        # -20 per 10% deviation
        penalty = (deviation_pct / 10.0) * 20
        score = max(0, 100 - penalty)

    return {
        "score": round(score),
        "original_words": orig_words,
        "translated_words": trans_words,
        "ratio": round(ratio, 4),
        "expected_range": list(expected),
    }


def _extract_formatting_elements(text):
    """Extract markdown and HTML formatting elements from text."""
    elements = []

    # Markdown headings
    for m in re.finditer(r"^(#{1,6})\s", text, re.MULTILINE):
        elements.append(("heading", m.group(0).strip()))

    # Bold
    for m in re.finditer(r"\*\*[^*]+\*\*", text):
        elements.append(("bold", m.group(0)))

    # Italic (single asterisk or underscore, not inside bold)
    for m in re.finditer(r"(?<!\*)\*(?!\*)[^*]+\*(?!\*)", text):
        elements.append(("italic", m.group(0)))
    for m in re.finditer(r"(?<!_)_(?!_)[^_]+_(?!_)", text):
        elements.append(("italic", m.group(0)))

    # Markdown links
    for m in re.finditer(r"\[[^\]]*\]\([^)]*\)", text):
        elements.append(("link", m.group(0)))

    # HTML tags
    for m in re.finditer(r"<[^>]+>", text):
        elements.append(("html_tag", m.group(0)))

    # Bullet lists
    for m in re.finditer(r"^[\s]*[-*+]\s", text, re.MULTILINE):
        elements.append(("bullet", m.group(0).strip()))

    # Numbered lists
    for m in re.finditer(r"^[\s]*\d+\.\s", text, re.MULTILINE):
        elements.append(("numbered", m.group(0).strip()))

    # Line breaks (double newline = paragraph break)
    double_breaks = len(re.findall(r"\n\n", text))
    for _ in range(double_breaks):
        elements.append(("paragraph_break", "\\n\\n"))

    return elements


def _score_formatting_preservation(original, translated):
    """Score how well formatting elements are preserved."""
    orig_elements = _extract_formatting_elements(original)
    if not orig_elements:
        return {"score": 100, "original_elements": 0, "preserved_elements": 0, "missing": []}

    trans_text = translated
    preserved = 0
    missing = []

    # For structural elements (headings, html tags, links), check exact presence
    for etype, evalue in orig_elements:
        if etype == "html_tag":
            if evalue in trans_text:
                preserved += 1
            else:
                missing.append(evalue)
        elif etype == "link":
            # Links: the URL part should be preserved, text may be translated
            url_match = re.search(r"\(([^)]*)\)", evalue)
            if url_match and url_match.group(1) in trans_text:
                preserved += 1
            elif evalue in trans_text:
                preserved += 1
            else:
                missing.append(evalue)
        elif etype == "heading":
            # Heading markers should be present
            if evalue.split()[0] in trans_text:
                preserved += 1
            else:
                missing.append(evalue)
        elif etype in ("bold", "italic"):
            # Check that bold/italic markers exist in translated text
            if etype == "bold" and "**" in trans_text:
                preserved += 1
            elif etype == "italic" and ("*" in trans_text or "_" in trans_text):
                preserved += 1
            else:
                missing.append(evalue)
        elif etype == "bullet":
            bullets_in_trans = re.findall(r"^[\s]*[-*+]\s", trans_text, re.MULTILINE)
            if bullets_in_trans:
                preserved += 1
            else:
                missing.append("bullet list marker")
        elif etype == "numbered":
            nums_in_trans = re.findall(r"^[\s]*\d+\.\s", trans_text, re.MULTILINE)
            if nums_in_trans:
                preserved += 1
            else:
                missing.append("numbered list marker")
        elif etype == "paragraph_break":
            if "\n\n" in trans_text:
                preserved += 1
            else:
                missing.append("paragraph break")

    total = len(orig_elements)
    score = (preserved / total) * 100 if total else 100

    return {
        "score": round(score),
        "original_elements": total,
        "preserved_elements": preserved,
        "missing": missing,
    }


def _score_key_term_consistency(original, translated, dnt_terms):
    """Score preservation of do-not-translate terms."""
    if not dnt_terms:
        return {"score": 100, "total_terms": 0, "preserved": 0, "missing": []}

    present_in_original = []
    for term in dnt_terms:
        term_stripped = term.strip()
        if term_stripped and term_stripped in original:
            present_in_original.append(term_stripped)

    if not present_in_original:
        return {"score": 100, "total_terms": 0, "preserved": 0, "missing": []}

    preserved = []
    missing = []
    for term in present_in_original:
        if term in translated:
            preserved.append(term)
        else:
            missing.append(term)

    total = len(present_in_original)
    score = (len(preserved) / total) * 100 if total else 100

    return {
        "score": round(score),
        "total_terms": total,
        "preserved": len(preserved),
        "missing": missing,
    }


def _extract_placeholders(text):
    """Extract template placeholders, merge tags, and tracking elements."""
    placeholders = set()

    # {{variable}} — double curly braces
    for m in re.finditer(r"\{\{[^}]+\}\}", text):
        placeholders.add(m.group(0))

    # {variable} — single curly braces (but not already matched as double)
    for m in re.finditer(r"(?<!\{)\{[^{}]+\}(?!\})", text):
        placeholders.add(m.group(0))

    # %variable%
    for m in re.finditer(r"%[A-Za-z_][A-Za-z0-9_]*%", text):
        placeholders.add(m.group(0))

    # [MERGE_TAG] style — uppercase with underscores inside brackets
    for m in re.finditer(r"\[[A-Z][A-Z0-9_]*\]", text):
        placeholders.add(m.group(0))

    # *|MERGE_TAG|* — Mailchimp style
    for m in re.finditer(r"\*\|[A-Z][A-Z0-9_]*\|\*", text):
        placeholders.add(m.group(0))

    # URL parameters (?utm_source=... &utm_medium=... etc.)
    for m in re.finditer(r"[?&][A-Za-z_][A-Za-z0-9_]*=[^&\s]*", text):
        placeholders.add(m.group(0))

    return placeholders


def _score_placeholder_integrity(original, translated):
    """Score preservation of placeholders and merge tags."""
    orig_placeholders = _extract_placeholders(original)

    if not orig_placeholders:
        return {"score": 100, "total_placeholders": 0, "preserved": 0, "missing": []}

    preserved = []
    missing = []
    for ph in orig_placeholders:
        if ph in translated:
            preserved.append(ph)
        else:
            missing.append(ph)

    total = len(orig_placeholders)
    score = (len(preserved) / total) * 100 if total else 100

    return {
        "score": round(score),
        "total_placeholders": total,
        "preserved": len(preserved),
        "missing": missing,
    }


def _interpret_score(score):
    """Return a human-readable interpretation of the composite score."""
    if score >= 95:
        return "Excellent translation quality"
    if score >= 85:
        return "Good translation quality"
    if score >= 70:
        return "Acceptable translation quality — review flagged dimensions"
    if score >= 50:
        return "Poor translation quality — significant issues detected"
    return "Very poor translation quality — retranslation recommended"


def action_score(args):
    """Score a translated text against its original."""
    original = args.original
    translated = args.translated
    source = args.source
    target = args.target

    if not original or not translated:
        print(json.dumps({"error": "Both --original and --translated are required for scoring"}))
        sys.exit(1)
    if not source or not target:
        print(json.dumps({"error": "Both --source and --target language codes are required for scoring"}))
        sys.exit(1)

    dnt_terms = []
    if args.do_not_translate:
        dnt_terms = [t.strip() for t in args.do_not_translate.split(",") if t.strip()]

    dim_length = _score_length_ratio(original, translated, source, target)
    dim_format = _score_formatting_preservation(original, translated)
    dim_terms = _score_key_term_consistency(original, translated, dnt_terms)
    dim_placeholders = _score_placeholder_integrity(original, translated)

    # Weighted average: each dimension 25%
    composite = (
        dim_length["score"] * 0.25
        + dim_format["score"] * 0.25
        + dim_terms["score"] * 0.25
        + dim_placeholders["score"] * 0.25
    )

    result = {
        "multilingual_score": round(composite),
        "interpretation": _interpret_score(composite),
        "dimensions": {
            "length_ratio": dim_length,
            "formatting_preservation": dim_format,
            "key_term_consistency": dim_terms,
            "placeholder_integrity": dim_placeholders,
        },
        "source_language": source,
        "target_language": target,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


# ── Action: supported-languages ─────────────────────────────────────────────

def action_supported_languages(args):
    """List all supported languages grouped by family."""
    total = sum(len(v) for v in LANGUAGE_FAMILIES.values())
    output = dict(LANGUAGE_FAMILIES)
    output["total_languages"] = total
    print(json.dumps(output, indent=2, ensure_ascii=False))


# ── CLI ─────────────────────────────────────────────────────────────────────

def build_parser():
    """Build the argument parser with all actions and arguments."""
    parser = argparse.ArgumentParser(
        prog="language-router",
        description=(
            "Language detection, translation service routing, and multilingual "
            "quality scoring.\n\n"
            "Actions:\n"
            "  detect               Detect language from text using Unicode script\n"
            "                       analysis and common word frequency matching.\n"
            "  route                Route a source/target language pair to a translation\n"
            "                       capability; resolves a concrete service only from the\n"
            "                       brand's preference or connected MCP servers.\n"
            "  score                Score translated content across length ratio,\n"
            "                       formatting preservation, key-term consistency,\n"
            "                       and placeholder integrity.\n"
            "  supported-languages  List all supported languages grouped by family."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=["detect", "route", "score", "supported-languages"],
        help="Action to perform.",
    )
    parser.add_argument(
        "--text",
        help="Inline text content (for detect action).",
    )
    parser.add_argument(
        "--file",
        help="Path to a text file (for detect action).",
    )
    parser.add_argument(
        "--source",
        help="Source language code, e.g. 'en' (for route/score actions).",
    )
    parser.add_argument(
        "--target",
        help="Target language code, e.g. 'hi' (for route/score actions).",
    )
    parser.add_argument(
        "--brand", type=_common.path_component,
        help="Brand slug — lets route honor the brand's recorded translation "
             "preference for the target language (for route action).",
    )
    parser.add_argument(
        "--original",
        help="Original text before translation (for score action).",
    )
    parser.add_argument(
        "--translated",
        help="Translated text to evaluate (for score action).",
    )
    parser.add_argument(
        "--do-not-translate",
        dest="do_not_translate",
        help="Comma-separated terms that must be preserved verbatim in translation (for score action).",
    )
    return parser


ACTIONS = {
    "detect": action_detect,
    "route": action_route,
    "score": action_score,
    "supported-languages": action_supported_languages,
}


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    action_fn = ACTIONS.get(args.action)
    if action_fn:
        action_fn(args)
    else:
        print(json.dumps({"error": f"Unknown action: {args.action}"}))
        sys.exit(1)
