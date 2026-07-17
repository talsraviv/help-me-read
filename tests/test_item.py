import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fetch_item import clean_description, parse_chapters, best_thumbnail, format_upload_date, build_item

DESC = """Claire Vo, founder of ChatPRD, on what product management becomes.

This talk covers the shift to abundance.

0:00 - Anybody can build anything
1:38 - Inventing ways to not build
Subscribe here: https://example.com
Follow us on Twitter
"""

def test_clean_description_summary_is_first_paragraph():
    d = clean_description(DESC)
    assert d["summary"] == "Claire Vo, founder of ChatPRD, on what product management becomes."
    assert "0:00" not in d["summary"]
    assert d["full"].startswith("Claire Vo")

def test_parse_chapters():
    info = {"chapters": [{"start_time": 0.0, "title": "Intro"}, {"start_time": 98.0, "title": "Next"}]}
    assert parse_chapters(info) == [{"start": 0.0, "title": "Intro"}, {"start": 98.0, "title": "Next"}]

def test_best_thumbnail_prefers_highest_resolution():
    info = {"thumbnails": [
        {"url": "http://a/small.jpg", "width": 120},
        {"url": "http://a/big.jpg", "width": 1280},
    ]}
    assert best_thumbnail(info) == "http://a/big.jpg"

def test_format_upload_date():
    assert format_upload_date("20260612") == "2026-06-12"
    assert format_upload_date(None) is None

def test_build_item_shape():
    info = {
        "id": "abc12345678", "title": "T", "channel": "Chan",
        "webpage_url": "https://www.youtube.com/watch?v=abc12345678",
        "duration": 91, "duration_string": "1:31", "upload_date": "20260612",
        "description": DESC, "chapters": [{"start_time": 0.0, "title": "Intro"}],
        "thumbnails": [{"url": "http://a/big.jpg", "width": 1280}],
    }
    segs = [{"start": 6.5, "text": "hi", "speaker": None}]
    item = build_item(info, segs, "human-edited", "2026-06-30T00:00:00+00:00")
    assert item["id"] == "abc12345678"
    assert item["type"] == "youtube"
    assert item["source"] == "Chan"
    assert item["duration"] == "1:31"
    assert item["published"] == "2026-06-12"
    assert item["added"] == "2026-06-30T00:00:00+00:00"
    assert item["transcript"] == {"kind": "human-edited", "segments": segs}
    assert item["chapters"] == [{"start": 0.0, "title": "Intro"}]
    assert item["overview"] is None

from fetch_item import build_blog_item

def test_build_blog_item_shape():
    extracted = {
        "title": "How I Write With AI", "source": "Isaac's Blog",
        "description": "A process for writing with AI.",
        "image": "https://example.com/card.png", "published": "2026-05-11",
        "html": "<p>body</p>", "word_count": 900,
    }
    item = build_blog_item(extracted, "https://isaacflath.com/writing/ai-writing-process",
                           "2026-07-02T00:00:00+00:00")
    assert item["type"] == "blog"
    assert item["id"].startswith("b-")
    assert item["title"] == "How I Write With AI"
    assert item["source"] == "Isaac's Blog"
    assert item["url"] == "https://isaacflath.com/writing/ai-writing-process"
    assert item["thumbnail"] == "https://example.com/card.png"
    assert item["duration"] == "4 min read"
    assert item["published"] == "2026-05-11"
    assert item["description"] == {"summary": "A process for writing with AI.",
                                   "full": "A process for writing with AI."}
    assert item["chapters"] == []
    assert item["article"] == {"html": "<p>body</p>", "word_count": 900}
    assert "transcript" not in item
    assert item["overview"] is None

import json
import pytest
from article_extract import blog_id
from fetch_item import load_email_html, blog_from_html

EMAIL_HTML = ("<html><body><div>" +
              "<p>" + " ".join(f"word{i}" for i in range(200)) + "</p>" +
              "</div></body></html>")

def test_load_email_html_from_get_thread_json(tmp_path):
    f = tmp_path / "thread.json"
    f.write_text(json.dumps({"id": "t1", "messages": [
        {"htmlBody": "<p>short</p>"},
        {"htmlBody": EMAIL_HTML},
    ]}), encoding="utf-8")
    assert load_email_html(str(f)) == EMAIL_HTML  # picks the longest body

def test_load_email_html_raw_html_passthrough(tmp_path):
    f = tmp_path / "body.html"
    f.write_text(EMAIL_HTML, encoding="utf-8")
    assert load_email_html(str(f)) == EMAIL_HTML

def test_blog_from_html_email_body_keeps_canonical_url():
    url = "https://www.lennysnewsletter.com/p/community-wisdom-example"
    item = blog_from_html(EMAIL_HTML, url, url, title="Community Wisdom")
    assert item["type"] == "blog"
    assert item["id"] == blog_id(url)
    assert item["url"] == url
    assert item["title"] == "Community Wisdom"
    assert item["article"]["word_count"] >= 200

def test_blog_from_html_rejects_paywall_stub():
    url = "https://example.com/p/stub"
    with pytest.raises(SystemExit):
        blog_from_html("<html><body><p>subscribe to read</p></body></html>",
                       url, url, title="Stub")
