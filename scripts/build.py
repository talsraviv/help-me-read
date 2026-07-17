#!/usr/bin/env python3
"""Build the site from templates/reader.html + data/items/ + fonts.

Output is a light site/index.html (metadata + overviews + moments only) plus
one site/items/<id>.json per item carrying the heavy fields (transcript,
article html) that the reader fetches on demand. Demo-frame images are copied
from data/assets/ to site/assets/, fonts to site/fonts/. The page therefore
stops scaling with the archive: opening the reader downloads the index, not
every transcript ever archived.
"""
import argparse, json, os, re, shutil, sys

# Anchor all inputs/outputs to the repo via this file's location, so the build
# works from any working directory (and still from a fresh clone).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
from archive import DEFAULT_ASSETS_DIR, DEFAULT_ITEMS_DIR, load_items, safe_id

DEFAULT_TEMPLATE = os.path.join(REPO_ROOT, "templates", "reader.html")
DEFAULT_OUT = os.path.join(REPO_ROOT, "site", "index.html")
DEFAULT_STATUS = os.path.join(REPO_ROOT, "data", "status.json")

# Font resolution: a gitignored assets/fonts-local/{book,bold}.ttf pair (any
# typeface the user owns, including commercially licensed ones that can't be
# committed) wins over the bundled Gelasio (SIL OFL — see assets/fonts/OFL.txt).
_FONTS_LOCAL = os.path.join(REPO_ROOT, "assets", "fonts-local")
_LOCAL_BOOK = os.path.join(_FONTS_LOCAL, "book.ttf")
_LOCAL_BOLD = os.path.join(_FONTS_LOCAL, "bold.ttf")
_BUNDLED_BOOK = os.path.join(REPO_ROOT, "assets", "fonts", "Gelasio-Regular.ttf")
_BUNDLED_BOLD = os.path.join(REPO_ROOT, "assets", "fonts", "Gelasio-Bold.ttf")
if os.path.exists(_LOCAL_BOOK) and os.path.exists(_LOCAL_BOLD):
    DEFAULT_BOOK, DEFAULT_BOLD = _LOCAL_BOOK, _LOCAL_BOLD
else:
    DEFAULT_BOOK, DEFAULT_BOLD = _BUNDLED_BOOK, _BUNDLED_BOLD


def fonts_css(book, bold):
    """@font-face rules for the template's 'Reader Serif' family.

    Fonts ship as files next to index.html (cacheable, no base64 bloat); the
    URLs come from the actual filenames so any font pair works.
    """
    return (
        "@font-face{font-family:'Reader Serif';font-weight:400;font-display:swap;"
        f"src:url('fonts/{os.path.basename(book)}') format('truetype');}}"
        "@font-face{font-family:'Reader Serif';font-weight:700;font-display:swap;"
        f"src:url('fonts/{os.path.basename(bold)}') format('truetype');}}"
    )


# Figure SVG is model-generated markup injected unescaped into the page, so the
# build neutralizes anything active: scripts, foreignObject, event handlers,
# and external references. Internal "#id" refs are kept.
_SVG_STRIP = [
    re.compile(r"<script\b.*?</script\s*>", re.I | re.S),
    re.compile(r"<foreignObject\b.*?</foreignObject\s*>", re.I | re.S),
    re.compile(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I),
]
_SVG_EXT_REF = re.compile(
    r"\s(?:xlink:)?(?:href|src)\s*=\s*(?:([\"'])(?!#)[^\"']*\1|(?!#)[^\s\"'>]+)", re.I)


def sanitize_svg(svg):
    if not isinstance(svg, str):
        return None
    for rx in _SVG_STRIP:
        svg = rx.sub("", svg)
    svg = _SVG_EXT_REF.sub("", svg)
    return svg if re.search(r"<svg\b", svg, re.I) else None


# Blog article HTML normally arrives pre-sanitized by article_extract's
# allowlist serializer; this pass is defense in depth for items that entered
# the archive any other way. Paired removal first (tag + contents), then any
# stray open/close tags a malformed page left behind.
_ARTICLE_STRIP = [
    re.compile(r"<(script|style|iframe|object|embed|form|noscript)\b.*?</\1\s*>", re.I | re.S),
    re.compile(r"</?(?:script|style|iframe|object|embed|form|noscript|link|meta|base|input)\b[^>]*>", re.I),
    re.compile(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I),
    re.compile(r"\s(?:href|src)\s*=\s*([\"']?)\s*javascript:[^\"'>\s]*\1", re.I),
]


def sanitize_article_html(article_html):
    if not isinstance(article_html, str):
        return article_html
    for rx in _ARTICLE_STRIP:
        article_html = rx.sub("", article_html)
    return article_html


