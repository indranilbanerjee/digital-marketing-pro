#!/usr/bin/env python3
"""
memory-manager.py
=================
Local memory management interface for Digital Marketing Pro.

Manages the local side of memory/RAG workflows: preparing data for vector DB
storage via MCP, indexing metadata, tracking sync state, and searching the
local memory index.  Actual vector DB and graph DB writes happen via MCP
servers — this script handles data prep, dedup, and bookkeeping.

Storage: ~/.claude-marketing/brands/{slug}/memory/

Usage:
    python memory-manager.py --brand acme --action prepare-store --data '{"content": "...", "content_type": "campaign-learning", "tags": ["ppc"], "source": "session"}'
    python memory-manager.py --brand acme --action log-stored --data '{"content_hash": "abc123", "vector_db": "pinecone", "storage_id": "vec_001"}'
    python memory-manager.py --brand acme --action search-local --type campaign-learning --tags ppc,retargeting --from-date 2026-01-01
    python memory-manager.py --brand acme --action prepare-graph --data '{"entity": "Summer Sale", "entity_type": "campaign", "relationships": [{"target": "Gen-Z", "relation_type": "targets", "temporal_context": "Q2 2026"}]}'
    python memory-manager.py --brand acme --action sync-insights
    python memory-manager.py --brand acme --action get-memory-status
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

BRANDS_DIR = Path.home() / ".claude-marketing" / "brands"

VALID_CONTENT_TYPES = [
    "guideline", "campaign-learning", "competitive-intel",
    "performance-insight", "brand-asset",
]

VALID_ENTITY_TYPES = [
    "brand", "campaign", "audience", "competitor", "channel", "message",
]

MEMORY_ENV_VARS = {
    "pinecone": "PINECONE_API_KEY",
    "qdrant": "QDRANT_API_KEY",
    "supermemory": "SUPERMEMORY_API_KEY",
    "graphiti": "GRAPHITI_API_KEY",
}


def get_brand_dir(slug):
    """Get and validate brand directory."""
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return None, f"Brand '{slug}' not found. Run /dm:brand-setup first."
    return brand_dir, None


def _load_json(path, default=None):
    """Safely load a JSON file, returning default on missing/corrupt."""
    if default is None:
        default = []
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path, data):
    """Atomically write JSON to a file."""
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def prepare_store(slug, data):
    """Prepare content for vector DB storage via MCP."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    # Validate required fields
    content = data.get("content")
    content_type = data.get("content_type")
    tags = data.get("tags", [])
    source = data.get("source", "session")

    if not content:
        return {"error": "Missing required field: content"}
    if content_type not in VALID_CONTENT_TYPES:
        return {"error": f"Invalid content_type '{content_type}'. Must be one of: {VALID_CONTENT_TYPES}"}

    # Generate content hash for dedup
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    # Check for existing item with same hash in index
    memory_dir = brand_dir / "memory"
    memory_dir.mkdir(exist_ok=True)
    index = _load_json(memory_dir / "_index.json", [])
    for entry in index:
        if entry.get("content_hash") == content_hash:
            return {
                "status": "duplicate",
                "content_hash": content_hash,
                "existing_entry": entry,
                "note": "Content with identical hash already stored.",
            }

    # Build storage-ready payload
    timestamp = datetime.now().isoformat()
    payload = {
        "content_hash": content_hash,
        "brand": slug,
        "content": content,
        "content_type": content_type,
        "tags": tags,
        "source": source,
        "created_at": timestamp,
        "metadata": {
            "char_count": len(content),
            "word_count": len(content.split()),
        },
    }

    # Save to pending directory for MCP pickup
    pending_dir = memory_dir / "pending"
    pending_dir.mkdir(exist_ok=True)
    filepath = pending_dir / f"{content_hash}.json"
    _save_json(filepath, payload)

    return {
        "status": "prepared",
        "content_hash": content_hash,
        "path": str(filepath),
        "payload": payload,
    }


def log_stored(slug, data):
    """Record that a pending item was stored in a vector DB."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    content_hash = data.get("content_hash")
    vector_db = data.get("vector_db")
    storage_id = data.get("storage_id")

    if not content_hash:
        return {"error": "Missing required field: content_hash"}
    if not vector_db:
        return {"error": "Missing required field: vector_db"}
    if not storage_id:
        return {"error": "Missing required field: storage_id"}

    memory_dir = brand_dir / "memory"
    pending_path = memory_dir / "pending" / f"{content_hash}.json"
    stored_dir = memory_dir / "stored"
    stored_dir.mkdir(exist_ok=True)

    # Load pending payload
    if pending_path.exists():
        payload = _load_json(pending_path, {})
        # Move to stored
        stored_path = stored_dir / f"{content_hash}.json"
        payload["vector_db"] = vector_db
        payload["storage_id"] = storage_id
        payload["stored_at"] = datetime.now().isoformat()
        _save_json(stored_path, payload)
        pending_path.unlink()
    else:
        payload = {"content_hash": content_hash}

    # Update master index
    index = _load_json(memory_dir / "_index.json", [])
    index.append({
        "content_hash": content_hash,
        "vector_db": vector_db,
        "storage_id": storage_id,
        "content_type": payload.get("content_type", "unknown"),
        "tags": payload.get("tags", []),
        "stored_at": datetime.now().isoformat(),
    })
    _save_json(memory_dir / "_index.json", index)

    return {"status": "logged", "content_hash": content_hash, "vector_db": vector_db}


def search_local(slug, content_type=None, tags=None, from_date=None, to_date=None):
    """Search the local memory index by content_type, tags, or date range."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    index = _load_json(brand_dir / "memory" / "_index.json", [])
    results = index

    if content_type:
        results = [e for e in results if e.get("content_type") == content_type]

    if tags:
        tag_set = set(tags)
        results = [e for e in results if tag_set & set(e.get("tags", []))]

    if from_date:
        results = [e for e in results if e.get("stored_at", "") >= from_date]

    if to_date:
        results = [e for e in results if e.get("stored_at", "") <= to_date]

    return {"results": list(reversed(results)), "total": len(results)}


