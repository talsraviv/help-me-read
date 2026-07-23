#!/usr/bin/env python3
"""Validate an overview-writer's output and merge it into the item file.

The writer (main agent or sub-agent) saves its raw JSON — {"overview": ...,
"moments": [...]} — to a file and this script does the rest: schema
validation (field names, block types, blog-specific rules) and an atomic
merge into the item. The agent never has to re-emit or hand-edit the item
JSON, and schema drift fails loudly here instead of surfacing as a broken
page.

Prints {"ok": true, ...} or {"ok": false, "errors": [...]} (exit 3).
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from archive import write_json_atomic

BLOCK_TYPES = ("prose", "quote", "figure")

# The reader renders overview text verbatim (HTML-escaped, no markdown pass),
# so **bold**/*italics* markers reach the page as literal asterisks. Strip
# well-formed pairs from every prose-rendered field; quote text is never
# touched — it must stay verbatim for check_quotes.py. The lookarounds keep
# literal asterisks that aren't emphasis (e.g. "deep**3", "2*3") intact.
_BOLD = re.compile(r"(?<![\w*])\*\*(?!\s)([^*]+?)(?<!\s)\*\*(?![\w*])")
_ITALIC = re.compile(r"(?<![\w*])\*(?!\s)([^*]+?)(?<!\s)\*(?![\w*])")


def strip_emphasis(text):
    prev = None
    while text != prev:  # nested cases: **bold with *italics* inside**
        prev = text
        text = _ITALIC.sub(r"\1", _BOLD.sub(r"\1", text))
    return text


def sanitize_emphasis(ov):
    """Strip markdown emphasis from an overview's prose-rendered fields
    in place. Returns the number of fields changed."""
    changed = 0

    def fix(obj, key):
        nonlocal changed
        v = obj.get(key)
        if isinstance(v, str):
            s = strip_emphasis(v)
            if s != v:
                obj[key] = s
                changed += 1

    def fix_blocks(blocks):
        for b in blocks or []:
            if isinstance(b, dict):
                if b.get("type") == "prose":
                    fix(b, "text")
                elif b.get("type") == "figure":
                    fix(b, "caption")

    for sec in ov.get("sections") or []:
        if isinstance(sec, dict):
            fix(sec, "heading")
            fix_blocks(sec.get("blocks"))
    for qa in ov.get("qa") or []:
        if isinstance(qa, dict):
            fix(qa, "question")
            fix_blocks(qa.get("answer"))
    return changed


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_block(b, where, is_blog, errors):
    if not isinstance(b, dict):
        errors.append(f"{where}: block must be an object, got {type(b).__name__}")
        return
    t = b.get("type")
    if t not in BLOCK_TYPES:
        errors.append(f"{where}: unknown block type {t!r} (must be one of {BLOCK_TYPES})")
        return
    if t in ("prose", "quote"):
        if not (isinstance(b.get("text"), str) and b["text"].strip()):
            errors.append(f"{where}: {t} block needs non-empty 'text'")
    if t == "quote":
        if is_blog and b.get("start") is not None:
            errors.append(f"{where}: blog quotes must not carry 'start'")
        if not is_blog and not _is_num(b.get("start")):
            errors.append(f"{where}: video quote needs a numeric 'start' (seconds)")
    if t == "figure":
        if not (isinstance(b.get("svg"), str) and "<svg" in b["svg"]):
            errors.append(f"{where}: figure block needs 'svg' containing an <svg> element")
        if not (isinstance(b.get("caption"), str) and b["caption"].strip()):
            errors.append(f"{where}: figure block needs a non-empty 'caption'")


def validate(payload, is_blog):
    errors = []
    if not isinstance(payload, dict):
        return ["output must be a JSON object with 'overview' (and optional 'moments')"]
    unknown = set(payload) - {"overview", "moments"}
    if unknown:
        errors.append(f"unknown top-level keys {sorted(unknown)} — only 'overview' and 'moments'")

    ov = payload.get("overview")
    if not isinstance(ov, dict):
        return errors + ["'overview' must be an object"]
    unknown = set(ov) - {"no_figure", "sections", "qa"}
    if unknown:
        errors.append(f"unknown overview keys {sorted(unknown)} — only no_figure/sections/qa")

    sections = ov.get("sections")
    if not (isinstance(sections, list) and sections):
        errors.append("'overview.sections' must be a non-empty array")
        sections = []
    n_figures = 0
    for si, sec in enumerate(sections):
        where = f"sections[{si}]"
        if not isinstance(sec, dict):
            errors.append(f"{where}: must be an object")
            continue
        if not (isinstance(sec.get("heading"), str) and sec["heading"].strip()):
            errors.append(f"{where}: needs a non-empty 'heading'")
        blocks = sec.get("blocks")
        if not (isinstance(blocks, list) and blocks):
            errors.append(f"{where}: 'blocks' must be a non-empty array")
            continue
        for bi, b in enumerate(blocks):
            validate_block(b, f"{where}.blocks[{bi}]", is_blog, errors)
            if isinstance(b, dict) and b.get("type") == "figure":
                n_figures += 1

    for qi, qa in enumerate(ov.get("qa") or []):
        where = f"qa[{qi}]"
        if not isinstance(qa, dict):
            errors.append(f"{where}: must be an object")
            continue
        if not (isinstance(qa.get("question"), str) and qa["question"].strip()):
            errors.append(f"{where}: needs a non-empty 'question'")
        if is_blog and qa.get("start") is not None:
            errors.append(f"{where}: blog qa must not carry 'start'")
        answer = qa.get("answer")
        if not (isinstance(answer, list) and answer):
            errors.append(f"{where}: 'answer' must be a non-empty array of blocks")
            continue
        for bi, b in enumerate(answer):
            validate_block(b, f"{where}.answer[{bi}]", is_blog, errors)
            if isinstance(b, dict) and b.get("type") == "figure":
                n_figures += 1

    no_fig = ov.get("no_figure")
    if n_figures and no_fig is not None:
        errors.append("no_figure is set but figures exist — remove one or the other")
    if not n_figures:
        if not (isinstance(no_fig, dict) and isinstance(no_fig.get("reason"), str)
                and no_fig["reason"].strip()):
            errors.append("zero figures requires no_figure.reason — skipping a diagram "
                          "must be an explicit decision the reader can see")

    moments = payload.get("moments", [])
    if not isinstance(moments, list):
        errors.append("'moments' must be an array")
        moments = []
    if is_blog and moments:
        errors.append("blog items must have moments: [] (demos are a video concept)")
    for mi, m in enumerate(moments):
        where = f"moments[{mi}]"
        if not isinstance(m, dict):
            errors.append(f"{where}: must be an object")
            continue
        if not (isinstance(m.get("title"), str) and m["title"].strip()):
            errors.append(f"{where}: needs a non-empty 'title'")
        if not (_is_num(m.get("start")) and _is_num(m.get("end"))):
            errors.append(f"{where}: needs numeric 'start' and 'end'")
        if m.get("frames") not in ([], None):
            errors.append(f"{where}: 'frames' must be [] — a deterministic script fills it")
        if not isinstance(m.get("kind"), str):
            errors.append(f"{where}: needs a 'kind' (e.g. \"demo\")")

    return errors, n_figures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", required=True, help="fetched item json to merge into")
    ap.add_argument("--overview", required=True,
                    help="writer output: {\"overview\": ..., \"moments\": [...]}")
    args = ap.parse_args()

    def load(path, name):
        try:
            return json.load(open(path, encoding="utf-8"))
        except FileNotFoundError:
            print(json.dumps({"error": f"{name} file not found", "path": path}))
            sys.exit(2)
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"{name} file is not valid JSON: {e}", "path": path}))
            sys.exit(2)

    item = load(args.item, "item")
    payload = load(args.overview, "overview")
    is_blog = item.get("type") == "blog"

    result = validate(payload, is_blog)
    errors, n_figures = result if isinstance(result, tuple) else (result, 0)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        sys.exit(3)

    item["overview"] = payload["overview"]
    stripped = sanitize_emphasis(item["overview"])
    item["moments"] = payload.get("moments", [])
    for m in item["moments"]:
        m.setdefault("frames", [])
    write_json_atomic(args.item, item)

    n_quotes = sum(1 for sec in item["overview"].get("sections") or []
                   for b in sec.get("blocks") or []
                   if isinstance(b, dict) and b.get("type") == "quote")
    print(json.dumps({"ok": True, "id": item.get("id"), "figures": n_figures,
                      "quotes": n_quotes, "moments": len(item["moments"]),
                      "emphasis_stripped": stripped}))


if __name__ == "__main__":
    main()
