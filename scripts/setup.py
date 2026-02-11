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

MEMORY_ROOT = Path.home() / ".claude-marketing"
BRANDS_DIR = MEMORY_ROOT / "brands"
ACTIVE_BRAND_FILE = BRANDS_DIR / "_active-brand.json"
SETTINGS_FILE = MEMORY_ROOT / "settings.json"
SCHEMA_VERSION = "1.0.0"

LITE_DEPS = [
    # Core NLP for brand voice scoring and content analysis
    "nltk>=3.8",
    "textstat>=0.7",
]

FULL_DEPS = LITE_DEPS + [
    # Web scraping for competitor analysis
    "beautifulsoup4>=4.12",
    "requests>=2.31",
    # QR code generation (utm-generator.py)
    "qrcode>=7.4",
    "Pillow>=10.0",
    # AI visibility checking (ai-visibility-checker.py --mode api)
    "openai>=1.0",
    "anthropic>=0.40",
]


def init_memory_dirs():
    """Create the persistent memory directory structure."""
    dirs = [
        MEMORY_ROOT,
        BRANDS_DIR,
        MEMORY_ROOT / "templates",
        MEMORY_ROOT / "industry-data",
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
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2))

    return True


def check_brand():
    """Check if an active brand is configured."""
    if not ACTIVE_BRAND_FILE.exists():
        print("NO_BRAND: No active brand configured.")
        print("Run /dm:brand-setup to create a brand profile.")
        return False

    try:
        active = json.loads(ACTIVE_BRAND_FILE.read_text())
        slug = active.get("active_slug", "")
        profile_path = BRANDS_DIR / slug / "profile.json"

        if not profile_path.exists():
            print(f"BROKEN_BRAND: Active brand '{slug}' profile not found.")
            return False

        profile = json.loads(profile_path.read_text())
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
        print("No active brand. Run /dm:brand-setup to create one.")
        print("===")
        return False

    try:
        active = json.loads(ACTIVE_BRAND_FILE.read_text())
        slug = active.get("active_slug", "")
        profile_path = BRANDS_DIR / slug / "profile.json"

        if not profile_path.exists():
            print("=== DIGITAL MARKETING PRO ===")
            print(f"BROKEN_BRAND: '{slug}' profile not found. Run /dm:brand-setup.")
            print("===")
            return False

        profile = json.loads(profile_path.read_text())
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
                camp_count = len(json.loads(idx_path.read_text()))
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
        print(f"Profile: {profile_path}")
        print("===")
        return True

    except (json.JSONDecodeError, KeyError) as e:
        print("=== DIGITAL MARKETING PRO ===")
        print(f"BRAND_ERROR: {e}")
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
        print("Run: pip install " + " ".join(missing))
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
            settings = json.loads(SETTINGS_FILE.read_text())
            settings["install_mode"] = mode
            SETTINGS_FILE.write_text(json.dumps(settings, indent=2))

        return True
    except subprocess.CalledProcessError as e:
        print(f"INSTALL_ERROR: {e}")
        return False


def create_brand(name, slug=None):
    """Create a new brand profile with default schema."""
    if slug is None:
        slug = name.lower().replace(" ", "-").replace("'", "").replace('"', "")

    brand_dir = BRANDS_DIR / slug
    brand_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    for subdir in ["campaigns", "performance", "content-library", "voice-samples"]:
        (brand_dir / subdir).mkdir(exist_ok=True)

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
    }

    profile_path = brand_dir / "profile.json"
    profile_path.write_text(json.dumps(profile, indent=2))

    # Create empty supporting files
    for fname in ["audiences.json", "competitors.json"]:
        fpath = brand_dir / fname
        if not fpath.exists():
            fpath.write_text("[]")

    # Set as active brand
    ACTIVE_BRAND_FILE.write_text(
        json.dumps({"active_slug": slug, "updated_at": datetime.now().isoformat()}, indent=2)
    )

    print(f"BRAND_CREATED: {name} ({slug})")
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
            active = json.loads(ACTIVE_BRAND_FILE.read_text())
            active_slug = active.get("active_slug", "")
        except json.JSONDecodeError:
            pass

    for item in BRANDS_DIR.iterdir():
        if item.is_dir() and not item.name.startswith("_"):
            profile_path = item / "profile.json"
            if profile_path.exists():
                try:
                    profile = json.loads(profile_path.read_text())
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
    slug = slug.lower().replace(" ", "-")
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
                                data = json.loads(p.read_text())
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
        profile = json.loads(profile_path.read_text())
        brand_name = profile.get("brand_name", slug)
    except json.JSONDecodeError:
        print(f"BRAND_ERROR: Profile for '{slug}' is corrupted.")
        return False

    # Update active brand
    ACTIVE_BRAND_FILE.write_text(
        json.dumps({"active_slug": slug, "updated_at": datetime.now().isoformat()}, indent=2)
    )

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
                    profile = json.loads(profile_path.read_text())
                    current_version = profile.get("schema_version", "0.0.0")

                    if current_version != SCHEMA_VERSION:
                        # Backup before migration
                        backup_path = item / "profile.backup.json"
                        backup_path.write_text(profile_path.read_text())

                        # Apply migrations (add new fields with defaults)
                        profile["schema_version"] = SCHEMA_VERSION
                        profile.setdefault("identity", {}).setdefault("elevator_pitch", "")
                        profile.setdefault("business_model", {}).setdefault("customer_lifetime_value", "")
                        profile["updated_at"] = datetime.now().isoformat()

                        profile_path.write_text(json.dumps(profile, indent=2))
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
    parser.add_argument("--list-brands", action="store_true", help="List all brands")
    parser.add_argument("--switch-brand", metavar="SLUG", help="Switch active brand")
    parser.add_argument("--migrate", action="store_true", help="Migrate brand schemas")
    parser.add_argument("--init", action="store_true", help="Initialize memory directories")
    parser.add_argument("--summary", action="store_true", help="Print rich brand context summary")

    args = parser.parse_args()

    # Always ensure memory dirs exist
    init_memory_dirs()

    if args.check_deps:
        check_deps()

    if args.check_brand:
        check_brand()

    if args.summary:
        print_brand_summary()

    if args.install:
        install_deps(args.install)

    if args.create_brand:
        create_brand(args.create_brand)

    if args.list_brands:
        list_brands()

    if args.switch_brand:
        switch_brand(args.switch_brand)

    if args.migrate:
        migrate_schema()

    if args.init:
        print("INIT_OK: Memory directories initialized.")

    # If no args, just run init + checks + summary
    if not any(vars(args).values()):
        init_memory_dirs()
        check_deps()
        print_brand_summary()


if __name__ == "__main__":
    main()
