"""Individual resource files can carry their own purchase link, shown on the
detail page when present."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.resources.models import Resource, ResourceFile

pytestmark = pytest.mark.django_db


def _resource():
    return Resource.objects.create(title="Boxset", kind="official", is_published=True)


def test_file_purchase_url_blank_by_default():
    rf = ResourceFile.objects.create(
        resource=_resource(), file=SimpleUploadedFile("a.mp3", b"x"), file_kind="audio"
    )
    assert rf.purchase_url == ""


def test_detail_renders_file_purchase_link_when_present(client):
    r = _resource()
    ResourceFile.objects.create(
        resource=r,
        file=SimpleUploadedFile("a.mp3", b"x"),
        file_kind="audio",
        purchase_url="https://shop.example/file",
    )
    html = client.get(r.get_absolute_url()).content.decode()
    assert 'href="https://shop.example/file"' in html


def test_detail_no_file_purchase_link_when_absent(client):
    r = _resource()
    ResourceFile.objects.create(
        resource=r, file=SimpleUploadedFile("a.mp3", b"x"), file_kind="audio"
    )
    html = client.get(r.get_absolute_url()).content.decode()
    assert "shop.example" not in html


def test_locked_file_can_still_show_purchase_link(client):
    r = _resource()
    ResourceFile.objects.create(
        resource=r,
        file=SimpleUploadedFile("a.flac", b"AUDIO"),
        file_kind="audio",
        is_locked=True,
        purchase_url="https://shop.example/buy-the-physical",
    )
    html = client.get(r.get_absolute_url()).content.decode()
    assert 'href="https://shop.example/buy-the-physical"' in html
