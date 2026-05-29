"""Unit tests for the pure Wayback recovery helpers."""

import pytest

from apps.importers.wayback import is_post_candidate, recover_post

POST_HTML = """
<html><head>
  <meta property="og:title" content="Dark Like Snow is out">
  <meta property="article:published_time" content="2009-06-17T07:08:54+00:00">
  <title>Dark Like Snow is out | 2 Bit Pie</title>
</head><body>
  <article>
    <h1 class="entry-title">Dark Like Snow is out</h1>
    <div class="entry-content"><p>The new Yuki record is here.</p><p>Grab it.</p></div>
  </article>
</body></html>
"""

NO_DATE_HTML = """
<html><head><title>An old note - 2 Bit Pie</title></head><body>
  <h2 class="entrytitle">An old note</h2>
  <div class="entry"><p>Some words survive.</p></div>
</body></html>
"""

THIN_HTML = "<html><head><title>Just a title | 2 Bit Pie</title></head><body></body></html>"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("http://www.2bitpie.net/2009/06/dark-like-snow/", True),
        ("http://www.2bitpie.net/about-the-band/", True),
        ("http://www.2bitpie.net/feed/", False),
        ("http://www.2bitpie.net/category/news/", False),
        ("http://www.2bitpie.net/wp-content/uploads/x.jpg", False),
        ("http://www.2bitpie.net/", False),
    ],
)
def test_is_post_candidate(url, expected):
    assert is_post_candidate(url) is expected


def test_recover_complete_post():
    post = recover_post(POST_HTML, "http://www.2bitpie.net/2009/06/dark-like-snow/")
    assert post.title == "Dark Like Snow is out"
    assert "The new Yuki record is here." in post.body
    assert post.published_at is not None
    assert post.published_at.year == 2009
    assert post.import_confidence == "complete"
    assert post.source_url.endswith("/dark-like-snow/")


def test_recover_partial_when_date_missing():
    post = recover_post(NO_DATE_HTML, "http://x/2/")
    assert post.title == "An old note"
    assert "Some words survive." in post.body
    assert post.published_at is None
    assert post.import_confidence == "partial"


def test_recover_stub_when_only_title():
    post = recover_post(THIN_HTML, "http://x/3/")
    assert post.title == "Just a title"  # title-suffix stripped
    assert post.body == ""
    assert post.import_confidence == "stub"
