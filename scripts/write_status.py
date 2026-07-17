#!/usr/bin/env python3
"""Write data/status.json — the run report the site turns into its banner.

Takes the report as a JSON argument (or --file), validates the shape, and
stamps the timestamp itself, so the status schema can't drift and no one has
to remember the `date -u` incantation:

  python3 write_status.py '{"added": [{"id": "...", "title": "...", "source": "..."}],
                            "skipped": [{"input": "...", "reason": "..."}]}'

Every attempted item must appear — successes in `added`, every failure/skip in
`skipped` with an honest plain-english reason. This is how the user sees what
happened without reading the chat.
"""
import argparse, json, os, sys
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DEFAULT_STATUS = os.path.join(REPO_ROOT, "data", "status.json")


def validate(payload):
    errors = []
    if not isinstance(payload, dict):
        return ["status must be a JSON object with 'added' and 'skipped' arrays"]
    unknown = set(payload) - {"added", "skipped"}
    if unknown:
        errors.append(f"unknown keys {sorted(unknown)} — only 'added' and 'skipped' "
                      "(the timestamp is stamped automatically)")
    for k in ("added", "skipped"):
        if not isinstance(payload.get(k), list):
            errors.append(f"'{k}' must be an array (use [] when empty)")
    for i, a in enumerate(payload.get("added") or []):
        if not isinstance(a, dict) or not a.get("id") or not a.get("title"):
            errors.append(f"added[{i}]: needs 'id' and 'title' (plus 'source')")
    for i, s in enumerate(payload.get("skipped") or []):
        if not isinstance(s, dict) or not s.get("input") or not s.get("reason"):
            errors.append(f"skipped[{i}]: needs 'input' (exactly what the user pasted) "
                          "and a plain-english 'reason'")
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report", nargs="?", help="the status JSON as a string")
    ap.add_argument("--file", help="or a path to read it from")
    ap.add_argument("--out", default=DEFAULT_STATUS)
    args = ap.parse_args()

    raw = args.report
    if args.file:
        raw = open(args.file, encoding="utf-8").read()
    if not raw:
        print(json.dumps({"error": "pass the status JSON as an argument or via --file"}))
        sys.exit(2)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"not valid JSON: {e}"}))
        sys.exit(2)

    errors = validate(payload)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        sys.exit(3)

    status = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "added": payload["added"], "skipped": payload["skipped"]}
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    print(json.dumps({"ok": True, "out": args.out,
                      "added": len(status["added"]), "skipped": len(status["skipped"])}))


if __name__ == "__main__":
    main()
