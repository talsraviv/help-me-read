import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from article_extract import extract, blog_id, read_time_label

# A semantic page: <article> plus the chrome an extractor must ignore.
SEMANTIC_PAGE = """<!DOCTYPE html>
<html><head>
<title>Fallback Title - My Blog</title>
<meta property="og:title" content="How I Write With AI">
<meta property="og:site_name" content="Isaac's Blog">
<meta property="og:description" content="A process for writing with AI.">
<meta property="og:image" content="https://example.com/card.png">
<meta property="article:published_time" content="2026-05-11T09:00:00Z">
</head><body>
<nav><ul><li><a href="/">Home</a></li><li><a href="/about">About</a></li></ul></nav>
<article>
<h1>How I Write With AI</h1>
<p>First paragraph of the actual article, which says something substantive
about the writing process and goes on for a while to look like real prose.</p>
<script>alert('evil')</script>
<p onclick="steal()">Second paragraph with an <a href="https://example.com/ref">inline link</a>
and <strong>bold text</strong> that should survive.</p>
<h2>A section heading</h2>
<blockquote><p>A quoted passage from someone.</p></blockquote>
<ul><li>list item one</li><li>list item two</li></ul>
<pre><code>print("code block")</code></pre>
<img src="https://example.com/fig.png" alt="a figure" width="600" style="border:1px">
<p>Closing paragraph with a <a href="javascript:evil()">bad link</a> inside.</p>
</article>
<footer><p>Subscribe to my newsletter! Follow me on Twitter.</p></footer>
</body></html>"""

# A substack-ish page: no <article>, content lives in a classed div.
DIV_PAGE = """<html><head><title>Is there a good way to write with AI?</title>
<meta property="og:site_name" content="Hils Substack"></head><body>
<div class="navbar"><a href="/">home</a></div>
<div class="available-content"><div class="body markup">
<p>The main argument, paragraph one, long enough to score as real content
because extraction ranks candidates by how much paragraph text they hold.</p>
<p>Paragraph two continues the argument with more real prose so that this
container clearly wins over the navigation and footer chrome.</p>
</div></div>
<div class="footer"><p>comments</p><p>share</p></div>
</body></html>"""


def _ex_semantic():
    return extract(SEMANTIC_PAGE, "https://isaacflath.com/writing/ai-writing-process")


def test_metadata_from_og_tags():
    ex = _ex_semantic()
    assert ex["title"] == "How I Write With AI"
    assert ex["source"] == "Isaac's Blog"
    assert ex["description"] == "A process for writing with AI."
    assert ex["image"] == "https://example.com/card.png"
    assert ex["published"] == "2026-05-11"


def test_article_body_extracted_and_chrome_dropped():
    html = _ex_semantic()["html"]
    assert "First paragraph of the actual article" in html
    assert "A section heading" in html
    assert "list item one" in html
    assert 'print("code block")' in html
    assert "Home" not in html            # nav dropped
    assert "Subscribe" not in html       # footer dropped


def test_unsafe_markup_stripped_at_extraction():
    html = _ex_semantic()["html"]
    assert "<script" not in html
    assert "alert(" not in html
    assert "onclick" not in html
    assert "javascript:" not in html
    assert "style=" not in html
    assert 'href="https://example.com/ref"' in html   # good link kept
    assert '<img src="https://example.com/fig.png"' in html


def test_h1_demoted_and_title_dedup():
    # The in-article <h1> duplicates the page title; it must not repeat in the body.
    html = _ex_semantic()["html"]
    assert "<h1" not in html


def test_div_page_finds_classed_container():
    ex = extract(DIV_PAGE, "https://hils.substack.com/p/is-there-a-good-way-to-write-with")
    assert "The main argument, paragraph one" in ex["html"]
    assert "comments" not in ex["html"]
    assert ex["title"] == "Is there a good way to write with AI?"
    assert ex["source"] == "Hils Substack"


def test_word_count_and_read_time():
    ex = _ex_semantic()
    assert ex["word_count"] > 40
    assert read_time_label(225) == "1 min read"
    assert read_time_label(2000) == "9 min read"


