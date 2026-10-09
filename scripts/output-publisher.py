#!/usr/bin/env python3
"""
output-publisher.py
===================
Dual-copy publisher for DMP workflow outputs.

Any file produced by a DMP workflow gets copied to TWO locations:

1. **Internal tracking copy** at ``~/.claude-marketing/brands/{brand}/output/{workflow}/{run_id}/``
   — system-of-record for ``/digital-marketing-pro:status``, audit history,
   the checkpoint manager.
2. **User-visible published copy** at
   ``~/Documents/DigitalMarketingPro/{brand}/{workflow}/{YYYY-MM}/{filename}``
   — visible in Windows Explorer / macOS Finder / Linux file managers by
   default. Override with ``$DIGITAL_MARKETING_PRO_PUBLISH_DIR`` env var or
   ``--publish-dir <path>``.

This exists because user-team feedback flagged that the hidden
``~/.claude-marketing/`` dotfolder made finished files "feel" unsaved.
DMP produces 50-60 files per engagement; without a visible publish path,
that confusion compounds.

Subcommands
-----------
    publish      — Copy one file or one directory into both locations
    publish-run  — Bulk-publish every artifact a checkpoint-manager run
                   produced (reads run.json, copies every step_artifact)
    where        — Print the visible-folder path for a brand (no copy)
    open         — Print + open the visible folder in the OS file manager

Usage
-----
    # Copy a single file
    python3 output-publisher.py publish --brand acme --workflow engagement \\
        --file ~/.claude-marketing/brands/acme/runs/engagement-.../part-8-growth-plan.md

    # Bulk-publish a whole run after it finishes
    python3 output-publisher.py publish-run --brand acme \\
        --run-id engagement-20260525-093015-fashion-q3

    # Just print the visible folder (for /digital-marketing-pro:output-folder)
    python3 output-publisher.py where --brand acme

    # Print + open
    python3 output-publisher.py open --brand acme
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402


def get_visible_publish_dir(brand: str, workflow: str | None = None,
                              override: str | None = None) -> Path:
    """Resolve the user-visible publish directory.

    Resolution order (first non-empty wins):
      1. ``override`` (CLI --publish-dir)
      2. ``$DIGITAL_MARKETING_PRO_PUBLISH_DIR`` env var (workspace default)
      3. ``~/Documents/DigitalMarketingPro/{brand}/[{workflow}/]``
    """
    base = override or os.environ.get("DIGITAL_MARKETING_PRO_PUBLISH_DIR")
    if base:
        root = Path(base).expanduser()
    else:
        root = Path.home() / "Documents" / "DigitalMarketingPro" / brand
    if workflow:
        root = root / workflow
    return root


def get_internal_tracking_dir(brand: str, workflow: str | None = None,
                                run_id: str | None = None) -> Path:
    base = _common.brand_dir(brand) / "output"
    if workflow:
        base = _common.safe_child(base, workflow)
    if run_id:
        base = _common.safe_child(base, run_id)
    return base


def _month_short() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _publish_file(src: Path, brand: str, workflow: str,
                   publish_dir_override: str | None = None,
                   skip_publish: bool = False) -> dict:
    """Copy src into both tracking + visible locations. Returns both paths."""
    if not src.exists():
        return {"error": f"source file not found: {src}"}

    # 1. Internal tracking copy
    tracking_dir = get_internal_tracking_dir(brand, workflow)
    tracking_dir.mkdir(parents=True, exist_ok=True)
    tracking_dest = tracking_dir / src.name
    shutil.copy2(str(src), str(tracking_dest))

    # 2. Visible publish copy
    published_path = None
    publish_error = None
    if not skip_publish:
        publish_dir = get_visible_publish_dir(brand, workflow, publish_dir_override) / _month_short()
        try:
            publish_dir.mkdir(parents=True, exist_ok=True)
            publish_dest = publish_dir / src.name
            shutil.copy2(str(src), str(publish_dest))
            published_path = str(publish_dest)
        except (OSError, PermissionError) as exc:
            publish_error = f"{type(exc).__name__}: {exc}"

    return {
        "status": "published",
        "source": str(src),
        "tracking_path": str(tracking_dest),
        "published_path": published_path,
        "publish_error": publish_error,
    }


def publish(args) -> dict:
    src = Path(args.file).expanduser()
    return _publish_file(src, args.brand, args.workflow,
                          publish_dir_override=args.publish_dir,
                          skip_publish=args.skip_publish)


def publish_run(args) -> dict:
    """Publish every artifact a checkpoint-manager run produced."""
    run_dir = _common.safe_child(_common.brand_dir(args.brand) / "runs", args.run_id)
    manifest_file = run_dir / "run.json"
    if not manifest_file.exists():
        return {"error": f"no run found: brand={args.brand} run_id={args.run_id}"}
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    workflow = manifest.get("workflow", "engagement")

    results = []
    for step, filename in manifest.get("step_artifacts", {}).items():
        src = run_dir / filename
        if not src.exists():
            continue
        r = _publish_file(src, args.brand, workflow,
                           publish_dir_override=args.publish_dir,
                           skip_publish=args.skip_publish)
        r["step"] = step
        results.append(r)

    return {
        "status": "published-run",
        "brand": args.brand,
        "run_id": args.run_id,
        "workflow": workflow,
        "artifact_count": len(results),
        "results": results,
        "publish_root": str(get_visible_publish_dir(args.brand, workflow, args.publish_dir)),
    }


def where(args) -> dict:
    visible = get_visible_publish_dir(args.brand, args.workflow, args.publish_dir)
    tracking = get_internal_tracking_dir(args.brand, args.workflow)
    return {
        "brand": args.brand,
        "workflow": args.workflow,
        "visible_publish_dir": str(visible),
        "visible_publish_dir_exists": visible.exists(),
        "internal_tracking_dir": str(tracking),
        "internal_tracking_dir_exists": tracking.exists(),
        "env_override_active": bool(os.environ.get("DIGITAL_MARKETING_PRO_PUBLISH_DIR")),
        "note": "The visible_publish_dir is the path to open in Explorer / Finder. "
                "The internal_tracking_dir is the dotfolder used by /digital-marketing-pro:status, "
                "checkpoint-manager.py, and other internal tools.",
    }


def _open_in_os(path: Path) -> tuple[bool, str]:
    """Best-effort 'reveal in file manager'. Returns (ok, message)."""
    if not path.exists():
        return False, f"path does not exist: {path}"
    try:
        system = platform.system()
        if system == "Windows":
            # 'start' is a cmd builtin; use the explorer.exe path-open
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
        return True, f"opened {path}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def open_folder(args) -> dict:
    visible = get_visible_publish_dir(args.brand, args.workflow, args.publish_dir)
    if not visible.exists():
        return {
            "brand": args.brand,
            "visible_publish_dir": str(visible),
            "status": "folder_does_not_exist_yet",
            "note": "No DMP workflow has finished for this brand+workflow yet. "
                    "Run a workflow first, then re-run this command. Expected location after first publish: "
                    f"{visible}",
        }
    ok, msg = _open_in_os(visible)
    return {
        "brand": args.brand,
        "workflow": args.workflow,
        "visible_publish_dir": str(visible),
        "opened": ok,
        "message": msg,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Dual-copy publisher for DMP outputs (internal tracking copy + user-visible published copy)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    common_pub_args = lambda p: (
        p.add_argument("--brand", type=_common.path_component, required=True),
        p.add_argument("--workflow", default="engagement"),
        p.add_argument("--publish-dir", default=None,
                       help="Override visible-publish root ($DIGITAL_MARKETING_PRO_PUBLISH_DIR or ~/Documents/DigitalMarketingPro/)"),
        p.add_argument("--skip-publish", action="store_true",
                       help="Skip the visible copy; only write the internal tracking copy"),
    )

    p_pub = sub.add_parser("publish", help="Publish a single file")
    common_pub_args(p_pub)
    p_pub.add_argument("--file", required=True, help="Path to the file to publish")

    p_run = sub.add_parser("publish-run", help="Publish every artifact in a checkpoint-manager run")
    common_pub_args(p_run)
    p_run.add_argument("--run-id", type=_common.path_component, required=True)

    p_where = sub.add_parser("where", help="Print the visible-publish path (no copy)")
    common_pub_args(p_where)

    p_open = sub.add_parser("open", help="Print + open the visible-publish folder in the OS file manager")
    common_pub_args(p_open)

    args = parser.parse_args()

    # Slugify brand at the boundary so tracking/publish dirs match the canon.
    if getattr(args, "brand", None):
        args.brand = _common.slugify_brand(args.brand)

    if args.cmd == "publish":
        result = publish(args)
    elif args.cmd == "publish-run":
        result = publish_run(args)
    elif args.cmd == "where":
        result = where(args)
    elif args.cmd == "open":
        result = open_folder(args)
    else:
        result = {"error": f"unknown cmd {args.cmd!r}"}

    _common.ensure_utf8_stdout()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    sys.exit(main())
