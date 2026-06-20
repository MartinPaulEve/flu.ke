"""The audio_samples command: 40s centred, fading samples + optional upload."""

import shutil
import subprocess
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.discography import sampler
from apps.discography.models import Artist, Edition, Release, ReleaseType, Track
from apps.discography.sampler import (
    AudioMeta,
    format_duration,
    match_track,
    output_filename,
    sample_window,
)


class _T:
    """Lightweight stand-in for a Track (attribute access only)."""

    def __init__(self, track_number="", name="", display_title=None):
        self.track_number = track_number
        self.name = name
        self.display_title = display_title if display_title is not None else name

# --- pure helpers -----------------------------------------------------------

def test_sample_window_is_centred():
    assert sample_window(100, 40) == (30, 40)


def test_sample_window_short_track_uses_the_whole_thing():
    start, length = sample_window(20, 40)
    assert start == 0 and length == 20


def test_format_duration():
    assert format_duration(330) == "5:30"
    assert format_duration(5) == "0:05"


def test_output_filename_from_metadata():
    meta = AudioMeta(
        artist="Fluke", title="Atom Bomb", album="Risotto", year="1997",
        track_number="1", ext=".mp3",
    )
    assert output_filename(meta) == "01 Fluke - Atom Bomb - Risotto - 1997.mp3"


def test_output_filename_sanitises_illegal_characters():
    meta = AudioMeta(artist="AC/DC", title="What?", album="A", year="2000",
                     track_number="2", ext=".flac")
    name = output_filename(meta)
    assert "/" not in name and "?" not in name
    assert name.endswith(".flac")


# --- track matching (pure) --------------------------------------------------

def test_match_track_by_track_number():
    tracks = [_T("1", "Squelch"), _T("2", "Bullet")]
    meta = AudioMeta(title="Different", track_number="2")
    assert match_track(meta, tracks).name == "Bullet"


def test_match_track_by_number_ignores_leading_zeros():
    tracks = [_T("01", "Squelch"), _T("02", "Bullet")]
    meta = AudioMeta(title="x", track_number="2")
    assert match_track(meta, tracks).name == "Bullet"


def test_match_track_falls_back_to_title_when_no_number():
    tracks = [_T("1", "Squelch"), _T("2", "Bullet")]
    meta = AudioMeta(title="bullet", track_number="")
    assert match_track(meta, tracks).name == "Bullet"


def test_match_track_title_matches_display_title_with_mix():
    tracks = [_T("", "Bullet", display_title="Bullet (Bullion)")]
    meta = AudioMeta(title="Bullet (Bullion)")
    assert match_track(meta, tracks).name == "Bullet"


def test_match_track_returns_none_when_nothing_matches():
    tracks = [_T("1", "Squelch")]
    meta = AudioMeta(title="Nope", track_number="9")
    assert match_track(meta, tracks) is None


def test_match_track_instrumentals_continue_the_numbering():
    # Site numbering: 12 then i-01, i-02 (instrumentals on a 2nd disc). The input
    # is plain-sequential 12, 13, 14 — so 13 -> i-01 and 14 -> i-02.
    tracks = [
        _T("12", "Closer"),
        _T("i-01", "Closer (Instrumental)"),
        _T("i-02", "Bullet (Instrumental)"),
    ]
    assert match_track(AudioMeta(title="z", track_number="12"), tracks).name == "Closer"
    assert match_track(AudioMeta(title="z", track_number="13"), tracks).track_number == "i-01"
    assert match_track(AudioMeta(title="z", track_number="14"), tracks).track_number == "i-02"


def test_match_track_instrumental_offset_uses_highest_plain_number():
    tracks = [_T(str(n), f"T{n}") for n in range(1, 13)]
    tracks += [_T("i-01", "First instrumental"), _T("i-02", "Second instrumental")]
    assert match_track(AudioMeta(title="z", track_number="13"), tracks).track_number == "i-01"
    assert match_track(AudioMeta(title="z", track_number="14"), tracks).track_number == "i-02"


def test_match_track_direct_instrumental_number_still_matches():
    tracks = [_T("12", "Closer"), _T("i-01", "Closer (Instrumental)")]
    assert match_track(AudioMeta(title="z", track_number="i-01"), tracks).name == \
        "Closer (Instrumental)"


# --- real ffmpeg integration (skipped if tools missing) ---------------------

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


@requires_ffmpeg
def test_make_sample_centres_fades_and_keeps_format(tmp_path):
    pytest.importorskip("mutagen")
    src = tmp_path / "src.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=60",
         "-metadata", "title=Song", "-metadata", "artist=Band", str(src)],
        check=True, capture_output=True,
    )
    meta = sampler.read_metadata(src)
    assert meta.title == "Song"
    assert 59 < meta.duration < 61
    assert meta.ext == ".mp3"

    out = tmp_path / "out.mp3"
    sampler.make_sample(src, out, meta, sample_seconds=40, fade_seconds=2)
    assert out.exists()
    out_meta = sampler.read_metadata(out)
    assert out_meta.title == "Song (sample)"  # title tagged in the sample file
    assert 39 < out_meta.duration < 41


# --- the command ------------------------------------------------------------

