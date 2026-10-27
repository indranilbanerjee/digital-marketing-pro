"""scripts/platform_specs.json is the one sourced copy of each social-platform limit.

Before 3.40.0 the same limit lived in platform-specs.md, platform-publishing-specs.md,
social-post-formatter.py, hashtag-analyzer.py, schedule-social and three content guides, and they
disagreed: Instagram's hashtag cap was 30 in four places and "15-20" in two after Instagram cut it to
5 (2025-12-18); Threads took 5 hashtags where it allows one topic tag; Facebook reels were "up to 90
seconds" after Meta lifted the limit. The checks:
  * every field carries value, source_url, source_date, verified_on and review_by;
  * no review_by is within 30 days (DMP_TODAY=YYYY-MM-DD freezes today; the weekly dated job runs it);
  * a doc that states a spec number tags it, "5 (platform_specs.json: instagram.hashtags_cap)", and
    the number must equal the JSON's;
  * the stale values the 2026-10-27 audit found are gone from the docs;
  * the two scripts take their limits from the file.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
SPECS = SCRIPTS / "platform_specs.json"
WARN_DAYS = 30
FIELDS = ("value", "source_url", "source_date", "verified_on", "review_by")
TAGGED = re.compile(r"(\d[\d,]*)\s*(characters|chars|hashtags?|seconds|sec|min(?:utes)?)?\s*"
                    r"\(platform_specs\.json: ([a-z_]+)\.([a-z_]+)\)")
UNTAGGED_VALUE = re.compile(r"(?:Any length|no length limit)[^\n(]{0,60}\(platform_specs\.json: ([a-z_]+)\.([a-z_]+)\)", re.I)
# The stale values the 2026-10-27 audit found, by file pattern: none may come back.
STALE = [
    (r"Hashtag limit \| 30 max", "Instagram's hashtag cap is 5"),
    (r"\(30 max\)", "Instagram's hashtag cap is 5"),
    (r"Instagram: 15-20", "Instagram allows 5 hashtags"),
    (r"15-20 in first comment", "Instagram allows 5 hashtags"),
    (r"5-15 relevant hashtags", "Instagram allows 5 hashtags"),
    (r"up to 3 min with some accounts", "Instagram reels run to 20 minutes"),
    (r"\| Duration \| Up to 90 seconds \|", "Facebook reels have no length limit"),
    (r"\| Caption limit \| 4,000 characters \|", "TikTok's caption number is unresolved; 2,200 fits either"),
    (r"Instagram Feed Video \|", "Instagram videos post as reels (20 minutes)"),
]
LIVE = ["README.md", "AGENTS.md", "docs/*.md", "skills/**/*.md", "agents/*.md", "commands/*.md"]


def today() -> date:
    frozen = os.environ.get("DMP_TODAY")
    return date.fromisoformat(frozen) if frozen else date.today()


def load() -> dict:
    return json.loads(SPECS.read_text(encoding="utf-8"))["platforms"]


def provenance_problems(platforms: dict, on: date) -> list[str]:
    out = []
    for platform, fields in platforms.items():
        for name, entry in fields.items():
            where = f"{platform}.{name}"
            missing = [k for k in FIELDS if k not in entry]
            if missing:
                out.append(f"{where}: missing {', '.join(missing)}")
                continue
            if not str(entry["source_url"]).startswith("https://"):
                out.append(f"{where}: source_url must be an https URL")
            for k in ("source_date", "verified_on"):
                if entry[k] is not None:
                    date.fromisoformat(entry[k])
            due = date.fromisoformat(entry["review_by"])
            if due - on <= timedelta(days=WARN_DAYS):
                out.append(f"{where}: review_by {due} is within {WARN_DAYS} days; re-read {entry['source_url']} "
                           f"and update value, verified_on and review_by")
    return out


def _number(text: str, unit: str | None, field: str):
    n = int(text.replace(",", ""))
    if field.endswith("_seconds") and unit and unit.startswith("min"):
        n *= 60
    return n


def prose_problems(root: Path, platforms: dict) -> list[str]:
    out = []
    for path in sorted({p for pattern in LIVE for p in root.glob(pattern)}):
        rel = path.relative_to(root)
        for n, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            for m in TAGGED.finditer(line):
                platform, field = m.group(3), m.group(4)
                entry = platforms.get(platform, {}).get(field)
                if entry is None:
                    out.append(f"{rel}:{n}: no such spec {platform}.{field}")
                elif _number(m.group(1), m.group(2), field) != entry["value"]:
                    out.append(f"{rel}:{n}: says {m.group(1)} {m.group(2) or ''} for {platform}.{field}, "
                               f"the spec says {entry['value']}")
            for m in UNTAGGED_VALUE.finditer(line):
                entry = platforms.get(m.group(1), {}).get(m.group(2))
                if entry is None or entry["value"] is not None:
                    out.append(f"{rel}:{n}: says no limit for {m.group(1)}.{m.group(2)}, the spec doesn't")
            for pattern, why in STALE:
                if re.search(pattern, line):
                    out.append(f"{rel}:{n}: stale value ({why})")
    return out


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


class TestPlatformSpecs(unittest.TestCase):

    def test_every_field_has_provenance_and_a_review_date_ahead(self):
        problems = provenance_problems(load(), today())
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_docs_agree_with_the_spec(self):
        problems = prose_problems(REPO, load())
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_the_tags_are_used(self):
        # The guard only checks tagged numbers; make sure the main tables carry tags.
        text = (REPO / "skills/context-engine/platform-specs.md").read_text(encoding="utf-8")
        self.assertGreaterEqual(len(TAGGED.findall(text)), 4)

    def test_scripts_read_the_spec(self):
        specs = load()
        analyzer = _load_script("hashtag-analyzer")
        self.assertEqual(analyzer.PLATFORM_LIMITS["instagram"]["absolute_max"], specs["instagram"]["hashtags_cap"]["value"])
        self.assertEqual(analyzer.PLATFORM_LIMITS["threads"]["absolute_max"], specs["threads"]["topic_tags_cap"]["value"])
        formatter = _load_script("social-post-formatter")
        self.assertEqual(formatter.PLATFORM_SPECS["instagram"]["limits"]["post"]["hashtags"], 5)
        self.assertEqual(formatter.PLATFORM_SPECS["tiktok"]["limits"]["post"]["chars"], specs["tiktok"]["caption_chars"]["value"])
        self.assertEqual(formatter.PLATFORM_SPECS["threads"]["limits"]["post"]["hashtags"], 1)

    def test_plants(self):
        import tempfile
        specs = {"instagram": {"hashtags_cap": {"value": 5, "source_url": "https://x", "source_date": None,
                                                "verified_on": None, "review_by": "2026-12-31"}}}
        self.assertEqual(provenance_problems(specs, date(2026, 11, 30)), [])  # 31 days ahead
        self.assertIn("within 30 days", provenance_problems(specs, date(2026, 12, 1))[0])
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "README.md").write_text(
                "Instagram allows 30 hashtags (platform_specs.json: instagram.hashtags_cap).\n"
                "| Hashtag limit | 30 max, 3-5 recommended |\n"
                "Instagram allows 5 (platform_specs.json: instagram.hashtags_cap).\n", encoding="utf-8")
            got = prose_problems(Path(tmp), specs)
        self.assertEqual(len(got), 2, got)


if __name__ == "__main__":
    unittest.main()
