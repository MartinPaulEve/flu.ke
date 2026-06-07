"""Admin action to move a track (its file + metadata) to another edition/release."""

import pytest
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.urls import reverse

from apps.discography.models import Artist, Edition, Release, ReleaseType, Track

pytestmark = pytest.mark.django_db

CHANGELIST = "admin:discography_track_changelist"


def _setup():
    artist = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Singles")
    r1 = Release.objects.create(name="Release1", artist=artist, type=rtype)
    r2 = Release.objects.create(name="Release2", artist=artist, type=rtype)
    e1 = Edition.objects.create(release=r1)
    e2 = Edition.objects.create(release=r2)
    track = Track.objects.create(edition=e1, name="file1", track_number="1", length="3:00")
    return track, e2


def test_move_action_renders_edition_picker(admin_client):
    track, _ = _setup()
    resp = admin_client.post(
        reverse(CHANGELIST),
        {"action": "move_to_edition", ACTION_CHECKBOX_NAME: [str(track.pk)]},
    )
    assert resp.status_code == 200
    assert b"Target edition" in resp.content


def test_move_action_reassigns_track_keeping_metadata(admin_client):
    track, e2 = _setup()
    admin_client.post(
        reverse(CHANGELIST),
        {
            "action": "move_to_edition",
            ACTION_CHECKBOX_NAME: [str(track.pk)],
            "apply": "1",
            "edition": str(e2.pk),
        },
    )
    track.refresh_from_db()
    assert track.edition_id == e2.pk           # moved to Release2's edition
    assert track.name == "file1"               # metadata travels with it
    assert track.length == "3:00"
