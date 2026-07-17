#!/usr/bin/env python3
"""Emit the overview-writer's brief for one item: everything the (sub)agent
needs and nothing it doesn't.

Layout is deliberate: the spec and output schema come FIRST and are identical
across every brief, so parallel sub-agents in a batch share a long common
prompt prefix (prompt-cache friendly); the item-specific content follows. The
transcript is rendered compactly — one "[seconds] text" line per segment —
which is ~half the tokens of the segments JSON and gives integer timestamps
the writer can lift straight into quote `start` fields. For blog items the
article html is rendered as plain text.
"""
import argparse, html, json, os, re, sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SPEC = os.path.join(REPO_ROOT, "references", "overview-spec.md")
SCHEMA = os.path.join(REPO_ROOT, "references", "overview-schema.md")

_BLOCK_END = re.compile(r"</(?:p|div|h[1-6]|li|blockquote|pre|figcaption|tr)>", re.I)
_TAG = re.compile(r"<[^>]+>")


def compact_transcript(item):
    segs = (item.get("transcript") or {}).get("segments") or []
    return "\n".join(f"[{int(s.get('start') or 0)}] {s.get('text', '')}" for s in segs)


def article_text(item):
    raw = (item.get("article") or {}).get("html") or ""
    txt = _BLOCK_END.sub("\n\n", raw)
    txt = _TAG.sub(" ", txt)
    txt = html.unescape(txt)
    txt = re.sub(r"[ \t]+", " ", txt)
    return re.sub(r"\n{3,}", "\n\n", txt).strip()


def fmt_chapters(item):
    chs = item.get("chapters") or []
    return "\n".join(f"[{int(c['start'])}] {c['title']}" for c in chs)


def build_brief(item):
    spec = open(SPEC, encoding="utf-8").read()
    schema = open(SCHEMA, encoding="utf-8").read()
    is_blog = item.get("type") == "blog"
    parts = [
        spec.strip(),
        "\n\n---\n\n",
        schema.strip(),
        "\n\n---\n\n# The item\n\n",
        f"- title: {item.get('title')}\n",
        f"- source: {item.get('source')}\n",
        f"- kind: {'article (blog post)' if is_blog else 'video (talk)'}\n",
        f"- duration: {item.get('duration')}\n" if item.get("duration") else "",
        f"- published: {item.get('published')}\n" if item.get("published") else "",
    ]
    summary = (item.get("description") or {}).get("summary")
    if summary:
        parts.append(f"\n## Official description\n\n{summary}\n")
    chs = fmt_chapters(item)
    if chs:
        parts.append(f"\n## Chapters ([seconds] title)\n\n{chs}\n")
    if is_blog:
        parts.append(f"\n## Article text\n\n{article_text(item)}\n")
    else:
        kind = (item.get("transcript") or {}).get("kind") or "unknown"
        parts.append(f"\n## Transcript ({kind} captions; [seconds] text)\n\n"
                     f"{compact_transcript(item)}\n")
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", required=True, help="path to a fetched item json")
    ap.add_argument("--out", required=True, help="where to write the brief")
    args = ap.parse_args()
    try:
        item = json.load(open(args.item, encoding="utf-8"))
    except FileNotFoundError:
        print(json.dumps({"error": "item file not found", "path": args.item}))
        sys.exit(2)
    except json.JSONDecodeError:
        print(json.dumps({"error": "item file is not valid JSON", "path": args.item}))
        sys.exit(2)
    brief = build_brief(item)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(brief)
    print(json.dumps({"ok": True, "id": item.get("id"), "out": args.out,
                      "chars": len(brief)}))


if __name__ == "__main__":
    main()