def test_errors_when_output_folder_exists(tmp_path):
    inp = tmp_path / "in"
    inp.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(CommandError):
        call_command("audio_samples", str(inp), str(out))


@pytest.fixture
def mocked_sampler(monkeypatch):
    """Replace the real metadata read + ffmpeg call with fakes (no audio needed)."""
    metas = {
        "01.mp3": AudioMeta(artist="Fluke", title="Squelch", album="Risotto",
                            year="1997", track_number="1", duration=330.0, ext=".mp3"),
        "02.mp3": AudioMeta(artist="Fluke", title="Bullet", album="Risotto",
                            year="1997", track_number="2", duration=200.0, ext=".mp3"),
    }
    monkeypatch.setattr(sampler, "read_metadata", lambda p: metas[Path(p).name])

    def fake_make(input_path, output_path, meta, **kwargs):
        Path(output_path).write_bytes(b"FAKE-SAMPLE-AUDIO")

    monkeypatch.setattr(sampler, "make_sample", fake_make)
    return metas


@pytest.mark.django_db
def test_upload_creates_an_edition_with_sampled_tracks(tmp_path, mocked_sampler):
    artist = Artist.objects.create(name="Fluke", slug="fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    release = Release.objects.create(
        name="Risotto", slug="risotto", artist=artist, type=rtype, year=1997,
        is_published=True,
    )
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "01.mp3").write_bytes(b"x")
    (inp / "02.mp3").write_bytes(b"x")
    out = tmp_path / "out"

    call_command("audio_samples", str(inp), str(out), upload="risotto")

    edition = Edition.objects.get(release=release)
    tracks = list(edition.tracks.order_by("display_order"))
    assert [t.name for t in tracks] == ["Squelch", "Bullet"]  # no "(sample)"
    assert tracks[0].length == "5:30"  # original duration, not the 40s sample
    assert tracks[0].track_number == "1"
    assert tracks[0].sample  # the sample file was attached
    release.refresh_from_db()
    assert release.is_published is False  # held back for review


@pytest.mark.django_db
def test_upload_unknown_release_warns_but_still_writes_samples(tmp_path, mocked_sampler):
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "01.mp3").write_bytes(b"x")
    out = tmp_path / "out"

    call_command("audio_samples", str(inp), str(out), upload="nope")

    # samples written to disk regardless
    assert (out / "01 Fluke - Squelch - Risotto - 1997.mp3").exists()
    assert Edition.objects.count() == 0  # nothing uploaded


# --- attaching samples to an existing Edition's tracks ----------------------

@pytest.fixture
def existing_edition():
    artist = Artist.objects.create(name="Fluke", slug="fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    release = Release.objects.create(
        name="Risotto", slug="risotto", artist=artist, type=rtype, year=1997,
    )
    edition = Edition.objects.create(release=release, media="CD")
    Track.objects.create(edition=edition, name="Squelch", track_number="1", display_order=0)
    Track.objects.create(edition=edition, name="Bullet", track_number="2", display_order=1)
    return edition


@pytest.mark.django_db
def test_edition_mode_attaches_samples_to_existing_tracks(tmp_path, mocked_sampler,
                                                          existing_edition):
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "01.mp3").write_bytes(b"x")  # Squelch, #1
    (inp / "02.mp3").write_bytes(b"x")  # Bullet, #2
    out = tmp_path / "out"

    call_command("audio_samples", str(inp), str(out), edition=existing_edition.pk)

    squelch = existing_edition.tracks.get(name="Squelch")
    bullet = existing_edition.tracks.get(name="Bullet")
    assert squelch.sample and bullet.sample  # samples attached to the matched tracks
    assert existing_edition.tracks.count() == 2  # no new tracks created


@pytest.mark.django_db
def test_edition_mode_reports_unmatched_samples(tmp_path, mocked_sampler, existing_edition,
                                                capsys):
    # An input whose metadata matches no track in the edition.
    metas = mocked_sampler
    metas["99.mp3"] = AudioMeta(artist="Fluke", title="Unknown Thing", album="Risotto",
                                year="1997", track_number="99", duration=100.0, ext=".mp3")
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "99.mp3").write_bytes(b"x")
    out = tmp_path / "out"

    call_command("audio_samples", str(inp), str(out), edition=existing_edition.pk)

    assert existing_edition.tracks.count() == 2  # unchanged — nothing created
    assert all(not t.sample for t in existing_edition.tracks.all())  # nothing attached
    assert "Unknown Thing" in capsys.readouterr().out  # the miss is reported


@pytest.mark.django_db
def test_edition_and_upload_are_mutually_exclusive(tmp_path, mocked_sampler):
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "01.mp3").write_bytes(b"x")
    out = tmp_path / "out"
    with pytest.raises(CommandError):
        call_command("audio_samples", str(inp), str(out), upload="risotto", edition=1)


@pytest.mark.django_db
def test_edition_mode_unknown_edition_warns_but_writes_samples(tmp_path, mocked_sampler):
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "01.mp3").write_bytes(b"x")
    out = tmp_path / "out"

    call_command("audio_samples", str(inp), str(out), edition=999999)

    assert (out / "01 Fluke - Squelch - Risotto - 1997.mp3").exists()  # samples still written
