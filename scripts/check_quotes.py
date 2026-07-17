#!/usr/bin/env python3
"""Verify the overview's grounding contract: every quote is verbatim, every
timestamp points where the words are actually said.

The overview's whole promise is "grounded in exact quotes" — this makes that
machine-checked, the same way check_figures.py checks the figures. For video
items each quote (and each elided part of a quote split on "…"/"...") must
appear in the transcript, in order, and the claimed `start` must sit near the
segment where the words occur. For blog items each quote must appear in the
article text. Matching is on normalized words (case, punctuation, curly
quotes, and whitespace ignored) so human-caption punctuation vs auto-caption
bareness never causes false failures.

Prints {"ok", "quotes", "errors", "warnings"}; errors must be fixed before
add_item.
"""
import argparse, json, os, re, sys

TS_ERROR = 30      # claimed start further than this from the words → error
TS_WARN = 10       # further than this → worth a second look

_ELLIPSIS = re.compile(r"\[\s*(?:…|\.{3})\s*\]|…|\.{3}")
_WORD = re.compile(r"[a-z0-9]+")


def norm_tokens(text):
    """Normalized word list; adjacent duplicates collapse so caption stutters
    ("familiar to to designing") never fail a cleaned-up quote."""
    t = (text or "").lower()
    t = t.replace("’", "'").replace("‘", "'")
    t = t.replace("“", '"').replace("”", '"')
    words = _WORD.findall(t)
    return [w for i, w in enumerate(words) if i == 0 or w != words[i - 1]]


def strip_html(html):
    html = re.sub(r"<[^>]+>", " ", html or "")
    import html as html_mod
    return html_mod.unescape(html)


def iter_quotes(overview):
    for si, sec in enumerate(overview.get("sections") or []):
        for b in sec.get("blocks") or []:
            if isinstance(b, dict) and b.get("type") == "quote":
                yield f"sections[{si}] ({sec.get('heading', '?')})", b
    for qi, qa in enumerate(overview.get("qa") or []):
        for b in qa.get("answer") or []:
            if isinstance(b, dict) and b.get("type") == "quote":
                yield f"qa[{qi}]", b


def find_subsequence(haystack, needle, from_pos=0):
    """All start indices >= from_pos where needle (token list) occurs."""
    if not needle:
        return []
    hits = []
    n = len(needle)
    first = needle[0]
    for i in range(from_pos, len(haystack) - n + 1):
        if haystack[i] == first and haystack[i:i + n] == needle:
            hits.append(i)
    return hits


def check_quote_in_stream(tokens, starts, quote_text, claimed_start, where,
                          errors, warnings):
    """tokens: transcript word list; starts: per-token segment start (or None
    for articles). Verifies presence (in order across '…' elisions) and, when
    starts is given, the claimed timestamp."""
    parts = [p for p in (_ELLIPSIS.split(quote_text or "")) if norm_tokens(p)]
    if not parts:
        errors.append(f"{where}: empty quote")
        return
    pos = 0
    first_hits = None
    for pi, part in enumerate(parts):
        needle = norm_tokens(part)
        hits = find_subsequence(tokens, needle, pos)
        if not hits:
            snippet = (part.strip()[:70] + "…") if len(part.strip()) > 70 else part.strip()
            errors.append(
                f"{where}: quote text not found verbatim in the source: \"{snippet}\""
                + ("" if pi == 0 else " (a later part of an elided quote, searched after the previous part)"))
            return
        if pi == 0:
            first_hits = hits
        pos = hits[0] + len(needle)
    if starts is None or claimed_start is None:
        return
    # Pick the occurrence closest to the claimed time (quotes can repeat).
    actual = min((starts[h] for h in first_hits), key=lambda s: abs(s - claimed_start))
    delta = abs(actual - claimed_start)
    if delta > TS_ERROR:
        errors.append(f"{where}: start={claimed_start} but the words are said at "
                      f"~{int(actual)}s ({int(delta)}s off) — fix the timestamp")
    elif delta > TS_WARN:
        warnings.append(f"{where}: start={claimed_start} is {int(delta)}s from the "
                        f"words at ~{int(actual)}s")


def check_item(item):
    overview = item.get("overview") or {}
    quotes = list(iter_quotes(overview))
    errors, warnings = [], []

    if item.get("type") == "blog":
        text = strip_html((item.get("article") or {}).get("html"))
        tokens = norm_tokens(text)
        starts = None
    else:
        segs = (item.get("transcript") or {}).get("segments") or []
        tokens, starts = [], []
        for s in segs:
            for w in norm_tokens(s.get("text")):
                if tokens and tokens[-1] == w:
                    continue  # stutter across a segment boundary
                tokens.append(w)
                starts.append(s.get("start") or 0)

    if not tokens and quotes:
        return {"ok": False, "quotes": len(quotes),
                "errors": ["no source text (transcript/article) to verify quotes against"],
                "warnings": []}

    for where, b in quotes:
        claimed = b.get("start")
        if item.get("type") == "blog" and claimed is not None:
            errors.append(f"{where}: blog quotes must not carry 'start' (found {claimed})")
        check_quote_in_stream(tokens, starts, b.get("text"), claimed,
                              where, errors, warnings)

    return {"ok": not errors, "quotes": len(quotes),
            "errors": errors, "warnings": warnings}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", required=True, help="path to a complete item json")
    args = ap.parse_args()
    try:
        item = json.load(open(args.item, encoding="utf-8"))
    except FileNotFoundError:
        print(json.dumps({"error": "item file not found", "path": args.item}))
        sys.exit(2)
    except json.JSONDecodeError:
        print(json.dumps({"error": "item file is not valid JSON", "path": args.item}))
        sys.exit(2)
    print(json.dumps(check_item(item), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
