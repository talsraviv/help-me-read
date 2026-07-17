import os, sys, json, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from build import inject

TEMPLATE = """<html><head><style>/*FONTS*/
body{}</style></head><body>
<script id="items-data" type="application/json">[]</script>
<script id="run-status" type="application/json">null</script>
</body></html>"""

def test_inject_replaces_fonts_and_items():
    out = inject(TEMPLATE, '[{"id":"a"}]', "@font-face{}")
    assert "/*FONTS*/" not in out
    assert "@font-face{}" in out
    assert '[{"id":"a"}]' in out
    assert "[]</script>" not in out

def test_inject_escapes_script_close_in_json():
    out = inject(TEMPLATE, '[{"t":"</script>"}]', "")
    assert "</script>" in out                 # the real closing tag survives
    assert "<\\/script>" in out               # the json occurrence is escaped

def test_inject_preserves_backslashes_and_quotes():
    items = [{"text": 'He said "hi" and a path C:\\\\temp\\\\1_backup'}]
    items_json = json.dumps(items)
    out = inject(TEMPLATE, items_json, "")
    m = re.search(r'<script id="items-data"[^>]*>(.*?)</script>', out, re.S)
    assert m, "island not found"
    recovered = m.group(1).replace("<\\/", "</")   # undo the script-close guard
    assert json.loads(recovered) == items

def test_inject_fills_run_status_island():
    status = {"updated": "2026-07-01T00:00:00Z", "added": [{"id": "a", "title": "T"}],
              "skipped": [{"input": "some talk", "reason": "no captions available"}]}
    out = inject(TEMPLATE, "[]", "", json.dumps(status))
    m = re.search(r'<script id="run-status"[^>]*>(.*?)</script>', out, re.S)
    assert m, "run-status island not found"
    recovered = m.group(1).replace("<\\/", "</")
    assert json.loads(recovered) == status
    assert ">null</script>" not in out            # default was replaced

def test_inject_defaults_run_status_to_null():
    out = inject(TEMPLATE, "[]", "")
    m = re.search(r'<script id="run-status"[^>]*>(.*?)</script>', out, re.S)
    assert m and m.group(1) == "null"


from build import sanitize_svg, sanitize_items

CLEAN = '<svg viewBox="0 0 720 400"><rect width="10" height="10" fill="#cf5a3c"/><use href="#a"/></svg>'

def test_sanitize_svg_passes_clean_svg_unchanged():
    assert sanitize_svg(CLEAN) == CLEAN               # internal #refs survive

def test_sanitize_svg_strips_dangerous_content():
    dirty = ('<svg viewBox="0 0 10 10"><script>alert(1)</script>'
             '<rect onclick="x()" onmouseover=\'y()\' width="5" height="5"/>'
             '<foreignObject><body>hi</body></foreignObject>'
             '<image href="https://evil.example/x.png"/>'
             '<a xlink:href="https://evil.example"><text>t</text></a></svg>')
    out = sanitize_svg(dirty)
    for bad in ("<script", "onclick", "onmouseover", "foreignObject", "evil.example"):
        assert bad not in out
    assert "<rect" in out and "<text>t</text>" in out

def test_sanitize_svg_strips_unquoted_external_refs():
    dirty = '<svg viewBox="0 0 10 10"><image href=https://evil.example/x.png /><use href=#ok /></svg>'
    out = sanitize_svg(dirty)
    assert "evil.example" not in out
    assert "href=#ok" in out

def test_sanitize_svg_rejects_non_svg():
    assert sanitize_svg("<div>not svg</div>") is None
    assert sanitize_svg(None) is None
    assert sanitize_svg("<script>only</script>") is None

def test_sanitize_items_drops_unrenderable_figures_keeps_rest():
    items = [{"id": "a", "overview": {"sections": [{"heading": "h", "blocks": [
        {"type": "prose", "text": "p"},
        {"type": "figure", "svg": "<div>junk</div>", "caption": "gone"},
        {"type": "figure", "svg": CLEAN, "caption": "kept"},
        {"type": "quote", "text": "q", "start": 5},
    ]}], "qa": [{"question": "q?", "answer": [
        {"type": "figure", "svg": "<b>junk</b>"}, {"type": "prose", "text": "a"}]}]}}]
    out = sanitize_items(items)
    blocks = out[0]["overview"]["sections"][0]["blocks"]
    assert [b["type"] for b in blocks] == ["prose", "figure", "quote"]
    assert blocks[1]["caption"] == "kept"
    assert [b["type"] for b in out[0]["overview"]["qa"][0]["answer"]] == ["prose"]

def test_sanitize_items_ignores_items_without_overview():
    assert sanitize_items([{"id": "a"}, {"id": "b", "overview": None}]) == \
        [{"id": "a"}, {"id": "b", "overview": None}]


from build import sanitize_article_html

