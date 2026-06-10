"""Release-level cover display: hoist covers when only one edition has images."""

import pytest

from apps.discography.models import Artist, CoverImage, Edition, Release, ReleaseType

pytestmark = pytest.mark.django_db


def _release():
    artist = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    return Release.objects.create(name="Risotto", slug="risotto", artist=artist, type=rtype)


def test_covers_hoisted_when_one_edition_has_images():
    release = _release()
    edition = Edition.objects.create(release=release)
    Edition.objects.create(release=release)  # a second edition with no images
    CoverImage.objects.create(edition=edition, kind="front", image="covers/front.jpg", display_order=0)
    CoverImage.objects.create(edition=edition, kind="back", image="covers/back.jpg", display_order=1)

    assert [c.kind for c in release.cover_images_for_release] == ["front", "back"]


def test_not_hoisted_when_no_edition_has_images():
    release = _release()
    Edition.objects.create(release=release)
    assert list(release.cover_images_for_release) == []


def test_not_hoisted_when_multiple_editions_have_images():
    release = _release()
    e1 = Edition.objects.create(release=release)
    e2 = Edition.objects.create(release=release)
    CoverImage.objects.create(edition=e1, image="covers/a.jpg")
    CoverImage.objects.create(edition=e2, image="covers/b.jpg")
    assert list(release.cover_images_for_release) == []


def test_cover_rows_without_a_file_are_ignored():
    release = _release()
    edition = Edition.objects.create(release=release)
    CoverImage.objects.create(edition=edition, kind="front", image="")  # row, but no file
    assert list(release.cover_images_for_release) == []


def test_release_page_shows_hoisted_covers(client):
    release = _release()
    edition = Edition.objects.create(release=release)
    CoverImage.objects.create(edition=edition, kind="front", image="covers/front.jpg", alt_text="Front")

    html = client.get(release.get_absolute_url()).content.decode()
    assert "covers--release" in html        # the release-level block rendered
    assert "covers/front.jpg" in html
    assert "gallery.js" in html             # the lightbox/modal gallery is wired up
