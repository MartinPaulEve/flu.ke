"""Rewriting hard-coded 2bitpie.net links in post content to site-relative paths."""

from apps.blog.links import relativize_2bitpie_links


def test_rewrites_https_www_link_to_relative_path():
    assert (
        relativize_2bitpie_links('<a href="https://www.2bitpie.net/news/2009/foo/">x</a>')
        == '<a href="/news/2009/foo/">x</a>'
    )


def test_rewrites_http_bare_domain_link_in_text():
    assert (
        relativize_2bitpie_links("see http://2bitpie.net/wp-content/uploads/a.jpg here")
        == "see /wp-content/uploads/a.jpg here"
    )


def test_bare_domain_becomes_root():
    assert relativize_2bitpie_links('<a href="https://2bitpie.net">home</a>') == '<a href="/">home</a>'


def test_preserves_query_and_fragment():
    assert relativize_2bitpie_links("https://www.2bitpie.net/p?x=1#f") == "/p?x=1#f"


def test_is_case_insensitive_on_the_domain():
    assert relativize_2bitpie_links("HTTPS://WWW.2BitPie.NET/News") == "/News"


def test_handles_protocol_relative_links():
    assert relativize_2bitpie_links('src="//www.2bitpie.net/img/x.png"') == 'src="/img/x.png"'


def test_handles_multiple_links():
    assert (
        relativize_2bitpie_links("a https://2bitpie.net/1 b http://www.2bitpie.net/2 c")
        == "a /1 b /2 c"
    )


def test_leaves_other_domains_untouched():
    text = '<a href="https://fluke.fm/x">a</a> and https://example.com/2bitpie.net/y'
    assert relativize_2bitpie_links(text) == text


def test_empty_and_none_pass_through():
    assert relativize_2bitpie_links("") == ""
    assert relativize_2bitpie_links(None) is None