def test_blog_id_stable_and_normalized():
    a = blog_id("https://www.Example.com/post/slug/?utm_source=x#frag")
    b = blog_id("http://example.com/post/slug")
    assert a == b
    assert a.startswith("b-") and len(a) == 14
    assert blog_id("https://example.com/other") != a


# The article's wrapper always outscores the article itself (superset), because
# real pages put signup/bio paragraphs outside </article>. The picker must take
# the tightest container that still holds (nearly) all the paragraph text.
WRAPPED_PAGE = """<html><head><title>T</title></head><body>
<div id="app">
<div><a href="/community">Community</a><a href="/writing">Writing</a><a href="/subscribe">Subscribe</a></div>
<article>
<p>Real article paragraph one, with enough text to dominate the scoring pass
and represent the actual content of the post being extracted here.</p>
<p>Real article paragraph two, also substantive prose that continues to make
this the clear winner among all the candidate containers on the page.</p>
</article>
<div><h3>Stay up to date</h3><p>I send useful notes. 5,000+ readers enjoy them a lot.</p></div>
</div></body></html>"""


def test_picks_article_not_its_wrapper():
    html = extract(WRAPPED_PAGE, "https://example.com/post")["html"]
    assert "Real article paragraph one" in html
    assert "Stay up to date" not in html      # outside </article>
    assert "5,000+ readers" not in html
    assert "Community" not in html            # link-menu div outside article


def test_link_dense_menu_inside_content_is_dropped():
    page = """<html><body><article>
    <div><a href="/a">Home</a><a href="/b">About</a><a href="/c">Subscribe</a></div>
    <p>Actual prose paragraph that is long enough to count as content here,
    going on for a couple of lines so scoring works as it does on real pages.</p>
    </article></body></html>"""
    html = extract(page, "https://example.com/x")["html"]
    assert "Actual prose" in html
    assert "Subscribe" not in html


def test_title_site_suffix_moves_to_source():
    page = """<html><head><title>My Post | Isaac Flath</title>
    <meta property="og:title" content="My Post | Isaac Flath"></head><body><article>
    <p>Prose long enough to be treated as the content of this small test page,
    and a second line so it comfortably clears the scoring threshold.</p>
    </article></body></html>"""
    ex = extract(page, "https://isaacflath.com/writing/my-post")
    assert ex["title"] == "My Post"
    assert ex["source"] == "Isaac Flath"


def test_title_suffix_kept_when_site_name_known():
    page = """<html><head><title>Real Title - Part 2</title>
    <meta property="og:site_name" content="Some Blog"></head><body><article>
    <p>Prose long enough to be treated as the content of this small test page,
    and a second line so it comfortably clears the scoring threshold.</p>
    </article></body></html>"""
    ex = extract(page, "https://example.com/p")
    assert ex["title"] == "Real Title - Part 2"   # suffix is not the site → keep
    assert ex["source"] == "Some Blog"


# A Quarto-ish page: the root layout wrapper's class mentions "navbar", but it
# holds the entire article. Pruning must recurse into it, not drop it.
CHROME_CLASSED_WRAPPER_PAGE = """<html><head><title>Do Automated Evals Work?</title>
</head><body>
<div class="quarto-container page-columns page-layout-article page-navbar">
<main class="content">
<p>Paragraph one of the actual article, long enough to register as real prose
so the wrapper carries essentially all of the document's paragraph text.</p>
<p>Paragraph two keeps going with substantive content so the paragraph score
of this subtree dominates the page beyond any doubt.</p>
</main>
</div>
<div class="footer"><p>share</p></div>
</body></html>"""


def test_chrome_classed_wrapper_holding_article_survives():
    ex = extract(CHROME_CLASSED_WRAPPER_PAGE, "https://parlance-labs.com/blog/posts/auto-evals/")
    assert "Paragraph one of the actual article" in ex["html"]
    assert "Paragraph two keeps going" in ex["html"]
