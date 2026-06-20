"""Behavioural tests for the idempotent, add-only Marcolphus ingest."""

import pytest

from apps.discography.marcolphus_ingest import import_marcolphus_releases
from apps.discography.models import Artist, Edition, Release, ReleaseType, Track
from apps.discography.parsers.marcolphus import (
    MarcolphusEdition,
    MarcolphusRelease,
    MarcolphusTrack,
)

pytestmark = pytest.mark.django_db


def _release(**kw):
    kw.setdefault("editions", [MarcolphusEdition(media='12"', year=kw.pop("year", 1990))])
    return MarcolphusRelease(**kw)


def _remix_release():
    return MarcolphusRelease(
        section="Remixes",
        artist="Bjork",
        name="Big Time Sensuality",
        year=1993,
        fluke_is_remixer=True,
        editions=[
            MarcolphusEdition(
                media='12"',
                year=1993,
                record_label="One Little Indian",
                catalogue_number="132 TP 12",
                tracks=[
                    MarcolphusTrack(
                        name="Big Time Sensuality", mix_info="fluke's magimix",
                        length="5:51", remixer="Fluke",
                    )
                ],
            )
        ],
    )


# --------------------------------------------------------------------------- #
# Artist resolution
# --------------------------------------------------------------------------- #


def test_remix_artist_is_independent_not_a_fluke_alias():
    import_marcolphus_releases([_remix_release()])
    bjork = Artist.objects.get(name="Bjork")
    assert bjork.is_alias is False
    assert bjork.primary_artist_id is None


def test_remix_track_credits_fluke_as_remixer():
    import_marcolphus_releases([_remix_release()])
    track = Track.objects.get(name="Big Time Sensuality")
    fluke = Artist.objects.get(name="Fluke")
    assert fluke in track.remixers.all()


def test_lucky_monkeys_is_a_fluke_alias():
    rel = MarcolphusRelease(
        section="Lucky Monkeys", artist="Lucky Monkeys", name="Bjango", year=1996,
        editions=[MarcolphusEdition(media='12"', year=1996)],
    )
    import_marcolphus_releases([rel])
    fluke = Artist.objects.get(name="Fluke")
    lm = Artist.objects.get(name="Lucky Monkeys")
    assert lm.is_alias is True
    assert lm.primary_artist == fluke


def test_2bit_pie_normalised_and_aliased():
    rel = MarcolphusRelease(
        section="Collaborations", artist="2Bit Pie", name="Nobody Never", year=2005,
        editions=[MarcolphusEdition(media='12"', year=2005)],
    )
    import_marcolphus_releases([rel])
    twobit = Artist.objects.get(name="2 Bit Pie")
    assert twobit.is_alias is True


def test_source_artist_typo_is_corrected():
    # The source misspells "Smashing Pumpkins" as "Smashing Pumpinks" on one line.
    rel = MarcolphusRelease(
        section="Remixes", artist="Smashing Pumpinks",
        name="The End is the Beginning... (the remixes)", year=1997,
        editions=[MarcolphusEdition(media="CD5", year=1997)],
    )
    import_marcolphus_releases([rel])
    assert Release.objects.get(name__startswith="The End").artist.name == "Smashing Pumpkins"
    assert not Artist.objects.filter(name="Smashing Pumpinks").exists()


def test_various_artists_created_and_not_alias():
    rel = MarcolphusRelease(
        section="Compilation Appearances", artist="Various Artists",
        name="Tomb Raider Soundtrack", year=2001,
        editions=[MarcolphusEdition(media="CD", year=2001,
                                    tracks=[MarcolphusTrack(name="Absurd")])],
    )
    import_marcolphus_releases([rel])
    va = Artist.objects.get(name="Various Artists")
    assert va.is_alias is False


def test_new_artists_stay_off_the_homepage():
    import_marcolphus_releases([_remix_release()])
    for name in ("Bjork", "Various Artists"):
        if Artist.objects.filter(name=name).exists():
            assert Artist.objects.get(name=name).appears_on_homepage is False


# --------------------------------------------------------------------------- #
# Release-type mapping
# --------------------------------------------------------------------------- #


def test_remix_section_uses_remixes_release_type():
    import_marcolphus_releases([_remix_release()])
    release = Release.objects.get(name="Big Time Sensuality")
    assert release.type.name == "Remixes"


def test_album_kind_maps_to_albums_type():
    rel = MarcolphusRelease(section="Fluke", artist="Fluke", name="Oto", year=1995,
                            kind="album",
                            editions=[MarcolphusEdition(media="CD", year=1995)])
    import_marcolphus_releases([rel])
    assert Release.objects.get(name="Oto").type.name == "Albums"


# --------------------------------------------------------------------------- #
# Add-only / fill-blank / idempotency
# --------------------------------------------------------------------------- #


def test_existing_release_is_matched_not_duplicated():
    fluke = Artist.objects.create(name="Fluke")
    singles = ReleaseType.objects.create(name="Singles")
    Release.objects.create(artist=fluke, name="Slid", year=1993, type=singles)

    rel = MarcolphusRelease(section="Fluke", artist="Fluke", name="Slid", year=1993,
                            kind="single",
                            editions=[MarcolphusEdition(media="CD5", year=1993)])
    import_marcolphus_releases([rel])
    assert Release.objects.filter(name="Slid").count() == 1


