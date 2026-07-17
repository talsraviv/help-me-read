import json, os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "retry_queue.py")
URL = "https://example.com/test-retry-queue-entry"


def run(*args):
    result = subprocess.run([sys.executable, SCRIPT, *args],
                            capture_output=True, text=True)
    return json.loads(result.stdout), result.returncode


def _cleanup():
    run("remove", URL)


def test_add_list_bump_remove_roundtrip():
    _cleanup()
    try:
        out, rc = run("add", URL, "--kind", "video", "--reason", "no captions yet",
                      "--title", "A Talk", "--thread", "t123")
        assert rc == 0 and out["ok"] and out["attempts"] == 1

        out, _ = run("list")
        mine = [e for e in out["entries"] if e["url"] == URL]
        assert len(mine) == 1
        assert mine[0]["reason"] == "no captions yet"
        assert mine[0]["stale"] is False

        out, _ = run("bump", URL, "--reason", "still no captions")
        assert out["attempts"] == 2

        out, _ = run("remove", URL, "--result", "added vid123")
        assert out["removed"] is True

        out, _ = run("list")
        assert not [e for e in out["entries"] if e["url"] == URL]
    finally:
        _cleanup()


def test_add_is_idempotent_per_url():
    _cleanup()
    try:
        run("add", URL, "--kind", "blog", "--reason", "first")
        out, _ = run("add", URL, "--kind", "blog", "--reason", "second")
        assert out["ok"]
        out, _ = run("list")
        mine = [e for e in out["entries"] if e["url"] == URL]
        assert len(mine) == 1 and mine[0]["reason"] == "second"
    finally:
        _cleanup()


def test_stale_after_max_attempts():
    _cleanup()
    try:
        run("add", URL, "--kind", "video", "--reason", "r")
        for _ in range(5):
            out, _ = run("bump", URL, "--reason", "r")
        assert out["attempts"] == 6 and out["stale"] is True
    finally:
        _cleanup()


def test_upgrade_entry_carries_item_id():
    _cleanup()
    try:
        out, _ = run("add", URL, "--kind", "blog", "--reason",
                     "added from email preview; retry full page",
                     "--upgrade", "--item-id", "b-abc123")
        assert out["ok"]
        out, _ = run("list")
        mine = [e for e in out["entries"] if e["url"] == URL][0]
        assert mine["upgrade"] is True and mine["itemId"] == "b-abc123"
    finally:
        _cleanup()
