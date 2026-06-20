"""enrich_from_musicbrainz command tests with musicbrainzngs mocked (no network)."""

import pytest
from django.core.management import call_command

from apps.discography.models import Artist, Edition, Release, ReleaseType, Track

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
        m,
        "search_release_groups",
        lambda **k: {
            "release-group-list": [
                {
                    "id": RG_MBID,
                    "title": "Risotto",
                    "artist-credit": [{"artist": {"name": "Fluke"}}],
                }
            ]
        },
    )
    monkeypatch.setattr(
        m,
        "get_release_group_by_id",
        lambda mbid, includes=None: {
            "release-group": {"id": RG_MBID, "release-list": [{"id": REL_MBID}]}
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
                    {"catalog-number": "6D-12-001", "label": {"name": "6 Degrees"}}
                ],
                "medium-list": [
                    {
                        "format": '12" Vinyl',
                        "track-list": [
                            {
                                "position": "1",
                                "recording": {
                                    "id": REC_MBID, "title": "Bermuda", "length": "120000"
                                },
                            }
                        ],
                    }
                ],
            }
        },
    )
    monkeypatch.setattr(m, "get_image_list", lambda mbid: {"images": []})


@pytest.fixture
def fluke_risotto():
    fluke = Artist.objects.create(name="Fluke")
    albums = ReleaseType.objects.create(name="Albums")
    return Release.objects.create(artist=fluke, name="Risotto", year=1997, type=albums)


def test_confident_match_sets_mbid_and_syncs_editions(mocked_mb, fluke_risotto):
    call_command("enrich_from_musicbrainz", "--artist", "Fluke")
    fluke_risotto.refresh_from_db()
    assert str(fluke_risotto.mbid) == RG_MBID
    assert Edition.objects.filter(release=fluke_risotto, mbid=REL_MBID).exists()
    assert Track.objects.filter(recording_mbid=REC_MBID, name="Bermuda").exists()


def test_no_confident_match_is_reported_not_synced(monkeypatch, mocked_mb, fluke_risotto):
    import musicbrainzngs as m

    # MusicBrainz returns a release-group whose title does not match.
    monkeypatch.setattr(
        m, "search_release_groups",
        lambda **k: {"release-group-list": [
            {"id": "x", "title": "Something Else",
             "artist-credit": [{"artist": {"name": "Fluke"}}]}
        ]},
    )
    call_command("enrich_from_musicbrainz", "--artist", "Fluke")
    fluke_risotto.refresh_from_db()
    assert fluke_risotto.mbid is None
    assert not Edition.objects.filter(release=fluke_risotto).exists()


def test_blank_catalogue_number_filled_from_matching_format(mocked_mb, fluke_risotto):
    # An existing edition with a blank (???) catalogue number and 12" media.
    edition = Edition.objects.create(release=fluke_risotto, media='12"', catalogue_number="")
    call_command("enrich_from_musicbrainz", "--artist", "Fluke")
    edition.refresh_from_db()
    assert edition.catalogue_number == "6D-12-001"


def test_dry_run_writes_nothing(mocked_mb, fluke_risotto):
    call_command("enrich_from_musicbrainz", "--artist", "Fluke", "--dry-run")
    fluke_risotto.refresh_from_db()
    assert fluke_risotto.mbid is None
    assert not Edition.objects.filter(release=fluke_risotto).exists()
