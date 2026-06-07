"""Importing MusicBrainz editions onto an existing Release by slug (no network)."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.discography.models import Artist, Edition, Release, ReleaseType, Track
from apps.discography.musicbrainz import parse_mbid, sync_editions_for_release

RG = "0838c153-c193-3fcc-93db-189d9ef592d9"
REL_MBID = "22222222-2222-2222-2222-222222222222"
REC_MBID = "33333333-3333-3333-3333-333333333333"


# --- parse_mbid (pure) ------------------------------------------------------
def test_parse_release_group_url():
    assert parse_mbid(f"https://musicbrainz.org/release-group/{RG}") == ("release-group", RG)


def test_parse_release_url():
    assert parse_mbid(f"https://musicbrainz.org/release/{RG}") == ("release", RG)


def test_parse_bare_id_defaults_to_release_group():
    assert parse_mbid(RG) == ("release-group", RG)


def test_parse_url_with_trailing_path_and_query():
    assert parse_mbid(f"http://musicbrainz.org/release-group/{RG}/aliases?x=1") == (
        "release-group",
        RG,
    )


def test_parse_invalid_raises():
    with pytest.raises(ValueError):
        parse_mbid("https://example.com/not-an-id")


# --- sync_editions_for_release (DB) -----------------------------------------
def _mb_release(rel=REL_MBID, rec=REC_MBID):
    return {
        "id": rel,
        "date": "2003",
        "label-info-list": [{"catalog-number": "NEO123", "label": {"name": "Neo"}}],
        "medium-list": [
            {
                "format": '12" Vinyl',
                "track-list": [
                    {
                        "position": "1",
                        "recording": {"id": rec, "title": "The Fruit", "length": "420000"},
                    }
                ],
            }
        ],
    }


def _release(slug="the-fruit"):
    artist = Artist.objects.create(name="Sander Kleinenberg")
    rtype = ReleaseType.objects.create(name="Singles")
    return Release.objects.create(name="The Fruit", slug=slug, artist=artist, type=rtype)


@pytest.mark.django_db
def test_sync_editions_attaches_to_existing_release():
    release = _release()
    stats = sync_editions_for_release(release, [_mb_release()])

    edition = Edition.objects.get(mbid=REL_MBID)
    assert edition.release == release
    assert edition.catalogue_number == "NEO123"
    assert edition.record_label == "Neo"
    assert edition.media == '12" Vinyl'
    assert edition.year == 2003

    track = Track.objects.get(recording_mbid=REC_MBID)
    assert track.edition == edition
    assert track.name == "The Fruit"
    assert track.track_number == "1"
    assert track.length == "7:00"
    assert (stats.editions, stats.tracks) == (1, 1)


@pytest.mark.django_db
def test_sync_editions_is_idempotent():
    release = _release()
    sync_editions_for_release(release, [_mb_release()])
    sync_editions_for_release(release, [_mb_release()])
    assert Edition.objects.count() == 1
    assert Track.objects.count() == 1


# --- command (musicbrainzngs mocked) ----------------------------------------
@pytest.fixture
def mocked_mb(monkeypatch, settings):
    settings.MUSICBRAINZ = {"app": "flukecms", "version": "1.0", "contact": "a@b.test"}
    import musicbrainzngs as m

    monkeypatch.setattr(m, "set_useragent", lambda *a, **k: None)
    monkeypatch.setattr(m, "set_rate_limit", lambda *a, **k: None)
    monkeypatch.setattr(
        m,
        "get_release_group_by_id",
        lambda mbid, includes=None: {"release-group": {"id": mbid, "release-list": [{"id": REL_MBID}]}},
    )
    monkeypatch.setattr(m, "get_release_by_id", lambda mbid, includes=None: {"release": _mb_release()})


@pytest.mark.django_db
def test_command_imports_editions_by_slug(mocked_mb):
    _release()
    call_command("musicbrainz_import", "the-fruit", f"https://musicbrainz.org/release-group/{RG}")
    assert Edition.objects.get(mbid=REL_MBID).media == '12" Vinyl'
    assert Track.objects.get(recording_mbid=REC_MBID).length == "7:00"


@pytest.mark.django_db
def test_command_errors_on_unknown_slug(mocked_mb):
    with pytest.raises(CommandError):
        call_command("musicbrainz_import", "nope", RG)
