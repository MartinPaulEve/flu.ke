"""Each page type should emit its own Open Graph tags (title + image) so shared
links get a tailored preview card, not just the generic site default.
"""

import pytest

from apps.discography.models import Artist, Lyric, Release, ReleaseType

pytestmark = pytest.mark.django_db


def test_homepage_emits_description_and_url(client):
    html = client.get("/").content.decode()
    assert 'property="og:description"' in html
    assert 'property="og:url"' in html
    assert "og-default.png" in html


def test_artist_page_emits_its_own_og(client):
    Artist.objects.create(name="Yuki", slug="yuki")
    html = client.get("/discography/yuki/").content.decode()
    assert "og/artist-" in html            # per-object image, not the default
    assert 'content="Yuki"' in html        # og:title from the artist name


def test_lyric_page_emits_its_own_og(client):
    Lyric.objects.create(title="Bullet", slug="bullet", lyrics="la la la")
    html = client.get("/lyrics/bullet/").content.decode()
    assert "og/lyric-" in html
    assert 'content="Bullet"' in html


def test_release_page_uses_name_for_title_and_its_own_image(client):
    artist = Artist.objects.create(name="Fluke", slug="fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    Release.objects.create(name="Risotto", slug="risotto", artist=artist, type=rtype, year=1997)
    html = client.get("/discography/fluke/risotto/").content.decode()
    assert "og/release-" in html
    assert 'content="Risotto"' in html
