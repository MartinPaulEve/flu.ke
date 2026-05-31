"""Regression: a hostile title/name must not break out of the JSON-LD script.

The release/post detail pages emit a ``<script type="application/ld+json">`` block
built from model fields. If a value containing ``</script><script>alert(1)</script>``
were emitted verbatim it would close the JSON-LD element and inject executable
markup. ``apps.core.seo.jsonld_dumps`` defends against this by escaping ``<``, ``>``
and ``&`` as JSON unicode escapes, so the payload can never break out. These tests
fetch the live detail pages and assert the dangerous sequences are escaped.
"""

import pytest
from django.utils import timezone

from apps.blog.models import Post
from apps.discography.models import Artist, Release, ReleaseType

pytestmark = pytest.mark.django_db

PAYLOAD = "</script><script>alert(1)</script>"


def _assert_jsonld_payload_is_escaped(html):
    """The page renders JSON-LD that cannot break out of its <script> element."""
    # The page does carry a JSON-LD block.
    assert "application/ld+json" in html
    # The injected markup must never appear verbatim. None of these breakout
    # sequences from the payload may survive into the HTML: the close-tag-then-open
    # breakout, the executable script, or the payload's trailing close tag.
    assert "</script><script>" not in html
    assert "<script>alert(1)" not in html
    assert "alert(1)</script>" not in html
    # The dangerous characters survive only as their JSON unicode escapes.
    assert "\\u003c" in html  # escaped "<"
    assert "\\u003e" in html  # escaped ">"


def test_release_name_cannot_break_out_of_jsonld(client):
    fluke = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    release = Release.objects.create(name=PAYLOAD, artist=fluke, type=rtype, is_published=True)

    response = client.get(release.get_absolute_url())
    assert response.status_code == 200
    _assert_jsonld_payload_is_escaped(response.content.decode())


def test_post_title_cannot_break_out_of_jsonld(client):
    post = Post.objects.create(title=PAYLOAD, is_published=True, published_at=timezone.now())

    response = client.get(post.get_absolute_url())
    assert response.status_code == 200
    _assert_jsonld_payload_is_escaped(response.content.decode())
