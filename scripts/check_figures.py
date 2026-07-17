#!/usr/bin/env python3
"""Lint an item's overview figures against the reader's mechanical constraints.

Catches, deterministically, everything the figure spec demands that a machine
can verify: well-formed SVG, a viewBox that fits the reader's 420px height cap,
theme-palette colors only, readable font sizes, no font-family, nothing the
build would strip (scripts, foreignObject, raster images, external refs), and
the no_figure contract. Prints one JSON report; "errors" must be fixed before
add_item, "warnings" are judgment calls worth a second look.

--fix applies the purely mechanical repairs in place before checking: off-
palette hex colors snap to the nearest theme color, font sizes below the
minimum clamp up to it. Anything needing judgment (viewBox redesign, captions,
no_figure contradictions) is still reported for the model to fix.
"""
import argparse, json, os, re, sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from archive import write_json_atomic

MAX_HEIGHT = 420          # reader.html caps .fig svg at max-height:420px
CANON_WIDTH = 720         # the coordinate space all craft guidance assumes
MIN_FONT = 16             # readable when the 720-wide viewBox is phone-scaled
PALETTE = {
    "#f4f4f3", "#333333", "#333", "#cf5a3c", "#c3bdb1",
    "none", "transparent", "currentcolor",
}
STRIPPED = ("script", "foreignObject", "image", "use")
CHAR_W = 0.55             # rough average glyph width in em for the page serif


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _iter_figures(overview):
    for si, sec in enumerate(overview.get("sections") or []):
        for b in sec.get("blocks") or []:
            if isinstance(b, dict) and b.get("type") == "figure":
                yield f"sections[{si}] ({sec.get('heading', '?')})", b
    for qi, qa in enumerate(overview.get("qa") or []):
        for b in qa.get("answer") or []:
            if isinstance(b, dict) and b.get("type") == "figure":
                yield f"qa[{qi}]", b


def _colors_in(el):
    for attr in ("fill", "stroke"):
        v = el.get(attr)
        if v:
            yield v
    style = el.get("style") or ""
    for m in re.finditer(r"(?:fill|stroke)\s*:\s*([^;]+)", style):
        yield m.group(1).strip()


def _font_size(el):
    v = el.get("font-size")
    if not v:
        m = re.search(r"font-size\s*:\s*([^;]+)", el.get("style") or "")
        v = m.group(1).strip() if m else None
    if not v:
        return None
    m = re.match(r"([\d.]+)", v)
    return float(m.group(1)) if m else None


def check_svg(svg, where):
    errors, warnings = [], []
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as e:
        return [f"{where}: svg is not well-formed XML ({e})"], []

    vb = root.get("viewBox")
    vb_w = vb_h = None
    if not vb:
        errors.append(f"{where}: missing viewBox")
    else:
        try:
            _, _, vb_w, vb_h = (float(p) for p in re.split(r"[\s,]+", vb.strip()))
        except ValueError:
            errors.append(f"{where}: unparseable viewBox '{vb}'")
        else:
            if vb_h > MAX_HEIGHT:
                errors.append(
                    f"{where}: viewBox height {vb_h:g} > {MAX_HEIGHT} — the reader "
                    f"caps figures at {MAX_HEIGHT}px tall, so everything (including "
                    "text) scales down; redesign wider, not taller")
            if vb_w != CANON_WIDTH:
                warnings.append(
                    f"{where}: viewBox width {vb_w:g} != {CANON_WIDTH} — font-size "
                    "guidance assumes a 720-wide coordinate space")
    for attr in ("width", "height"):
        if root.get(attr):
            errors.append(f"{where}: fixed {attr} attribute on <svg> — use viewBox only")

    n_text = 0
    for el in root.iter():
        tag = _local(el.tag)
        if tag in STRIPPED:
            errors.append(f"{where}: <{tag}> is stripped by the build — remove it")
        if el.get("font-family") or "font-family" in (el.get("style") or ""):
            errors.append(f"{where}: font-family set on <{tag}> — the page font is inherited")
        for href in (el.get("href"), el.get("{http://www.w3.org/1999/xlink}href")):
            if href and not href.startswith("#"):
                errors.append(f"{where}: external reference '{href[:40]}' is stripped by the build")
        for c in _colors_in(el):
            if c.lower() not in PALETTE:
                errors.append(f"{where}: color '{c}' is not in the theme palette")
        if tag == "text":
            n_text += 1
            fs = _font_size(el)
            if fs is not None and fs < MIN_FONT:
                errors.append(
                    f"{where}: font-size {fs:g} < {MIN_FONT} — unreadable on a phone")
            # Flag text that likely runs past the canvas edge (skip rotated text).
            txt = "".join(el.itertext()).strip()
            if txt and vb_w and not el.get("transform"):
                try:
                    x = float(el.get("x", "0"))
                except ValueError:
                    continue
                est = len(txt) * CHAR_W * (fs or MIN_FONT)
                anchor = el.get("text-anchor", "start")
                lo, hi = {
                    "start": (x, x + est),
                    "middle": (x - est / 2, x + est / 2),
                    "end": (x - est, x),
                }.get(anchor, (x, x + est))
                if lo < -8 or hi > vb_w + 8:
                    warnings.append(
                        f"{where}: text '{txt[:32]}…' (~{est:.0f}px wide, anchor="
                        f"{anchor}, x={x:g}) likely overflows the {vb_w:g}-wide canvas")
    if n_text > 14:
        warnings.append(
            f"{where}: {n_text} <text> elements — likely over the ~12-label budget; "
            "move explanation into the caption or prose")
    return errors, warnings


