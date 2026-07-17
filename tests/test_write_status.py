import json, os, subprocess, sys
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "write_status.py")


def run(payload, out):
    return subprocess.run([sys.executable, SCRIPT, json.dumps(payload), "--out", out],
                          capture_output=True, text=True)


def test_writes_status_with_stamped_timestamp(tmp_path):
    out = str(tmp_path / "status.json")
    r = run({"added": [{"id": "a", "title": "T", "source": "Ch"}],
             "skipped": [{"input": "pasted thing", "reason": "no captions"}]}, out)
    assert r.returncode == 0, r.stdout
    status = json.load(open(out))
    assert status["added"][0]["id"] == "a"
    assert status["skipped"][0]["reason"] == "no captions"
    assert status["updated"].endswith("Z") and "T" in status["updated"]


def test_rejects_missing_reason(tmp_path):
    out = str(tmp_path / "status.json")
    r = run({"added": [], "skipped": [{"input": "x"}]}, out)
    assert r.returncode == 3
    assert not os.path.exists(out)


def test_rejects_unknown_keys_and_manual_timestamp(tmp_path):
    out = str(tmp_path / "status.json")
    r = run({"added": [], "skipped": [], "updated": "2026-01-01T00:00:00Z"}, out)
    assert r.returncode == 3
    assert "updated" in r.stdout
