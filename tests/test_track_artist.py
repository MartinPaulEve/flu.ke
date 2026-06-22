"""Per-track artist display and track-number normalisation on Track."""

import pytest

from apps.discography.models import Artist, Edition, Release, ReleaseType, Track

pytestmark = pytest.mark.django_db


def _release(artist_name="Fluke"):
    artist = Artist.objects.create(name=artist_name)
    rtype = ReleaseType.objects.create(name="Singles")
    return Release.objects.create(name="Rel", artist=artist, type=rtype, year=2000)


def _edition(release):
    return Edition.objects.create(release=release, media="CD")


# --- display_artist ---------------------------------------------------------


def test_explicit_track_artist_is_shown_on_a_various_artists_comp():
    release = _release("Various Artists")
    edition = _edition(release)
    fluke = Artist.objects.create(name="Fluke")
    track = Track.objects.create(edition=edition, name="Tosh", artist=fluke)
    assert track.display_artist == fluke


def test_blank_track_artist_on_a_various_comp_shows_nothing():
    release = _release("Various Artists")
    track = Track.objects.create(edition=_edition(release), name="Tosh")
    assert track.display_artist is None


def test_blank_track_artist_does_not_repeat_the_release_artist():
    # On a Fluke release every track is Fluke; the heading already says so.
    release = _release("Fluke")
    track = Track.objects.create(edition=_edition(release), name="Bullet")
    assert track.display_artist is None


def test_explicit_guest_artist_is_shown_even_on_a_single_artist_release():
    release = _release("Fluke")
    guest = Artist.objects.create(name="Guest Vocalist")
    track = Track.objects.create(edition=_edition(release), name="Duet", artist=guest)
    assert track.display_artist == guest


def test_various_artists_is_never_shown_even_if_set_explicitly():
    release = _release("Fluke")
    various = Artist.objects.create(name="Various Artists")
    track = Track.objects.create(edition=_edition(release), name="Medley", artist=various)
    assert track.display_artist is None


# --- track-number normalisation on save -------------------------------------


@pytest.mark.parametrize("given,stored", [("3", "03"), ("9", "09"), ("A1", "A01"),
                                          ("10", "10"), ("01", "01"), ("", "")])
def test_save_normalises_track_number(given, stored):
    release = _release()
    track = Track.objects.create(edition=_edition(release), name="X", track_number=given)
    track.refresh_from_db()
    assert track.track_number == stored


# --- rendered page ----------------------------------------------------------


def test_comp_track_artist_renders_on_the_release_page(client):
    release = _release("Various Artists")
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    Track.objects.create(edition=_edition(release), name="Tosh", artist=fluke,
                         track_number="5")
    html = client.get(release.get_absolute_url()).content.decode()
    assert "Fluke" in html  # the per-track artist is shown
    assert "05" in html     # and the number is zero-padded


def test_legacy_bare_track_numbers_are_normalised_by_the_migration_logic():
    from apps.core.text import normalize_track_number

    release = _release()
    track = Track.objects.create(edition=_edition(release), name="X", track_number="5")
    # Force a legacy bare value straight into the DB (bypassing save() padding).
    Track.objects.filter(pk=track.pk).update(track_number="1")
    # The data migration applies normalize_track_number to every track.
    for pk, number in Track.objects.values_list("pk", "track_number"):
        Track.objects.filter(pk=pk).update(track_number=normalize_track_number(number))
    track.refresh_from_db()
    assert track.track_number == "01"


def test_single_artist_release_does_not_repeat_artist_on_each_track(client):
    release = _release("Fluke")
    Artist.objects.filter(name="Fluke").update(slug="fluke")
    Track.objects.create(edition=_edition(release), name="Bullet", track_number="1")
    html = client.get(release.get_absolute_url()).content.decode()
    # The track row should not carry a redundant per-track "Fluke —" artist link.
    assert "track__artist" not in html
