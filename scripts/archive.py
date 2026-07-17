#!/usr/bin/env python3
"""Shared access to the per-item archive: data/items/<id>.json + data/assets/<id>/.

One file per item so concurrent adds from different sessions/machines are
different files — git merges them natively, no custom merge driver. Frame
images live beside the archive as real files (data/assets/<id>/*.jpg), never
as base64 inside the JSON, so item files stay small enough to read and diff.
"""
import json
import os
import re
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DEFAULT_ITEMS_DIR = os.path.join(REPO_ROOT, "data", "items")
DEFAULT_ASSETS_DIR = os.path.join(REPO_ROOT, "data", "assets")

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def safe_id(item_id):
    """Validate an id for use as a filename (YouTube ids and b-<hash> both fit)."""
    if not (isinstance(item_id, str) and _SAFE_ID.fullmatch(item_id)):
        raise ValueError(f"item id {item_id!r} is not filename-safe")
    return item_id


def item_path(item_id, items_dir=DEFAULT_ITEMS_DIR):
    return os.path.join(items_dir, safe_id(item_id) + ".json")


def assets_dir_for(item_id, assets_dir=DEFAULT_ASSETS_DIR):
    return os.path.join(assets_dir, safe_id(item_id))


def load_items(items_dir=DEFAULT_ITEMS_DIR):
    """All items, newest-first by 'added' (the order the reader shows)."""
    items = []
    if not os.path.isdir(items_dir):
        return items
    for name in os.listdir(items_dir):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(items_dir, name), encoding="utf-8") as f:
            items.append(json.load(f))
    items.sort(key=lambda it: it.get("added") or "", reverse=True)
    return items


def write_json_atomic(path, data):
    dirn = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(dirn, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dirn, prefix=".item-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_item(item, items_dir=DEFAULT_ITEMS_DIR):
    """Write the item to its archive file. Returns (path, existed_before)."""
    path = item_path(item["id"], items_dir)
    existed = os.path.exists(path)
    write_json_atomic(path, item)
    return path, existed