def _sanitize_blocks(blocks):
    kept = []
    for b in blocks or []:
        if isinstance(b, dict) and b.get("type") == "figure":
            svg = sanitize_svg(b.get("svg"))
            if svg is None:
                continue  # prose must stand on its own; dropping is safe
            b = {**b, "svg": svg}
        kept.append(b)
    return kept


def sanitize_items(items):
    for it in items:
        art = it.get("article")
        if isinstance(art, dict) and isinstance(art.get("html"), str):
            it["article"] = {**art, "html": sanitize_article_html(art["html"])}
        ov = it.get("overview")
        if not isinstance(ov, dict):
            continue
        for sec in ov.get("sections") or []:
            sec["blocks"] = _sanitize_blocks(sec.get("blocks"))
        for qa in ov.get("qa") or []:
            qa["answer"] = _sanitize_blocks(qa.get("answer"))
    return items


def split_item(it):
    """(light, heavy): heavy carries transcript + article html, light the rest.

    The light item gets a `lazy` flag object so the reader knows what it can
    fetch from items/<id>.json without carrying the payload itself.
    """
    light = dict(it)
    heavy = {}
    transcript = light.pop("transcript", None)
    if isinstance(transcript, dict) and transcript.get("segments"):
        heavy["transcript"] = transcript
    art = light.get("article")
    if isinstance(art, dict) and art.get("html"):
        heavy["article"] = {"html": art["html"]}
        light["article"] = {k: v for k, v in art.items() if k != "html"}
    if heavy:
        light["lazy"] = {"transcript": "transcript" in heavy,
                         "article": "article" in heavy}
    return light, heavy


def _inject_island(html, island_id, json_text):
    # Replace the contents of <script id="ID" ...>...</script>. Escape "</" so an
    # embedded string can't close the tag; a function replacement keeps the JSON's
    # backslashes literal (re.sub processes backslash escapes in a string repl).
    safe = json_text.replace("</", "<\\/")
    island = f'<script id="{island_id}" type="application/json">' + safe + "</script>"
    pattern = r'<script id="' + re.escape(island_id) + r'"[^>]*>.*?</script>'
    return re.sub(pattern, lambda _m: island, html, flags=re.S)


def inject(template, items_json, fonts_css, status_json="null"):
    html = template.replace("/*FONTS*/", fonts_css)
    html = _inject_island(html, "items-data", items_json)
    html = _inject_island(html, "run-status", status_json)
    return html


def write_site(items, template, out_path, status_json="null",
               book=DEFAULT_BOOK, bold=DEFAULT_BOLD, assets_dir=DEFAULT_ASSETS_DIR):
    out_dir = os.path.dirname(os.path.abspath(out_path))
    items_out = os.path.join(out_dir, "items")
    fonts_out = os.path.join(out_dir, "fonts")
    assets_out = os.path.join(out_dir, "assets")

    lights = []
    os.makedirs(items_out, exist_ok=True)
    for stale in os.listdir(items_out):          # drop payloads of removed items
        if stale.endswith(".json"):
            os.unlink(os.path.join(items_out, stale))
    heavy_count = 0
    for it in items:
        light, heavy = split_item(it)
        lights.append(light)
        if heavy:
            heavy["id"] = it["id"]
            with open(os.path.join(items_out, safe_id(it["id"]) + ".json"),
                      "w", encoding="utf-8") as f:
                json.dump(heavy, f, ensure_ascii=False)
            heavy_count += 1

    os.makedirs(fonts_out, exist_ok=True)
    for stale in os.listdir(fonts_out):         # drop fonts from prior builds
        os.unlink(os.path.join(fonts_out, stale))
    for src in (book, bold):
        shutil.copy2(src, os.path.join(fonts_out, os.path.basename(src)))

    if os.path.isdir(assets_out):
        shutil.rmtree(assets_out)
    if os.path.isdir(assets_dir):
        shutil.copytree(assets_dir, assets_out)

    items_json = json.dumps(lights, ensure_ascii=False)
    html = inject(template, items_json, fonts_css(book, bold), status_json)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return {"ok": True, "out": out_path, "items": len(lights),
            "heavy_files": heavy_count}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--items-dir", default=DEFAULT_ITEMS_DIR)
    ap.add_argument("--assets-dir", default=DEFAULT_ASSETS_DIR)
    ap.add_argument("--book", default=DEFAULT_BOOK)
    ap.add_argument("--bold", default=DEFAULT_BOLD)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--status", default=DEFAULT_STATUS)
    args = ap.parse_args()

    template = open(args.template, encoding="utf-8").read()
    items = sanitize_items(load_items(args.items_dir))
    # Optional, transient run status (added / skipped) shown as a banner on the
    # site. Absent or empty file → no banner.
    status_json = "null"
    if os.path.exists(args.status):
        status_json = open(args.status, encoding="utf-8").read().strip() or "null"
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    report = write_site(items, template, args.out, status_json,
                        args.book, args.bold, args.assets_dir)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