def prepare_graph(slug, data):
    """Prepare an entity + relationships payload for Graphiti MCP."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    entity = data.get("entity")
    entity_type = data.get("entity_type")
    relationships = data.get("relationships", [])

    if not entity:
        return {"error": "Missing required field: entity"}
    if entity_type not in VALID_ENTITY_TYPES:
        return {"error": f"Invalid entity_type '{entity_type}'. Must be one of: {VALID_ENTITY_TYPES}"}

    payload = {
        "brand": slug,
        "entity": entity,
        "entity_type": entity_type,
        "relationships": relationships,
        "created_at": datetime.now().isoformat(),
    }

    memory_dir = brand_dir / "memory"
    pending_dir = memory_dir / "pending"
    pending_dir.mkdir(exist_ok=True)
    entity_hash = hashlib.sha256(f"{entity}:{entity_type}".encode()).hexdigest()[:12]
    filepath = pending_dir / f"graph-{entity_hash}.json"
    _save_json(filepath, payload)

    return {"status": "prepared", "entity": entity, "path": str(filepath), "payload": payload}


def sync_insights(slug):
    """Diff insights.json against last sync and prepare new items for storage."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    insights_path = brand_dir / "insights.json"
    if not insights_path.exists():
        return {"items_to_sync": [], "total": 0, "note": "No insights.json found."}

    insights = _load_json(insights_path, [])
    memory_dir = brand_dir / "memory"
    memory_dir.mkdir(exist_ok=True)

    last_sync = _load_json(memory_dir / "_last_sync.json", {})
    last_sync_ts = last_sync.get("last_sync_at", "")

    # Find insights newer than last sync
    new_insights = [i for i in insights if i.get("recorded_at", "") > last_sync_ts] if last_sync_ts else insights

    # Prepare each as a store payload
    pending_dir = memory_dir / "pending"
    pending_dir.mkdir(exist_ok=True)
    payloads = []
    for insight in new_insights:
        content = insight.get("insight", "")
        if not content:
            continue
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        payload = {
            "content_hash": content_hash,
            "brand": slug,
            "content": content,
            "content_type": "performance-insight",
            "tags": [insight.get("type", "learning"), insight.get("source", "session")],
            "source": "insights-sync",
            "created_at": datetime.now().isoformat(),
            "original_recorded_at": insight.get("recorded_at", ""),
        }
        _save_json(pending_dir / f"{content_hash}.json", payload)
        payloads.append(payload)

    # Update last sync timestamp
    _save_json(memory_dir / "_last_sync.json", {
        "last_sync_at": datetime.now().isoformat(),
        "items_synced": len(payloads),
    })

    return {"items_to_sync": payloads, "total": len(payloads)}


def get_memory_status(slug):
    """Return memory system status: counts, services, sync state."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    memory_dir = brand_dir / "memory"
    index = _load_json(memory_dir / "_index.json", [])
    last_sync = _load_json(memory_dir / "_last_sync.json", {})

    # Count pending items
    pending_dir = memory_dir / "pending"
    pending_count = len(list(pending_dir.glob("*.json"))) if pending_dir.exists() else 0

    # Count by content_type
    type_counts = {}
    for entry in index:
        ct = entry.get("content_type", "unknown")
        type_counts[ct] = type_counts.get(ct, 0) + 1

    # Check connected services
    connected = {}
    for service, env_var in MEMORY_ENV_VARS.items():
        connected[service] = bool(os.environ.get(env_var))

    return {
        "total_stored": len(index),
        "by_content_type": type_counts,
        "pending_items": pending_count,
        "last_sync_at": last_sync.get("last_sync_at"),
        "connected_services": connected,
    }


def main():
    parser = argparse.ArgumentParser(description="Memory management for Digital Marketing Pro")
    parser.add_argument("--brand", required=True, help="Brand slug")
    parser.add_argument("--action", required=True,
                        choices=["prepare-store", "log-stored", "search-local",
                                 "prepare-graph", "sync-insights", "get-memory-status"],
                        help="Action to perform")
    parser.add_argument("--data", help="JSON data (for prepare/log actions)")
    parser.add_argument("--type", dest="content_type", help="Filter by content_type")
    parser.add_argument("--tags", help="Comma-separated tags to filter by")
    parser.add_argument("--from-date", help="Start date filter (ISO format)")
    parser.add_argument("--to-date", help="End date filter (ISO format)")
    args = parser.parse_args()

    if args.action == "prepare-store":
        if not args.data:
            print(json.dumps({"error": "Provide --data with content JSON"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = prepare_store(args.brand, data)

    elif args.action == "log-stored":
        if not args.data:
            print(json.dumps({"error": "Provide --data with storage confirmation JSON"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = log_stored(args.brand, data)

    elif args.action == "search-local":
        tag_list = args.tags.split(",") if args.tags else None
        result = search_local(args.brand, args.content_type, tag_list,
                              args.from_date, args.to_date)

    elif args.action == "prepare-graph":
        if not args.data:
            print(json.dumps({"error": "Provide --data with entity/relationship JSON"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = prepare_graph(args.brand, data)

    elif args.action == "sync-insights":
        result = sync_insights(args.brand)

    elif args.action == "get-memory-status":
        result = get_memory_status(args.brand)

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
