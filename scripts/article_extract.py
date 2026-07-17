#!/usr/bin/env python3
"""Extract readable article content + metadata from a blog page. Stdlib only.

Readability-lite: build a small DOM, prune chrome (nav/footer/scripts/...),
pick the container with the most paragraph text, and re-serialize just the
reading tags. The output HTML is injected unescaped into the reader, so
serialization doubles as the sanitizer: only allowlisted tags and attributes
are ever emitted, all text is re-escaped, and urls must be http(s).
"""
import gzip, hashlib, html, io, json, re, urllib.request, zlib
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

VOID = {"br", "img", "hr", "meta", "link", "input", "source", "embed", "area",
        "base", "col", "wbr", "track", "param"}

# Tags whose subtrees are never content.
DROP_TAGS = {"script", "style", "noscript", "nav", "header", "footer", "aside",
             "form", "iframe", "svg", "button", "select", "textarea",
             "template", "dialog", "video", "audio"}

# class/id fragments that mark page chrome rather than content.
CHROME_RX = re.compile(
    r"comment|share|subscribe|related|promo|sidebar|footer|navbar|navigation|"
    r"topbar|menu|social|paywall|banner|popup|cookie|newsletter-signup", re.I)

# class/id fragments that suggest a content container (used to widen the
# candidate pool beyond <article>/<main> for div-soup sites like Substack).
CONTENT_RX = re.compile(r"post|article|content|entry|body|markup|prose|essay", re.I)

ALLOWED = {"p", "h2", "h3", "h4", "blockquote", "ul", "ol", "li", "pre", "code",
           "em", "i", "b", "strong", "a", "img", "figure", "figcaption", "hr",
           "br", "table", "thead", "tbody", "tr", "th", "td", "sup", "sub"}


class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.parent = tag, parent
        self.attrs = dict(attrs or [])
        self.children = []


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        if data:
            self.cur.children.append(data)


def parse_tree(html_text):
    tb = TreeBuilder()
    tb.feed(html_text)
    return tb.root


def walk(node):
    for c in node.children:
        if isinstance(c, Node):
            yield c
            yield from walk(c)


def text_of(node):
    out = []
    for c in node.children:
        out.append(c if isinstance(c, str) else text_of(c))
    return "".join(out)


def _class_id(node):
    return (node.attrs.get("class", "") or "") + " " + (node.attrs.get("id", "") or "")


def _link_density(node):
    total = len(_norm_ws(text_of(node)))
    if not total:
        return 0.0
    linked = sum(len(_norm_ws(text_of(n))) for n in walk(node) if n.tag == "a")
    return linked / total


def _is_link_menu(node):
    # A short block that is nearly all links is a menu, not content. Footnote
    # lists (<ol>) are exempt: their entries are legitimately link-heavy.
    if node.tag not in ("div", "section", "ul"):
        return False
    t = _norm_ws(text_of(node))
    return bool(t) and len(t) < 150 and _link_density(node) > 0.7


def prune_chrome(node, doc_para=None):
    # A node whose class/id merely mentions a chrome word can still be the
    # page's layout wrapper holding the whole article (Quarto tags its root
    # container "page-navbar"). Never drop a subtree carrying most of the
    # document's paragraph text — recurse into it instead.
    if doc_para is None:
        doc_para = _para_score(node)
    kept = []
    for c in node.children:
        if isinstance(c, Node):
            if c.tag in DROP_TAGS or _is_link_menu(c):
                continue
            if CHROME_RX.search(_class_id(c)) and not (
                    doc_para and _para_score(c) > 0.5 * doc_para):
                continue
            prune_chrome(c, doc_para)
        kept.append(c)
    node.children = kept


def _para_score(node):
    return sum(len(text_of(n).strip()) for n in walk(node) if n.tag == "p")


def _depth(node):
    d = 0
    while node.parent is not None:
        d += 1
        node = node.parent
    return d


def pick_content(root):
    """Take the deepest candidate scoring within 80% of the best. A wrapper
    always outscores the <article> inside it (superset), because real pages
    put signup/bio paragraphs outside the article — the tightest container
    that still holds nearly all the paragraph text is the content."""
    cands = [n for n in walk(root)
             if n.tag in ("article", "main")
             or (n.tag in ("div", "section", "td") and CONTENT_RX.search(_class_id(n)))]
    cands += [n for n in walk(root) if n.tag == "body"]
    if not cands:
        cands = [root]
    best = max(_para_score(n) for n in cands)
    if best <= 0:
        return max(cands, key=_para_score)
    tight = [n for n in cands if _para_score(n) >= 0.8 * best]
    return max(tight, key=_depth)


def _norm_ws(s):
    return re.sub(r"\s+", " ", s or "").strip()


def _safe_url(base_url, val):
    if not val:
        return None
    u = urljoin(base_url, val.strip())
    return u if u.startswith(("http://", "https://")) else None


