"""Behavioural tests for the live sitemap, RSS feed and robots.txt."""

import pytest
from django.utils import timezone

from apps.blog.models import Post
from apps.discography.models import Artist, Lyric, Release, ReleaseType
from apps.pages.models import Page
from apps.resources.models import KIND_OFFICIAL, Resource

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _canonical_base_url(settings):
    """Pin the canonical host so the domain assertions don't depend on a local .env."""
    settings.SITE_BASE_URL = "https://fluke.fm"


@pytest.fixture
def seeded():
    fluke = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    release = Release.objects.create(
        name="Risotto", artist=fluke, type=rtype, year=1997, is_published=True
    )
    Release.objects.create(
        name="Hidden Record", artist=fluke, type=rtype, year=2000, is_published=False
    )
    post = Post.objects.create(
        title="Hello World", excerpt="An announcement", is_published=True,
        published_at=timezone.now(),
    )
    Post.objects.create(title="Draft Post", is_published=False)
    Resource.objects.create(title="Live Set", kind=KIND_OFFICIAL, is_published=True)
    Page.objects.create(title="About", is_published=True)
    Page.objects.create(title="Secret Draft", is_published=False)
    Lyric.objects.create(title="You Got Me", artist=fluke, lyrics="You got me, baby")
    return {"release": release, "post": post}


def test_sitemap_returns_xml_with_published_url(client, seeded):
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert "xml" in response["Content-Type"]
    body = response.content.decode()
    # URLs are absolute and pinned to the canonical SITE_BASE_URL host.
    assert f"https://fluke.fm{seeded['post'].get_absolute_url()}" in body
    assert f"https://fluke.fm{seeded['release'].get_absolute_url()}" in body
    assert "testserver" not in body


def test_sitemap_excludes_draft_content(client, seeded):
    response = client.get("/sitemap.xml")
    body = response.content.decode()
    assert "/secret-draft/" not in body
    assert "hidden-record" not in body
    assert "draft-post" not in body


def test_sitemap_includes_section_indexes(client, seeded):
    response = client.get("/sitemap.xml")
    body = response.content.decode()
    assert "https://fluke.fm/" in body
    assert "/news/" in body
    assert "/discography/" in body
    assert "/resources/" in body


def test_feed_returns_xml_and_lists_published_post(client, seeded):
    response = client.get("/feed.xml")
    assert response.status_code == 200
    assert "xml" in response["Content-Type"]
    body = response.content.decode()
    assert "Hello World" in body
    assert "Draft Post" not in body
    assert "Fluke" in body


def test_robots_txt_is_plain_text_with_sitemap_line(client, seeded):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    body = response.content.decode()
    assert "User-agent: *" in body
    assert "Sitemap: https://fluke.fm/sitemap.xml" in body


def test_atom_feed_returns_atom_and_lists_published_post(client, seeded):
    response = client.get("/feed.atom")
    assert response.status_code == 200
    assert "atom" in response["Content-Type"]
    body = response.content.decode()
    assert "Hello World" in body
    assert "Draft Post" not in body
    assert "Fluke" in body


def test_footer_links_to_both_feeds(client, seeded):
    body = client.get("/news/").content.decode()
    # The visible footer anchors (the <link> autodiscovery tags have no text).
    assert ">RSS</a>" in body
    assert ">Atom</a>" in body
    assert "/feed.atom" in body
