"""Resource file rows show the download size, even when byte_size wasn't recorded."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.resources.models import Resource, ResourceFile

pytestmark = pytest.mark.django_db


def test_display_byte_size_prefers_the_recorded_value():
    f = ResourceFile(byte_size=1_336_532)
    assert f.display_byte_size == 1_336_532


def test_display_byte_size_falls_back_to_the_stored_file():
    resource = Resource.objects.create(title="Set", kind="official")
    payload = b"x" * 2048
    f = ResourceFile.objects.create(
        resource=resource,
        file=SimpleUploadedFile("set.mp3", payload),
        file_kind="audio",
        byte_size=0,  # never recorded
    )
    assert f.display_byte_size == len(payload)


def test_display_byte_size_is_none_when_unknown():
    f = ResourceFile(byte_size=0)
    assert f.display_byte_size is None


def test_resource_page_shows_the_download_size(client):
    resource = Resource.objects.create(title="Live Set", kind="official", is_published=True)
    ResourceFile.objects.create(
        resource=resource,
        file=SimpleUploadedFile("set.mp3", b"x" * 2048),
        file_kind="audio",
        byte_size=0,
    )

    html = client.get(resource.get_absolute_url()).content.decode()

    assert "2.0" in html and "KB" in html  # filesizeformat of 2048 bytes
