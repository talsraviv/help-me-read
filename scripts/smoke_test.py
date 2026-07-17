#!/usr/bin/env python3
"""Gate the deploy: verify the built site is coherent before it replaces the
live one.

Deploys are autonomous, so a template or build regression would otherwise
silently ship to the fixed url. Checks are deterministic and dependency-free:

- index.html exists, both JSON islands parse, item count matches the archive
- every light item's `lazy` flags have a matching site/items/<id>.json payload
  carrying exactly the flagged fields
- every demo-frame src referenced by a moment exists under site/
- font files referenced by the CSS exist; no /*FONTS*/ marker survived
- the inline app script passes `node --check` (catches JS syntax regressions)
- best-effort: if a Chrome/Chromium binary is present, render index.html
  headlessly and assert the sidebar actually shows one row per item (catches
  runtime JS breakage, not just syntax)

Prints {"ok": ..., "checks": [...], "errors": [...]}; exit 1 on any error.
"""
import json, os, re, subprocess, sys, tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
from archive import DEFAULT_ITEMS_DIR

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
)


def island(html, island_id):
    m = re.search(r'<script id="' + island_id + r'"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    return json.loads(m.group(1).replace("<\\/", "</"))


def run(site_dir, items_dir=DEFAULT_ITEMS_DIR):
    errors, checks = [], []
    index = os.path.join(site_dir, "index.html")
    if not os.path.exists(index):
        return {"ok": False, "errors": [f"{index} does not exist — build first"], "checks": []}
    html = open(index, encoding="utf-8").read()

    if "/*FONTS*/" in html:
        errors.append("the /*FONTS*/ marker was never replaced — fonts CSS missing")

    try:
        items = island(html, "items-data")
        assert isinstance(items, list)
        checks.append(f"items island parses ({len(items)} items)")
    except Exception as e:
        return {"ok": False, "errors": [f"items-data island unusable: {e}"], "checks": checks}
    try:
        island(html, "run-status")
        checks.append("run-status island parses")
    except Exception as e:
        errors.append(f"run-status island unusable: {e}")

    n_archive = len([n for n in os.listdir(items_dir) if n.endswith(".json")]) \
        if os.path.isdir(items_dir) else 0
    if len(items) != n_archive:
        errors.append(f"index has {len(items)} items but the archive has {n_archive}")

    for it in items:
        iid = it.get("id", "?")
        lazy = it.get("lazy") or {}
        payload_path = os.path.join(site_dir, "items", f"{iid}.json")
        if lazy.get("transcript") or lazy.get("article"):
            if not os.path.exists(payload_path):
                errors.append(f"{iid}: lazy flags set but {payload_path} is missing")
                continue
            try:
                payload = json.load(open(payload_path, encoding="utf-8"))
            except json.JSONDecodeError:
                errors.append(f"{iid}: heavy payload is not valid JSON")
                continue
            if lazy.get("transcript") and not (payload.get("transcript") or {}).get("segments"):
                errors.append(f"{iid}: lazy.transcript set but payload has no segments")
            if lazy.get("article") and not (payload.get("article") or {}).get("html"):
                errors.append(f"{iid}: lazy.article set but payload has no article html")
        if "transcript" in it:
            errors.append(f"{iid}: light item still carries a transcript — split failed")
        for m in it.get("moments") or []:
            for fr in m.get("frames") or []:
                src = fr.get("src") or ""
                if src.startswith("data:"):
                    errors.append(f"{iid}: frame still embedded as base64 — should be a file")
                elif not os.path.exists(os.path.join(site_dir, src)):
                    errors.append(f"{iid}: frame {src} missing under {site_dir}")
    checks.append("lazy payloads and frame assets verified")

    for font in re.findall(r"url\('(fonts/[^']+)'\)", html):
        if not os.path.exists(os.path.join(site_dir, font)):
            errors.append(f"font file {font} missing under {site_dir}")
    checks.append("fonts verified")

    # node --check on the inline app script (the last plain <script> block).
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    if scripts:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(scripts[-1])
            js_path = f.name
        try:
            p = subprocess.run(["node", "--check", js_path], capture_output=True, text=True)
            if p.returncode != 0:
                errors.append(f"inline script fails node --check: {p.stderr.strip()[:300]}")
            else:
                checks.append("inline script passes node --check")
        except FileNotFoundError:
            checks.append("node not found — syntax check skipped")
        finally:
            os.unlink(js_path)
    else:
        errors.append("no inline <script> found in index.html")

    chrome = next((c for c in CHROME_CANDIDATES if os.path.exists(c)), None)
    if chrome and items:
        try:
            p = subprocess.run(
                [chrome, "--headless=new", "--disable-gpu", "--no-first-run",
                 "--no-sandbox", "--virtual-time-budget=4000", "--timeout=15000",
                 "--dump-dom", "file://" + os.path.abspath(index)],
                capture_output=True, text=True, timeout=40)
            # Strip script bodies first: the app script's own template-literal
            # source contains the row markup and would inflate the count.
            dom = re.sub(r"<script\b.*?</script>", "", p.stdout, flags=re.S)
            rows = len(re.findall(r'class="row"', dom))
            if rows != len(items):
                errors.append(f"headless render shows {rows} sidebar rows, expected "
                              f"{len(items)} — the app script is likely failing at runtime")
            else:
                checks.append(f"headless render OK ({rows} rows)")
        except (subprocess.TimeoutExpired, OSError) as e:
            checks.append(f"headless render skipped ({e.__class__.__name__})")
    elif not chrome:
        checks.append("no Chrome/Chromium found — headless render skipped")

    return {"ok": not errors, "errors": errors, "checks": checks}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-dir", default=os.path.join(REPO_ROOT, "site"))
    ap.add_argument("--items-dir", default=DEFAULT_ITEMS_DIR)
    args = ap.parse_args()
    report = run(args.site_dir, args.items_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
