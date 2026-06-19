"""A track can credit more than one remixer (multi-select)."""

import pytest
from rest_framework.test import APIClient

from apps.discography.models import Artist, Edition, Release, ReleaseType, Track

pytestmark = pytest.mark.django_db


def _track():
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    rt = ReleaseType.objects.create(name="Singles")
    rel = Release.objects.create(
        name="Atom Bomb", slug="atom-bomb", artist=fluke, type=rt, year=2026, is_published=True
    )
    ed = Edition.objects.create(release=rel, media="CD")
    track = Track.objects.create(edition=ed, name="Atom Bomb", track_number="1")
    return rel, ed, track


def test_track_can_have_multiple_remixers():
    _, _, track = _track()
    avery = Artist.objects.create(name="Daniel Avery", slug="daniel-avery")
    myagi = Artist.objects.create(name="Myagi", slug="myagi")
    track.remixers.add(avery, myagi)
    assert set(track.remixers.all()) == {avery, myagi}


def test_release_page_lists_all_remixers(client):
    rel, _, track = _track()
    track.remixers.add(Artist.objects.create(name="Daniel Avery", slug="daniel-avery"))
    track.remixers.add(Artist.objects.create(name="Myagi", slug="myagi"))
    html = client.get(rel.get_absolute_url()).content.decode()
    assert "Daniel Avery" in html
    assert "Myagi" in html


def test_api_track_lists_remixers():
    _, _, track = _track()
    track.remixers.add(Artist.objects.create(name="Daniel Avery", slug="daniel-avery"))
    resp = APIClient().get(f"/api/discography/tracks/{track.id}/")
    assert resp.status_code == 200
    slugs = [r["slug"] for r in resp.json()["remixers"]]
    assert "daniel-avery" in slugs
