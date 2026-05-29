"""Idempotent upsert of MusicBrainz data into the discography (no network)."""

import pytest

from apps.discography.models import Artist, Edition, Release, ReleaseType, Track
from apps.discography.musicbrainz import sync_release_groups

pytestmark = pytest.mark.django_db

RG_MBID = "11111111-1111-1111-1111-111111111111"
REL_MBID = "22222222-2222-2222-2222-222222222222"
REC_MBID = "33333333-3333-3333-3333-333333333333"


def _data(title="Risotto"):
    return [
        {
            "id": RG_MBID,
            "title": title,
            "first-release-date": "1997-09-22",
            "release-list": [
                {
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
                                    "recording": {
                                        "id": REC_MBID,
                                        "title": "Fly",
                                        "length": "361000",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    ]


@pytest.fixture
def artist_and_type():
    return Artist.objects.create(name="Fluke"), ReleaseType.objects.create(name="Albums")


def test_sync_creates_release_edition_track(artist_and_type):
    artist, rtype = artist_and_type
    stats = sync_release_groups(artist, rtype, _data())

    release = Release.objects.get(mbid=RG_MBID)
    assert release.name == "Risotto"
    assert release.year == 1997
    edition = Edition.objects.get(mbid=REL_MBID)
    assert edition.catalogue_number == "ASW6224-2"
    assert edition.media == "CD"
    track = Track.objects.get(recording_mbid=REC_MBID)
    assert track.name == "Fly"
    assert track.length == "6:01"
    assert (stats.releases, stats.editions, stats.tracks) == (1, 1, 1)


def test_sync_is_idempotent(artist_and_type):
    artist, rtype = artist_and_type
    sync_release_groups(artist, rtype, _data())
    sync_release_groups(artist, rtype, _data())
    assert Release.objects.count() == 1
    assert Edition.objects.count() == 1
    assert Track.objects.count() == 1


def test_sync_updates_changed_fields(artist_and_type):
    artist, rtype = artist_and_type
    sync_release_groups(artist, rtype, _data(title="Risoto (typo)"))
    sync_release_groups(artist, rtype, _data(title="Risotto"))
    assert Release.objects.get(mbid=RG_MBID).name == "Risotto"


def test_dry_run_writes_nothing(artist_and_type):
    artist, rtype = artist_and_type
    sync_release_groups(artist, rtype, _data(), dry_run=True)
    assert Release.objects.count() == 0
