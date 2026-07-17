import json, os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from merge_overview import validate

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "merge_overview.py")

GOOD = {"overview": {"sections": [{"heading": "main contribution", "blocks": [
            {"type": "prose", "text": "explains"},
            {"type": "quote", "text": "exact words", "start": 12}]}],
        "no_figure": {"reason": "narrative interview"}},
        "moments": [{"kind": "demo", "start": 10, "end": 99, "title": "d", "frames": []}]}


def test_good_video_payload_validates():
    errors, n_figures = validate(GOOD, is_blog=False)
    assert errors == [] and n_figures == 0


def test_unknown_keys_and_block_types_are_errors():
    bad = {"overview": {"sections": [{"heading": "h", "blocks": [
        {"type": "wisdom", "text": "x"}]}], "extra": 1}, "surprise": True}
    errors = validate(bad, is_blog=False)
    errors = errors[0] if isinstance(errors, tuple) else errors
    text = " ".join(errors)
    assert "surprise" in text and "extra" in text and "wisdom" in text


def test_video_quote_without_start_is_error():
    bad = {"overview": {"sections": [{"heading": "h", "blocks": [
        {"type": "quote", "text": "words"}]}], "no_figure": {"reason": "r"}}}
    errors, _ = validate(bad, is_blog=False)
    assert any("needs a numeric 'start'" in e for e in errors)


def test_blog_rules_no_start_no_moments():
    bad = {"overview": {"sections": [{"heading": "h", "blocks": [
        {"type": "quote", "text": "words", "start": 5}]}], "no_figure": {"reason": "r"}},
        "moments": [{"kind": "demo", "start": 1, "end": 2, "title": "t", "frames": []}]}
    errors, _ = validate(bad, is_blog=True)
    text = " ".join(errors)
    assert "must not carry 'start'" in text and "moments: []" in text


def test_figure_and_no_figure_contract():
    fig = {"type": "figure", "svg": "<svg viewBox=\"0 0 720 300\"/>", "caption": "c"}
    both = {"overview": {"sections": [{"heading": "h", "blocks": [fig]}],
                         "no_figure": {"reason": "r"}}}
    errors, n = validate(both, is_blog=False)
    assert n == 1 and any("remove one or the other" in e for e in errors)
    neither = {"overview": {"sections": [{"heading": "h", "blocks": [
        {"type": "prose", "text": "p"}]}]}}
    errors, _ = validate(neither, is_blog=False)
    assert any("no_figure.reason" in e for e in errors)


def test_moment_with_prefilled_frames_is_error():
    bad = dict(GOOD, moments=[{"kind": "demo", "start": 1, "end": 2, "title": "t",
                               "frames": [{"src": "x"}]}])
    errors, _ = validate(bad, is_blog=False)
    assert any("frames" in e for e in errors)


def test_cli_merges_into_item_file(tmp_path):
    item_path = tmp_path / "item.json"
    ov_path = tmp_path / "overview.json"
    item_path.write_text(json.dumps({"id": "v1", "type": "youtube", "overview": None}))
    ov_path.write_text(json.dumps(GOOD))
    r = subprocess.run([sys.executable, SCRIPT, "--item", str(item_path),
                        "--overview", str(ov_path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    out = json.loads(r.stdout)
    assert out["ok"] and out["quotes"] == 1 and out["moments"] == 1
    merged = json.loads(item_path.read_text())
    assert merged["overview"] == GOOD["overview"]
    assert merged["moments"] == GOOD["moments"]


def test_cli_rejects_invalid_payload_without_touching_item(tmp_path):
    item_path = tmp_path / "item.json"
    ov_path = tmp_path / "overview.json"
    original = {"id": "v1", "type": "youtube", "overview": None}
    item_path.write_text(json.dumps(original))
    ov_path.write_text(json.dumps({"overview": {"sections": []}}))
    r = subprocess.run([sys.executable, SCRIPT, "--item", str(item_path),
                        "--overview", str(ov_path)], capture_output=True, text=True)
    assert r.returncode == 3
    assert not json.loads(r.stdout)["ok"]
    assert json.loads(item_path.read_text()) == original
