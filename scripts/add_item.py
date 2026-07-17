#!/usr/bin/env python3
"""Add a complete item (with overview filled in) to the archive.

The archive is one file per item: data/items/<id>.json. A same-id file that
already exists means the item was added before — we leave it untouched and
report added=false, same contract as the old monolithic archive.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from archive import DEFAULT_ITEMS_DIR, item_path, write_json_atomic

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

REQUIRED_FIELDS = ("id", "type", "title", "url", "added")


def validate_item(item):
    errors = [f"missing or empty required field '{k}'"
              for k in REQUIRED_FIELDS if not item.get(k)]
    if item.get("type") not in ("youtube", "blog"):
        errors.append(f"type must be 'youtube' or 'blog', got {item.get('type')!r}")
    if not isinstance(item.get("overview"), dict):
        errors.append("overview is missing — run merge_overview.py first")
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items-dir", default=DEFAULT_ITEMS_DIR)
    ap.add_argument("--item", required=True, help="path to a complete item json")
    ap.add_argument("--replace", action="store_true",
                    help="overwrite a same-id item (upgrading a partial item "
                         "to the full version)")
    args = ap.parse_args()

    try:
        item = json.load(open(args.item, encoding="utf-8"))
    except FileNotFoundError:
        print(json.dumps({"error": "item file not found", "path": args.item}))
        sys.exit(2)
    except json.JSONDecodeError:
        print(json.dumps({"error": "item file is not valid JSON", "path": args.item}))
        sys.exit(2)

    errors = validate_item(item)
    if errors:
        print(json.dumps({"error": "item failed validation", "details": errors}))
        sys.exit(3)

    try:
        target = item_path(item["id"], args.items_dir)
    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(3)

    existed = os.path.exists(target)
    if existed and not args.replace:
        added = False
    else:
        write_json_atomic(target, item)
        added = True

    total = len([n for n in os.listdir(args.items_dir) if n.endswith(".json")]) \
        if os.path.isdir(args.items_dir) else 0
    out = {"added": added, "id": item["id"], "total": total}
    if existed and args.replace:
        out["replaced"] = True
    print(json.dumps(out))


if __name__ == "__main__":
    main()