# --- mechanical fixes (--fix) -------------------------------------------------

_SNAP_TARGETS = ("#f4f4f3", "#333333", "#cf5a3c", "#c3bdb1")
_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_ATTR_COLOR = re.compile(r'\b(fill|stroke)\s*=\s*(["\'])(.*?)\2', re.I)
_STYLE_COLOR = re.compile(r'\b(fill|stroke)\s*:\s*([^;"\'>]+)', re.I)
_ATTR_FONT = re.compile(r'\bfont-size\s*=\s*(["\'])([\d.]+)(?:px)?\1', re.I)
_STYLE_FONT = re.compile(r'\bfont-size\s*:\s*([\d.]+)(?:px)?', re.I)


def _to_rgb(hexstr):
    h = hexstr.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def snap_color(value):
    """Nearest palette color for an off-palette hex; None if not fixable."""
    v = value.strip()
    if v.lower() in PALETTE or not _HEX.match(v):
        return None
    r, g, b = _to_rgb(v)
    return min(_SNAP_TARGETS,
               key=lambda p: sum((a - b_) ** 2 for a, b_ in zip((r, g, b), _to_rgb(p))))


def fix_svg(svg):
    """Snap colors and clamp font sizes in place. Returns (svg, [descriptions])."""
    fixes = []

    def color_attr(m):
        snapped = snap_color(m.group(3))
        if snapped is None:
            return m.group(0)
        fixes.append(f"{m.group(1)} {m.group(3)} -> {snapped}")
        return f"{m.group(1)}={m.group(2)}{snapped}{m.group(2)}"

    def color_style(m):
        snapped = snap_color(m.group(2))
        if snapped is None:
            return m.group(0)
        fixes.append(f"{m.group(1)} {m.group(2).strip()} -> {snapped}")
        return f"{m.group(1)}:{snapped}"

    def font_attr(m):
        if float(m.group(2)) >= MIN_FONT:
            return m.group(0)
        fixes.append(f"font-size {m.group(2)} -> {MIN_FONT}")
        return f'font-size={m.group(1)}{MIN_FONT}{m.group(1)}'

    def font_style(m):
        if float(m.group(1)) >= MIN_FONT:
            return m.group(0)
        fixes.append(f"font-size {m.group(1)} -> {MIN_FONT}")
        return f"font-size:{MIN_FONT}"

    svg = _ATTR_COLOR.sub(color_attr, svg)
    svg = _STYLE_COLOR.sub(color_style, svg)
    svg = _ATTR_FONT.sub(font_attr, svg)
    svg = _STYLE_FONT.sub(font_style, svg)
    return svg, fixes


def fix_item(item):
    """Apply mechanical fixes to every figure. Returns descriptions of fixes."""
    all_fixes = []
    for where, block in _iter_figures(item.get("overview") or {}):
        svg = block.get("svg")
        if not isinstance(svg, str):
            continue
        fixed, fixes = fix_svg(svg)
        if fixes:
            block["svg"] = fixed
            all_fixes += [f"{where}: {f}" for f in fixes]
    return all_fixes


def check_item(item):
    errors, warnings = [], []
    overview = item.get("overview") or {}
    figures = list(_iter_figures(overview))
    no_fig = overview.get("no_figure")
    if figures and no_fig:
        errors.append("no_figure is set but figures exist — remove one or the other")
    if not figures and not (isinstance(no_fig, dict) and no_fig.get("reason")):
        errors.append("no figures and no no_figure.reason — skipping a diagram must be "
                      "an explicit decision the reader can see")
    for where, block in figures:
        e, w = check_svg(block.get("svg") or "", where)
        errors += e
        warnings += w
        if not (block.get("caption") or "").strip():
            errors.append(f"{where}: figure has no caption")
    return {"ok": not errors, "figures": len(figures), "errors": errors, "warnings": warnings}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", required=True, help="path to a complete item json")
    ap.add_argument("--fix", action="store_true",
                    help="apply mechanical fixes (palette snap, font-size clamp) first")
    args = ap.parse_args()
    try:
        item = json.load(open(args.item, encoding="utf-8"))
    except FileNotFoundError:
        print(json.dumps({"error": "item file not found", "path": args.item}))
        sys.exit(2)
    except json.JSONDecodeError:
        print(json.dumps({"error": "item file is not valid JSON", "path": args.item}))
        sys.exit(2)
    fixes = []
    if args.fix:
        fixes = fix_item(item)
        if fixes:
            write_json_atomic(args.item, item)
    report = check_item(item)
    if args.fix:
        report["fixed"] = fixes
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
