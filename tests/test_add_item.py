import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ADD_ITEM_SCRIPT = os.path.join(REPO_ROOT, "scripts", "add_item.py")

VALID_ITEM = {"id": "vid1", "type": "youtube", "title": "Test Item",
              "url": "https://youtube.com/watch?v=vid1",
              "added": "2026-06-30T00:00:00+00:00",
              "overview": {"sections": [{"heading": "h", "blocks": [
                  {"type": "prose", "text": "p"}]}]}}


def run_add(tmp, item, items_dir=None):
    item_path = os.path.join(tmp, "item.json")
    items_dir = items_dir or os.path.join(tmp, "items")
    with open(item_path, "w", encoding="utf-8") as f:
        json.dump(item, f)
    return subprocess.run(
        [sys.executable, ADD_ITEM_SCRIPT, "--item", item_path, "--items-dir", items_dir],
        capture_output=True, text=True), items_dir


def test_cli_adds_item_as_per_item_file():
    with tempfile.TemporaryDirectory() as tmp:
        result, items_dir = run_add(tmp, VALID_ITEM)
        assert result.returncode == 0, result.stdout
        payload = json.loads(result.stdout)
        assert payload == {"added": True, "id": "vid1", "total": 1}
        stored = json.load(open(os.path.join(items_dir, "vid1.json"), encoding="utf-8"))
        assert stored == VALID_ITEM


def test_cli_duplicate_id_reports_added_false_and_keeps_original():
    with tempfile.TemporaryDirectory() as tmp:
        _, items_dir = run_add(tmp, VALID_ITEM)
        changed = {**VALID_ITEM, "title": "Changed"}
        result, _ = run_add(tmp, changed, items_dir)
        assert json.loads(result.stdout) == {"added": False, "id": "vid1", "total": 1}
        stored = json.load(open(os.path.join(items_dir, "vid1.json"), encoding="utf-8"))
        assert stored["title"] == "Test Item"          # original untouched


def test_cli_missing_item_file_errors_nonzero():
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [sys.executable, ADD_ITEM_SCRIPT, "--item", os.path.join(tmp, "nope.json"),
             "--items-dir", os.path.join(tmp, "items")],
            capture_output=True, text=True)
        assert result.returncode != 0
        assert "error" in json.loads(result.stdout)


def test_cli_rejects_item_without_overview():
    with tempfile.TemporaryDirectory() as tmp:
        incomplete = {k: v for k, v in VALID_ITEM.items() if k != "overview"}
        result, _ = run_add(tmp, incomplete)
        assert result.returncode != 0
        out = json.loads(result.stdout)
        assert any("overview" in d for d in out["details"])


def test_cli_rejects_unsafe_id():
    with tempfile.TemporaryDirectory() as tmp:
        bad = {**VALID_ITEM, "id": "../evil"}
        result, _ = run_add(tmp, bad)
        assert result.returncode != 0
        assert "error" in json.loads(result.stdout)


def test_cli_replace_flag_upgrades_existing_item():
    with tempfile.TemporaryDirectory() as tmp:
        _, items_dir = run_add(tmp, VALID_ITEM)
        upgraded = {**VALID_ITEM, "title": "Full Version"}
        item_path = os.path.join(tmp, "item.json")
        with open(item_path, "w", encoding="utf-8") as f:
            json.dump(upgraded, f)
        result = subprocess.run(
            [sys.executable, ADD_ITEM_SCRIPT, "--item", item_path,
             "--items-dir", items_dir, "--replace"],
            capture_output=True, text=True)
        payload = json.loads(result.stdout)
        assert payload == {"added": True, "id": "vid1", "total": 1, "replaced": True}
        stored = json.load(open(os.path.join(items_dir, "vid1.json"), encoding="utf-8"))
        assert stored["title"] == "Full Version"
