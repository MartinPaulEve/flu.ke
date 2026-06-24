"""Locked resource files: stored for archival, downloadable only by staff."""

import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.resources.models import Resource, ResourceFile

pytestmark = pytest.mark.django_db


def test_private_storage_location_follows_setting(settings, tmp_path):
    from apps.resources.storage import private_storage

    settings.PRIVATE_MEDIA_ROOT = str(tmp_path / "priv")
    name = private_storage.save("resources/x.bin", SimpleUploadedFile("x.bin", b"hi"))

    assert private_storage.path(name).startswith(str(tmp_path / "priv"))
    assert (tmp_path / "priv" / name).read_bytes() == b"hi"


def _resource():
    return Resource.objects.create(title="Mag Interview", kind="official", is_published=True)


def test_is_locked_defaults_false():
    f = ResourceFile(resource=_resource(), file=SimpleUploadedFile("a.mp3", b"x"))
    assert f.is_locked is False


def test_locking_moves_bytes_into_private_storage(settings):
    rf = ResourceFile.objects.create(
        resource=_resource(),
        file=SimpleUploadedFile("set.flac", b"AUDIO"),
        file_kind="audio",
    )
    public_path = rf.file.path
    assert rf.file and not rf.locked_file

    rf.is_locked = True
    rf.save()
    rf.refresh_from_db()

    assert rf.locked_file and not rf.file
    assert rf.locked_file.read() == b"AUDIO"
    assert rf.locked_file.path.startswith(str(settings.PRIVATE_MEDIA_ROOT))
    assert not os.path.exists(public_path)


def test_unlocking_moves_bytes_back_to_public_storage(settings):
    rf = ResourceFile.objects.create(
        resource=_resource(),
        file=SimpleUploadedFile("set.flac", b"AUDIO"),
        is_locked=True,
    )
    assert rf.locked_file and not rf.file

    rf.is_locked = False
    rf.save()
    rf.refresh_from_db()

    assert rf.file and not rf.locked_file
    assert rf.file.read() == b"AUDIO"
    assert str(settings.MEDIA_ROOT) in rf.file.path


def test_locked_external_link_has_no_bytes_to_move():
    rf = ResourceFile.objects.create(
        resource=_resource(),
        external_url="https://example.com/x.zip",
        is_locked=True,
    )
    assert rf.is_external is True
    assert not rf.file and not rf.locked_file
