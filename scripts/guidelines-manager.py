#!/usr/bin/env python3
"""
guidelines-manager.py
=====================
Brand guidelines, templates, and SOP management for Digital Marketing Pro.

Manages per-brand guidelines (voice & tone, messaging, restrictions, channel styles,
visual identity), per-brand templates (proposals, reports, briefs), and agency-level
SOPs (workflows, checklists, escalation procedures).

Storage:
    ~/.claude-marketing/brands/{slug}/guidelines/   — per-brand guidelines
    ~/.claude-marketing/brands/{slug}/templates/     — per-brand templates
    ~/.claude-marketing/sops/                        — agency-level SOPs

Usage:
    python guidelines-manager.py --brand acme --action summary
    python guidelines-manager.py --brand acme --action get --category restrictions
    python guidelines-manager.py --brand acme --action save --category restrictions --file restrictions.md
    python guidelines-manager.py --brand acme --action list-categories
    python guidelines-manager.py --brand acme --action list-templates
    python guidelines-manager.py --brand acme --action get-template --name proposal
    python guidelines-manager.py --brand acme --action save-template --name proposal --file proposal.md
    python guidelines-manager.py --action list-sops
    python guidelines-manager.py --action get-sop --name content-workflow
    python guidelines-manager.py --action save-sop --name content-workflow --file content-workflow.md
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

def _sops_root() -> Path:
    """Agency SOPs live under the same workspace as everything else
    (CLAUDE_MARKETING_HOME / PLUGIN_DATA / ~/.claude-marketing). Before 3.35.0
    this script ignored those overrides and always used ~/.claude-marketing/sops;
    if that legacy folder holds SOPs and the workspace one does not exist yet,
    keep using it so nothing disappears. An explicit CLAUDE_MARKETING_HOME
    (tests, isolated runs) never falls back."""
    current = _common.workspace_root() / "sops"
    legacy = Path.home() / ".claude-marketing" / "sops"
    if (not os.environ.get("CLAUDE_MARKETING_HOME") and not current.exists() and legacy.is_dir()
            and legacy.resolve() != current.resolve()):
        return legacy
    return current


MEMORY_ROOT = _common.workspace_root()
BRANDS_DIR = _common.brands_root()
SOPS_DIR = _sops_root()

GUIDELINE_CATEGORIES = {
    "voice-and-tone": {
        "file": "voice-and-tone.md",
        "description": "Detailed voice guide — tone rules, dos/don'ts, examples beyond numeric scores",
    },
    "messaging": {
        "file": "messaging.md",
        "description": "Key messages, value propositions, positioning statements, approved taglines",
    },
    "restrictions": {
        "file": "restrictions.md",
        "description": "Banned words, restricted claims, mandatory disclaimers, prohibited topics",
    },
    "channel-styles": {
        "file": "channel-styles.md",
        "description": "Per-channel tone and format rules (LinkedIn=formal, IG=casual, etc.)",
    },
    "visual-identity": {
        "file": "visual-identity.md",
        "description": "Colors, fonts, logo usage rules, image style (text descriptions for briefs)",
    },
}


def get_brand_dir(slug):
    """Resolve + validate the brand directory. Delegates to _common so the slug
    is normalised (slugify at the boundary) and legacy raw-name dirs still
    resolve, with the standard not-found message."""
    return _common.get_brand_dir(slug)


def get_guidelines_dir(slug):
    """Get the guidelines directory for a brand, creating if needed."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return None, err
    guidelines_dir = brand_dir / "guidelines"
    guidelines_dir.mkdir(exist_ok=True)
    (guidelines_dir / "custom").mkdir(exist_ok=True)
    return guidelines_dir, None


