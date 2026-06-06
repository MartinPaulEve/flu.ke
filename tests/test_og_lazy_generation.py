"""Visiting an object's page generates its OG image on demand when it's missing
(e.g. legacy content imported before OG generation existed)."""

import pytest

from apps.discography.models import Artist, Lyric, Release, ReleaseType

pytestmark = pytest.mark.django_db


def _clear_og(obj):
    obj.og_image.delete(save=False)
    type(obj).objects.filter(pk=obj.pk).update(og_image="")


def test_visiting_artist_page_generates_missing_og_image(client):
    artist = Artist.objects.create(name="ANAXATON6", slug="anaxaton6")
    _clear_og(artist)

    client.get("/discography/anaxaton6/")

    artist.refresh_from_db()
    assert artist.og_image.name


def test_visiting_release_page_generates_missing_og_image(client):
    artist = Artist.objects.create(name="Fluke", slug="fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    release = Release.objects.create(
        name="Risotto", slug="risotto", artist=artist, type=rtype, year=1997
    )
    _clear_og(release)

    client.get("/discography/fluke/risotto/")

    release.refresh_from_db()
    assert release.og_image.name


def test_visiting_lyric_page_generates_missing_og_image(client):
    lyric = Lyric.objects.create(title="Bullet", slug="bullet", lyrics="la la")
    _clear_og(lyric)

    client.get("/lyrics/bullet/")

    lyric.refresh_from_db()
    assert lyric.og_image.name
