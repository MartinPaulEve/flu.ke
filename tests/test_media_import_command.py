"""Integration tests for sha256_of and the import_media command (real temp IO)."""

import pytest
from django.core.management import call_command
from django.test import override_settings

from apps.discography.media_import import sha256_of
from apps.discography.models import Artist, CoverImage, Edition, Release, ReleaseType, Track
from apps.resources.models import Resource, ResourceFile

pytestmark = pytest.mark.django_db


def test_sha256_of_known_value(tmp_path):
    target = tmp_path / "f.txt"
    target.write_bytes(b"hello")
    assert sha256_of(target) == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


def _make_files(root):
    (root / "Covers" / "DLS").mkdir(parents=True)
    (root / "Samples").mkdir(parents=True)
    (root / "Covers" / "DLS" / "DLSFront.jpg").write_bytes(b"\xff\xd8jpeg-front")
    (root / "Samples" / "track1.mp3").write_bytes(b"id3-audio-sample")
    (root / "JCToshRemix2012.mp3").write_bytes(b"a-fan-remix")
    (root / "BBC Radio 1.zip").write_bytes(b"PK-official-archive")
    (root / "stray.pdf").write_bytes(b"%PDF-doc")


def _seed_discography():
    fluke = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    release = Release.objects.create(name="Dark Like Snow", artist=fluke, type=rtype)
    edition = Edition.objects.create(release=release, name="Promo")
    cover = CoverImage.objects.create(
        edition=edition,
        display_name="Front",
        kind="front",
        source_url="http://www.2bitpie.net/Files/Covers/DLS/DLSFront.jpg",
    )
    track = Track.objects.create(
        edition=edition,
        track_number="01",
        name="Key Lime Heart",
        sample_source_url="http://2bitpie.net/Files/Samples/track1.mp3",
    )
    return cover, track


def _run(files_dir, media_root):
    with override_settings(MEDIA_ROOT=media_root):
        call_command("import_media", files_dir=str(files_dir))


def test_matches_cover_and_sample_and_copies_files(tmp_path):
    files_dir = tmp_path / "Files"
    files_dir.mkdir()
    _make_files(files_dir)
    media_root = tmp_path / "media"
    cover, track = _seed_discography()

    _run(files_dir, media_root)

    cover.refresh_from_db()
    track.refresh_from_db()
    assert cover.image.name  # FileField populated
    assert (media_root / cover.image.name).exists()
    assert track.sample.name
    assert (media_root / track.sample.name).exists()


def test_unmatched_audio_and_archive_become_resources(tmp_path):
    files_dir = tmp_path / "Files"
    files_dir.mkdir()
    _make_files(files_dir)
    _seed_discography()

    _run(files_dir, tmp_path / "media")

    kinds = dict(Resource.objects.values_list("title", "kind"))
    # the remix is classified fan; the radio archive official
    assert any("JCToshRemix" in t and k == "fan" for t, k in kinds.items())
    assert any("BBC Radio 1" in t and k == "official" for t, k in kinds.items())
    # the matched cover/sample files are NOT turned into resources
    assert not Resource.objects.filter(title__icontains="DLSFront").exists()
    assert not Resource.objects.filter(title__icontains="track1").exists()


def test_resource_files_have_checksum_and_size(tmp_path):
    files_dir = tmp_path / "Files"
    files_dir.mkdir()
    _make_files(files_dir)
    _seed_discography()

    _run(files_dir, tmp_path / "media")

    rf = ResourceFile.objects.get(resource__title__icontains="JCToshRemix")
    assert len(rf.checksum) == 64
    assert rf.byte_size == len(b"a-fan-remix")
    assert rf.file_kind == "audio"


def test_import_media_is_idempotent(tmp_path):
    files_dir = tmp_path / "Files"
    files_dir.mkdir()
    _make_files(files_dir)
    _seed_discography()
    media_root = tmp_path / "media"

    _run(files_dir, media_root)
    resources_after_first = Resource.objects.count()
    files_after_first = ResourceFile.objects.count()
    _run(files_dir, media_root)

    assert Resource.objects.count() == resources_after_first
    assert ResourceFile.objects.count() == files_after_first
