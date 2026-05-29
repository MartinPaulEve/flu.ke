from django.utils.safestring import SafeString

from apps.core.templatetags.content import markdownify


def test_renders_basic_markdown():
    html = markdownify("**bold** and *italic*")
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html


def test_output_is_marked_safe():
    assert isinstance(markdownify("# Heading"), SafeString)


def test_handles_empty_input():
    assert markdownify("") == ""
    assert markdownify(None) == ""