def _serialize(node, base_url, title, out):
    for c in node.children:
        if isinstance(c, str):
            out.append(html.escape(c, quote=False))
            continue
        tag = c.tag
        if tag == "h1":
            # An in-article h1 usually repeats the page title; drop the dup,
            # demote any other h1 so the reader's own title stays the only h1.
            if _norm_ws(text_of(c)).lower() == _norm_ws(title or "").lower():
                continue
            tag = "h2"
        if tag not in ALLOWED:
            _serialize(c, base_url, title, out)      # unwrap unknown containers
            continue
        if tag == "a":
            href = _safe_url(base_url, c.attrs.get("href"))
            if not href:
                _serialize(c, base_url, title, out)   # linkless <a> reads as text
                continue
            out.append(f'<a href="{html.escape(href, quote=True)}" target="_blank" rel="noopener">')
            _serialize(c, base_url, title, out)
            out.append("</a>")
            continue
        if tag == "img":
            src = _safe_url(base_url, c.attrs.get("src") or c.attrs.get("data-src"))
            if src:
                alt = html.escape(c.attrs.get("alt") or "", quote=True)
                out.append(f'<img src="{html.escape(src, quote=True)}" alt="{alt}" loading="lazy">')
            continue
        if tag in ("br", "hr"):
            out.append(f"<{tag}>")
            continue
        inner = []
        _serialize(c, base_url, title, inner)
        body = "".join(inner)
        if tag == "p" and not body.strip():
            continue
        out.append(f"<{tag}>{body}</{tag}>")


def serialize_content(node, base_url, title):
    out = []
    _serialize(node, base_url, title, out)
    return "".join(out).strip()


# ---------------------------------------------------------------- metadata

def _meta_map(root):
    metas = {}
    for n in walk(root):
        if n.tag != "meta":
            continue
        key = n.attrs.get("property") or n.attrs.get("name")
        val = n.attrs.get("content")
        if key and val and key.lower() not in metas:
            metas[key.lower()] = val.strip()
    return metas


def _json_ld(root):
    for n in walk(root):
        if n.tag == "script" and "ld+json" in (n.attrs.get("type") or ""):
            try:
                data = json.loads(text_of(n))
            except (json.JSONDecodeError, ValueError):
                continue
            for obj in data if isinstance(data, list) else [data]:
                if isinstance(obj, dict):
                    yield obj


def _iso_date(s):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s or "")
    return m.group(1) if m else None


def _squash(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def extract_metadata(root, url):
    metas = _meta_map(root)
    ld = {}
    for obj in _json_ld(root):
        t = obj.get("@type") or ""
        if "Article" in (t if isinstance(t, str) else " ".join(t)):
            ld = obj
            break
    title_el = next((n for n in walk(root) if n.tag == "title"), None)
    title = (metas.get("og:title") or metas.get("twitter:title")
             or ld.get("headline")
             or (_norm_ws(text_of(title_el)) if title_el else None))
    host = urlsplit(url).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    source = metas.get("og:site_name") or host
    # "Post Title | Site Name" → title "Post Title"; the suffix becomes the
    # source when we had nothing better than the domain. Only when the suffix
    # actually names the site — a suffix that is part of the title stays.
    if title:
        parts = re.split(r"\s+[|–—-]\s+", title)
        if len(parts) > 1:
            suffix = parts[-1].strip()
            sq = _squash(suffix)
            if sq and (sq in _squash(host) or _squash(host) in sq
                       or sq == _squash(metas.get("og:site_name"))):
                title = title[: len(title) - len(parts[-1])].rstrip()
                title = re.sub(r"[\s|–—-]+$", "", title)
                if not metas.get("og:site_name"):
                    source = suffix
    published = _iso_date(metas.get("article:published_time")
                          or ld.get("datePublished") or "")
    return {
        "title": title,
        "source": source,
        "description": metas.get("og:description") or metas.get("description"),
        "image": _safe_url(url, metas.get("og:image") or metas.get("twitter:image")),
        "published": published,
    }


# ---------------------------------------------------------------- top level

WORDS_PER_MINUTE = 225


def read_time_label(word_count):
    return f"{max(1, round((word_count or 0) / WORDS_PER_MINUTE))} min read"


def normalize_url(url):
    p = urlsplit(url.strip())
    host = p.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    return host + p.path.rstrip("/")


def blog_id(url):
    return "b-" + hashlib.sha1(normalize_url(url).encode()).hexdigest()[:12]


def extract(html_text, url):
    root = parse_tree(html_text)
    meta = extract_metadata(root, url)          # before pruning: needs <head>
    prune_chrome(root)
    content = pick_content(root)
    body_html = serialize_content(content, url, meta["title"])
    words = len(re.findall(r"\w+", re.sub(r"<[^>]+>", " ", body_html)))
    return {**meta, "html": body_html, "word_count": words}


def fetch_html(url, timeout=30):
    req = urllib.request.Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        enc = (resp.headers.get("Content-Encoding") or "").lower()
        if enc == "gzip":
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        elif enc == "deflate":
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        ctype = resp.headers.get("Content-Type") or ""
        m = re.search(r"charset=([\w-]+)", ctype)
        charset = m.group(1) if m else "utf-8"
        final_url = resp.geturl() or url
    try:
        return raw.decode(charset, errors="replace"), final_url
    except LookupError:
        return raw.decode("utf-8", errors="replace"), final_url