def get_templates_dir(slug):
    """Get the templates directory for a brand, creating if needed."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return None, err
    templates_dir = brand_dir / "templates"
    templates_dir.mkdir(exist_ok=True)
    return templates_dir, None


def load_manifest(manifest_path):
    """Load a _manifest.json file, returning empty dict if missing."""
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_manifest(manifest_path, data):
    """Save a _manifest.json file."""
    data["updated_at"] = datetime.now().isoformat()
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def count_rules_in_file(filepath):
    """Count rules/items in a markdown file (lines starting with - or *)."""
    if not filepath.exists():
        return 0
    content = filepath.read_text(encoding="utf-8")
    count = 0
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("1."):
            count += 1
    return count


def rebuild_manifest(guidelines_dir, slug):
    """Rebuild _manifest.json from existing guideline files."""
    manifest = {
        "brand": slug,
        "updated_at": datetime.now().isoformat(),
        "categories": {},
        "custom_files": [],
        "total_rules": 0,
    }

    total = 0
    for cat_key, cat_info in GUIDELINE_CATEGORIES.items():
        filepath = guidelines_dir / cat_info["file"]
        if filepath.exists():
            rules = count_rules_in_file(filepath)
            total += rules
            entry = {
                "file": cat_info["file"],
                "rules_count": rules,
                "updated": datetime.fromtimestamp(filepath.stat().st_mtime).isoformat(),
            }
            if cat_key == "restrictions":
                # Count banned words and restricted claims separately
                content = filepath.read_text(encoding="utf-8")
                banned = 0
                claims = 0
                in_banned = False
                in_claims = False
                for line in content.splitlines():
                    lower = line.lower().strip()
                    if "banned" in lower and ("word" in lower or "phrase" in lower or "#" in line):
                        in_banned = True
                        in_claims = False
                    elif "restricted" in lower and "claim" in lower:
                        in_claims = True
                        in_banned = False
                    elif line.strip().startswith("#"):
                        in_banned = False
                        in_claims = False

                    if (in_banned and (line.strip().startswith("- ") or line.strip().startswith("* "))):
                        banned += 1
                    elif (in_claims and (line.strip().startswith("- ") or line.strip().startswith("* "))):
                        claims += 1

                entry["banned_words"] = banned
                entry["restricted_claims"] = claims
            elif cat_key == "channel-styles":
                content = filepath.read_text(encoding="utf-8")
                channels = sum(1 for line in content.splitlines()
                             if line.strip().startswith("##") and not line.strip().startswith("###"))
                entry["channels_covered"] = channels

            manifest["categories"][cat_key] = entry

    # Check custom files
    custom_dir = guidelines_dir / "custom"
    if custom_dir.exists():
        for f in sorted(custom_dir.iterdir()):
            if f.is_file() and f.suffix == ".md":
                manifest["custom_files"].append(f.name)
                total += count_rules_in_file(f)

    manifest["total_rules"] = total
    save_manifest(guidelines_dir / "_manifest.json", manifest)
    return manifest


# --- Actions ---

def summary(slug):
    """Get guidelines summary for a brand."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"has_guidelines": False, "brand": slug, "error": err}

    guidelines_dir = brand_dir / "guidelines"
    templates_dir = brand_dir / "templates"

    if not guidelines_dir.exists() or not (guidelines_dir / "_manifest.json").exists():
        # Check if any guideline files exist without manifest
        has_files = False
        if guidelines_dir.exists():
            has_files = any(f.suffix == ".md" for f in guidelines_dir.iterdir() if f.is_file())

        if has_files:
            manifest = rebuild_manifest(guidelines_dir, slug)
        else:
            result = {
                "has_guidelines": False,
                "brand": slug,
                "categories": {},
                "total_rules": 0,
                "custom_files": [],
                "templates": 0,
                "note": "No guidelines configured. Use /digital-marketing-pro:import-guidelines to add.",
            }
            # Check templates
            if templates_dir.exists():
                tmpl_manifest = load_manifest(templates_dir / "_manifest.json")
                result["templates"] = len(tmpl_manifest.get("templates", {}))
            return result
    else:
        manifest = load_manifest(guidelines_dir / "_manifest.json")

    result = {
        "has_guidelines": True,
        "brand": slug,
        "categories": {},
        "total_rules": manifest.get("total_rules", 0),
        "custom_files": manifest.get("custom_files", []),
    }

    for cat_key, cat_data in manifest.get("categories", {}).items():
        result["categories"][cat_key] = {
            "rules_count": cat_data.get("rules_count", 0),
            "file": cat_data.get("file", ""),
        }
        if "banned_words" in cat_data:
            result["categories"][cat_key]["banned_words"] = cat_data["banned_words"]
        if "restricted_claims" in cat_data:
            result["categories"][cat_key]["restricted_claims"] = cat_data["restricted_claims"]
        if "channels_covered" in cat_data:
            result["categories"][cat_key]["channels_covered"] = cat_data["channels_covered"]

    # Check templates
    if templates_dir.exists():
        tmpl_manifest = load_manifest(templates_dir / "_manifest.json")
        result["templates"] = len(tmpl_manifest.get("templates", {}))
    else:
        result["templates"] = 0

    return result