def test_sanitize_article_passes_clean_html():
    clean = '<p>Hello <a href="https://a.example/x">link</a></p><h2>Head</h2>'
    assert sanitize_article_html(clean) == clean

def test_sanitize_article_strips_active_content():
    dirty = ('<p onclick="x()">hi</p><script>alert(1)</script>'
             '<style>p{}</style><iframe src="https://evil.example"></iframe>'
             '<form action="/steal"><input></form>'
             '<a href="javascript:evil()">bad</a>'
             '<img src="https://ok.example/i.png" onerror="p()">')
    out = sanitize_article_html(dirty)
    for bad in ("<script", "<style", "<iframe", "<form", "onclick", "onerror", "javascript:"):
        assert bad not in out
    assert "<p" in out and "hi" in out
    assert 'src="https://ok.example/i.png"' in out

def test_sanitize_items_sanitizes_blog_article():
    items = [{"id": "b-x", "type": "blog",
              "article": {"html": '<p>ok</p><script>bad()</script>', "word_count": 1}}]
    out = sanitize_items(items)
    assert "<script" not in out[0]["article"]["html"]
    assert "<p>ok</p>" in out[0]["article"]["html"]


from build import split_item, write_site

VIDEO_ITEM = {"id": "v1", "type": "youtube", "title": "T", "added": "2026-07-01T00:00:00Z",
              "transcript": {"kind": "human-edited", "segments": [{"start": 1, "text": "hi"}]},
              "overview": {"sections": [{"heading": "h", "blocks": [{"type": "prose", "text": "p"}]}]},
              "moments": []}
BLOG_ITEM = {"id": "b-1", "type": "blog", "title": "P", "added": "2026-07-02T00:00:00Z",
             "article": {"html": "<p>body</p>", "word_count": 2},
             "overview": {"sections": [{"heading": "h", "blocks": [{"type": "prose", "text": "p"}]}]}}


def test_split_item_moves_transcript_and_article_html_to_heavy():
    light, heavy = split_item(dict(VIDEO_ITEM))
    assert "transcript" not in light
    assert light["lazy"] == {"transcript": True, "article": False}
    assert heavy["transcript"]["segments"][0]["text"] == "hi"
    assert light["overview"] == VIDEO_ITEM["overview"]     # overview stays in the index

    light, heavy = split_item(dict(BLOG_ITEM))
    assert light["lazy"] == {"transcript": False, "article": True}
    assert light["article"] == {"word_count": 2}           # metadata stays, html moves
    assert heavy["article"]["html"] == "<p>body</p>"


def test_split_item_without_heavy_fields_has_no_lazy_flags():
    light, heavy = split_item({"id": "x", "overview": None})
    assert heavy == {} and "lazy" not in light


def test_write_site_emits_index_payloads_and_fonts(tmp_path):
    template = ('<html><head><style>/*FONTS*/</style></head><body>'
                '<script id="items-data" type="application/json">[]</script>'
                '<script id="run-status" type="application/json">null</script>'
                '</body></html>')
    out = tmp_path / "site" / "index.html"
    out.parent.mkdir()
    # Explicit font paths so the test doesn't depend on which default (local
    # override vs bundled Gelasio) this machine resolves.
    book = tmp_path / "my-book.ttf"
    bold = tmp_path / "my-bold.ttf"
    book.write_bytes(b"fake-font")
    bold.write_bytes(b"fake-font")
    report = write_site([dict(VIDEO_ITEM), dict(BLOG_ITEM)], template, str(out),
                        book=str(book), bold=str(bold),
                        assets_dir=str(tmp_path / "no-assets"))
    assert report["ok"] and report["items"] == 2 and report["heavy_files"] == 2
    html = out.read_text()
    assert "/*FONTS*/" not in html and "fonts/my-book.ttf" in html
    assert "'Reader Serif'" in html
    assert (out.parent / "fonts" / "my-book.ttf").exists()
    m = re.search(r'<script id="items-data"[^>]*>(.*?)</script>', html, re.S)
    lights = json.loads(m.group(1).replace("<\\/", "</"))
    assert all("transcript" not in it for it in lights)
    v1 = json.load(open(out.parent / "items" / "v1.json"))
    assert v1["transcript"]["segments"]
    b1 = json.load(open(out.parent / "items" / "b-1.json"))
    assert b1["article"]["html"] == "<p>body</p>"


def test_write_site_drops_stale_payloads(tmp_path):
    template = ('<style>/*FONTS*/</style>'
                '<script id="items-data" type="application/json">[]</script>'
                '<script id="run-status" type="application/json">null</script>')
    out = tmp_path / "index.html"
    (tmp_path / "items").mkdir()
    (tmp_path / "items" / "gone.json").write_text("{}")
    write_site([dict(VIDEO_ITEM)], template, str(out),
               assets_dir=str(tmp_path / "no-assets"))
    assert not (tmp_path / "items" / "gone.json").exists()
    assert (tmp_path / "items" / "v1.json").exists()
