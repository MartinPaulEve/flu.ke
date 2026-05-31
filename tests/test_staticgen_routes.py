"""Tests for the route manifest (which pages the static site contains)."""

import pytest
from django.utils import timezone

from apps.blog.models import Post
from apps.discography.models import Artist, Lyric, Release, ReleaseType
from apps.pages.models import Page
from apps.resources.models import Resource
from apps.staticgen.routes import iter_routes

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded():
    fluke = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    release = Release.objects.create(name="Risotto", artist=fluke, type=rtype, year=1997)
    Page.objects.create(title="About", is_published=True)
    Page.objects.create(title="Secret draft", is_published=False)
    Post.objects.create(title="Hello world", is_published=True, published_at=timezone.now())
    Post.objects.create(title="Draft post", is_published=False)
    Resource.objects.create(title="Live set", kind="official", is_published=True)
    Resource.objects.create(title="Hidden", kind="fan", is_published=False)
    return {"release": release, "fluke": fluke}


def _paths(seeded=None):
    return {route.url_path for route in iter_routes()}


def test_includes_core_sections(seeded):
    paths = _paths()
    assert {"/", "/news/", "/discography/", "/resources/"} <= paths


def test_includes_published_detail_pages(seeded):
    paths = _paths()
    assert "/about/" in paths
    assert f"/news/{timezone.now().year}/hello-world/" in paths
    assert "/discography/fluke/risotto/" in paths
    assert "/discography/fluke/" in paths  # artist index
    assert "/resources/official/live-set/" in paths


def test_excludes_drafts(seeded):
    paths = _paths()
    assert "/secret-draft/" not in paths
    assert not any(p.endswith("/draft-post/") for p in paths)
    assert "/resources/fan/hidden/" not in paths


def test_lyric_pages_only_for_lyrics_with_text(seeded):
    Lyric.objects.create(title="You Got Me", lyrics="You got me, baby")
    Lyric.objects.create(title="Empty One", lyrics="")
    paths = _paths()
    assert "/lyrics/" in paths  # lyrics index
    assert "/lyrics/you-got-me/" in paths
    assert "/lyrics/empty-one/" not in paths  # no body -> no page


def test_no_lyrics_index_when_no_lyrics_have_text(seeded):
    Lyric.objects.create(title="Empty One", lyrics="")
    assert "/lyrics/" not in _paths()


def test_every_route_has_a_template(seeded):
    assert all(route.template for route in iter_routes())
