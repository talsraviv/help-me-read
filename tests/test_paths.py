import os, sys

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import archive, build


def test_repo_root_resolves_from_script_location():
    # Scripts anchor to the repo via their own file location, not the cwd.
    assert archive.REPO_ROOT == REPO
    assert build.REPO_ROOT == REPO


def test_default_paths_are_absolute_repo_paths():
    assert archive.DEFAULT_ITEMS_DIR == os.path.join(REPO, "data", "items")
    assert archive.DEFAULT_ASSETS_DIR == os.path.join(REPO, "data", "assets")
    assert os.path.isabs(archive.DEFAULT_ITEMS_DIR)
    assert build.DEFAULT_TEMPLATE == os.path.join(REPO, "templates", "reader.html")
    assert build.DEFAULT_OUT == os.path.join(REPO, "site", "index.html")


def test_default_fonts_prefer_local_override_else_bundled():
    # A gitignored assets/fonts-local/{book,bold}.ttf pair (the user's own
    # typeface) wins over the bundled OFL Gelasio.
    local_book = os.path.join(REPO, "assets", "fonts-local", "book.ttf")
    local_bold = os.path.join(REPO, "assets", "fonts-local", "bold.ttf")
    if os.path.exists(local_book) and os.path.exists(local_bold):
        assert build.DEFAULT_BOOK == local_book
        assert build.DEFAULT_BOLD == local_bold
    else:
        assert build.DEFAULT_BOOK == os.path.join(REPO, "assets", "fonts", "Gelasio-Regular.ttf")
        assert build.DEFAULT_BOLD == os.path.join(REPO, "assets", "fonts", "Gelasio-Bold.ttf")
    assert os.path.exists(build.DEFAULT_BOOK) and os.path.exists(build.DEFAULT_BOLD)


def test_item_path_is_id_scoped_and_safe():
    assert archive.item_path("abc_-123", "/x") == "/x/abc_-123.json"
    for bad in ("../evil", "a/b", "", None, "a b"):
        try:
            archive.item_path(bad, "/x")
            assert False, f"{bad!r} should have been rejected"
        except ValueError:
            pass


def test_load_items_sorts_newest_first(tmp_path):
    import json
    d = tmp_path / "items"
    d.mkdir()
    for iid, added in (("a", "2026-06-01T00:00:00Z"), ("b", "2026-06-30T00:00:00Z")):
        (d / f"{iid}.json").write_text(json.dumps({"id": iid, "added": added}))
    items = archive.load_items(str(d))
    assert [i["id"] for i in items] == ["b", "a"]
