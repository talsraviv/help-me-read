#!/usr/bin/env python3
"""Persistent retry queue for items that couldn't be added (yet).

Nothing the user hands the reader is ever silently lost: when an item can't
be built (no captions yet, unreadable page, truncated transcript), it goes
here and every future invocation retries it. One JSON file per queued item
under data/retry/, mirroring gmail_seen/ so concurrent machines merge
natively via git.

Records also cover *upgrades*: an item that was added from partial content
(email preview, truncated captions) can carry upgrade=true — a later
successful fetch rebuilds it in full and replaces the archived item.

Usage:
  retry_queue.py add <url> --kind video|blog --reason "..."
      [--title "..."] [--source "..."] [--thread <gmailThreadId>]
      [--upgrade --item-id <archivedItemId>]
      Queue (or re-queue) an item. Idempotent per url.

  retry_queue.py list
      Print every queued record (the skill drains this each invocation).

  retry_queue.py bump <url> --reason "..."
      Record another failed attempt (increments attempts, keeps the entry).

  retry_queue.py remove <url> [--result "..."]
      Resolve an entry (fetched successfully, or salvaged into the archive).

Give-up policy is the *skill's* job, not this script's: `list` flags entries
as stale=true once they exceed MAX_ATTEMPTS attempts or MAX_AGE_DAYS days,
and the skill then salvages them (adds the best-effort item so the content
still surfaces) instead of retrying forever. The script never deletes
anything on its own.
"""
import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RETRY_DIR = ROOT / "data" / "retry"

MAX_ATTEMPTS = 6
MAX_AGE_DAYS = 21


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _entry_path(url: str) -> Path:
    return RETRY_DIR / f"r-{hashlib.sha1(url.encode()).hexdigest()[:12]}.json"


def _load(url: str):
    path = _entry_path(url)
    if not path.exists():
        return None, path
    try:
        return json.loads(path.read_text()), path
    except json.JSONDecodeError:
        return None, path


def _write(path: Path, record: dict):
    RETRY_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")


def _is_stale(rec: dict) -> bool:
    if rec.get("attempts", 0) >= MAX_ATTEMPTS:
        return True
    try:
        first = datetime.datetime.fromisoformat(rec["firstQueued"])
        age = datetime.datetime.now(datetime.timezone.utc) - first
        return age.days >= MAX_AGE_DAYS
    except (KeyError, ValueError):
        return False


def cmd_add(args) -> dict:
    rec, path = _load(args.url)
    if rec is None:
        rec = {"url": args.url, "firstQueued": _now(), "attempts": 1}
    rec.update({
        "kind": args.kind,
        "reason": args.reason,
        "lastAttempt": _now(),
    })
    for key, val in (("title", args.title), ("source", args.source),
                     ("thread", args.thread), ("itemId", args.item_id)):
        if val:
            rec[key] = val
    if args.upgrade:
        rec["upgrade"] = True
    _write(path, rec)
    return {"ok": True, "url": args.url, "path": str(path.relative_to(ROOT)),
            "attempts": rec["attempts"]}


def cmd_list(_args) -> dict:
    entries = []
    if RETRY_DIR.is_dir():
        for f in sorted(RETRY_DIR.glob("*.json")):
            try:
                rec = json.loads(f.read_text())
            except json.JSONDecodeError:
                continue
            rec["stale"] = _is_stale(rec)
            entries.append(rec)
    return {"ok": True, "count": len(entries), "entries": entries}


def cmd_bump(args) -> dict:
    rec, path = _load(args.url)
    if rec is None:
        return {"ok": False, "error": "no queued entry for that url", "url": args.url}
    rec["attempts"] = rec.get("attempts", 0) + 1
    rec["lastAttempt"] = _now()
    rec["reason"] = args.reason
    _write(path, rec)
    return {"ok": True, "url": args.url, "attempts": rec["attempts"],
            "stale": _is_stale(rec)}


def cmd_remove(args) -> dict:
    rec, path = _load(args.url)
    if not path.exists():
        return {"ok": True, "url": args.url, "removed": False,
                "note": "no queued entry (already resolved?)"}
    path.unlink()
    return {"ok": True, "url": args.url, "removed": True,
            "result": args.result or None}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add")
    p.add_argument("url")
    p.add_argument("--kind", required=True, choices=("video", "blog"))
    p.add_argument("--reason", required=True)
    p.add_argument("--title")
    p.add_argument("--source")
    p.add_argument("--thread")
    p.add_argument("--upgrade", action="store_true")
    p.add_argument("--item-id")
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("list")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("bump")
    p.add_argument("url")
    p.add_argument("--reason", required=True)
    p.set_defaults(fn=cmd_bump)

    p = sub.add_parser("remove")
    p.add_argument("url")
    p.add_argument("--result")
    p.set_defaults(fn=cmd_remove)

    args = ap.parse_args()
    out = args.fn(args)
    print(json.dumps(out, ensure_ascii=False))
    sys.exit(0 if out.get("ok") else 1)


if __name__ == "__main__":
    main()
