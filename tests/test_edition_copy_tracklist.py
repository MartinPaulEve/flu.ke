"""Admin: copy another edition's tracklist into the current edition (overwrite)."""

import pytest
from django.urls import reverse

from apps.discography.models import Artist, Edition, Release, ReleaseType, Track

pytestmark = pytest.mark.django_db


def _setup():
    artist = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    release = Release.objects.create(name="Risotto", artist=artist, type=rtype)
    source = Edition.objects.create(release=release, name="CD")
    target = Edition.objects.create(release=release, name="Vinyl")
    Track.objects.create(edition=source, name="Fly", track_number="1", length="6:01", display_order=0)
    Track.objects.create(edition=source, name="Bermuda", track_number="2", length="5:00", display_order=1)
    Track.objects.create(edition=target, name="OLD", track_number="1", display_order=0)
    return source, target


def _url(target):
    return reverse("admin:discography_edition_copy_tracklist", args=[target.pk])


def test_copy_view_renders_source_picker(admin_client):
    _, target = _setup()
    resp = admin_client.get(_url(target))
    assert resp.status_code == 200
    assert b"Copy from" in resp.content


def test_copy_overwrites_with_source_tracklist(admin_client):
    source, target = _setup()
    admin_client.post(_url(target), {"source": str(source.pk)})

    names = list(target.tracks.order_by("display_order").values_list("name", flat=True))
    assert names == ["Fly", "Bermuda"]          # old track replaced
    fly = target.tracks.get(name="Fly")
    assert fly.length == "6:01" and fly.track_number == "1"   # metadata copied
    assert source.tracks.count() == 2           # source untouched (copy, not move)


def test_change_page_has_copy_button(admin_client):
    _, target = _setup()
    html = admin_client.get(reverse("admin:discography_edition_change", args=[target.pk])).content.decode()
    assert "Copy tracklist from another edition" in html
