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


def _norm_number(value: str) -> str:
    """Normalise a track number for comparison ("01" and "1" are the same)."""
    value = (value or "").strip()
    return value.lstrip("0") or ("0" if value else "")


def _norm_text(value: str) -> str:
    return (value or "").strip().lower()


def match_track(meta: AudioMeta, tracks):
    """Find the track in ``tracks`` that ``meta`` belongs to, or ``None``.

    Matches by track number first (leading zeros ignored), then by title — the
    title is compared against each track's ``name`` and, if present, its
    ``display_title`` (so "Bullet" or "Bullet (Bullion)" both match). ``tracks``
    is any iterable of objects exposing ``track_number``, ``name`` and
    (optionally) ``display_title``.
    """
    tracks = list(tracks)

    number = _norm_number(meta.track_number)
    if number:
        for track in tracks:
            if _norm_number(getattr(track, "track_number", "")) == number:
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
