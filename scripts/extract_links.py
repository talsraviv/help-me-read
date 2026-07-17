#!/usr/bin/env python3
"""Distill a saved Gmail get_thread result into candidate content links.

Newsletter emails are 90-140KB of HTML; the model only needs a short list of
plausible content urls plus the body's opening lines to judge what the email
points to. This does the mechanical part deterministically: parse the saved
thread JSON, collect urls from the plaintext body (anchor hrefs as fallback),
drop boilerplate (unsubscribe, social profiles, app badges, tracking pixels,
image CDNs), dedupe, and print compact JSON.

Usage:
  extract_links.py <path-to-saved-get_thread-json> [--max-links 40]

Prints {"ok": true, "subject", "sender", "body_head", "links": ["url", ...]}.
Judgment (which link IS the content) stays with the caller.
"""
import argparse
import json
import re
import sys

# unambiguous junk — dropped entirely (never content, in any email)
JUNK = re.compile(
    r"unsubscribe|email-settings|manage.*subscriptions|disable_email"
    r"|/legal|/privacy|/terms|/feedback/|#/portal/"
    r"|apps\.apple\.com|play\.google\.com"
    r"|substackcdn|substack\.com/(app|subscribe|profile|home|notes)"
    r"|li\.blogtrottr\.com|blogtrottr\.com|ghost\.org"
    r"|\.(png|jpe?g|gif|webp|svg|ico)(\?|$)",
    re.I,
)

# usually sidebar/footer noise, occasionally the actual content — demoted to
# a separate bucket, never deleted, so the judgment call stays with the model
DEMOTED = re.compile(
    r"facebook\.com|linkedin\.com|tiktok\.com"
    r"|twitter\.com|x\.com/[^/]+/?$|instagram\.com"
    r"|open\.spotify\.com|podcasts\.apple\.com|wikipedia\.org",
    re.I,
)
URL = re.compile(r"https?://[^\s\]\)>\"'<]+")

# tracking wrappers whose path is an opaque token — the content is *behind*
# them, so they rank below any link that names its destination
WRAPPED = re.compile(r"substack\.com/redirect/|/r/[0-9a-f]{6,}(\?|$)", re.I)


def dedupe_key(url: str) -> str:
    # utm/source noise and substack redirect ids make identical targets look
    # distinct; strip query for keying only (the printed url stays intact)
    return url.split("?")[0].rstrip("/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="saved get_thread JSON (harness overflow file or raw result)")
    ap.add_argument("--max-links", type=int, default=40)
    args = ap.parse_args()

    data = json.load(open(args.file, encoding="utf-8"))
    messages = data.get("messages") or [data]
    msg = messages[0]
    import html as html_mod
    body = msg.get("plaintextBody") or ""
    html_text = html_mod.unescape(re.sub(r"<[^>]+>", " ", msg.get("htmlBody") or ""))
    if not body:
        body = html_text
    # hunt urls in every surface: hidden preheaders exist only in the html,
    # and gmail's snippet is often the cleanest copy of the lead link
    haystack = "\n".join([body, html_text, msg.get("snippet") or ""])
    # repair quoted-printable mangling: an original "=XX" hex pair decoded
    # into C0 control byte XX (e.g. "watch?v=1e6…" arriving as "watch?v\x1e6…")
    haystack = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]",
                      lambda m: "=%02x" % ord(m.group()), haystack)

    seen, named, other, wrapped = set(), [], [], []
    for u in URL.findall(haystack):
        u = u.rstrip(".,;")
        key = dedupe_key(u)
        if key in seen or JUNK.search(u):
            continue
        seen.add(key)
        bucket = wrapped if WRAPPED.search(u) else other if DEMOTED.search(u) else named
        bucket.append(u)

    print(json.dumps({
        "ok": True,
        "subject": msg.get("subject"),
        "sender": msg.get("sender"),
        "body_head": re.sub(r"\s+", " ", body[:600]).strip(),
        "body_words": len(re.findall(r"\w+", body)),
        "links": named[:args.max_links],
        "other_links": other[:8],
        "wrapped_links": wrapped[:8],
        "omitted": {"other": max(0, len(other) - 8),
                    "wrapped": max(0, len(wrapped) - 8)},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)
