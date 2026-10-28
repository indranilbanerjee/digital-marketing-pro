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
  * the two scripts take their limits from the file, and the formatter's table states the numbers it
    uses (at 25ae7cf it still said 5 Facebook hashtags and 120,000 LinkedIn article characters);
  * what the 2026-10-28 re-read of LinkedIn, X, Facebook and Bluesky corrected stays corrected: the
    LinkedIn article limit is 125,000 (the file said 120,000), a LinkedIn photo 5 MB (prose said 8 MB),
    X takes no WebP, and a Facebook Page photo is 10 MB without WebP (prose said 30 MB, the ads figure).
"""
from __future__ import annotations

import ast
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
TAGGED = re.compile(r"(\d[\d,]*)\s*(characters|chars|hashtags?|seconds|sec|min(?:utes)?|MB)?\s*"
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
# The 2026-10-28 re-read, by section, since Meta Ads rightly keeps 30 MB further down the same file.
PLATFORM_MD = "skills/context-engine/platform-specs.md"
STALE_IN_SECTION = [
    (PLATFORM_MD, "#### LinkedIn Post", r"\| Max image file size \| 8 MB", "a LinkedIn photo is 5 MB"),
    (PLATFORM_MD, "### Twitter/X", r"WebP", "X accepts GIF, JPEG and PNG only"),
    (PLATFORM_MD, "#### Facebook Post", r"WebP", "a Page photo upload takes JPEG, PNG, GIF, BMP and TIFF"),
    (PLATFORM_MD, "#### Facebook Post", r"\| Max image file size \| 30 MB", "a Page photo is 10 MB; 30 MB is ads"),
]
STALE_SPECS = [("linkedin", "article_chars", 120000, "LinkedIn says 125,000 (help answer a522483)")]
# Fields read at their vendor page on 2026-10-28; a later re-read may move the date on, never back.
READ_2026_10_28 = [("linkedin", "post_chars"), ("linkedin", "article_chars"), ("linkedin", "image_max_mb"),
                   ("twitter", "post_chars"), ("twitter", "hashtags_advised"), ("twitter", "link_chars"),
                   ("facebook", "image_max_mb"), ("bluesky", "post_chars")]
LIVE =["README.md", "AGENTS.md", "docs/*.md", "skills/**/*.md", "agents/*.md", "commands/*.md"]


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
    for rel, heading, pattern, why in STALE_IN_SECTION:
        path = root / rel
        if path.exists():
            for n, line in _section(path.read_text(encoding="utf-8-sig").splitlines(), heading):
                if re.search(pattern, line):
                    out.append(f"{rel}:{n}: stale value under {heading!r} ({why})")
    return out


def _section(lines: list[str], heading: str):
    """(line number, line) from `heading` down to the next heading of the same or a higher level."""
    level = len(heading) - len(heading.lstrip("#"))
    inside = False
    for n, line in enumerate(lines, 1):
        if line.startswith("#"):
            this = len(line) - len(line.lstrip("#"))
            if line.strip() == heading:
                inside = True
                continue
            if inside and this <= level:
                return
        if inside:
            yield n, line


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
        tagged = {(m.group(3), m.group(4)) for m in TAGGED.finditer(text)}
        for field in (("linkedin", "article_chars"), ("linkedin", "image_max_mb"), ("facebook", "image_max_mb")):
            self.assertIn(field, tagged, f"platform-specs.md no longer tags {'.'.join(field)}, so the guard "
                                         f"can't check that number")

    def test_scripts_read_the_spec(self):
        specs = load()
        analyzer = _load_script("hashtag-analyzer")
        self.assertEqual(analyzer.PLATFORM_LIMITS["instagram"]["absolute_max"], specs["instagram"]["hashtags_cap"]["value"])
        self.assertEqual(analyzer.PLATFORM_LIMITS["threads"]["absolute_max"], specs["threads"]["topic_tags_cap"]["value"])
        formatter = _load_script("social-post-formatter")
        self.assertEqual(formatter.PLATFORM_SPECS["instagram"]["limits"]["post"]["hashtags"], 5)
        self.assertEqual(formatter.PLATFORM_SPECS["tiktok"]["limits"]["post"]["chars"], specs["tiktok"]["caption_chars"]["value"])
        self.assertEqual(formatter.PLATFORM_SPECS["threads"]["limits"]["post"]["hashtags"], 1)
        self.assertEqual(formatter.PLATFORM_SPECS["facebook"]["limits"]["post"]["hashtags"],
                         specs["facebook"]["hashtags_advised"]["value"][1])
        self.assertEqual(formatter.PLATFORM_SPECS["linkedin"]["limits"]["article"]["chars"],
                         specs["linkedin"]["article_chars"]["value"])

    def test_formatter_table_states_the_numbers_it_uses(self):
        # The import overwrites the table from the file, so a literal that differs is a number in the
        # source the script never uses; at 25ae7cf the table said 5 Facebook hashtags, 5 for X, 30 for
        # Instagram and 120,000 LinkedIn article characters.
        source = (SCRIPTS / "social-post-formatter.py").read_text(encoding="utf-8")
        literal = next(ast.literal_eval(node.value) for node in ast.parse(source).body
                       if isinstance(node, ast.Assign)
                       and any(getattr(t, "id", None) == "PLATFORM_SPECS" for t in node.targets))
        used = _load_script("social-post-formatter").PLATFORM_SPECS
        differ = [f"{platform}.{kind}.{key}: the table says {value}, the script uses {used[platform]['limits'][kind][key]}"
                  for platform, row in literal.items() for kind, limits in row["limits"].items()
                  for key, value in limits.items() if used[platform]["limits"][kind][key] != value]
        self.assertEqual(differ, [], "\n  " + "\n  ".join(differ))

    def test_values_the_2026_10_28_reread_corrected(self):
        specs = load()
        for platform, field, old, why in STALE_SPECS:
            self.assertNotEqual(specs[platform][field]["value"], old, f"{platform}.{field} is back at {old}: {why}")
        for platform, field in READ_2026_10_28:
            entry = specs[platform][field]
            self.assertIsNotNone(entry["verified_on"], f"{platform}.{field} lost its 2026-10-28 read")
            self.assertGreaterEqual(entry["verified_on"], "2026-10-28", f"{platform}.{field}")
            self.assertRegex(entry["source_url"], r"https://[^/]+/.+/.+", f"{platform}.{field} points at a site "
                                                                          f"root again, not the page read")

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
        # The re-read's pins: an MB tag is compared, and a section pin fires only in its own section.
        specs["linkedin"] = {"image_max_mb": dict(specs["instagram"]["hashtags_cap"], value=5)}
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp, PLATFORM_MD)
            md.parent.mkdir(parents=True)
            md.write_text("#### LinkedIn Post\n"
                          "| Max image file size | 8 MB (platform_specs.json: linkedin.image_max_mb) |\n"
                          "### Twitter/X\n| Image formats | JPEG, PNG, GIF, WebP |\n"
                          "#### Facebook Post\n| Max image file size | 30 MB |\n#### Facebook Reels\n"
                          "### Meta Ads (Facebook & Instagram)\n| Max image file size | 30 MB |\n"
                          "### Pinterest\n| Image format | JPEG, PNG, WebP |\n", encoding="utf-8")
            got = prose_problems(Path(tmp), specs)
        self.assertEqual(len(got), 4, got)  # 8 MB twice (tag and pin), X's WebP, Facebook Post's 30 MB
        self.assertFalse([g for g in got if g.startswith(f"{PLATFORM_MD}:9:") or g.startswith(f"{PLATFORM_MD}:11:")], got)


if __name__ == "__main__":
    unittest.main()
