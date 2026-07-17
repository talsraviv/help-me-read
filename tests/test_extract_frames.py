import io, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import extract_frames as xf


def test_frame_times_clamps_to_3_and_5():
    assert len(xf.frame_times(0, 60)) == 3        # 1 min -> floor is 3
    assert len(xf.frame_times(0, 240)) == 4       # 4 min -> 4
    assert len(xf.frame_times(0, 3600)) == 5      # 60 min -> cap at 5


def test_frame_times_evenly_spaced_inside_segment():
    ts = xf.frame_times(100, 400)                  # 5 min -> 5 frames
    assert len(ts) == 5
    assert all(100 < t < 400 for t in ts)
    diffs = [round(b - a) for a, b in zip(ts, ts[1:])]
    assert len(set(diffs)) == 1                    # equal gaps
    assert ts == sorted(ts)


def test_frame_times_tolerates_reversed_bounds():
    assert xf.frame_times(400, 100) == xf.frame_times(100, 400)


def test_tile_for_maps_time_to_fragment_and_grid():
    # fps=0.2 (one tile / 5s), 3x3 tiles per fragment
    assert xf.tile_for(0, 0.2, 3, 3) == (0, 0, 0)
    assert xf.tile_for(5, 0.2, 3, 3) == (0, 0, 1)      # 2nd tile, row-major
    assert xf.tile_for(44.9, 0.2, 3, 3) == (0, 2, 2)   # last tile of frag 0
    assert xf.tile_for(45, 0.2, 3, 3) == (1, 0, 0)     # first tile of frag 1
    assert xf.tile_for(100, 0.2, 3, 3) == (2, 0, 2)    # tile 20 -> frag 2, idx 2


def test_pick_storyboard_takes_highest_resolution_sb():
    formats = [
        {"format_id": "251", "width": 0},
        {"format_id": "sb2", "width": 80, "fragments": [{"url": "u"}]},
        {"format_id": "sb0", "width": 320, "fragments": [{"url": "u"}]},
        {"format_id": "sb9", "width": 640},            # no fragments -> ignored
    ]
    assert xf.pick_storyboard(formats)["format_id"] == "sb0"
    assert xf.pick_storyboard([]) is None
    assert xf.pick_storyboard(None) is None


def _sprite_bytes(rows=3, cols=3, w=320, h=180):
    from PIL import Image
    im = Image.new("RGB", (cols * w, rows * h), (255, 0, 0))
    buf = io.BytesIO(); im.save(buf, "JPEG")
    return buf.getvalue()


def _item(tmp_path, moments):
    p = tmp_path / "item.json"
    p.write_text(json.dumps({"id": "vid1", "url": "https://youtube.com/watch?v=vid1",
                             "moments": moments}))
    return str(p)


def test_run_writes_frames_as_asset_files(tmp_path, monkeypatch):
    sb = {"format_id": "sb0", "width": 320, "height": 180, "rows": 3, "columns": 3,
          "fps": 0.2, "fragments": [{"url": f"frag{i}"} for i in range(30)]}
    monkeypatch.setattr(xf, "fetch_info", lambda url: {"formats": [sb]})
    monkeypatch.setattr(xf, "download", lambda url: _sprite_bytes())
    assets = tmp_path / "assets"
    path = _item(tmp_path, [{"kind": "demo", "start": 100, "end": 400,
                             "title": "d", "frames": []}])
    out = xf.run(path, str(assets))
    item = json.loads(open(path).read())
    frames = item["moments"][0]["frames"]
    assert out["ok"] and out["frames"] == 5 and len(frames) == 5
    for f in frames:
        assert f["src"].startswith("assets/vid1/") and f["src"].endswith(".jpg")
        assert (assets / "vid1" / os.path.basename(f["src"])).exists()
        assert isinstance(f["start"], int) and 100 < f["start"] < 400
    # no base64 anywhere in the item file
    assert "base64" not in open(path).read()


def test_run_is_graceful_when_info_fetch_fails(tmp_path, monkeypatch):
    def boom(url): raise RuntimeError("network down")
    monkeypatch.setattr(xf, "fetch_info", boom)
    path = _item(tmp_path, [{"kind": "demo", "start": 0, "end": 300,
                             "title": "d", "frames": []}])
    out = xf.run(path)
    assert out["ok"] and out["frames"] == 0 and out["warnings"]
    assert json.loads(open(path).read())["moments"][0]["frames"] == []


def test_run_is_graceful_without_pillow(tmp_path, monkeypatch):
    monkeypatch.setattr(xf, "pillow_available", lambda: False)
    monkeypatch.setattr(xf, "fetch_info",
                        lambda url: (_ for _ in ()).throw(AssertionError("must not fetch")))
    path = _item(tmp_path, [{"kind": "demo", "start": 0, "end": 300,
                             "title": "d", "frames": []}])
    out = xf.run(path)
    assert out["ok"] and out["frames"] == 0
    assert any("Pillow" in w for w in out["warnings"])
    assert json.loads(open(path).read())["moments"][0]["frames"] == []


def test_run_noop_without_moments(tmp_path, monkeypatch):
    monkeypatch.setattr(xf, "fetch_info",
                        lambda url: (_ for _ in ()).throw(AssertionError("must not fetch")))
    path = _item(tmp_path, [])
    out = xf.run(path)
    assert out == {"ok": True, "id": "vid1", "moments": 0, "frames": 0, "warnings": []}
