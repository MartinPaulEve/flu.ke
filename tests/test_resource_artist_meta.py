"""The resource page's metadata bar shows the artist, linked when they have a page."""

import pytest

from apps.discography.models import Artist, Release, ReleaseType
from apps.resources.models import KIND_OFFICIAL, Resource

pytestmark = pytest.mark.django_db


def test_artist_with_releases_is_linked_in_the_metadata_bar(client):
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    ReleaseType.objects.create(name="Albums")
    Release.objects.create(
        name="Risotto", artist=fluke, type=ReleaseType.objects.first(),
        year=1997, is_published=True,
    )
    r = Resource.objects.create(
        title="A Fluke Promo", kind=KIND_OFFICIAL, artist=fluke, is_published=True
    )

    html = client.get(r.get_absolute_url()).content.decode()

    assert "Fluke" in html
    assert f'href="{fluke.get_absolute_url()}"' in html


def test_artist_without_a_page_is_shown_but_not_linked(client):
    ghost = Artist.objects.create(name="Mike Tournier", slug="mike-tournier")  # no releases
    r = Resource.objects.create(
        title="A solo thing", kind=KIND_OFFICIAL, artist=ghost, is_published=True
    )

    html = client.get(r.get_absolute_url()).content.decode()

    assert "Mike Tournier" in html
    assert f'href="{ghost.get_absolute_url()}"' not in html


def test_no_artist_means_no_artist_label(client):
    r = Resource.objects.create(
        title="Anonymous upload", kind=KIND_OFFICIAL, license="CC-BY", is_published=True
    )

    html = client.get(r.get_absolute_url()).content.decode()

    assert "Artist" not in html