def get_category(slug, category):
    """Get the content of a specific guideline category."""
    if category not in GUIDELINE_CATEGORIES and category != "custom":
        return {"error": f"Unknown category '{category}'. Valid: {', '.join(GUIDELINE_CATEGORIES.keys())}, custom"}

    guidelines_dir, err = get_guidelines_dir(slug)
    if err:
        return {"error": err}

    if category == "custom":
        custom_dir = guidelines_dir / "custom"
        if not custom_dir.exists():
            return {"category": "custom", "files": [], "note": "No custom guideline files."}
        files = {}
        for f in sorted(custom_dir.iterdir()):
            if f.is_file() and f.suffix == ".md":
                files[f.name] = f.read_text(encoding="utf-8")
        return {"category": "custom", "files": files, "count": len(files)}

    cat_info = GUIDELINE_CATEGORIES[category]
    filepath = guidelines_dir / cat_info["file"]

    if not filepath.exists():
        return {
            "category": category,
            "exists": False,
            "note": f"No {category} guidelines configured. Use /digital-marketing-pro:import-guidelines to add.",
        }

    content = filepath.read_text(encoding="utf-8")
    return {
        "category": category,
        "exists": True,
        "file": cat_info["file"],
        "content": content,
        "rules_count": count_rules_in_file(filepath),
    }


def save_category(slug, category, content=None, filepath=None):
    """Save content to a guideline category file."""
    is_custom = category not in GUIDELINE_CATEGORIES

    guidelines_dir, err = get_guidelines_dir(slug)
    if err:
        return {"error": err}

    # Determine target path
    if is_custom:
        custom_dir = guidelines_dir / "custom"
        custom_dir.mkdir(exist_ok=True)
        safe_name = category.lower().replace(" ", "-")
        if not safe_name.endswith(".md"):
            safe_name += ".md"
        target, path_err = _common.child_or_error(custom_dir, safe_name)
        if path_err:
            return {"error": path_err}
    else:
        cat_info = GUIDELINE_CATEGORIES[category]
        target = guidelines_dir / cat_info["file"]

    # Get content from file or direct content
    if filepath:
        source = Path(filepath)
        if not source.exists():
            return {"error": f"Source file not found: {filepath}"}
        save_content = source.read_text(encoding="utf-8")
    elif content:
        save_content = content
    else:
        return {"error": "Provide --content or --file with the guideline content."}

    target.write_text(save_content, encoding="utf-8")

    # Rebuild manifest
    manifest = rebuild_manifest(guidelines_dir, slug)

    return {
        "status": "saved",
        "category": category,
        "file": str(target),
        "rules_count": count_rules_in_file(target),
        "total_rules": manifest.get("total_rules", 0),
    }


def list_categories(slug):
    """List all guideline categories and their status."""
    guidelines_dir, err = get_guidelines_dir(slug)
    if err:
        return {"error": err}

    result = {"brand": slug, "categories": {}}
    for cat_key, cat_info in GUIDELINE_CATEGORIES.items():
        filepath = guidelines_dir / cat_info["file"]
        result["categories"][cat_key] = {
            "description": cat_info["description"],
            "file": cat_info["file"],
            "configured": filepath.exists(),
            "rules_count": count_rules_in_file(filepath) if filepath.exists() else 0,
        }

    custom_dir = guidelines_dir / "custom"
    custom_files = []
    if custom_dir.exists():
        custom_files = [f.name for f in sorted(custom_dir.iterdir()) if f.suffix == ".md"]
    result["custom_files"] = custom_files

    return result


def delete_category(slug, category):
    """Delete a guideline category file."""
    guidelines_dir, err = get_guidelines_dir(slug)
    if err:
        return {"error": err}

    if category in GUIDELINE_CATEGORIES:
        target = guidelines_dir / GUIDELINE_CATEGORIES[category]["file"]
    else:
        target, path_err = _common.child_or_error(guidelines_dir / "custom", category)
        if path_err:
            return {"error": path_err}
        if not target.suffix:
            target = target.with_suffix(".md")

    if not target.exists():
        return {"error": f"Guideline file not found: {target.name}"}

    target.unlink()
    manifest = rebuild_manifest(guidelines_dir, slug)
    return {"status": "deleted", "category": category, "total_rules": manifest.get("total_rules", 0)}


# --- Template Actions ---

