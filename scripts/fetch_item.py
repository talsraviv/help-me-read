#!/usr/bin/env python3
"""Resolve a YouTube URL/title/subject — or a blog post URL — into a structured
item minus the AI overview. Prints the item as JSON.

Usage:
  python3 fetch_item.py "<url-or-name-or-subject>" [--duration "31:27"] [--out item.json]
  python3 fetch_item.py "<canonical-url>" --html-file saved-thread.json [--title "..."] [--out item.json]

--html-file builds the blog item from a saved email body (a get_thread JSON
or a raw HTML file) instead of fetching the url — for paid-newsletter posts
whose web version is a paywall stub. The item keeps the canonical url as its
id and link; only the article text comes from the email.
"""
import argparse, glob, hashlib, html, json, os, re, shutil, subprocess, sys, tempfile, time
import urllib.error
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from article_extract import blog_id, extract, fetch_html, read_time_label

YT_HOSTS = ("youtube.com", "youtu.be")


def is_url(s):
    return s.strip().lower().startswith(("http://", "https://"))


def is_youtube(s):
    return any(h in s for h in YT_HOSTS)


def extract_video_id(url):
    m = re.search(r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def parse_ts(ts):
    ts = ts.strip().replace(",", ".")
    m = re.match(r"(\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)", ts)
    if m:
        h, mi, s = m.groups()
        return int(h) * 3600 + int(mi) * 60 + float(s)
    m = re.match(r"(\d{1,2}):(\d{2}(?:\.\d+)?)", ts)
    if m:
        mi, s = m.groups()
        return int(mi) * 60 + float(s)
    return None


def hms_to_seconds(s):
    parts = s.strip().split(":")
    try:
        parts = [int(p) for p in parts]
    except ValueError:
        return None
    sec = 0
    for p in parts:
        sec = sec * 60 + p
    return sec


def seconds_to_hms(sec):
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def clean_vtt_to_segments(vtt_text):
    """Return [{start, text, speaker}] with timestamps preserved.

    Human captions: one segment per cue. Auto captions carry <c> word tags and
    repeat each settled line as scroll context in the next cue, so we keep only
    the tagged 'live' lines and dedupe against the previous emitted text.
    """
    is_auto = "<c>" in vtt_text
    segments = []
    prev_text = None
    cur_start = None
    cur_texts = []

    def flush():
        nonlocal cur_texts, cur_start, prev_text
        if cur_start is None or not cur_texts:
            cur_texts = []
            return
        text = re.sub(r"\s+", " ", " ".join(cur_texts)).strip()
        if text and text != prev_text:
            seg = {"start": round(cur_start, 2), "text": text}
            if text.startswith(">>"):        # a null speaker is dead weight; omit
                seg["speaker"] = ">>"
            segments.append(seg)
            prev_text = text
        cur_texts = []

    for ln in vtt_text.splitlines():
        if ln.startswith(("WEBVTT", "Kind:", "Language:")):
            continue
        if "-->" in ln:
            flush()
            cur_start = parse_ts(ln.split("-->")[0])
            continue
        if ln.strip() == "" or re.match(r"^\d+$", ln.strip()):
            continue
        if is_auto and "<c>" not in ln:
            continue
        u = html.unescape(ln)
        if "-->" in u:
            continue
        if re.match(r"^\d{1,2}:\d{2}:\d{2}[.,]\d{3}\s*$", u.strip()):
            continue
        t = re.sub(r"<[^>]+>", "", u).strip()
        if t:
            cur_texts.append(t)
    flush()
    return segments


def clean_description(desc):
    full = (desc or "").strip()
    kept = []
    for ln in full.splitlines():
        s = ln.strip()
        if not s:
            if kept and kept[-1] != "":
                kept.append("")
            continue
        if re.match(r"^\(?\d{1,2}:\d{2}", s):        # chapter timestamp line
            continue
        low = s.lower()
        if s.startswith(("http://", "https://")) or "http" in low:
            continue
        if any(k in low for k in ("subscribe", "follow us", "twitter", "linkedin", "instagram")):
            continue
        kept.append(s)
    summary_lines = []
    for s in kept:
        if s == "" and summary_lines:
            break
        if s:
            summary_lines.append(s)
    return {"summary": " ".join(summary_lines).strip(), "full": full}


def parse_chapters(info):
    out = []
    for c in info.get("chapters") or []:
        start, title = c.get("start_time"), c.get("title")
        if start is not None and title:
            out.append({"start": round(float(start), 2), "title": title})
    return out


def best_thumbnail(info):
    thumbs = info.get("thumbnails") or []
    if not thumbs:
        return info.get("thumbnail")
    best = max(thumbs, key=lambda t: t.get("width") or 0)
    return best.get("url")


def format_upload_date(yyyymmdd):
    if not yyyymmdd or len(str(yyyymmdd)) != 8:
        return None
    s = str(yyyymmdd)
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def build_item(info, segments, caption_kind, added_iso):
    vid = info.get("id")
    dur = info.get("duration_string")
    if not dur and info.get("duration"):
        dur = seconds_to_hms(info["duration"])
    return {
        "id": vid,
        "type": "youtube",
        "title": info.get("title"),
        "source": info.get("channel") or info.get("uploader"),
        "url": info.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}",
        "thumbnail": best_thumbnail(info),
        "duration": dur,
        "published": format_upload_date(info.get("upload_date")),
        "added": added_iso,
        "description": clean_description(info.get("description")),
        "chapters": parse_chapters(info),
        "transcript": {"kind": caption_kind, "segments": segments},
        "overview": None,
    }


