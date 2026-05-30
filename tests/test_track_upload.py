"""Behavioural tests for Track.sample upload naming.

Uploaded track files must be stored under a random UUID filename that
preserves the (lowercased) extension, so two files with the same original
name cannot collide / overwrite one another.
"""

import re

import pytest
from django.core.files.base import ContentFile

from apps.discography.models import (
    Artist,
    Edition,
    Release,
    ReleaseType,
    Track,
)

pytestmark = pytest.mark.django_db


def _edition():
    artist = Artist.objects.create(name="Fluke")
    rtype, _ = ReleaseType.objects.get_or_create(name="Album")
    release = Release.objects.create(name="Risotto", artist=artist, type=rtype)
    return Edition.objects.create(release=release)


def test_sample_stored_under_uuid_filename_preserving_extension():
    track = Track.objects.create(
        edition=_edition(),
        name="Blue",
        sample=ContentFile(b"audio", name="1.mp3"),
    )
    assert re.fullmatch(r"samples/[0-9a-f]{32}\.mp3", track.sample.name)
    assert track.sample.name != "samples/1.mp3"


def test_two_samples_with_same_name_do_not_collide():
    first = Track.objects.create(
        edition=_edition(),
        name="One",
        sample=ContentFile(b"audio", name="1.mp3"),
    )
    second = Track.objects.create(
        edition=_edition(),
        name="Two",
        sample=ContentFile(b"audio", name="1.mp3"),
    )
    assert first.sample.name != second.sample.name
