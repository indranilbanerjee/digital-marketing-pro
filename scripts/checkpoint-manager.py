#!/usr/bin/env python3
"""
checkpoint-manager.py
=====================
Per-step checkpoint storage for Digital Marketing Pro long-running workflows.
Adapted for DMP's 12-Part Strategy Flow: a single interruption used to mean
restarting the entire multi-part run from Part 1; with checkpoints, a fresh
session reloads completed parts and continues from the next one.

Workflows tracked
-----------------
- ``engagement``       — 12-Part Strategy Flow (the slow one, 50-60 files)
- ``campaign-plan``    — Campaign planning workflow
- ``content-engine``   — Content production sweep
- ``seo-audit``        — Technical + content + E-E-A-T + AI-visibility audit
- ``competitor-analysis`` — Multi-dimensional competitor deep-dive
- ``campaign-audit``   — Cross-channel current-state audit (v3.7.5)
- ``launch-campaign``  — 14-step multi-channel launch (v3.7.5)
- ``custom``           — Any other long workflow the user wants resumable

Storage layout
--------------
    <workspace>/brands/{brand-slug}/runs/{run_id}/
        run.json                 — manifest (workflow, status, parts, timestamps)
        part-1-client-inputs.md      — Part 1 deliverable
        part-2-research.md           — Part 2 deliverable
        ...
        part-12-improvement-loop.md  — Part 12 deliverable

For non-engagement workflows the part / step names differ but the contract is
identical — each step writes its output as ``step-<N>-<name>.{md,json}`` and
``run.json`` records the order + status.

Subcommands
-----------
    init      — Start a tracked workflow run, returns run_id
    save      — Save the output of a step (--phase NAME or --step NUMBER)
    status    — Show run status + completed/remaining steps
    load      — Print the saved content for a step
    list      — All runs for a brand (with workflow filter)
    resume    — Pick the latest in-progress run (or --run-id) and report next step
    finalize  — Mark a run completed / failed / abandoned
    discard   — Delete a run's checkpoint directory

Stdlib only. Atomic writes. Works in headless / cron contexts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

# The 12-Part Strategy Flow — DMP's canonical engagement workflow
ENGAGEMENT_PARTS = {
    "1": "Stone-vs-Opinion intake",
    "2": "External market research",
    "3": "Four Core Documents (61 explicit steps)",
    "4": "Competitive / customer / market analysis",
    "5": "Client Validation Document",
    "6": "Selective v2 re-runs per Decision Matrix",
    "7": "Preparation documents (campaign architecture, KPI tree, content pillars)",
    "8": "Growth Plan + 12-month Yearly Planner",
    "9": "Channel-strategy fan-out (up to 17 channel docs in 7 families)",
    "10": "Execution artefacts (ad copy, post copy, headlines, CTAs)",
    "11": "AI creative briefs (current image/video generation models + C2PA + deepfake-disclosure)",
    "12": "Continuous improvement loop",
}

# Other DMP workflows are open-ended — we don't impose a fixed step list.
# They use --step <N> and any string name, and `status` reports whatever was saved.
WORKFLOW_PRESETS = {
    "engagement": ENGAGEMENT_PARTS,
    "campaign-plan": None,
    "content-engine": None,
    "seo-audit": None,
    "competitor-analysis": None,
    "campaign-audit": None,
    "launch-campaign": None,
    "custom": None,
}


def _slug(text: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^\w\s-]", "", (text or "").lower())
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:maxlen] or "untitled"


def _runs_dir(brand: str) -> Path:
    # Env-aware, slugified, canonical brands/ layout (with legacy-dir fallback
    # for pre-v3.15 runs stored at the old ~/.claude-marketing/{brand}/runs).
    return _common.brand_dir(brand) / "runs"


def _run_dir(brand: str, run_id: str) -> Path:
    # run_id comes from the model; contain it so `discard` can never rmtree outside runs/.
    return _common.safe_child(_runs_dir(brand), run_id)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_manifest(brand: str, run_id: str) -> dict | None:
    f = _run_dir(brand, run_id) / "run.json"
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def _save_manifest(brand: str, run_id: str, manifest: dict) -> None:
    f = _run_dir(brand, run_id) / "run.json"
    tmp = f.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def _step_order_for(workflow: str, parts_seen: list[str]) -> list[str]:
    """Return canonical step order. For engagement it's PARTS keys 1..12;
    for other workflows it's whatever steps have been recorded so far,
    sorted numerically when possible."""
    preset = WORKFLOW_PRESETS.get(workflow)
    if preset:
        return list(preset.keys())
    # Sort the steps actually seen — numeric first, then lexicographic
    def sort_key(s):
        try:
            return (0, float(s))
        except ValueError:
            return (1, s)
    return sorted(set(parts_seen), key=sort_key)


def init_run(brand: str, workflow: str, topic: str | None = None) -> dict:
    if workflow not in WORKFLOW_PRESETS:
        return {"error": f"unknown workflow {workflow!r}. One of: {list(WORKFLOW_PRESETS)}"}
    now = datetime.now(timezone.utc)
    label = _slug(topic or workflow, maxlen=40)
    run_id = f"{workflow}-{now.strftime('%Y%m%d-%H%M%S')}-{label}"
    run_dir = _run_dir(brand, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    preset = WORKFLOW_PRESETS.get(workflow)
    manifest = {
        "run_id": run_id,
        "brand": brand,
        "workflow": workflow,
        "topic": topic,
        "status": "in_progress",
        "started_at": _now_iso(),
        "last_updated": _now_iso(),
        "completed_steps": [],
        "step_artifacts": {},
        "step_labels": preset if preset else {},
    }
    _save_manifest(brand, run_id, manifest)
    return {"run_id": run_id, "path": str(run_dir), "manifest": manifest}


def save_step(brand: str, run_id: str, step: str, content: str, extension: str = "md", label: str | None = None) -> dict:
    manifest = _load_manifest(brand, run_id)
    if manifest is None:
        return {"error": f"no run found: brand={brand} run_id={run_id}"}

    workflow = manifest.get("workflow", "custom")
    preset = WORKFLOW_PRESETS.get(workflow)
    if preset and step not in preset:
        return {"error": f"workflow {workflow!r} uses fixed steps {list(preset)}; step {step!r} is not one of them"}

    if preset:
        label_text = preset[step]
    else:
        label_text = label or f"step-{step}"
    label_slug = _slug(label_text, maxlen=25)
    filename = f"part-{step}-{label_slug}.{extension.lstrip('.')}" if preset \
                else f"step-{step}-{label_slug}.{extension.lstrip('.')}"
    out = _run_dir(brand, run_id) / filename
    out.write_text(content, encoding="utf-8")

    if step not in manifest["completed_steps"]:
        manifest["completed_steps"].append(step)
        # Sort by preset order when fixed, else numeric+lex
        ordered = _step_order_for(workflow, manifest["completed_steps"])
        manifest["completed_steps"] = [s for s in ordered if s in manifest["completed_steps"]]
    manifest["step_artifacts"][step] = filename
    if label and not preset:
        manifest.setdefault("step_labels", {})[step] = label
    manifest["last_updated"] = _now_iso()
    _save_manifest(brand, run_id, manifest)

    return {
        "status": "saved",
        "run_id": run_id,
        "step": step,
        "step_label": label_text,
        "artifact": str(out),
        "completed_steps": manifest["completed_steps"],
    }


def get_status(brand: str, run_id: str) -> dict:
    manifest = _load_manifest(brand, run_id)
    if manifest is None:
        return {"error": f"no run found: brand={brand} run_id={run_id}"}
    workflow = manifest.get("workflow", "custom")
    done = manifest["completed_steps"]
    order = _step_order_for(workflow, done)
    remaining = [s for s in order if s not in done]
    next_step = remaining[0] if remaining else None
    preset = WORKFLOW_PRESETS.get(workflow) or manifest.get("step_labels", {})
    return {
        "run_id": run_id,
        "brand": brand,
        "workflow": workflow,
        "topic": manifest.get("topic"),
        "status": manifest.get("status"),
        "started_at": manifest.get("started_at"),
        "last_updated": manifest.get("last_updated"),
        "completed_steps": done,
        "remaining_steps": remaining,
        "next_step": next_step,
        "next_step_label": preset.get(next_step) if (preset and next_step) else None,
        "step_artifacts": {
            s: str(_run_dir(brand, run_id) / fn)
            for s, fn in manifest.get("step_artifacts", {}).items()
        },
    }


def load_step(brand: str, run_id: str, step: str) -> dict:
    manifest = _load_manifest(brand, run_id)
    if manifest is None:
        return {"error": f"no run found: brand={brand} run_id={run_id}"}
    fn = manifest.get("step_artifacts", {}).get(step)
    if not fn:
        return {"error": f"step {step} has no checkpoint in run {run_id}"}
    artifact = _run_dir(brand, run_id) / fn
    return {
        "step": step,
        "artifact": str(artifact),
        "content": artifact.read_text(encoding="utf-8") if artifact.exists() else None,
    }


def list_runs(brand: str, workflow: str | None = None) -> dict:
    rd = _runs_dir(brand)
    if not rd.exists():
        return {"brand": brand, "runs": []}
    runs = []
    for d in sorted(rd.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        m = _load_manifest(brand, d.name)
        if m is None:
            continue
        if workflow and m.get("workflow") != workflow:
            continue
        last_step = m["completed_steps"][-1] if m.get("completed_steps") else None
        runs.append({
            "run_id": m["run_id"],
            "workflow": m.get("workflow"),
            "topic": m.get("topic"),
            "status": m.get("status"),
            "last_step": last_step,
            "last_updated": m.get("last_updated"),
            "completed_steps": m.get("completed_steps", []),
        })
    return {"brand": brand, "runs": runs}


def pick_resumable(brand: str, run_id: str | None, workflow: str | None = None) -> dict:
    """Pick the run to resume. With --run-id, use it. Otherwise the most recent
    in-progress run, optionally filtered to a specific workflow (so the user can
    say 'resume my engagement' vs 'resume my SEO audit')."""
    if run_id:
        s = get_status(brand, run_id)
        return {"resume_run": s} if "error" not in s else s
    listed = list_runs(brand, workflow)
    candidates = [r for r in listed["runs"] if r["status"] == "in_progress"]
    if not candidates:
        wf_msg = f" for workflow={workflow!r}" if workflow else ""
        return {"brand": brand, "resume_run": None,
                "message": f"No in-progress runs found{wf_msg}. Start a new workflow first."}
    target = candidates[0]
    s = get_status(brand, target["run_id"])
    return {"brand": brand, "resume_run": s}


def finalize_run(brand: str, run_id: str, status: str = "completed") -> dict:
    manifest = _load_manifest(brand, run_id)
    if manifest is None:
        return {"error": f"no run found: brand={brand} run_id={run_id}"}
    manifest["status"] = status
    manifest["finalized_at"] = _now_iso()
    manifest["last_updated"] = _now_iso()
    _save_manifest(brand, run_id, manifest)
    return {"status": status, "run_id": run_id}


def discard_run(brand: str, run_id: str) -> dict:
    rd = _run_dir(brand, run_id)
    if not rd.exists():
        return {"error": f"no run found: brand={brand} run_id={run_id}"}
    shutil.rmtree(rd)
    return {"status": "discarded", "run_id": run_id}


def main() -> int:
    parser = argparse.ArgumentParser(description="DMP per-step checkpoint manager (resumable workflows)")
    sub = parser.add_subparsers(dest="action", required=True)

    p_init = sub.add_parser("init", help="Start a tracked workflow run")
    p_init.add_argument("--brand", type=_common.path_component, required=True)
    p_init.add_argument("--workflow", required=True, choices=list(WORKFLOW_PRESETS))
    p_init.add_argument("--topic", default=None, help="Run topic/label for the run_id")

    p_save = sub.add_parser("save", help="Save the output of a step")
    p_save.add_argument("--brand", type=_common.path_component, required=True)
    p_save.add_argument("--run-id", type=_common.path_component, required=True)
    p_save.add_argument("--step", required=True, help="Step / part identifier (engagement: 1..12; others: any)")
    g = p_save.add_mutually_exclusive_group(required=True)
    g.add_argument("--content", help="Step content inline")
    g.add_argument("--content-file", help="Path to a file containing step content")
    p_save.add_argument("--extension", default="md", help="md / json / txt")
    p_save.add_argument("--label", help="Step label (only used for workflows without a fixed preset)")

    p_status = sub.add_parser("status", help="Show run status, completed + remaining steps")
    p_status.add_argument("--brand", type=_common.path_component, required=True)
    p_status.add_argument("--run-id", type=_common.path_component, required=True)

    p_load = sub.add_parser("load", help="Print the saved content for a step")
    p_load.add_argument("--brand", type=_common.path_component, required=True)
    p_load.add_argument("--run-id", type=_common.path_component, required=True)
    p_load.add_argument("--step", required=True)

    p_list = sub.add_parser("list", help="List runs for a brand (optional workflow filter)")
    p_list.add_argument("--brand", type=_common.path_component, required=True)
    p_list.add_argument("--workflow", default=None, choices=list(WORKFLOW_PRESETS))

    p_resume = sub.add_parser("resume", help="Pick the run to resume (latest in_progress, or --run-id)")
    p_resume.add_argument("--brand", type=_common.path_component, required=True)
    p_resume.add_argument("--run-id", type=_common.path_component, default=None)
    p_resume.add_argument("--workflow", default=None, choices=list(WORKFLOW_PRESETS))

    p_fin = sub.add_parser("finalize", help="Mark a run completed/failed/abandoned")
    p_fin.add_argument("--brand", type=_common.path_component, required=True)
    p_fin.add_argument("--run-id", type=_common.path_component, required=True)
    p_fin.add_argument("--status", default="completed", choices=["completed", "failed", "abandoned"])

    p_dis = sub.add_parser("discard", help="Delete a run's checkpoint directory")
    p_dis.add_argument("--brand", type=_common.path_component, required=True)
    p_dis.add_argument("--run-id", type=_common.path_component, required=True)

    args = parser.parse_args()

    # Slugify the brand at the boundary so checkpoint runs land in the SAME
    # directory the rest of the plugin reads from.
    if getattr(args, "brand", None):
        args.brand = _common.slugify_brand(args.brand)

    try:
        if args.action == "init":
            result = init_run(args.brand, args.workflow, args.topic)
        elif args.action == "save":
            content = args.content
            if args.content_file:
                content = Path(args.content_file).expanduser().read_text(encoding="utf-8")
            result = save_step(args.brand, args.run_id, args.step, content, args.extension, args.label)
        elif args.action == "status":
            result = get_status(args.brand, args.run_id)
        elif args.action == "load":
            result = load_step(args.brand, args.run_id, args.step)
        elif args.action == "list":
            result = list_runs(args.brand, args.workflow)
        elif args.action == "resume":
            result = pick_resumable(args.brand, args.run_id, args.workflow)
        elif args.action == "finalize":
            result = finalize_run(args.brand, args.run_id, args.status)
        elif args.action == "discard":
            result = discard_run(args.brand, args.run_id)
        else:
            result = {"error": f"unknown action {args.action!r}"}
    except Exception as exc:
        result = {"error": f"{type(exc).__name__}: {exc}"}

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    sys.exit(main())
