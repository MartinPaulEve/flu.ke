"""Every public content type should auto-generate an Open Graph image on save,
and the SEO title should fall back to a model's ``name`` when it has no ``title``.
"""

import pytest

from apps.discography.models import Artist, Lyric, Release, ReleaseType
from apps.pages.models import Page
from apps.resources.models import Resource

pytestmark = pytest.mark.django_db


def _release(name="Risotto"):
    artist = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    return Release.objects.create(name=name, artist=artist, type=rtype, year=1997)


def test_page_save_generates_og_image():
    page = Page.objects.create(title="About")
    assert page.og_image.name and page.og_image.name.endswith(".png")


def test_resource_save_generates_og_image():
    resource = Resource.objects.create(title="X-Files", kind="fan")
    assert resource.og_image.name and resource.og_image.name.endswith(".png")


def test_release_save_generates_og_image():
    release = _release()
    assert release.og_image.name and release.og_image.name.endswith(".png")


def test_artist_save_generates_og_image():
    artist = Artist.objects.create(name="Yuki")
    assert artist.og_image.name and artist.og_image.name.endswith(".png")


def test_lyric_save_generates_og_image():
    lyric = Lyric.objects.create(title="Bullet")
    assert lyric.og_image.name and lyric.og_image.name.endswith(".png")


def test_existing_og_image_is_not_regenerated_on_edit():
    page = Page.objects.create(title="Original")
    original = page.og_image.name
    page.title = "Changed title"
    page.save()
    page.refresh_from_db()
    assert page.og_image.name == original


def test_resolved_seo_title_falls_back_to_name():
    release = _release(name="Atom Bomb")
    assert release.resolved_og_title() == "Atom Bomb"
    assert Artist.objects.create(name="Syntax").resolved_og_title() == "Syntax"
