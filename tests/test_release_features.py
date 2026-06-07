"""Releases can credit featured artists, shown as '(feat. …)' after the title."""

import pytest

from apps.discography.models import Artist, Release, ReleaseType

pytestmark = pytest.mark.django_db


def _release(name="The Fruit", artist_name="Sander Kleinenberg"):
    artist = Artist.objects.create(name=artist_name)
    rtype = ReleaseType.objects.create(name="Singles")
    return Release.objects.create(name=name, artist=artist, type=rtype, year=2003)


def test_no_featured_artists_leaves_the_name_unchanged():
    release = _release()
    assert release.featured_credit == ""
    assert release.display_name == "The Fruit"


def test_one_featured_artist():
    release = _release()
    release.featured_artists.add(Artist.objects.create(name="Jon Fugler"))
    assert release.featured_credit == "feat. Jon Fugler"
    assert release.display_name == "The Fruit (feat. Jon Fugler)"


def test_two_featured_artists():
    release = _release()
    release.featured_artists.add(Artist.objects.create(name="Aaa"), Artist.objects.create(name="Bbb"))
    assert release.featured_credit == "feat. Aaa & Bbb"
    assert release.display_name == "The Fruit (feat. Aaa & Bbb)"


def test_three_featured_artists():
    release = _release()
    for name in ("Aaa", "Bbb", "Ccc"):
        release.featured_artists.add(Artist.objects.create(name=name))
    assert release.featured_credit == "feat. Aaa, Bbb & Ccc"


def test_display_title_keeps_artist_for_non_fluke():
    release = _release()  # artist is Sander Kleinenberg
    release.featured_artists.add(Artist.objects.create(name="Jon Fugler"))
    assert release.display_title == "The Fruit (feat. Jon Fugler) (Sander Kleinenberg)"


def test_display_title_omits_artist_for_fluke():
    release = _release(name="Atom Bomb", artist_name="Fluke")
    release.featured_artists.add(Artist.objects.create(name="Jon Fugler"))
    assert release.display_title == "Atom Bomb (feat. Jon Fugler)"


def test_seo_title_includes_feat():
    release = _release()
    release.featured_artists.add(Artist.objects.create(name="Jon Fugler"))
    assert release.resolved_seo_title() == "The Fruit (feat. Jon Fugler)"


def test_release_detail_heading_shows_feat(client):
    release = _release()
    release.featured_artists.add(Artist.objects.create(name="Jon Fugler"))
    html = client.get(release.get_absolute_url()).content.decode()
    assert "The Fruit (feat. Jon Fugler)" in html
