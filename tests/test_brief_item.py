import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from brief_item import article_text, build_brief, compact_transcript

VIDEO = {"id": "v1", "type": "youtube", "title": "T", "source": "Ch",
         "duration": "10:00", "published": "2026-07-01",
         "description": {"summary": "What the talk is about."},
         "chapters": [{"start": 0.0, "title": "Intro"}, {"start": 62.0, "title": "Core"}],
         "transcript": {"kind": "auto-generated", "segments": [
             {"start": 1.28, "text": "hello there"},
             {"start": 4.9, "text": "welcome to the talk"}]}}

BLOG = {"id": "b-1", "type": "blog", "title": "Post", "source": "blog.example",
        "duration": "4 min read", "description": {"summary": "s"},
        "article": {"html": "<h2>Head</h2><p>First para.</p><p>Second &amp; more.</p>"}}


def test_compact_transcript_is_integer_second_lines():
    assert compact_transcript(VIDEO) == "[1] hello there\n[4] welcome to the talk"


def test_article_text_strips_tags_and_unescapes():
    txt = article_text(BLOG)
    assert "Head" in txt and "First para." in txt and "Second & more." in txt
    assert "<" not in txt


def test_brief_puts_spec_and_schema_before_item_content():
    brief = build_brief(VIDEO)
    # spec first (cache-friendly shared prefix), then schema, then the item
    spec_pos = brief.find("# Overview spec")
    schema_pos = brief.find("# Overview output schema")
    item_pos = brief.find("# The item")
    assert 0 <= spec_pos < schema_pos < item_pos
    assert "[1] hello there" in brief
    assert "Chapters" in brief and "[62] Core" in brief
    # no raw segments JSON leaked in
    assert '"segments"' not in brief


def test_blog_brief_carries_article_text_not_transcript():
    brief = build_brief(BLOG)
    assert "Article text" in brief and "First para." in brief
    assert "Transcript" not in brief


def test_video_brief_notes_caption_kind():
    assert "auto-generated" in build_brief(VIDEO)
