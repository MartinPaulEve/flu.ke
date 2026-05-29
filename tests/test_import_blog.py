"""Integration test for import_blog with the network mocked via responses."""

import pytest
import responses
from django.core.management import call_command

from apps.blog.models import Post
from apps.importers.wayback import cdx_url, snapshot_url

pytestmark = pytest.mark.django_db

DOMAIN = "2bitpie.net"
POST_URL = "http://www.2bitpie.net/2009/06/dark-like-snow/"
FEED_URL = "http://www.2bitpie.net/feed/"
TS = "20090617070854"

POST_HTML = """
<html><head>
  <meta property="og:title" content="Dark Like Snow is out">
  <meta property="article:published_time" content="2009-06-17T07:08:54+00:00">
</head><body>
  <div class="entry-content"><p>The new Yuki record is here.</p></div>
</body></html>
"""


def _mock_wayback():
    responses.add(
        responses.GET,
        cdx_url(DOMAIN),
        json=[["timestamp", "original"], [TS, POST_URL], ["20100101000000", FEED_URL]],
        status=200,
    )
    responses.add(responses.GET, snapshot_url(TS, POST_URL), body=POST_HTML, status=200)


@responses.activate
def test_recovers_post_and_skips_non_posts():
    _mock_wayback()
    call_command("import_blog", domain=DOMAIN, delay=0)

    assert Post.objects.count() == 1
    post = Post.objects.get()
    assert post.title == "Dark Like Snow is out"
    assert post.source_url == POST_URL
    assert post.is_published is True  # complete recovery is published
    assert post.import_confidence == "complete"


@responses.activate
def test_rerun_is_idempotent():
    _mock_wayback()
    call_command("import_blog", domain=DOMAIN, delay=0)
    _mock_wayback()
    call_command("import_blog", domain=DOMAIN, delay=0)
    assert Post.objects.count() == 1


@responses.activate
def test_manually_edited_posts_are_not_overwritten():
    _mock_wayback()
    call_command("import_blog", domain=DOMAIN, delay=0)
    post = Post.objects.get()
    post.body = "Hand-written replacement."
    post.manually_edited = True
    post.save()

    _mock_wayback()
    call_command("import_blog", domain=DOMAIN, delay=0)

    post.refresh_from_db()
    assert post.body == "Hand-written replacement."