def list_templates(slug):
    """List all templates for a brand."""
    templates_dir, err = get_templates_dir(slug)
    if err:
        return {"error": err}

    manifest = load_manifest(templates_dir / "_manifest.json")
    templates = manifest.get("templates", {})

    # Also scan for files not in manifest
    for f in sorted(templates_dir.iterdir()):
        if f.is_file() and f.suffix == ".md" and f.name != "_manifest.json":
            name = f.stem
            if name not in templates:
                templates[name] = {
                    "file": f.name,
                    "description": "",
                    "added": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                }

    return {"brand": slug, "templates": templates, "count": len(templates)}


def get_template(slug, name):
    """Get a specific template."""
    templates_dir, err = get_templates_dir(slug)
    if err:
        return {"error": err}

    filepath, path_err = _common.child_or_error(templates_dir, name, ".md")
    if path_err:
        return {"error": path_err}
    if not filepath.exists():
        # Try with original name
        filepath = templates_dir / name.strip()
        if not filepath.exists():
            return {"error": f"Template '{name}' not found."}

    return {
        "name": name,
        "file": filepath.name,
        "content": filepath.read_text(encoding="utf-8"),
    }


def save_template(slug, name, content=None, filepath=None, description=""):
    """Save a template for the brand."""
    templates_dir, err = get_templates_dir(slug)
    if err:
        return {"error": err}

    safe_name = name.lower().replace(" ", "-")
    target, path_err = _common.child_or_error(templates_dir, safe_name, ".md")
    if path_err:
        return {"error": path_err}

    if filepath:
        source = Path(filepath)
        if not source.exists():
            return {"error": f"Source file not found: {filepath}"}
        save_content = source.read_text(encoding="utf-8")
    elif content:
        save_content = content
    else:
        return {"error": "Provide --content or --file with the template content."}

    target.write_text(save_content, encoding="utf-8")

    # Update manifest
    manifest = load_manifest(templates_dir / "_manifest.json")
    if "templates" not in manifest:
        manifest["templates"] = {}
    manifest["templates"][safe_name] = {
        "file": target.name,
        "description": description,
        "added": datetime.now().isoformat(),
    }
    save_manifest(templates_dir / "_manifest.json", manifest)

    return {"status": "saved", "name": safe_name, "file": str(target)}


def delete_template(slug, name):
    """Delete a template."""
    templates_dir, err = get_templates_dir(slug)
    if err:
        return {"error": err}

    target, path_err = _common.child_or_error(templates_dir, name, ".md")
    if path_err:
        return {"error": path_err}
    if not target.exists():
        return {"error": f"Template '{name}' not found."}

    target.unlink()

    manifest = load_manifest(templates_dir / "_manifest.json")
    if "templates" in manifest and name in manifest["templates"]:
        del manifest["templates"][name]
        save_manifest(templates_dir / "_manifest.json", manifest)

    return {"status": "deleted", "name": name}


# --- SOP Actions ---

def list_sops():
    """List all agency SOPs."""
    SOPS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(SOPS_DIR / "_manifest.json")
    sops = manifest.get("sops", {})

    for f in sorted(SOPS_DIR.iterdir()):
        if f.is_file() and f.suffix == ".md" and f.name != "_manifest.json":
            name = f.stem
            if name not in sops:
                sops[name] = {
                    "file": f.name,
                    "description": "",
                    "added": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                }

    return {"sops": sops, "count": len(sops)}


def get_sop(name):
    """Get a specific SOP."""
    SOPS_DIR.mkdir(parents=True, exist_ok=True)
    filepath, path_err = _common.child_or_error(SOPS_DIR, name, ".md")
    if path_err:
        return {"error": path_err}
    if not filepath.exists():
        filepath = SOPS_DIR / name.strip()
        if not filepath.exists():
            return {"error": f"SOP '{name}' not found."}

    return {
        "name": name,
        "file": filepath.name,
        "content": filepath.read_text(encoding="utf-8"),
    }


