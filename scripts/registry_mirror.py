#!/usr/bin/env python3
"""Mirror the canonical model registry into the sibling plugins: canonical minus DMP_ONLY.

DMP's scripts/model_registry.json is the canonical registry. Each sibling plugin's copy is
exactly the canonical file minus the DMP-only model families (DMP_ONLY_MODELS) and their
aliases (DMP_ONLY_ALIASES), keeping only the sibling's own `$comment`. That is the whole rule:
an entry DMP drops is dropped from the siblings, and a new canonical entry or alias key
reaches them even when nothing points at it yet. (The old surgical by-id update did neither,
so the 3.36.2 sync had to be finished by hand with this same mirror.)

Usage (sync_model_registry.sh calls this):
    python registry_mirror.py              write each checked-out sibling's mirror
    python registry_mirror.py --check      report drift in both directions; write nothing
    python registry_mirror.py --parent DIR siblings live in DIR (default: this repo's parent)

--check lists, per sibling: entries and alias keys the sibling is MISSING, entries and alias
keys it has that the canonical file dropped (EXTRA), shared entries whose content DRIFTED,
and top-level metadata that differs. Exit status: 0 in sync (or synced), 1 drift or error,
2 bad argument. Stdlib only; reads accept a UTF-8 BOM, writes never make one.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CANONICAL = Path(__file__).resolve().parent / "model_registry.json"

# Marketing-suite-only families the content plugins never call. Two of them (deepseek-chat,
# gpt-5.2) and the evolink aliases are exercised by tests/test_resolve_model.py.
DMP_ONLY_MODELS = frozenset({
    "deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash", "deepseek-v4-pro",
    "doubao-seed-2.0-lite", "doubao-seed-2.0-pro", "evolink-auto",
    "gpt-5.1", "gpt-5.2", "minimax-m2.5", "minimax-m3",
})
DMP_ONLY_ALIASES = frozenset({
    "latest-balanced-evolink", "latest-fast-evolink", "latest-text-evolink",
})

# Sibling -> its registry copy, relative to the sibling's repo folder.
SIBLINGS = {
    "contentforge": "scripts/model_registry.json",
    "socialforge": "scripts/model_registry.json",
    # CutForge has no scripts/ folder: engine/template/ is what each new project copies, so the
    # registry travels with every project next to the resolver that reads it.
    "cutforge": "engine/template/tools/model_registry.json",
}
# Folder spellings to try, in order (working copies are capitalised on some machines, and a
# case-sensitive disk will not match the other spelling).
FOLDERS = {
    "contentforge": ("contentforge", "ContentForge"),
    "socialforge": ("socialforge", "SocialForge"),
    "cutforge": ("CutForge", "cutforge"),
}
# Siblings whose first sync creates the copy (its folder must already exist).
CREATE_IF_MISSING = frozenset({"cutforge"})


def mirror(canonical: dict, sibling: dict | None = None) -> dict:
    """The sibling's registry as it should be. Raises ValueError if the result would dangle."""
    out = {}
    for key, value in canonical.items():
        if key == "models":
            value = [m for m in value if m.get("id") not in DMP_ONLY_MODELS]
        elif key == "aliases":
            value = {k: v for k, v in value.items() if k not in DMP_ONLY_ALIASES}
        elif key == "$comment" and sibling and "$comment" in sibling:
            value = sibling["$comment"]
        out[key] = value
    ids = {m.get("id") for m in out.get("models", [])}
    dangling = sorted(f"alias {k} -> {v}" for k, v in out.get("aliases", {}).items() if v not in ids)
    dangling += sorted(f"{m['id']} replacement -> {m['replacement_id']}" for m in out.get("models", [])
                       if m.get("replacement_id") and m["replacement_id"] not in ids)
    dangling += sorted(f"{m['id']} replacement on {backend} -> {rep}" for m in out.get("models", [])
                       for backend, rep in (m.get("replacement_by_backend") or {}).items() if rep not in ids)
    if dangling:
        raise ValueError("the mirror would point at DMP-only or missing entries: " + "; ".join(dangling))
    return out


def render(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def differences(expected: dict, actual: dict) -> list[str]:
    """Human-readable drift between the mirror and a sibling's copy, both directions."""
    out = []
    want = {m.get("id"): m for m in expected.get("models", [])}
    have = {m.get("id"): m for m in actual.get("models", [])}
    if missing := sorted(set(want) - set(have)):
        out.append("missing models: " + ", ".join(missing))
    if extra := sorted(set(have) - set(want)):
        out.append("extra models (dropped or DMP-only upstream): " + ", ".join(extra))
    if drift := sorted(i for i in set(want) & set(have) if want[i] != have[i]):
        out.append("drifted models: " + ", ".join(drift))
    wa, ha = expected.get("aliases", {}), actual.get("aliases", {})
    if missing := sorted(set(wa) - set(ha)):
        out.append("missing aliases: " + ", ".join(missing))
    if extra := sorted(set(ha) - set(wa)):
        out.append("extra aliases (dropped or DMP-only upstream): " + ", ".join(extra))
    if drift := sorted(k for k in set(wa) & set(ha) if wa[k] != ha[k]):
        out.append("drifted aliases: " + ", ".join(drift))
    top = (set(expected) | set(actual)) - {"models", "aliases", "$comment"}
    if meta := sorted(k for k in top if expected.get(k) != actual.get(k)):
        out.append("metadata differs: " + ", ".join(meta))
    if not out and render(expected) != render(actual):
        out.append("same content, different order")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mirror the canonical model registry into sibling plugins.")
    parser.add_argument("--check", action="store_true", help="report drift both ways; write nothing")
    parser.add_argument("--parent", type=Path, default=CANONICAL.parent.parent.parent,
                        help="folder that holds the sibling repos (default: this repo's parent)")
    args = parser.parse_args(argv)

    canonical = json.loads(CANONICAL.read_text(encoding="utf-8-sig"))
    status = 0
    for name, rel in SIBLINGS.items():
        folder = next((args.parent / f for f in FOLDERS.get(name, (name,)) if (args.parent / f).is_dir()), None)
        if folder is None:
            print(f"SKIP  {name} (not checked out under {args.parent})")
            continue
        dest = folder / rel
        if not dest.is_file():
            if name in CREATE_IF_MISSING and dest.parent.is_dir():
                if args.check:
                    print(f"DRIFT {name}: no registry copy yet at {dest} (a sync creates it)")
                    status = 1
                else:
                    dest.write_text(render(mirror(canonical)), encoding="utf-8", newline="")
                    print(f"SYNC  {name} created {dest} as the canonical mirror")
                continue
            print(f"SKIP  {name} (no registry at {dest})")
            continue
        text = dest.read_text(encoding="utf-8-sig")
        try:
            actual = json.loads(text)
            expected = mirror(canonical, actual)
        except ValueError as exc:
            print(f"ERROR {name}: {exc}", file=sys.stderr)
            status = 1
            continue
        if render(expected) == text:
            print(f"OK    {name} matches the canonical mirror")
            continue
        found = differences(expected, actual) or ["formatting differs"]
        if args.check:
            print(f"DRIFT {name}: " + "; ".join(found))
            status = 1
        else:
            dest.write_text(render(expected), encoding="utf-8", newline="")
            print(f"SYNC  {name} rewritten as the canonical mirror (" + "; ".join(found) + ")")
    return status


if __name__ == "__main__":
    sys.exit(main())
