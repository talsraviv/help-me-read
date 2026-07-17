#!/usr/bin/env python3
"""One-time migration: data/items.json -> data/items/<id>.json + data/assets/.

- Splits the monolithic archive into one file per item (newest-first order is
  reconstructed from 'added' at load time, so no order is stored).
- Extracts base64 demo-frame data URIs into real JPEG files under
  data/assets/<id>/, leaving relative paths ("assets/<id>/<name>.jpg") in the
  item JSON — the same paths the built site serves them at.
- Drops null 'speaker' keys from transcript segments (pure dead weight).

Idempotent: re-running overwrites the same per-item files. The old
data/items.json is left in place for the caller to `git rm`.
"""
import argparse
import base64
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from archive import (DEFAULT_ASSETS_DIR, DEFAULT_ITEMS_DIR, REPO_ROOT,
                     assets_dir_for, save_item)

LEGACY_DATA = os.path.join(REPO_ROOT, "data", "items.json")
_DATA_URI = re.compile(r"^data:image/(jpeg|png|webp);base64,(.+)$", re.S)


def strip_null_speakers(item):
    segs = (item.get("transcript") or {}).get("segments") or []
    n = 0
    for s in segs:
        if "speaker" in s and not s["speaker"]:
            del s["speaker"]
            n += 1
    return n


def externalize_frames(item, assets_dir):
    """Decode data-URI frames to files; rewrite src to a relative asset path."""
    n = 0
    for mi, m in enumerate(item.get("moments") or []):
        for fi, fr in enumerate(m.get("frames") or []):
            mm = _DATA_URI.match(fr.get("src") or "")
            if not mm:
                continue
            ext = {"jpeg": "jpg"}.get(mm.group(1), mm.group(1))
            adir = assets_dir_for(item["id"], assets_dir)
            os.makedirs(adir, exist_ok=True)
            name = f"m{mi}-f{fi}.{ext}"
            with open(os.path.join(adir, name), "wb") as f:
                f.write(base64.b64decode(mm.group(2)))
            fr["src"] = f"assets/{item['id']}/{name}"
            n += 1
    return n


def migrate(legacy_path=LEGACY_DATA, items_dir=DEFAULT_ITEMS_DIR,
            assets_dir=DEFAULT_ASSETS_DIR):
    items = json.load(open(legacy_path, encoding="utf-8"))
    report = {"ok": True, "items": len(items), "frames_externalized": 0,
              "null_speakers_dropped": 0, "items_dir": items_dir}
    for item in items:
        report["null_speakers_dropped"] += strip_null_speakers(item)
        report["frames_externalized"] += externalize_frames(item, assets_dir)
        save_item(item, items_dir)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy", default=LEGACY_DATA)
    ap.add_argument("--items-dir", default=DEFAULT_ITEMS_DIR)
    ap.add_argument("--assets-dir", default=DEFAULT_ASSETS_DIR)
    args = ap.parse_args()
    if not os.path.exists(args.legacy):
        print(json.dumps({"error": "legacy archive not found", "path": args.legacy}))
        sys.exit(2)
    print(json.dumps(migrate(args.legacy, args.items_dir, args.assets_dir)))


if __name__ == "__main__":
    main()
