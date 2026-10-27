#!/usr/bin/env sh
# sync_model_registry.sh
# ======================
# Distributes the canonical Neelverse Marketing Suite model registry from this
# repo (Digital Marketing Pro) to the sibling plugin repos checked out next to it.
#
# Each sibling's copy is a MIRROR: the canonical scripts/model_registry.json minus
# the DMP-only model families and aliases (DMP_ONLY_MODELS / DMP_ONLY_ALIASES in
# scripts/registry_mirror.py), keeping only the sibling's own "$comment". An entry
# DMP drops is dropped from the siblings, and a new canonical entry or alias key
# reaches them even when nothing points at it yet. The merge itself lives in
# registry_mirror.py so tests can drive it; this script only finds Python.
#
# (Until 3.37.2 this script did a surgical by-id update: it refreshed shared
# entries, but left entries DMP had dropped and never added unreferenced
# canonical entries or new alias keys, so the 3.36.2 sync had to be finished by
# hand.)
#
# Windows-first: invoke via Git Bash (`sh scripts/sync_model_registry.sh`).
# Idempotent; skips any sibling repo that is not checked out.
#
# Usage:
#   sh scripts/sync_model_registry.sh                # rewrite each sibling as the mirror
#   sh scripts/sync_model_registry.sh --check        # report missing / extra / drifted entries, write nothing
#   sh scripts/sync_model_registry.sh --parent DIR   # siblings live in DIR (default: this repo's parent)
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
    echo "ERROR: python not found on PATH (needed for the registry mirror)" >&2
    exit 1
fi

exec "$PY" "$SCRIPT_DIR/registry_mirror.py" "$@"
