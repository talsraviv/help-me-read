#!/usr/bin/env python3
"""
Fetch a clean YouTube transcript from a URL, a video name, or a Gmail-style
subject line. Emits a cleaned transcript file plus JSON metadata on stdout.

Usage:
  python3 fetch_transcript.py "<url-or-name-or-subject>" \
      [--duration "1:02:33"] [--out /path/to/transcript.txt]

Notes:
- YouTube now forces a PO token for the default web client, which silently
  drops English captions. We work around it by asking yt-dlp to use the
  android/web/tv clients, which still serve captions. This was verified to work.
- We prefer human-edited captions (no inline <c> word tags). If only
  auto-generated captions exist, we de-duplicate YouTube's rolling-window
  repetition by keeping only the "live" tagged lines.
"""

import argparse
import glob
import html
import json
import os
import re
import subprocess
import sys
import tempfile


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def is_url(s):
    return ("youtube.com" in s) or ("youtu.be" in s)


def parse_duration_to_seconds(s):
    """Accepts '1:02:33', '12:05', '733', or 'Nh Nm Ns'. Returns int seconds or None."""
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    # try H:M:S / M:S
    if ":" in s:
        parts = s.split(":")
        try:
            parts = [int(p) for p in parts]
        except ValueError:
            return None
        sec = 0
        for p in parts:
            sec = sec * 60 + p
        return sec
    # try plain seconds
    if s.isdigit():
        return int(s)
    # try "1h2m33s" / "2m5s"
    m = re.findall(r"(\d+)\s*([hms])", s.lower())
    if m:
        mult = {"h": 3600, "m": 60, "s": 1}
        return sum(int(n) * mult[u] for n, u in m)
    return None


def extract_duration_hint(text):
    """Pull a likely duration like (1:02:33) or 1:02:33 out of free text."""
    m = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b", text)
    return m.group(1) if m else None


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def resolve_via_search(query, duration_hint_sec):
    """Search YouTube and return (url, chosen_meta, candidates)."""
    cmd = [
        "yt-dlp", "--no-update", "--skip-download", "--flat-playlist",
        "--print", "%(id)s\t%(title)s\t%(duration)s\t%(channel)s",
        f"ytsearch8:{query}",
    ]
    res = run(cmd)
    candidates = []
    for line in res.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        vid, title, dur, channel = parts[0], parts[1], parts[2], parts[3]
        try:
            dur_sec = int(float(dur))
        except (ValueError, TypeError):
            dur_sec = None
        candidates.append({
            "id": vid,
            "title": title,
            "duration_sec": dur_sec,
            "channel": channel,
            "url": f"https://www.youtube.com/watch?v={vid}",
        })
    if not candidates:
        return None, None, []

    chosen = candidates[0]
    if duration_hint_sec is not None:
        scored = [c for c in candidates if c["duration_sec"] is not None]
        if scored:
            chosen = min(scored, key=lambda c: abs(c["duration_sec"] - duration_hint_sec))
    return chosen["url"], chosen, candidates


def download_captions(url, workdir):
    base = os.path.join(workdir, "yt")
    cmd = [
        "yt-dlp", "--no-update", "--skip-download",
        "--write-auto-subs", "--write-subs", "--write-info-json",
        "--sub-langs", "en.*,en", "--sub-format", "vtt",
        "--extractor-args", "youtube:player_client=android,web,tv",
        "-o", base, url,
    ]
    res = run(cmd)
    if res.returncode != 0:
        log(res.stderr[-2000:])
    info_files = glob.glob(base + "*.info.json")
    vtt_files = glob.glob(base + "*.vtt")
    return info_files, vtt_files


def pick_vtt(vtt_files):
    """Prefer human-edited captions (no <c> tags). Fall back to auto."""
    if not vtt_files:
        return None
    manual, auto = [], []
    for f in vtt_files:
        try:
            content = open(f, encoding="utf-8").read()
        except OSError:
            continue
        (auto if "<c>" in content else manual).append((f, len(content)))
    if manual:
        return max(manual, key=lambda x: x[1])[0]
    # prefer the original auto track if present
    orig = [f for f, _ in auto if "orig" in os.path.basename(f)]
    if orig:
        return orig[0]
    return max(auto, key=lambda x: x[1])[0] if auto else None


