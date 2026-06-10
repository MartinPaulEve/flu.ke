"""Release OG cards draw on the front cover; covers show only in their edition."""

import pytest
from django.core.files.base import ContentFile

from apps.discography.models import Artist, CoverImage, Edition, Release, ReleaseType

pytestmark = pytest.mark.django_db


def _release():
    artist = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    return Release.objects.create(name="Risotto", slug="risotto", artist=artist, type=rtype)


def _cover(edition, kind, content):
    cover = CoverImage.objects.create(edition=edition, kind=kind)
    cover.image.save(f"{kind}.png", ContentFile(content), save=True)
    return cover


def test_og_cover_prefers_the_front_cover():
    release = _release()
    edition = Edition.objects.create(release=release)
    _cover(edition, "back", b"BACK")
    _cover(edition, "front", b"FRONT")
    assert release._og_cover_bytes() == b"FRONT"


def test_og_cover_falls_back_to_any_cover():
    release = _release()
    edition = Edition.objects.create(release=release)
    _cover(edition, "back", b"BACK")
    assert release._og_cover_bytes() == b"BACK"


def test_og_cover_is_none_without_covers():
    release = _release()
    Edition.objects.create(release=release)
    assert release._og_cover_bytes() is None


def test_release_page_shows_edition_covers_not_a_top_level_block(client):
    release = _release()
    edition = Edition.objects.create(release=release)
    cover = _cover(edition, "front", b"x")

    html = client.get(release.get_absolute_url()).content.decode()
    assert "covers--release" not in html      # no hoisted covers at the top
    assert cover.image.name in html           # still shown in the edition section
    assert "gallery.js" in html               # lightbox still wired for edition covers
