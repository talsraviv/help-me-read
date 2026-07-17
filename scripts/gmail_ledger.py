#!/usr/bin/env python3
"""Track which Gmail threads (the user's configured reading label) this reader has scanned.

One JSON file per thread under data/gmail_seen/, mirroring the per-item
archive design so concurrent runs on different machines merge natively.

Usage:
  gmail_ledger.py check <threadId> [<threadId> ...]
      Splits the given ids into new vs already-seen.
      Prints {"ok": true, "new": ["..."], "seen": [{"threadId","subject","result"}]}

  gmail_ledger.py mark <threadId> --subject "..." [--result "..."]
      Records a scanned thread (whatever the outcome). Idempotent: marking an
      already-seen thread overwrites its record.
      Prints {"ok": true, "threadId": "...", "path": "..."}
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEEN_DIR = ROOT / "data" / "gmail_seen"


def safe_id(thread_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", thread_id)
    if not cleaned:
        raise ValueError(f"unusable thread id: {thread_id!r}")
    return cleaned


def cmd_check(args) -> dict:
    new, seen = [], []
    for tid in args.thread_ids:
        path = SEEN_DIR / f"{safe_id(tid)}.json"
        if path.exists():
            try:
                rec = json.loads(path.read_text())
            except json.JSONDecodeError:
                rec = {"threadId": tid}
            seen.append({k: rec.get(k) for k in ("threadId", "subject", "result")})
        else:
            new.append(tid)
    return {"ok": True, "new": new, "seen": seen}


def cmd_mark(args) -> dict:
    SEEN_DIR.mkdir(parents=True, exist_ok=True)
    path = SEEN_DIR / f"{safe_id(args.thread_id)}.json"
    record = {
        "threadId": args.thread_id,
        "subject": args.subject,
        "result": args.result,
        "markedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return {"ok": True, "threadId": args.thread_id, "path": str(path.relative_to(ROOT))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="split thread ids into new vs seen")
    p_check.add_argument("thread_ids", nargs="+")
    p_check.set_defaults(func=cmd_check)

    p_mark = sub.add_parser("mark", help="record a scanned thread")
    p_mark.add_argument("thread_id")
    p_mark.add_argument("--subject", default="")
    p_mark.add_argument("--result", default="", help="item ids added, or why skipped/failed")
    p_mark.set_defaults(func=cmd_mark)

    args = parser.parse_args()
    try:
        print(json.dumps(args.func(args), ensure_ascii=False))
    except Exception as e:  # keep the autonomous run moving; caller sees the reason
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
