"""A release can opt out of the '(artist, artist)' suffix on the discography listing."""

import pytest

from apps.discography.models import Artist, Release, ReleaseType

pytestmark = pytest.mark.django_db


def _collab():
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    avery = Artist.objects.create(name="Daniel Avery", slug="daniel-avery")
    rtype = ReleaseType.objects.create(name="Singles")
    rel = Release.objects.create(
        name="Atom Bomb (Daniel Avery Nuclear Summer Remix)",
        artist=fluke, type=rtype, year=2026, is_published=True,
    )
    rel.additional_artists.add(avery)
    return rel


def test_artist_list_is_shown_by_default():
    rel = _collab()
    assert rel.display_title == "Atom Bomb (Daniel Avery Nuclear Summer Remix) (Fluke, Daniel Avery)"


def test_hide_artist_list_drops_the_bracketed_artists():
    rel = _collab()
    rel.hide_artist_list = True
    rel.save()
    assert rel.display_title == "Atom Bomb (Daniel Avery Nuclear Summer Remix)"


def test_discography_listing_omits_the_artist_list_when_hidden(client):
    rel = _collab()
    rel.hide_artist_list = True
    rel.save()
    html = client.get("/discography/").content.decode()
    assert "Atom Bomb (Daniel Avery Nuclear Summer Remix)" in html
    assert "(Fluke, Daniel Avery)" not in html
