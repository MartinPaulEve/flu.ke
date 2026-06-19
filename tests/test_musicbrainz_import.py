"""Importing MusicBrainz editions onto an existing Release by slug (no network)."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.discography.models import Artist, CoverImage, Edition, Release, ReleaseType, Track
from apps.discography.musicbrainz import map_cover, parse_mbid, sync_editions_for_release

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


# --- map_cover (pure) -------------------------------------------------------
def test_map_cover_front():
    fields = map_cover({"image": "http://caa/1.jpg", "types": ["Front"]})
    assert fields["kind"] == CoverImage.KIND_FRONT
    assert fields["source_url"] == "http://caa/1.jpg"
    assert fields["display_name"] == "Front"


def test_map_cover_unknown_type_is_other():
    fields = map_cover({"image": "http://caa/2.jpg", "types": ["Spine"]})
    assert fields["kind"] == "other"
    assert fields["source_url"] == "http://caa/2.jpg"


def test_map_cover_no_types_defaults_name_cover():
    fields = map_cover({"image": "http://caa/3.jpg", "types": []})
    assert fields["display_name"] == "Cover"


# --- sync_editions_for_release (DB) -----------------------------------------
COVER_URL = "http://caa/the-fruit/front.jpg"


def _mb_release(rel=REL_MBID, rec=REC_MBID, cover_art=None):
    release = {
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
    if cover_art is not None:
        release["cover-art"] = cover_art
    return release


def _cover_art(url=COVER_URL, data=b"\xff\xd8jpegbytes"):
    return [{"image": url, "id": "1", "types": ["Front"], "data": data}]


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


@pytest.mark.django_db
def test_sync_editions_attaches_cover_image():
    release = _release()
    stats = sync_editions_for_release(release, [_mb_release(cover_art=_cover_art())])

    edition = Edition.objects.get(mbid=REL_MBID)
    cover = CoverImage.objects.get(edition=edition)
    assert cover.kind == CoverImage.KIND_FRONT
    assert cover.source_url == COVER_URL
    assert bool(cover.image)
    assert cover.image.read() == b"\xff\xd8jpegbytes"
    assert stats.covers == 1


@pytest.mark.django_db
def test_sync_editions_cover_is_idempotent():
    release = _release()
    sync_editions_for_release(release, [_mb_release(cover_art=_cover_art())])
    sync_editions_for_release(release, [_mb_release(cover_art=_cover_art())])
    assert CoverImage.objects.count() == 1


@pytest.mark.django_db
def test_sync_editions_dry_run_counts_covers_without_saving():
    release = _release()
    stats = sync_editions_for_release(
        release, [_mb_release(cover_art=_cover_art())], dry_run=True
    )
    assert stats.covers == 1
    assert CoverImage.objects.count() == 0


REL_B = "44444444-4444-4444-4444-444444444444"


@pytest.mark.django_db
def test_recording_shared_across_editions_is_kept_on_each():
    """Editions in a release-group share recordings; each edition must still get
    its own copy of the track, not have it claimed by the first edition."""
    release = _release()
    sync_editions_for_release(
        release,
        [_mb_release(rel=REL_MBID, rec=REC_MBID), _mb_release(rel=REL_B, rec=REC_MBID)],
    )

    assert Edition.objects.get(mbid=REL_MBID).tracks.count() == 1
    assert Edition.objects.get(mbid=REL_B).tracks.count() == 1


@pytest.mark.django_db
def test_shared_recording_import_is_idempotent_per_edition():
    release = _release()
    pair = [_mb_release(rel=REL_MBID, rec=REC_MBID), _mb_release(rel=REL_B, rec=REC_MBID)]
    sync_editions_for_release(release, pair)
    sync_editions_for_release(release, pair)
    assert Track.objects.count() == 2  # one per edition, not duplicated


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
    monkeypatch.setattr(
        m,
        "get_image_list",
        lambda mbid: {"images": [{"image": COVER_URL, "id": "1", "types": ["Front"]}]},
    )
    monkeypatch.setattr(m, "get_image", lambda mbid, coverid: b"\xff\xd8jpegbytes")


@pytest.mark.django_db
def test_command_imports_editions_by_slug(mocked_mb):
    _release()
    call_command("musicbrainz_import", "the-fruit", f"https://musicbrainz.org/release-group/{RG}")
    assert Edition.objects.get(mbid=REL_MBID).media == '12" Vinyl'
    assert Track.objects.get(recording_mbid=REC_MBID).length == "7:00"


@pytest.mark.django_db
def test_command_imports_cover_art(mocked_mb):
    _release()
    call_command("musicbrainz_import", "the-fruit", f"https://musicbrainz.org/release-group/{RG}")
    cover = CoverImage.objects.get(edition__mbid=REL_MBID)
    assert cover.kind == CoverImage.KIND_FRONT
    assert cover.source_url == COVER_URL
    assert bool(cover.image)


@pytest.mark.django_db
def test_command_errors_on_unknown_slug(mocked_mb):
    with pytest.raises(CommandError):
        call_command("musicbrainz_import", "nope", RG)
