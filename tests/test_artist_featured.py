"""An artist's page also lists releases they're only a *featured* artist on.

Releases where the artist is the primary act show under "Releases"; releases
where they merely guest (``Release.featured_artists``) must also appear, without
duplicating anything already listed.
"""

import pytest

from apps.discography.models import Artist, Release, ReleaseType

pytestmark = pytest.mark.django_db


@pytest.fixture
def rtype():
    return ReleaseType.objects.create(name="Singles")


def test_artist_page_lists_releases_they_are_featured_on(client, rtype):
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    guest = Artist.objects.create(name="Jon Fugler", slug="jon-fugler")
    rel = Release.objects.create(
        name="Atom Bomb", artist=fluke, type=rtype, year=1996, is_published=True
    )
    rel.featured_artists.add(guest)

    html = client.get(guest.get_absolute_url()).content.decode()

    assert "Atom Bomb" in html
    assert f'href="{rel.get_absolute_url()}"' in html


def test_featured_only_artist_with_no_releases_of_their_own_still_lists_them(client, rtype):
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    guest = Artist.objects.create(name="Mike Tournier", slug="mike-tournier")
    rel = Release.objects.create(
        name="Bullet", artist=fluke, type=rtype, year=1995, is_published=True
    )
    rel.featured_artists.add(guest)

    html = client.get(guest.get_absolute_url()).content.decode()

    # The guest has no releases of their own, but the featured one must show.
    assert guest.releases.count() == 0
    assert f'href="{rel.get_absolute_url()}"' in html


def test_featured_release_is_not_duplicated_when_artist_is_also_the_primary(client, rtype):
    artist = Artist.objects.create(name="Fluke", slug="fluke")
    rel = Release.objects.create(
        name="Slid", artist=artist, type=rtype, year=1993, is_published=True
    )
    rel.featured_artists.add(artist)  # both the primary act and a credited feature

    html = client.get(artist.get_absolute_url()).content.decode()

    assert html.count(f'href="{rel.get_absolute_url()}"') == 1


def test_unpublished_featured_release_is_hidden(client, rtype):
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    guest = Artist.objects.create(name="Secret Guest", slug="secret-guest")
    rel = Release.objects.create(
        name="Unreleased Collab", artist=fluke, type=rtype, year=2099, is_published=False
    )
    rel.featured_artists.add(guest)

    html = client.get(guest.get_absolute_url()).content.decode()

    assert "Unreleased Collab" not in html
