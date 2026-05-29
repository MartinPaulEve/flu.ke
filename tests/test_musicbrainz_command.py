"""musicbrainz_sync command test with musicbrainzngs fully mocked (no network)."""

import pytest
from django.core.management import call_command

from apps.discography.models import Edition, Release, Track

pytestmark = pytest.mark.django_db

RG_MBID = "11111111-1111-1111-1111-111111111111"
REL_MBID = "22222222-2222-2222-2222-222222222222"
REC_MBID = "33333333-3333-3333-3333-333333333333"


@pytest.fixture
def mocked_mb(monkeypatch, settings):
    settings.MUSICBRAINZ = {"app": "flukecms", "version": "1.0", "contact": "a@b.test"}
    import musicbrainzngs as m

    monkeypatch.setattr(m, "set_useragent", lambda *a, **k: None)
    monkeypatch.setattr(m, "set_rate_limit", lambda *a, **k: None)
    monkeypatch.setattr(
        m, "browse_release_groups", lambda **k: {"release-group-list": [{"id": RG_MBID}]}
    )
    monkeypatch.setattr(
        m,
        "get_release_group_by_id",
        lambda mbid, includes=None: {
            "release-group": {
                "id": RG_MBID,
                "title": "Risotto",
                "first-release-date": "1997",
                "release-list": [{"id": REL_MBID}],
            }
        },
    )
    monkeypatch.setattr(
        m,
        "get_release_by_id",
        lambda mbid, includes=None: {
            "release": {
                "id": REL_MBID,
                "date": "1997",
                "label-info-list": [
                    {"catalog-number": "ASW6224-2", "label": {"name": "Astralwerks"}}
                ],
                "medium-list": [
                    {
                        "format": "CD",
                        "track-list": [
                            {
                                "position": "1",
                                "recording": {"id": REC_MBID, "title": "Fly", "length": "361000"},
                            }
                        ],
                    }
                ],
            }
        },
    )


def test_command_syncs_from_musicbrainz(mocked_mb):
    call_command("musicbrainz_sync", artist_mbid="artist-x")
    assert Release.objects.filter(mbid=RG_MBID).exists()
    assert Edition.objects.get(mbid=REL_MBID).media == "CD"
    assert Track.objects.get(recording_mbid=REC_MBID).length == "6:01"


def test_command_is_idempotent(mocked_mb):
    call_command("musicbrainz_sync", artist_mbid="artist-x")
    call_command("musicbrainz_sync", artist_mbid="artist-x")
    assert Release.objects.count() == 1
    assert Track.objects.count() == 1
