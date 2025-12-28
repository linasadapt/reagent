# storage.py
import json
import os
from copy import deepcopy
from datetime import datetime, timezone

def _now():
    return datetime.now(timezone.utc).isoformat()

def load_existing(filepath: str):
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        f"{item['source']['id']}:{item['id']}": item
        for item in data
        if item.get("id") and item.get("source")
    }

def has_changed(old: dict, new: dict) -> bool:
    # Ignore timestamps when comparing
    old_clean = {k: v for k, v in old.items() if k not in ("inserted_at", "updated_at")}
    new_clean = {k: v for k, v in new.items() if k not in ("inserted_at", "updated_at")}
    return old_clean != new_clean

def upsert_items(existing_index: dict, new_items: list):
    added = 0
    updated = 0
    now = _now()

    for item in new_items:
        key = f"{item['source']['id']}:{item['id']}"

        if key not in existing_index:
            record = deepcopy(item)
            record["inserted_at"] = now
            record["updated_at"] = None   # 👈 explicitly blank
            existing_index[key] = record
            added += 1

        else:
            if has_changed(existing_index[key], item):
                record = deepcopy(item)
                record["inserted_at"] = existing_index[key].get("inserted_at")
                record["updated_at"] = now  # 👈 only set on real change
                existing_index[key] = record
                updated += 1

    return added, updated

def save_all(filepath: str, index: dict):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(list(index.values()), f, indent=2, ensure_ascii=False)
