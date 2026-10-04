#!/usr/bin/env sh
# sync_model_registry.sh
# ======================
# Distributes the canonical Neelverse Marketing Suite model registry from this
# repo (Digital Marketing Pro) to the sibling content-plugin repos.
#
# DMP's model_registry.json is the canonical superset: it carries every entry
# the sibling plugins use PLUS a handful of marketing-suite-specific model
# families (deepseek / doubao / minimax / evolink / gpt-5.1 / gpt-5.2) that the
# content plugins do not need. Siblings deliberately keep a SUBSET registry,
# so this script never copies the whole file. Instead it performs a surgical
# by-id update: for each sibling it refreshes ONLY the entries whose ids
# already exist in that sibling's registry, and always refreshes `aliases`
# values for alias keys the sibling shares with the canonical file. Entries
# and alias keys that exist only in the sibling are left untouched; canonical-
# only entries are added ONLY when a shared alias or a replacement_id now
# points at them (otherwise the sibling would carry a dangling alias).
#
# This resolves the ghost referenced by model_registry.json's "$comment"
# ("Update this file then run scripts/sync_model_registry.sh to distribute").
#
# Windows-first: invoke via Git Bash (`sh scripts/sync_model_registry.sh`).
# It is idempotent and skips any sibling repo that is not checked out.
#
# Usage:
#   sh scripts/sync_model_registry.sh            # surgical update of siblings
#   sh scripts/sync_model_registry.sh --check    # report drift in SHARED entries only, copy nothing
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SRC="$SCRIPT_DIR/model_registry.json"
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
PARENT=$(CDPATH= cd -- "$REPO_ROOT/.." && pwd)

CHECK_ONLY=0
if [ "${1:-}" = "--check" ]; then
    CHECK_ONLY=1
fi

if [ ! -f "$SRC" ]; then
    echo "ERROR: canonical registry not found at $SRC" >&2
    exit 1
fi

PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
    echo "ERROR: python not found on PATH (needed for subset-safe merge)" >&2
    exit 1
fi

status=0
for sibling in contentforge socialforge; do
    dest="$PARENT/$sibling/scripts/model_registry.json"
    if [ ! -f "$dest" ]; then
        echo "SKIP  $sibling (not checked out at $dest)"
        continue
    fi
    result=$("$PY" - "$SRC" "$dest" "$CHECK_ONLY" <<'PYEOF'
import json
import sys

src_path, dest_path, check_only = sys.argv[1], sys.argv[2], sys.argv[3] == "1"

with open(src_path, encoding="utf-8") as f:
    src = json.load(f)
with open(dest_path, encoding="utf-8") as f:
    dest = json.load(f)

# Surgical by-id update: refresh only entries whose ids already exist in the
# sibling's (deliberately subset) registry.
canon = {m.get("id"): m for m in src.get("models", [])}
models_changed = 0
dest_models = dest.get("models", [])
for i, entry in enumerate(dest_models):
    cid = entry.get("id")
    if cid in canon and entry != canon[cid]:
        dest_models[i] = canon[cid]
        models_changed += 1

# Always refresh shared alias keys; sibling-only alias keys stay untouched.
src_aliases = src.get("aliases", {})
dest_aliases = dest.get("aliases", {})
aliases_changed = 0
for key in dest_aliases:
    if key in src_aliases and dest_aliases[key] != src_aliases[key]:
        dest_aliases[key] = src_aliases[key]
        aliases_changed += 1

# Closure: a refreshed alias (or a replacement_id the resolver falls forward
# along) may now name an entry the subset registry never carried. Copying the
# alias value without its target leaves a dangling alias that fails at
# resolution time, so pull every referenced canonical entry in.
present = {m.get("id") for m in dest_models}
pending = [v for v in dest_aliases.values() if v not in present]
pending += [m.get("replacement_id") for m in dest_models
            if m.get("replacement_id") and m.get("replacement_id") not in present]
while pending:
    rid = pending.pop()
    if rid in present or rid not in canon:
        continue
    dest_models.append(canon[rid])
    present.add(rid)
    models_changed += 1
    nxt = canon[rid].get("replacement_id")
    if nxt and nxt not in present:
        pending.append(nxt)

dangling = sorted({f"{k}->{v}" for k, v in dest_aliases.items() if v not in present})
if dangling:
    print("dangling " + ", ".join(dangling))
    sys.exit(0)

# Shared top-level metadata (sampling-param rules, tier vocabulary, stewardship)
# is suite-wide truth, not subset data — a sibling missing a param rule would
# send rejected parameters to the API.
for key in ("schema_version", "tiers", "param_compatibility_notes", "stewardship_policy"):
    if key in src and dest.get(key) != src[key]:
        dest[key] = src[key]
        models_changed += 1

if models_changed + aliases_changed and not check_only:
    for stamp in ("last_updated", "last_updated_by", "next_review_due"):
        if stamp in src:
            dest[stamp] = src[stamp]

if models_changed + aliases_changed == 0:
    print("in-sync")
elif check_only:
    print(f"drift models={models_changed} aliases={aliases_changed}")
else:
    with open(dest_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"synced models={models_changed} aliases={aliases_changed}")
PYEOF
)
    case "$result" in
        in-sync)
            echo "OK    $sibling shared entries already in sync"
            ;;
        drift*)
            echo "DRIFT $sibling shared entries differ from canonical DMP copy ($result)"
            status=1
            ;;
        synced*)
            echo "SYNC  $sibling updated in place ($result)"
            ;;
        dangling*)
            echo "ERROR $sibling: alias targets missing from canonical too ($result)" >&2
            status=1
            ;;
        *)
            echo "ERROR $sibling: unexpected merge output: $result" >&2
            status=1
            ;;
    esac
done

exit $status