def clean_vtt(path):
    content = open(path, encoding="utf-8").read()
    is_auto = "<c>" in content
    lines = content.splitlines()
    cleaned = []
    prev = None
    for ln in lines:
        if ln.startswith(("WEBVTT", "Kind:", "Language:")):
            continue
        if is_auto and "<c>" not in ln:
            # In auto captions, untagged lines are scroll-context repeats of
            # already-emitted text. Keep only the "live" tagged lines.
            continue
        # Unescape BEFORE filtering: captions sometimes contain a stray SRT
        # timestamp as escaped text (e.g. "00:02:56,120 --&gt; 00:02:58,540"),
        # which only looks like a cue line after unescaping.
        u = html.unescape(ln)
        if "-->" in u or u.strip() == "" or re.match(r"^\d+$", u.strip()):
            continue
        # Drop any line that is purely a timestamp (either . or , millis form).
        if re.match(r"^\d{1,2}:\d{2}:\d{2}[.,]\d{3}\s*$", u.strip()):
            continue
        t = re.sub(r"<[^>]+>", "", u).strip()
        if t and t != prev:
            cleaned.append(t)
            prev = t

    # Reflow into readable paragraphs.
    if any(t.startswith(">>") for t in cleaned):
        # Human captions: start a new paragraph at each speaker marker.
        paras, cur = [], []
        for t in cleaned:
            if t.startswith(">>") and cur:
                paras.append(" ".join(cur))
                cur = []
            cur.append(t)
        if cur:
            paras.append(" ".join(cur))
        return "\n\n".join(paras)
    # Auto captions: chunk into ~6-sentence paragraphs for readability.
    text = " ".join(cleaned)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    paras, cur = [], []
    for s in sentences:
        cur.append(s)
        if len(cur) >= 6:
            paras.append(" ".join(cur))
            cur = []
    if cur:
        paras.append(" ".join(cur))
    return "\n\n".join(paras)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="YouTube URL, video name, or notification subject line")
    ap.add_argument("--duration", help="Duration hint to disambiguate search, e.g. 1:02:33")
    ap.add_argument("--out", help="Where to write the cleaned transcript text")
    args = ap.parse_args()

    workdir = tempfile.mkdtemp(prefix="yt_transcript_")

    duration_hint = args.duration or extract_duration_hint(args.query)
    duration_hint_sec = parse_duration_to_seconds(duration_hint)

    candidates = []
    if is_url(args.query):
        url = args.query.strip()
        chosen = None
    else:
        log(f"Searching YouTube for: {args.query!r}")
        url, chosen, candidates = resolve_via_search(args.query, duration_hint_sec)
        if not url:
            print(json.dumps({"error": "No search results found", "query": args.query}))
            sys.exit(1)
        log(f"Chosen: {chosen['title']} ({chosen['url']})")

    info_files, vtt_files = download_captions(url, workdir)

    title = None
    duration_string = None
    webpage_url = url
    if info_files:
        info = json.load(open(info_files[0], encoding="utf-8"))
        title = info.get("title")
        duration_string = info.get("duration_string")
        webpage_url = info.get("webpage_url", url)

    # Fall back to search-candidate metadata if the info.json was missing or
    # got rate-limited (HTTP 429). Better an approximate title than none.
    if chosen:
        if not title:
            title = chosen.get("title")
        if not duration_string and chosen.get("duration_sec"):
            s = chosen["duration_sec"]
            duration_string = f"{s // 60}:{s % 60:02d}" if s < 3600 else f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"

    vtt = pick_vtt(vtt_files)
    if not vtt:
        print(json.dumps({
            "error": "No English captions available for this video",
            "url": webpage_url,
            "title": title,
            "candidates": candidates,
        }))
        sys.exit(2)

    transcript = clean_vtt(vtt)
    caption_kind = "auto-generated" if "<c>" in open(vtt, encoding="utf-8").read() else "human-edited"

    out_path = args.out or os.path.join(workdir, "transcript.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(transcript + "\n")

    print(json.dumps({
        "title": title,
        "url": webpage_url,
        "duration": duration_string,
        "caption_kind": caption_kind,
        "transcript_path": out_path,
        "word_count": len(transcript.split()),
        "candidates": candidates,
    }, indent=2))


if __name__ == "__main__":
    main()
