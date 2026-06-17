"""The footer's "Discography API" link points at the API entry for the item on
the page (a release, artist or lyric), or the API root on every other page."""

import pytest

from apps.discography.models import Artist, Lyric, Release, ReleaseType

pytestmark = pytest.mark.django_db


def test_release_page_footer_links_to_its_api_entry(client):
    fluke = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    release = Release.objects.create(
        name="Risotto", artist=fluke, type=rtype, year=1997, is_published=True
    )
    response = client.get(release.get_absolute_url())
    assert response.status_code == 200
    html = response.content.decode()
    assert f'href="/discography/api/releases/{release.slug}/"' in html


def test_artist_page_footer_links_to_its_api_entry(client):
    artist = Artist.objects.create(name="Syntax")
    response = client.get(artist.get_absolute_url())
    assert response.status_code == 200
    html = response.content.decode()
    assert f'href="/discography/api/artists/{artist.slug}/"' in html


def test_lyric_page_footer_links_to_its_api_entry(client):
    fluke = Artist.objects.create(name="Fluke")
    lyric = Lyric.objects.create(title="You Got Me", artist=fluke, lyrics="words")
    response = client.get(lyric.get_absolute_url())
    assert response.status_code == 200
    html = response.content.decode()
    assert f'href="/discography/api/lyrics/{lyric.slug}/"' in html


def test_non_discography_page_footer_falls_back_to_api_root(client):
    response = client.get("/news/")
    assert response.status_code == 200
    html = response.content.decode()
    assert 'href="/discography/api/"' in html
