import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from check_quotes import check_item, norm_tokens

SEGS = [
    {"start": 10.0, "text": "we decided to keep the full trace"},
    {"start": 14.5, "text": "away from the main agent, because these"},
    {"start": 18.2, "text": "tool calls really gobbled up the context"},
    {"start": 60.0, "text": "and that's why the harness matters more"},
]


def video_item(quotes):
    blocks = [{"type": "quote", "text": t, "start": s} for t, s in quotes]
    return {"id": "v", "type": "youtube",
            "transcript": {"kind": "human-edited", "segments": SEGS},
            "overview": {"sections": [{"heading": "h", "blocks": blocks}]}}


def test_verbatim_quote_with_right_timestamp_passes():
    rep = check_item(video_item([("keep the full trace away from the main agent", 10)]))
    assert rep["ok"], rep


def test_punctuation_and_case_differences_are_ignored():
    rep = check_item(video_item([("Keep the full trace — away from the main agent!", 12)]))
    assert rep["ok"], rep


def test_fabricated_quote_is_error():
    rep = check_item(video_item([("we never said these exact words at all", 10)]))
    assert not rep["ok"]
    assert any("not found verbatim" in e for e in rep["errors"])


def test_wrong_timestamp_is_error():
    rep = check_item(video_item([("keep the full trace", 300)]))
    assert not rep["ok"]
    assert any("fix the timestamp" in e for e in rep["errors"])


def test_elided_quote_parts_must_appear_in_order():
    ok = check_item(video_item([("we decided to keep … gobbled up the context", 10)]))
    assert ok["ok"], ok
    bad = check_item(video_item([("gobbled up the context … we decided to keep", 18)]))
    assert not bad["ok"]


def test_qa_answer_quotes_are_checked():
    item = video_item([])
    item["overview"]["qa"] = [{"question": "why?", "start": 60, "answer": [
        {"type": "quote", "text": "the harness matters more", "start": 60}]}]
    assert check_item(item)["ok"]
    item["overview"]["qa"][0]["answer"][0]["text"] = "something never said"
    assert not check_item(item)["ok"]


def blog_item(quote, start=None):
    b = {"type": "quote", "text": quote}
    if start is not None:
        b["start"] = start
    return {"id": "b-x", "type": "blog",
            "article": {"html": "<p>The whole design exists to keep the full "
                                "trace away from the main agent.</p>"},
            "overview": {"sections": [{"heading": "h", "blocks": [b]}]}}


def test_blog_quote_matches_article_text():
    assert check_item(blog_item("keep the full trace away from the main agent"))["ok"]


def test_blog_quote_not_in_article_is_error():
    rep = check_item(blog_item("words that are not in the article"))
    assert not rep["ok"]


def test_blog_quote_with_start_is_error():
    rep = check_item(blog_item("keep the full trace", start=5))
    assert any("must not carry 'start'" in e for e in rep["errors"])


def test_norm_tokens_handles_curly_quotes():
    assert norm_tokens("Don’t “quote” me") == ["don", "t", "quote", "me"]