# A page with less readable text than this is a failed extraction (a paywall
# stub, a JS-only shell, a link roundup) — better to report it than archive it.
MIN_ARTICLE_WORDS = 120


def build_blog_item(extracted, url, added_iso):
    words = extracted.get("word_count") or 0
    desc = (extracted.get("description") or "").strip()
    return {
        "id": blog_id(url),
        "type": "blog",
        "title": extracted.get("title"),
        "source": extracted.get("source"),
        "url": url,
        "thumbnail": extracted.get("image"),
        "duration": read_time_label(words),
        "published": extracted.get("published"),
        "added": added_iso,
        "description": {"summary": desc, "full": desc},
        "chapters": [],
        "article": {"html": extracted["html"], "word_count": words},
        "overview": None,
    }


# Transient-failure retry policy shared by network steps: 429s and 5xx-ish
# hiccups get two spaced retries inside the script, so the caller never has to
# babysit rate limits.
RETRY_DELAYS = (5, 15)
_TRANSIENT = re.compile(r"429|too many requests|rate.?limit|timed? ?out|"
                        r"temporar|50[234]", re.I)


def _is_transient(err_text):
    return bool(_TRANSIENT.search(err_text or ""))


def with_retries(fn, describe):
    """Run fn(); on a transient error, sleep and retry per RETRY_DELAYS."""
    for attempt, delay in enumerate(RETRY_DELAYS + (None,)):
        try:
            return fn()
        except Exception as e:                          # noqa: BLE001 — re-raised below
            if delay is None or not _is_transient(str(e)):
                raise
            print(json.dumps({"retrying": describe, "after_error": str(e)[:200],
                              "sleep": delay}), file=sys.stderr)
            time.sleep(delay)


