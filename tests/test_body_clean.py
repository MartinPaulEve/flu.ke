"""Tests for the pure post-body cleaner (share/related stripping + URL remap)."""

from apps.blog.body_clean import clean_body_html

SHARE = (
    '<div class="sharedaddy sd-sharing-enabled"><div class="sd-block sd-social">'
    '<h3 class="sd-title">Share this:</h3><ul><li class="share-twitter">'
    '<a href="x?share=twitter">Click to share on Twitter</a></li></ul></div></div>'
)
RELATED = (
    '<div class="jp-relatedposts" id="jp-relatedposts">'
    '<h3 class="jp-relatedposts-headline"><em>Related</em></h3></div>'
)
TWEET = '<p><a href="http://t/?tweet"><img src="http://x/icons/en/twitter/tt-twitter-big1.png?w=640"/></a></p>'


def _res(url):
    return "/media/posts/orange_flower.jpg" if "orange_flower" in url else None


def test_removes_share_related_and_tweet_button():
    html = "<p>Real content here.</p>" + TWEET + SHARE + RELATED
    out, removed, _ = clean_body_html(html, lambda u: None)
    assert "Real content here." in out
    assert "sharedaddy" not in out
    assert "jp-relatedposts" not in out
    assert "tt-twitter" not in out
    assert "Share this" not in out
    assert "Click to share on Twitter" not in out
    assert removed >= 3


def test_keeps_paragraph_text_when_removing_inline_share_button():
    html = '<p>Final words. <a href="t"><img src="tt-twitter-big1.png"/></a></p>'
    out, _, _ = clean_body_html(html, lambda u: None)
    assert "Final words." in out
    assert "tt-twitter" not in out
    assert "<p>" in out  # the paragraph itself is kept


def test_remaps_image_when_available():
    html = '<img src="http://www.2bitpie.net/2bitpie/Files/orange_flower.jpg"/>'
    out, _, remapped = clean_body_html(html, _res)
    assert "/media/posts/orange_flower.jpg" in out
    assert "2bitpie.net" not in out
    assert remapped == 1


def test_remaps_file_hyperlink():
    html = '<a href="http://www.2bitpie.net/2bitpie/Files/orange_flower.jpg">photo</a>'
    out, _, remapped = clean_body_html(html, _res)
    assert 'href="/media/posts/orange_flower.jpg"' in out
    assert remapped == 1


def test_leaves_unmatched_files_url_untouched():
    html = '<img src="http://x/Files/unknown.jpg"/>'
    out, _, remapped = clean_body_html(html, lambda u: None)
    assert "Files/unknown.jpg" in out
    assert remapped == 0


def test_ignores_non_files_urls():
    html = '<a href="https://example.com/page">link</a>'
    out, _, remapped = clean_body_html(html, lambda u: "/should-not-be-used")
    assert "example.com/page" in out
    assert remapped == 0
