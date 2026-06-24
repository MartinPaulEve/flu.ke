"""Locked resource files: stored for archival, downloadable only by staff."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db


def test_private_storage_location_follows_setting(settings, tmp_path):
    from apps.resources.storage import private_storage

    settings.PRIVATE_MEDIA_ROOT = str(tmp_path / "priv")
    name = private_storage.save("resources/x.bin", SimpleUploadedFile("x.bin", b"hi"))

    assert private_storage.path(name).startswith(str(tmp_path / "priv"))
    assert (tmp_path / "priv" / name).read_bytes() == b"hi"
