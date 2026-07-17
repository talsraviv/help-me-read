#!/usr/bin/env python3
"""Fill demo-moment frames from YouTube storyboard sprites.

Deterministic, no tokens. Reads an item JSON file (fetch_item.py shape) that
carries a "moments" array, downloads the video's storyboard sprite sheets, and
writes 3-5 evenly spaced frames per moment as JPEG files under
data/assets/<id>/, recording relative paths ("assets/<id>/mX-fY.jpg") — the
same paths the built site serves them at. Item JSON stays small and free of
base64. Failures never break the item: affected moments keep empty frames and
the reason lands in "warnings".
"""
import argparse, io, json, os, subprocess, sys, urllib.request

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from archive import DEFAULT_ASSETS_DIR, assets_dir_for

JPEG_QUALITY = 70
MIN_FRAMES, MAX_FRAMES = 3, 5


def frame_times(start, end):
    """Evenly spaced interior timestamps; count tracks segment length in minutes."""
    start, end = float(start), float(end)
    if end < start:
        start, end = end, start
    n = max(MIN_FRAMES, min(MAX_FRAMES, round((end - start) / 60)))
    step = (end - start) / (n + 1)
    return [start + step * (i + 1) for i in range(n)]


def tile_for(t, fps, rows, cols):
    """(fragment index, tile row, tile col) covering time t. Sheets fill row-major."""
    n = int(t * fps)
    tpf = rows * cols
    return n // tpf, (n % tpf) // cols, (n % tpf) % cols


def pick_storyboard(formats):
    sbs = [f for f in formats or []
           if str(f.get("format_id", "")).startswith("sb") and f.get("fragments")]
    return max(sbs, key=lambda f: f.get("width") or 0) if sbs else None


def fetch_info(url):
    cmd = ["yt-dlp", "--no-update", "--skip-download", "-j",
           "--extractor-args", "youtube:player_client=android,web,tv", url]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        tail = (p.stderr or "yt-dlp failed").strip().splitlines()[-1]
        raise RuntimeError(tail[:300])
    return json.loads(p.stdout)


def download(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def moment_frames(sb, moment, frag_cache, warnings, item_id, mi, assets_dir):
    from PIL import Image
    fps, rows, cols = sb["fps"], sb["rows"], sb["columns"]
    w, h = sb["width"], sb["height"]
    frags = sb["fragments"]
    frames = []
    adir = assets_dir_for(item_id, assets_dir)
    for j, t in enumerate(frame_times(moment.get("start", 0), moment.get("end", 0))):
        fi, row, col = tile_for(t, fps, rows, cols)
        if fi >= len(frags):
            continue
        try:
            if fi not in frag_cache:
                frag_cache[fi] = Image.open(io.BytesIO(download(frags[fi]["url"]))).convert("RGB")
            im = frag_cache[fi]
            box = (col * w, row * h, (col + 1) * w, (row + 1) * h)
            if box[2] > im.width or box[3] > im.height:
                continue  # past the sheet's last real tile
            os.makedirs(adir, exist_ok=True)
            name = f"m{mi}-f{j}.jpg"
            im.crop(box).save(os.path.join(adir, name), "JPEG", quality=JPEG_QUALITY)
            frames.append({"start": int(t), "src": f"assets/{item_id}/{name}"})
        except Exception as e:
            warnings.append(f"frame at {int(t)}s: {e}")
    return frames


def pillow_available():
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def run(item_path, assets_dir=DEFAULT_ASSETS_DIR):
    item = json.load(open(item_path, encoding="utf-8"))
    moments = item.get("moments") or []
    out = {"ok": True, "id": item.get("id"), "moments": len(moments),
           "frames": 0, "warnings": []}
    if not moments:
        return out
    if not pillow_available():
        out["warnings"].append(
            "Pillow not installed (python3 -m pip install Pillow) — demo cards will have no thumbnails")
        with open(item_path, "w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False, indent=2)
        return out
    sb = None
    try:
        sb = pick_storyboard(fetch_info(item["url"]).get("formats"))
        if sb is None:
            out["warnings"].append("no storyboards available for this video")
    except Exception as e:
        out["warnings"].append(f"could not fetch storyboards: {e}")
    if sb is not None:
        frag_cache = {}
        for mi, m in enumerate(moments):
            m["frames"] = moment_frames(sb, m, frag_cache, out["warnings"],
                                        item["id"], mi, assets_dir)
            out["frames"] += len(m["frames"])
    with open(item_path, "w", encoding="utf-8") as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", required=True, help="path to an item json with moments")
    ap.add_argument("--assets-dir", default=DEFAULT_ASSETS_DIR)
    args = ap.parse_args()
    try:
        out = run(args.item, args.assets_dir)
    except FileNotFoundError:
        print(json.dumps({"error": "item file not found", "path": args.item})); sys.exit(2)
    except json.JSONDecodeError:
        print(json.dumps({"error": "item file is not valid JSON", "path": args.item})); sys.exit(2)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
