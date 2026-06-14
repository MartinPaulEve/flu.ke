"""News posts can surface related releases and artists in a side rail.

A Post may link releases (``related_releases``) and artists (``related_artists``)
that show in the post's sidebar. Only published releases are linked; artists are
always linkable. These exercise the rendered page, not the layout specifics.
"""

import pytest
from django.utils import timezone

from apps.blog.models import Post
from apps.discography.models import Artist, Release, ReleaseType

pytestmark = pytest.mark.django_db


@pytest.fixture
def post():
    return Post.objects.create(
        title="New Anaxaton6 video",
        body="Some words about the video.",
        is_published=True,
        published_at=timezone.now(),
    )


@pytest.fixture
def release():
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    return Release.objects.create(
        name="Risotto", artist=fluke, type=rtype, year=1997, is_published=True
    )


def test_related_release_is_linked_on_the_post_page(client, post, release):
    post.related_releases.add(release)

    html = client.get(post.get_absolute_url()).content.decode()

    assert "Risotto" in html
    assert f'href="{release.get_absolute_url()}"' in html


def test_related_artist_is_linked_on_the_post_page(client, post):
    artist = Artist.objects.create(name="Mike Tournier", slug="mike-tournier")
    post.related_artists.add(artist)

    html = client.get(post.get_absolute_url()).content.decode()

    assert "Mike Tournier" in html
    assert f'href="{artist.get_absolute_url()}"' in html


def test_unpublished_related_release_is_not_linked(client, post):
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    hidden = Release.objects.create(
        name="Hidden Record", artist=fluke, type=rtype, year=2000, is_published=False
    )
    post.related_releases.add(hidden)

    html = client.get(post.get_absolute_url()).content.decode()

    assert "Hidden Record" not in html


def test_post_without_relations_omits_the_related_headings(client, post):
    html = client.get(post.get_absolute_url()).content.decode()

    assert "Related releases" not in html
    assert "Related artists" not in html
