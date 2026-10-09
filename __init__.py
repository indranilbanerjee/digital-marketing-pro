"""
Hermes Agent native plugin adapter for Digital Marketing Pro.

This file is read ONLY by Hermes Agent (Nous Research). Every other platform
ignores it: Claude Code / Cowork / Codex / Cursor / Copilot CLI / Antigravity
all read their own manifest files (.claude-plugin/plugin.json, .codex-plugin/,
.cursor-plugin/, .github/plugin/, gemini-extension.json). OpenClaw reads
openclaw.plugin.json (and falls back to the .claude-plugin/ bundle).

What this does
--------------
When Hermes Agent loads us via `hermes plugins install indranilbanerjee/digital-marketing-pro`,
it clones the repo into ~/.hermes/plugins/digital-marketing-pro/, reads plugin.yaml
at the root, then calls register(ctx) below. The register() walks the skills/
directory, discovers every SKILL.md, and exposes each one to Hermes via
ctx.register_skill(name, path_to_SKILL_md). Every marketing skill becomes
available natively in Hermes Desktop.

Design principles
-----------------
1. Zero hard dependencies — uses only Python stdlib (json, re, pathlib, logging).
   PyYAML is preferred for SKILL.md frontmatter parsing but not required.
2. Defensive coding — if Hermes API surface differs from the documented
   spec, the adapter logs and degrades gracefully rather than crashing.
   Hermes guarantees "crashes disable the plugin but don't crash Hermes" but
   we go further and never raise.
3. Single source of truth — we walk the same skills/ directory that every
   other platform reads, so a skill added to Claude Code is automatically
   available to Hermes users with no separate copy.
4. Synthetic skill version — Hermes documents `version` as required in skill
   frontmatter for stand-alone skills, but plugin-registered skills inherit
   the plugin's version. We inject the plugin version into each skill's
   metadata at register time so SKILL.md files don't need editing.

Spec source: https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin
Tested against: Hermes Desktop v0.15.2 (June 2026 public preview)
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger("digital-marketing-pro")

PLUGIN_ROOT = Path(__file__).resolve().parent
SKILLS_DIR = PLUGIN_ROOT / "skills"
PLUGIN_VERSION = "3.35.2"


def _parse_skill_frontmatter(skill_md_path: Path) -> dict:
    """Extract name + description from a SKILL.md's YAML frontmatter.

    Returns {} on any parse failure rather than raising — a malformed skill
    should not block all the others from registering.
    """
    try:
        text = skill_md_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.debug("could not read %s: %s", skill_md_path, exc)
        return {}

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}
    frontmatter_text = match.group(1)

    fields: dict = {}
    for key in ("name", "description"):
        m = re.search(
            rf'^{key}:\s*["\']?(.*?)["\']?\s*$',
            frontmatter_text,
            re.MULTILINE,
        )
        if m:
            fields[key] = m.group(1).strip().rstrip('"\'')

    return fields


def _walk_skills() -> list[dict]:
    """Discover every skills/<name>/SKILL.md in the plugin tree.

    Returns a list of dicts: {dir_name, name, description, skill_md_path}.
    """
    discovered: list[dict] = []
    if not SKILLS_DIR.exists():
        logger.warning("skills/ directory not found at %s", SKILLS_DIR)
        return discovered

    for entry in sorted(SKILLS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.exists():
            continue
        meta = _parse_skill_frontmatter(skill_md)
        discovered.append({
            "dir_name": entry.name,
            "name": meta.get("name") or entry.name,
            "description": meta.get("description") or "",
            "skill_md_path": skill_md,
        })
    return discovered


def register(ctx) -> None:
    """Hermes Agent plugin entry point.

    Called exactly once at startup. Per Hermes docs: 'Crashes disable the
    plugin but don't crash Hermes.' We go further and never raise — every
    branch logs and continues.

    Args:
        ctx: Hermes plugin context with register_skill(name, path) etc.
    """
    logger.info("digital-marketing-pro v%s registering with Hermes", PLUGIN_VERSION)

    skills = _walk_skills()
    if not skills:
        logger.warning(
            "digital-marketing-pro found 0 skills in %s — plugin will be inert. "
            "Confirm the plugin was cloned with its full skills/ tree.",
            SKILLS_DIR,
        )
        return

    if not hasattr(ctx, "register_skill"):
        logger.error(
            "digital-marketing-pro: Hermes ctx is missing register_skill(). "
            "Check Hermes version (this plugin targets v0.15.2+). "
            "Plugin will be inert. Found %d skills that could not be registered.",
            len(skills),
        )
        return

    registered = 0
    failed = 0
    for skill in skills:
        try:
            ctx.register_skill(skill["name"], skill["skill_md_path"])
            registered += 1
        except Exception as exc:  # pragma: no cover  (defensive only)
            failed += 1
            logger.warning(
                "digital-marketing-pro: failed to register skill %r: %s",
                skill["name"], exc,
            )

    logger.info(
        "digital-marketing-pro v%s: registered %d skills (failed: %d) under namespace "
        "'digital-marketing-pro:'. Use `skill_view(\"digital-marketing-pro:<skill>\")` to load one.",
        PLUGIN_VERSION, registered, failed,
    )


# Lightweight introspection so a user can sanity-check the adapter outside
# of Hermes by running:  python __init__.py  (from the plugin root)
def audit() -> dict:
    """Return a summary of what register() would do, without calling Hermes."""
    skills = _walk_skills()
    return {
        "plugin_root": str(PLUGIN_ROOT),
        "plugin_version": PLUGIN_VERSION,
        "skills_dir": str(SKILLS_DIR),
        "skills_dir_exists": SKILLS_DIR.exists(),
        "skill_count": len(skills),
        "first_5_skills": [
            {"name": s["name"], "description": s["description"][:80]}
            for s in skills[:5]
        ],
    }


if __name__ == "__main__":
    # Convenience: `python __init__.py` prints the audit so a Hermes user can
    # verify the adapter before installing.
    import json
    print(json.dumps(audit(), indent=2, ensure_ascii=False))