def fetch_blog(url):
    try:
        html_text, final_url = with_retries(lambda: fetch_html(url), f"fetch {url}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(json.dumps({"error": f"could not fetch page: {e}", "url": url}))
        sys.exit(4)
    return blog_from_html(html_text, final_url, url)


def load_email_html(path):
    """HTML body from a saved get_thread JSON, or the file verbatim if raw HTML."""
    raw = open(path, encoding="utf-8").read()
    try:
        data = json.loads(raw)
    except ValueError:
        return raw
    messages = data.get("messages") or [data]
    html_text = max((m.get("htmlBody") or "" for m in messages), key=len)
    if not html_text:
        print(json.dumps({"error": "no htmlBody in saved thread file", "file": path}))
        sys.exit(4)
    return html_text


def blog_from_html(html_text, extract_url, canonical_url, title=None):
    extracted = extract(html_text, extract_url)
    if title:
        extracted["title"] = title
    if extracted["word_count"] < MIN_ARTICLE_WORDS:
        print(json.dumps({"error": "could not extract readable article text "
                          f"(only {extracted['word_count']} words found)",
                          "url": canonical_url, "title": extracted.get("title")}))
        sys.exit(5)
    if not extracted.get("title"):
        print(json.dumps({"error": "no title found — pass --title",
                          "url": canonical_url}))
        sys.exit(5)
    added = datetime.now(timezone.utc).isoformat()
    return build_blog_item(extracted, canonical_url, added)


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def resolve_query(query, duration_hint=None):
    """Return a YouTube watch url for a url/title/subject. Uses search for names."""
    if is_youtube(query):
        return query.strip()
    hint_sec = hms_to_seconds(duration_hint) if duration_hint else None
    cmd = ["yt-dlp", "--no-update", "--skip-download", "--flat-playlist",
           "--print", "%(id)s\t%(duration)s", f"ytsearch8:{query}"]
    res = _run(cmd)
    cands = []
    for line in res.stdout.strip().splitlines():
        parts = line.split("\t")
        if not parts or not parts[0]:
            continue
        vid = parts[0]
        try:
            dsec = int(float(parts[1]))
        except (IndexError, ValueError):
            dsec = None
        cands.append((vid, dsec))
    if not cands:
        return None
    if hint_sec is not None:
        scored = [c for c in cands if c[1] is not None]
        if scored:
            best = min(scored, key=lambda c: abs(c[1] - hint_sec))
            return f"https://www.youtube.com/watch?v={best[0]}"
    return f"https://www.youtube.com/watch?v={cands[0][0]}"


def download_info_and_captions(url, workdir):
    base = os.path.join(workdir, "yt")
    cmd = ["yt-dlp", "--no-update", "--skip-download",
           "--write-auto-subs", "--write-subs", "--write-info-json",
           "--sub-langs", "en.*,en", "--sub-format", "vtt",
           "--extractor-args", "youtube:player_client=android,web,tv",
           "-o", base, url]

    def attempt():
        res = _run(cmd)
        got_output = glob.glob(base + "*")
        if not got_output and _is_transient(res.stderr):
            raise RuntimeError((res.stderr or "").strip()[-300:])
        return res

    try:
        with_retries(attempt, f"yt-dlp {url}")
    except RuntimeError:
        pass  # fall through — the no-captions/no-info paths below report it
    info = {}
    ij = glob.glob(base + "*.info.json")
    if ij:
        info = json.load(open(ij[0], encoding="utf-8"))
    vtts = glob.glob(base + "*.vtt")
    manual = [(f, len(open(f, encoding="utf-8").read())) for f in vtts if "<c>" not in open(f, encoding="utf-8").read()]
    if manual:
        chosen = max(manual, key=lambda x: x[1])[0]
        kind = "human-edited"
    elif vtts:
        orig = [f for f in vtts if "orig" in os.path.basename(f)]
        chosen = orig[0] if orig else max(vtts, key=lambda f: len(open(f, encoding="utf-8").read()))
        kind = "auto-generated"
    else:
        chosen, kind = None, None
    vtt_text = open(chosen, encoding="utf-8").read() if chosen else ""
    return info, vtt_text, kind


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--duration")
    ap.add_argument("--out")
    ap.add_argument("--html-file", help="saved email body (get_thread JSON or "
                    "raw HTML) to extract from instead of fetching the url")
    ap.add_argument("--title", help="title override for --html-file (email "
                    "HTML rarely carries one)")
    args = ap.parse_args()

    if args.html_file:
        url = args.query.strip()
        if not is_url(url) or is_youtube(url):
            print(json.dumps({"error": "--html-file needs the canonical "
                              "article url as the positional argument",
                              "query": args.query}))
            sys.exit(3)
        item = blog_from_html(load_email_html(args.html_file), url, url,
                              title=args.title)
        out = json.dumps(item, ensure_ascii=False, indent=2)
        if args.out:
            open(args.out, "w", encoding="utf-8").write(out)
            print(json.dumps({"ok": True, "id": item["id"], "title": item["title"],
                              "kind": "article", "words": item["article"]["word_count"],
                              "from": "email-body", "out": args.out}))
        else:
            print(out)
        return

    if is_url(args.query) and not is_youtube(args.query):
        item = fetch_blog(args.query.strip())
        out = json.dumps(item, ensure_ascii=False, indent=2)
        if args.out:
            open(args.out, "w", encoding="utf-8").write(out)
            print(json.dumps({"ok": True, "id": item["id"], "title": item["title"],
                              "kind": "article", "words": item["article"]["word_count"],
                              "out": args.out}))
        else:
            print(out)
        return

    url = resolve_query(args.query, args.duration)
    if not url:
        print(json.dumps({"error": "no video found", "query": args.query}))
        sys.exit(1)

    workdir = tempfile.mkdtemp(prefix="hmr_")
    try:
        info, vtt_text, kind = download_info_and_captions(url, workdir)
        if not info.get("id"):
            info["id"] = extract_video_id(url)
        if not vtt_text:
            print(json.dumps({"error": "no english captions", "url": info.get("webpage_url", url),
                              "title": info.get("title")}))
            sys.exit(2)

        segments = clean_vtt_to_segments(vtt_text)
        added = datetime.now(timezone.utc).isoformat()
        item = build_item(info, segments, kind, added)

        out = json.dumps(item, ensure_ascii=False, indent=2)
        if args.out:
            open(args.out, "w", encoding="utf-8").write(out)
            print(json.dumps({"ok": True, "id": item["id"], "title": item["title"],
                              "caption_kind": kind, "segments": len(segments), "out": args.out}))
        else:
            print(out)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
