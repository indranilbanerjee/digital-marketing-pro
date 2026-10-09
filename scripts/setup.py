#!/usr/bin/env python3
"""
Digital Marketing Pro — Setup & Dependency Manager

Handles:
- First-run dependency installation (lite or full mode)
- Memory directory initialization (~/.claude-marketing/)
- Brand profile existence check
- Schema migration between plugin versions
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

MEMORY_ROOT = _common.workspace_root()
BRANDS_DIR = _common.brands_root()
ACTIVE_BRAND_FILE = BRANDS_DIR / "_active-brand.json"
SETTINGS_FILE = MEMORY_ROOT / "settings.json"
SCHEMA_VERSION = "1.0.0"

# Package names only. The versions come from _common.PINNED_DEPENDENCIES, the one
# place they are pinned; scripts/requirements.txt lists the same pins.
LITE_PACKAGES = [
    # Core NLP for brand voice scoring and content analysis
    "nltk",
    "textstat",
]

FULL_PACKAGES = LITE_PACKAGES + [
    # Web scraping for competitor analysis
    "beautifulsoup4",
    "requests",
    # QR code generation (utm-generator.py)
    "qrcode",
    "pillow",
    # AI visibility checking (ai-visibility-checker.py --mode api)
    "openai",
    "anthropic",
]

LITE_DEPS = _common.pinned_specs(LITE_PACKAGES)
FULL_DEPS = _common.pinned_specs(FULL_PACKAGES)


def init_memory_dirs():
    """Create the persistent memory directory structure."""
    dirs = [
        MEMORY_ROOT,
        BRANDS_DIR,
        MEMORY_ROOT / "templates",
        MEMORY_ROOT / "industry-data",
        MEMORY_ROOT / "sops",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    if not SETTINGS_FILE.exists():
        settings = {
            "schema_version": SCHEMA_VERSION,
            "created_at": datetime.now().isoformat(),
            "install_mode": "lite",
            "auto_compliance_check": True,
            "auto_voice_check": True,
            "default_scoring": True,
        }
        _common.atomic_write_json(SETTINGS_FILE, settings)

    return True


def check_brand():
    """Check if an active brand is configured."""
    if not ACTIVE_BRAND_FILE.exists():
        print("NO_BRAND: No active brand configured.")
        print("Run /digital-marketing-pro:brand-setup to create a brand profile.")
        return False

    try:
        active = json.loads(ACTIVE_BRAND_FILE.read_text(encoding="utf-8"))
        slug = active.get("active_slug", "")
        profile_path = BRANDS_DIR / slug / "profile.json"

        if not profile_path.exists():
            print(f"BROKEN_BRAND: Active brand '{slug}' profile not found.")
            return False

        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        brand_name = profile.get("brand_name", slug)
        print(f"BRAND_ACTIVE: {brand_name}")
        return True
    except (json.JSONDecodeError, KeyError) as e:
        print(f"BRAND_ERROR: Could not load active brand: {e}")
        return False


def print_brand_summary():
    """Print rich brand context summary for SessionStart injection."""
    if not ACTIVE_BRAND_FILE.exists():
        print("=== DIGITAL MARKETING PRO ===")
        print("No active brand. Run /digital-marketing-pro:brand-setup to create one.")
        scripts_dir = Path(__file__).resolve().parent
        print(f"Scripts: {scripts_dir}")
        print(f"Plugin root: {scripts_dir.parent}")
        print("===")
        return False

    try:
        active = json.loads(ACTIVE_BRAND_FILE.read_text(encoding="utf-8"))
        slug = active.get("active_slug", "")
        profile_path = BRANDS_DIR / slug / "profile.json"

        if not profile_path.exists():
            print("=== DIGITAL MARKETING PRO ===")
            print(f"BROKEN_BRAND: '{slug}' profile not found. Run /digital-marketing-pro:brand-setup.")
            scripts_dir = Path(__file__).resolve().parent
            print(f"Scripts: {scripts_dir}")
            print(f"Plugin root: {scripts_dir.parent}")
            print("===")
            return False

        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        name = profile.get("brand_name", slug)
        biz = profile.get("business_model", {})
        ind = profile.get("industry", {})
        v = profile.get("brand_voice", {})
        ch = profile.get("channels", {})
        g = profile.get("goals", {})
        markets = profile.get("target_markets", [])
        comps = profile.get("competitors", [])

        comp_names = [c.get("name", str(c)) if isinstance(c, dict) else str(c) for c in comps]
        market_names = [m.get("country", str(m)) if isinstance(m, dict) else str(m) for m in markets]
        reg_codes = ind.get("regulation_codes", []) if ind.get("regulated") else []

        camp_count = 0
        idx_path = BRANDS_DIR / slug / "campaigns" / "_index.json"
        if idx_path.exists():
            try:
                camp_count = len(json.loads(idx_path.read_text(encoding="utf-8")))
            except Exception:
                pass

        print("=== DIGITAL MARKETING PRO ===")
        print(f"Brand: {name} ({slug})")
        print(f"Industry: {ind.get('primary', 'Not set')}"
              f" (regulated: {'yes' if ind.get('regulated') else 'no'})")
        print(f"Model: {biz.get('type', 'Not set')}"
              f" | Revenue: {biz.get('revenue_model', 'Not set')}"
              f" | Sales cycle: {biz.get('sales_cycle_length', 'Not set')}")
        print(f"Voice: Formality {v.get('formality', 5)}/10"
              f" | Energy {v.get('energy', 5)}/10"
              f" | Humor {v.get('humor', 3)}/10"
              f" | Authority {v.get('authority', 5)}/10")
        print(f"Tone: {', '.join(v.get('tone_keywords', [])[:5]) or 'Not set'}")
        print(f"Avoid: {', '.join(v.get('avoid_words', [])[:5]) or 'None'}"
              f" | Prefer: {', '.join(v.get('prefer_words', [])[:5]) or 'None'}")
        act_ch = ch.get("active", [])
        pri = ch.get("primary", "")
        print(f"Channels: {', '.join(act_ch[:5]) or 'Not set'}"
              f"{' (primary: ' + pri + ')' if pri else ''}")
        print(f"Goals: {g.get('primary_objective', 'Not set')}"
              f" | KPIs: {', '.join(g.get('kpis', [])[:3]) or 'Not set'}")
        print(f"Markets: {', '.join(market_names[:5]) or 'Not set'}"
              f"{' (compliance: ' + ', '.join(reg_codes) + ')' if reg_codes else ''}")
        print(f"Competitors: {', '.join(comp_names[:5]) or 'None configured'}")
        if camp_count:
            print(f"Campaigns: {camp_count} total")
        else:
            print("Campaigns: None yet")

        # Guidelines summary
        gl_manifest = BRANDS_DIR / slug / "guidelines" / "_manifest.json"
        tmpl_dir = BRANDS_DIR / slug / "templates"
        sops_dir = MEMORY_ROOT / "sops"
        gl_parts = []
        if gl_manifest.exists():
            try:
                gl = json.loads(gl_manifest.read_text(encoding="utf-8"))
                total_rules = gl.get("total_rules", 0)
                cats = len(gl.get("categories", {}))
                custom = len(gl.get("custom_files", []))
                restrictions = gl.get("categories", {}).get("restrictions", {})
                banned = restrictions.get("banned_words", 0)
                gl_parts.append(f"{total_rules} rules across {cats} categories")
                if banned:
                    gl_parts.append(f"{banned} restrictions")
                if custom:
                    gl_parts.append(f"{custom} custom files")
            except Exception:
                gl_parts.append("configured (manifest error)")
        tmpl_count = 0
        if tmpl_dir.exists():
            tmpl_manifest = tmpl_dir / "_manifest.json"
            if tmpl_manifest.exists():
                try:
                    tmpl_count = len(json.loads(tmpl_manifest.read_text(encoding="utf-8")).get("templates", {}))
                except Exception:
                    pass
        if tmpl_count:
            gl_parts.append(f"{tmpl_count} templates")
        sop_count = 0
        if sops_dir.exists():
            sop_manifest = sops_dir / "_manifest.json"
            if sop_manifest.exists():
                try:
                    sop_count = len(json.loads(sop_manifest.read_text(encoding="utf-8")).get("sops", {}))
                except Exception:
                    pass
        if sop_count:
            gl_parts.append(f"{sop_count} SOPs")
        if gl_parts:
            print(f"Guidelines: {' · '.join(gl_parts)}")
        else:
            print("Guidelines: Not configured")

        print(f"Profile: {profile_path}")
        # Output plugin paths so Claude can resolve script locations
        scripts_dir = Path(__file__).resolve().parent
        print(f"Scripts: {scripts_dir}")
        print(f"Plugin root: {scripts_dir.parent}")
        print("===")
        return True

    except (json.JSONDecodeError, KeyError) as e:
        print("=== DIGITAL MARKETING PRO ===")
        print(f"BRAND_ERROR: {e}")
        scripts_dir = Path(__file__).resolve().parent
        print(f"Scripts: {scripts_dir}")
        print(f"Plugin root: {scripts_dir.parent}")
        print("===")
        return False


def check_deps():
    """Check if required dependencies are installed."""
    missing = []
    for dep in LITE_DEPS:
        pkg_name = dep.split(">=")[0].split("==")[0].replace("-", "_")
        try:
            __import__(pkg_name)
        except ImportError:
            # Handle package name mismatches
            alt_names = {
                "python_dotenv": "dotenv",
                "python_dateutil": "dateutil",
                "pyyaml": "yaml",
            }
            alt = alt_names.get(pkg_name)
            if alt:
                try:
                    __import__(alt)
                    continue
                except ImportError:
                    pass
            missing.append(dep)

    if missing:
        print(f"DEPS_MISSING: {', '.join(missing)}")
        print("Run: " + _common.install_command(missing))
        return False

    print("DEPS_OK")
    return True


def install_deps(mode="lite"):
    """Install dependencies."""
    deps = LITE_DEPS if mode == "lite" else FULL_DEPS
    print(f"Installing {mode} dependencies ({len(deps)} packages)...")

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + deps
        )
        print(f"INSTALL_OK: {mode} dependencies installed.")

        # Download NLTK data (needed for both lite and full)
        print("Downloading NLTK data packages...")
        import nltk
        for pkg in ["punkt_tab", "stopwords", "averaged_perceptron_tagger",
                     "averaged_perceptron_tagger_eng", "vader_lexicon"]:
            nltk.download(pkg, quiet=True)

        if mode == "full":
            print("INSTALL_FULL_OK: All dependencies and models installed.")

        # Update settings with install mode
        if SETTINGS_FILE.exists():
            settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            settings["install_mode"] = mode
            _common.atomic_write_json(SETTINGS_FILE, settings)

        return True
    except subprocess.CalledProcessError as e:
        print(f"INSTALL_ERROR: {e}")
        return False


def create_brand(name, slug=None):
    """Create a new brand profile with default schema."""
    if slug is None:
        slug = _common.slugify_brand(name)

    brand_dir = BRANDS_DIR / slug
    brand_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    for subdir in ["campaigns", "performance", "content-library", "voice-samples",
                   "guidelines", "guidelines/custom", "templates"]:
        (brand_dir / subdir).mkdir(parents=True, exist_ok=True)

    profile = {
        "brand_name": name,
        "brand_slug": slug,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "schema_version": SCHEMA_VERSION,
        "identity": {
            "tagline": "",
            "mission": "",
            "vision": "",
            "values": [],
            "unique_selling_proposition": "",
            "positioning_statement": "",
            "elevator_pitch": "",
        },
        "business_model": {
            "type": "",
            "revenue_model": "",
            "price_range": "",
            "sales_cycle_length": "",
            "average_deal_size": "",
            "customer_lifetime_value": "",
        },
        "industry": {
            "primary": "",
            "secondary": [],
            "regulated": False,
            "regulation_codes": [],
            "compliance_notes": "",
        },
        "target_markets": [],
        "brand_voice": {
            "formality": 5,
            "energy": 5,
            "humor": 3,
            "authority": 5,
            "personality_traits": [],
            "tone_keywords": [],
            "avoid_words": [],
            "prefer_words": [],
            "this_not_that": [],
            "sample_content": [],
        },
        "channels": {"active": [], "primary": "", "handles": {}},
        "competitors": [],
        "goals": {
            "primary_objective": "",
            "kpis": [],
            "budget_range": "",
            "team_size": "",
        },
        "language": {
            "primary_language": "",
            "secondary_languages": [],
            "content_languages": [],
            "do_not_translate": [],
            "translation_preferences": {},
            "locale_formatting": {
                "date_format": "",
                "number_format": "",
                "measurement": "",
            },
        },
    }

    profile_path = brand_dir / "profile.json"
    _common.atomic_write_json(profile_path, profile)

    # Create empty supporting files
    for fname in ["audiences.json", "competitors.json", "insights.json"]:
        fpath = brand_dir / fname
        if not fpath.exists():
            fpath.write_text("[]", encoding="utf-8")

    # Set as active brand. This is a GLOBAL side effect: every skill that reads
    # "the active brand" now resolves to the new one, and _active-brand.json
    # stores a single value with no history. Creating a throwaway brand used to
    # silently repoint a working session at it with nothing printed, so say so
    # and name the way back.
    previous = None
    if ACTIVE_BRAND_FILE.exists():
        try:
            previous = json.loads(
                ACTIVE_BRAND_FILE.read_text(encoding="utf-8")).get("active_slug")
        except (json.JSONDecodeError, OSError):
            previous = None

    _common.atomic_write_json(
        ACTIVE_BRAND_FILE,
        {"active_slug": slug, "updated_at": datetime.now().isoformat(),
         "previous_slug": previous})

    print(f"BRAND_CREATED: {name} ({slug})")
    if previous and previous != slug:
        print(f"ACTIVE_BRAND_CHANGED: {previous} -> {slug}")
        print(f"  Every skill that reads the active brand now resolves to {slug!r}.")
        print(f"  To go back: python setup.py --switch-brand {previous}")
    print(f"Profile: {profile_path}")
    return str(profile_path)


def list_brands():
    """List all configured brands."""
    if not BRANDS_DIR.exists():
        print("NO_BRANDS: No brands directory found.")
        return []

    brands = []
    active_slug = ""
    if ACTIVE_BRAND_FILE.exists():
        try:
            active = json.loads(ACTIVE_BRAND_FILE.read_text(encoding="utf-8"))
            active_slug = active.get("active_slug", "")
        except json.JSONDecodeError:
            pass

    for item in BRANDS_DIR.iterdir():
        if item.is_dir() and not item.name.startswith("_"):
            profile_path = item / "profile.json"
            if profile_path.exists():
                try:
                    profile = json.loads(profile_path.read_text(encoding="utf-8"))
                    is_active = "* " if item.name == active_slug else "  "
                    brands.append(
                        f"{is_active}{profile.get('brand_name', item.name)} [{item.name}]"
                    )
                except json.JSONDecodeError:
                    brands.append(f"  {item.name} [corrupted profile]")

    if brands:
        print("BRANDS:")
        for b in brands:
            print(f"  {b}")
    else:
        print("NO_BRANDS: No brand profiles found.")

    return brands


def switch_brand(slug):
    """Switch the active brand to the specified slug."""
    slug = _common.slugify_brand(slug)
    brand_dir = BRANDS_DIR / slug
    profile_path = brand_dir / "profile.json"

    if not profile_path.exists():
        # Try fuzzy match
        available = []
        if BRANDS_DIR.exists():
            for item in BRANDS_DIR.iterdir():
                if item.is_dir() and not item.name.startswith("_"):
                    if slug in item.name or item.name in slug:
                        available.append(item.name)
                    else:
                        # Check brand_name in profile
                        p = item / "profile.json"
                        if p.exists():
                            try:
                                data = json.loads(p.read_text(encoding="utf-8"))
                                if slug in data.get("brand_name", "").lower():
                                    available.append(item.name)
                            except json.JSONDecodeError:
                                pass

        if available:
            print(f"BRAND_NOT_FOUND: '{slug}' not found. Did you mean: {', '.join(available)}?")
        else:
            print(f"BRAND_NOT_FOUND: '{slug}' not found. Run --list-brands to see available brands.")
        return False

    # Load and validate profile
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        brand_name = profile.get("brand_name", slug)
    except json.JSONDecodeError:
        print(f"BRAND_ERROR: Profile for '{slug}' is corrupted.")
        return False

    # Update active brand
    _common.atomic_write_json(
        ACTIVE_BRAND_FILE,
        {"active_slug": slug, "updated_at": datetime.now().isoformat()})

    print(f"BRAND_SWITCHED: Now using '{brand_name}' ({slug})")
    print(f"Industry: {profile.get('industry', {}).get('primary', 'Not set')}")
    print(f"Business model: {profile.get('business_model', {}).get('type', 'Not set')}")
    return True


def migrate_schema():
    """Migrate brand profiles to current schema version."""
    if not BRANDS_DIR.exists():
        print("NO_BRANDS: Nothing to migrate.")
        return

    migrated = 0
    for item in BRANDS_DIR.iterdir():
        if item.is_dir() and not item.name.startswith("_"):
            profile_path = item / "profile.json"
            if profile_path.exists():
                try:
                    profile = json.loads(profile_path.read_text(encoding="utf-8"))
                    current_version = profile.get("schema_version", "0.0.0")

                    if current_version != SCHEMA_VERSION:
                        # Backup before migration
                        backup_path = item / "profile.backup.json"
                        backup_path.write_text(profile_path.read_text(encoding="utf-8"), encoding="utf-8")

                        # Apply migrations (add new fields with defaults)
                        profile["schema_version"] = SCHEMA_VERSION
                        profile.setdefault("identity", {}).setdefault("elevator_pitch", "")
                        profile.setdefault("business_model", {}).setdefault("customer_lifetime_value", "")
                        profile["updated_at"] = datetime.now().isoformat()

                        _common.atomic_write_json(profile_path, profile)
                        migrated += 1
                        print(f"  Migrated: {item.name} ({current_version} → {SCHEMA_VERSION})")

                except (json.JSONDecodeError, KeyError) as e:
                    print(f"  Error migrating {item.name}: {e}")

    print(f"MIGRATION_COMPLETE: {migrated} profiles updated.")


def main():
    parser = argparse.ArgumentParser(description="Digital Marketing Pro — Setup")
    parser.add_argument("--check-deps", action="store_true", help="Check dependencies")
    parser.add_argument("--check-brand", action="store_true", help="Check active brand")
    parser.add_argument("--install", choices=["lite", "full"], help="Install dependencies")
    parser.add_argument("--create-brand", metavar="NAME", help="Create a new brand profile")
    # create_brand() has always accepted a slug; the CLI never exposed it, so a
    # caller who needed a specific slug had to import the module and call the
    # function directly. The storage path IS the slug, so this was not optional.
    parser.add_argument("--slug", type=_common.path_component, metavar="SLUG",
                        help="Explicit slug for --create-brand (default: slugified name). "
                             "The slug is the directory name under ~/.claude-marketing/brands/.")
    parser.add_argument("--list-brands", action="store_true", help="List all brands")
    parser.add_argument("--switch-brand", metavar="SLUG", help="Switch active brand")
    parser.add_argument("--migrate", action="store_true", help="Migrate brand schemas")
    parser.add_argument("--init", action="store_true", help="Initialize memory directories")
    parser.add_argument("--summary", action="store_true", help="Print rich brand context summary")

    args = parser.parse_args()

    # Always ensure memory dirs exist
    init_memory_dirs()

    # Track hard failures so the shell caller can trust $? (H4: a failed
    # dependency install or a missing switch target must NOT exit 0).
    exit_code = 0

    if args.check_deps:
        check_deps()

    if args.check_brand:
        check_brand()

    if args.summary:
        print_brand_summary()

    if args.install:
        if not install_deps(args.install):
            exit_code = 1

    if args.create_brand:
        create_brand(args.create_brand, slug=args.slug)

    if args.list_brands:
        list_brands()

    if args.switch_brand:
        if not switch_brand(args.switch_brand):
            exit_code = 1

    if args.migrate:
        migrate_schema()

    if args.init:
        print("INIT_OK: Memory directories initialized.")

    # If no args, just run init + checks + summary
    if not any(vars(args).values()):
        init_memory_dirs()
        check_deps()
        print_brand_summary()

    if exit_code:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
