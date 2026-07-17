import base64, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from migrate_archive import migrate

TINY_JPEG = base64.b64encode(b"\xff\xd8\xff\xe0fakejpegbytes\xff\xd9").decode()

LEGACY = [
    {"id": "vid1", "type": "youtube", "added": "2026-06-30T00:00:00Z",
     "transcript": {"kind": "auto-generated", "segments": [
         {"start": 1.0, "text": "hi", "speaker": None},
         {"start": 2.0, "text": ">> Bye", "speaker": ">>"}]},
     "moments": [{"kind": "demo", "start": 5, "end": 60, "title": "d", "frames": [
         {"start": 10, "src": f"data:image/jpeg;base64,{TINY_JPEG}"}]}]},
    {"id": "b-abc", "type": "blog", "added": "2026-07-01T00:00:00Z",
     "article": {"html": "<p>x</p>"}, "moments": []},
]


def test_migrate_splits_strips_and_externalizes(tmp_path):
    legacy = tmp_path / "items.json"
    legacy.write_text(json.dumps(LEGACY))
    items_dir, assets_dir = str(tmp_path / "items"), str(tmp_path / "assets")
    report = migrate(str(legacy), items_dir, assets_dir)
    assert report["items"] == 2
    assert report["null_speakers_dropped"] == 1
    assert report["frames_externalized"] == 1

    vid = json.load(open(os.path.join(items_dir, "vid1.json")))
    segs = vid["transcript"]["segments"]
    assert "speaker" not in segs[0] and segs[1]["speaker"] == ">>"
    src = vid["moments"][0]["frames"][0]["src"]
    assert src == "assets/vid1/m0-f0.jpg"
    with open(os.path.join(assets_dir, "vid1", "m0-f0.jpg"), "rb") as f:
        assert f.read() == base64.b64decode(TINY_JPEG)

    blog = json.load(open(os.path.join(items_dir, "b-abc.json")))
    assert blog["article"]["html"] == "<p>x</p>"


def test_migrate_is_idempotent(tmp_path):
    legacy = tmp_path / "items.json"
    legacy.write_text(json.dumps(LEGACY))
    items_dir, assets_dir = str(tmp_path / "items"), str(tmp_path / "assets")
    migrate(str(legacy), items_dir, assets_dir)
    report2 = migrate(str(legacy), items_dir, assets_dir)
    assert report2["items"] == 2
    assert len([n for n in os.listdir(items_dir) if n.endswith(".json")]) == 2
