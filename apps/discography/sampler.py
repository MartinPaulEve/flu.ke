"""Audio sampling: pure helpers + an ffmpeg-backed sample maker.

Read metadata, work out a centred window, name the output from the tags, and
extract a short fading sample keeping the source format (no flac<->mp3
transcode). No Django/DB here — the management command adds the optional upload.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

AUDIO_EXTENSIONS = {".mp3", ".flac"}

_ILLEGAL_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass
class AudioMeta:
    artist: str = ""
    title: str = ""
    album: str = ""
    year: str = ""
    track_number: str = ""
    duration: float = 0.0
    ext: str = ""  # ".mp3" / ".flac"


def read_metadata(path) -> AudioMeta:
    """Read tags + duration from a flac/mp3 file with mutagen."""
    from mutagen import File as MutagenFile

    audio = MutagenFile(str(path), easy=True)

    def first(key):
        value = audio.get(key) if audio else None
        return (value[0] if value else "") or ""

    return AudioMeta(
        artist=first("artist"),
        title=first("title"),
        album=first("album"),
        year=first("date")[:4],
        track_number=first("tracknumber").split("/")[0].strip(),
        duration=float(audio.info.length) if audio else 0.0,
        ext=os.path.splitext(str(path))[1].lower(),
    )


def sample_window(duration, sample_seconds=40.0):
    """Return ``(start, length)`` for a sample taken from the middle of a track.

    Short tracks (< ``sample_seconds``) yield the whole thing from the start.
    """
    length = min(sample_seconds, duration)
    start = max(0.0, (duration - length) / 2.0)
    return start, length


def format_duration(seconds) -> str:
    """Seconds → ``m:ss``."""
    total = round(seconds)
    return f"{total // 60}:{total % 60:02d}"


def _safe(part: str) -> str:
    return _ILLEGAL_FILENAME.sub("_", (part or "").strip()).strip()


def output_filename(meta: AudioMeta) -> str:
    """Build ``NN Artist - Title - Album - Year.ext`` from the metadata."""
    number = (meta.track_number or "0").zfill(2)
    fields = [
        _safe(meta.artist) or "Unknown Artist",
        _safe(meta.title) or "Untitled",
        _safe(meta.album),
        (meta.year or "").strip(),
    ]
    stem = f"{number} " + " - ".join(f for f in fields if f)
    return f"{stem}{meta.ext}"


_INSTRUMENTAL_RE = re.compile(r"^i-?0*(\d+)$")
_PLAIN_RE = re.compile(r"^0*(\d+)$")


def _norm_text(value: str) -> str:
    return (value or "").strip().lower()


def _parse_number(value: str):
    """Classify a track number → ``("plain", n)`` / ``("inst", n)`` / ``("other", s)``.

    ``"plain"`` is an ordinary number (leading zeros ignored); ``"inst"`` is an
    instrumental like ``i-01`` / ``i1`` (so a second-disc instrumental run);
    ``"other"`` is anything else (e.g. a vinyl side "A1"), compared as text.
    """
    text = (value or "").strip().lower()
    if not text:
        return None
    inst = _INSTRUMENTAL_RE.match(text)
    if inst:
        return ("inst", int(inst.group(1)))
    plain = _PLAIN_RE.match(text)
    if plain:
        return ("plain", int(plain.group(1)))
    return ("other", text)


def _effective_number(parsed, offset):
    """The position of a track in the overall sequence; instrumentals continue it.

    ``i-01`` on a release whose main tracks run up to N is the (N+1)th track, so
    its effective number is ``offset + 1`` where ``offset`` is the highest plain
    track number. Returns ``None`` for non-numeric ("other") track numbers.
    """
    kind, value = parsed
    if kind == "plain":
        return value
    if kind == "inst":
        return offset + value
    return None


def match_track(meta: AudioMeta, tracks):
    """Find the track in ``tracks`` that ``meta`` belongs to, or ``None``.

    Matches by track number first, then by title. ``tracks`` is any iterable of
    objects exposing ``track_number``, ``name`` and (optionally) ``display_title``.

    Track-number matching is leading-zero insensitive and understands
    instrumental second-disc numbering: where the site lists ``12, i-01, i-02``
    the instrumentals continue the sequence, so a plain input ``13`` matches
    ``i-01`` and ``14`` matches ``i-02``. Title matching compares against each
    track's ``name`` and ``display_title`` (so "Bullet" or "Bullet (Bullion)"
    both match).
    """
    tracks = list(tracks)
    parsed = [(t, _parse_number(getattr(t, "track_number", ""))) for t in tracks]
    want = _parse_number(meta.track_number)

    if want is not None:
        # An exact same-kind match (plain↔plain, inst↔inst, other↔other) wins.
        for track, track_num in parsed:
            if track_num == want:
                return track
        # Otherwise fall back to the effective sequence position, so a plain
        # input number can reach an instrumental that continues the numbering.
        plain_numbers = [p[1] for _, p in parsed if p and p[0] == "plain"]
        offset = max(plain_numbers, default=0)
        target = _effective_number(want, offset)
        if target is not None:
            for track, track_num in parsed:
                if track_num is not None and _effective_number(track_num, offset) == target:
                    return track

    title = _norm_text(meta.title)
    if title:
        for track in tracks:
            names = {
                _norm_text(getattr(track, "name", "")),
                _norm_text(getattr(track, "display_title", "")),
            }
            if title in names:
                return track
    return None


def make_sample(input_path, output_path, meta: AudioMeta, *, sample_seconds=40.0, fade_seconds=2.0):
    """Write a centred, fading sample of ``input_path`` to ``output_path``.

    Keeps the source format (the output extension drives the codec, so an mp3
    stays mp3 and a flac stays flac — never transcoded between them). Source
    metadata is copied and ``" (sample)"`` appended to the title.
    """
    start, length = sample_window(meta.duration, sample_seconds)
    fade = min(fade_seconds, length / 2)
    afade = f"afade=t=in:st=0:d={fade},afade=t=out:st={length - fade}:d={fade}"
    title = f"{meta.title} (sample)".strip()
    cmd = [
        "ffmpeg", "-nostdin", "-y",
        "-ss", f"{start}",
        "-t", f"{length}",
        "-i", str(input_path),
        "-af", afade,
        "-map_metadata", "0",
        "-metadata", f"title={title}",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