def save_sop(name, content=None, filepath=None, description=""):
    """Save an agency SOP."""
    SOPS_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = name.lower().replace(" ", "-")
    target, path_err = _common.child_or_error(SOPS_DIR, safe_name, ".md")
    if path_err:
        return {"error": path_err}

    if filepath:
        source = Path(filepath)
        if not source.exists():
            return {"error": f"Source file not found: {filepath}"}
        save_content = source.read_text(encoding="utf-8")
    elif content:
        save_content = content
    else:
        return {"error": "Provide --content or --file with the SOP content."}

    target.write_text(save_content, encoding="utf-8")

    manifest = load_manifest(SOPS_DIR / "_manifest.json")
    if "sops" not in manifest:
        manifest["sops"] = {}
    manifest["sops"][safe_name] = {
        "file": target.name,
        "description": description,
        "added": datetime.now().isoformat(),
    }
    save_manifest(SOPS_DIR / "_manifest.json", manifest)

    return {"status": "saved", "name": safe_name, "file": str(target)}


def delete_sop(name):
    """Delete an agency SOP."""
    target, path_err = _common.child_or_error(SOPS_DIR, name, ".md")
    if path_err:
        return {"error": path_err}
    if not target.exists():
        return {"error": f"SOP '{name}' not found."}

    target.unlink()

    manifest = load_manifest(SOPS_DIR / "_manifest.json")
    if "sops" in manifest and name in manifest["sops"]:
        del manifest["sops"][name]
        save_manifest(SOPS_DIR / "_manifest.json", manifest)

    return {"status": "deleted", "name": name}


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="Brand guidelines, templates, and SOP management for Digital Marketing Pro"
    )
    parser.add_argument("--brand", type=_common.path_component, help="Brand slug (required for brand-level actions)")
    parser.add_argument(
        "--action",
        required=True,
        choices=[
            "summary", "get", "save", "delete", "list-categories",
            "list-templates", "get-template", "save-template", "delete-template",
            "list-sops", "get-sop", "save-sop", "delete-sop",
        ],
        help="Action to perform",
    )
    parser.add_argument("--category", help="Guideline category (for get/save/delete)")
    parser.add_argument("--name", help="Template or SOP name")
    parser.add_argument("--file", help="Source file path (for save actions)")
    parser.add_argument("--content", help="Direct content string (for save actions)")
    parser.add_argument("--description", default="", help="Description (for save-template/save-sop)")

    args = parser.parse_args()

    # Brand-level actions require --brand
    brand_actions = {"summary", "get", "save", "delete", "list-categories",
                     "list-templates", "get-template", "save-template", "delete-template"}
    if args.action in brand_actions and not args.brand:
        print(json.dumps({"error": f"--brand is required for action '{args.action}'"}))
        sys.exit(1)

    # Route to action
    if args.action == "summary":
        result = summary(args.brand)

    elif args.action == "get":
        if not args.category:
            print(json.dumps({"error": "Provide --category for get action."}))
            sys.exit(1)
        result = get_category(args.brand, args.category)

    elif args.action == "save":
        if not args.category:
            print(json.dumps({"error": "Provide --category for save action."}))
            sys.exit(1)
        result = save_category(args.brand, args.category, content=args.content, filepath=args.file)

    elif args.action == "delete":
        if not args.category:
            print(json.dumps({"error": "Provide --category for delete action."}))
            sys.exit(1)
        result = delete_category(args.brand, args.category)

    elif args.action == "list-categories":
        result = list_categories(args.brand)

    elif args.action == "list-templates":
        result = list_templates(args.brand)

    elif args.action == "get-template":
        if not args.name:
            print(json.dumps({"error": "Provide --name for get-template."}))
            sys.exit(1)
        result = get_template(args.brand, args.name)

    elif args.action == "save-template":
        if not args.name:
            print(json.dumps({"error": "Provide --name for save-template."}))
            sys.exit(1)
        result = save_template(args.brand, args.name, content=args.content,
                              filepath=args.file, description=args.description)

    elif args.action == "delete-template":
        if not args.name:
            print(json.dumps({"error": "Provide --name for delete-template."}))
            sys.exit(1)
        result = delete_template(args.brand, args.name)

    elif args.action == "list-sops":
        result = list_sops()

    elif args.action == "get-sop":
        if not args.name:
            print(json.dumps({"error": "Provide --name for get-sop."}))
            sys.exit(1)
        result = get_sop(args.name)

    elif args.action == "save-sop":
        if not args.name:
            print(json.dumps({"error": "Provide --name for save-sop."}))
            sys.exit(1)
        result = save_sop(args.name, content=args.content,
                         filepath=args.file, description=args.description)

    elif args.action == "delete-sop":
        if not args.name:
            print(json.dumps({"error": "Provide --name for delete-sop."}))
            sys.exit(1)
        result = delete_sop(args.name)

    _common.finish(result)


if __name__ == "__main__":
    main()