def test_missing_edition_is_added_to_existing_release():
    fluke = Artist.objects.create(name="Fluke")
    singles = ReleaseType.objects.create(name="Singles")
    release = Release.objects.create(artist=fluke, name="Slid", year=1993, type=singles)
    Edition.objects.create(release=release, media='12"', catalogue_number="YRT103")

    rel = MarcolphusRelease(
        section="Fluke", artist="Fluke", name="Slid", year=1993, kind="single",
        editions=[
            MarcolphusEdition(media='12"', catalogue_number="YRT103"),
            MarcolphusEdition(media="CD5", catalogue_number="YRCD103"),
        ],
    )
    import_marcolphus_releases([rel])
    assert release.editions.count() == 2
    assert release.editions.filter(catalogue_number="YRCD103").exists()


def test_blank_field_on_matched_edition_is_filled():
    fluke = Artist.objects.create(name="Fluke")
    singles = ReleaseType.objects.create(name="Singles")
    release = Release.objects.create(artist=fluke, name="Slid", year=1993, type=singles)
    # Same edition (catalogue number YRT103) but with a blank record label.
    Edition.objects.create(
        release=release, media='12"', catalogue_number="YRT103", record_label=""
    )
    rel = MarcolphusRelease(
        section="Fluke", artist="Fluke", name="Slid", year=1993, kind="single",
        editions=[MarcolphusEdition(
            media='12"', catalogue_number="YRT103", record_label="Circa Records"
        )],
    )
    import_marcolphus_releases([rel])
    edition = release.editions.get(catalogue_number="YRT103")
    assert edition.record_label == "Circa Records"  # blank filled
    assert release.editions.count() == 1  # matched, not duplicated


def test_nonblank_field_is_never_overwritten():
    fluke = Artist.objects.create(name="Fluke")
    singles = ReleaseType.objects.create(name="Singles")
    release = Release.objects.create(artist=fluke, name="Slid", year=1993, type=singles)
    Edition.objects.create(
        release=release, media='12"', catalogue_number="YRT103",
        record_label="Circa Records",
    )
    rel = MarcolphusRelease(
        section="Fluke", artist="Fluke", name="Slid", year=1993, kind="single",
        editions=[MarcolphusEdition(
            media='12"', catalogue_number="YRT103", record_label="Wrong Label"
        )],
    )
    import_marcolphus_releases([rel])
    edition = release.editions.get(catalogue_number="YRT103")
    assert edition.record_label == "Circa Records"  # existing value preserved


def test_import_is_idempotent():
    releases = [_remix_release()]
    import_marcolphus_releases(releases)
    counts = (Release.objects.count(), Edition.objects.count(), Track.objects.count())
    second = import_marcolphus_releases([_remix_release()])
    assert (Release.objects.count(), Edition.objects.count(), Track.objects.count()) == counts
    assert second.releases_created == 0
    assert second.editions_created == 0
    assert second.tracks_created == 0


# --------------------------------------------------------------------------- #
# Remixer & featured credits
# --------------------------------------------------------------------------- #


def test_named_remixer_on_fluke_track_is_added():
    rel = MarcolphusRelease(
        section="Fluke", artist="Fluke", name="Slid", year=1993, kind="single",
        editions=[MarcolphusEdition(media='12"', year=1993, tracks=[
            MarcolphusTrack(name="Slid", mix_info="scat and sax frenzy",
                            remixer="Lionrock (Justin Robertson)"),
        ])],
    )
    import_marcolphus_releases([rel])
    lionrock = Artist.objects.get(name="Lionrock (Justin Robertson)")
    assert lionrock.is_alias is False
    track = Track.objects.get(mix_info="scat and sax frenzy")
    assert lionrock in track.remixers.all()


def test_fluke_member_credit_adds_fluke_as_featured_artist():
    rel = MarcolphusRelease(
        section="Collaborations", artist="Trisco", name="Ultra", year=2001,
        featured_credits=["Jon Fugler"],
        editions=[MarcolphusEdition(media='2x12"', year=2001)],
    )
    import_marcolphus_releases([rel])
    release = Release.objects.get(name="Ultra")
    fluke = Artist.objects.get(name="Fluke")
    assert fluke in release.featured_artists.all()


# --------------------------------------------------------------------------- #
# Reporting & dry-run
# --------------------------------------------------------------------------- #


def test_change_log_records_creations():
    stats = import_marcolphus_releases([_remix_release()])
    kinds = {(c.action, c.entity) for c in stats.changes}
    assert ("create", "Release") in kinds
    assert ("create", "Track") in kinds
    assert stats.releases_created == 1


def test_dry_run_reports_changes_without_writing():
    stats = import_marcolphus_releases([_remix_release()], dry_run=True)
    assert stats.releases_created == 1  # would create
    assert Release.objects.count() == 0  # but wrote nothing


def test_placeholder_named_release_is_skipped():
    rel = MarcolphusRelease(section="Collaborations", artist="Various Artists",
                            name="???", editions=[MarcolphusEdition(media="CD")])
    stats = import_marcolphus_releases([rel])
    assert Release.objects.count() == 0
    assert stats.skipped == 1
