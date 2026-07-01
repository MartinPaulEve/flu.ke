"""Resource OG cards draw on the first image file (or a locked file's preview
image), mirroring how release cards use album covers."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.resources.models import Resource, ResourceFile

pytestmark = pytest.mark.django_db


def _resource():
    return Resource.objects.create(title="Scans", kind="fan", is_published=True)


def _file(resource, **kw):
    return ResourceFile.objects.create(resource=resource, **kw)


def test_og_cover_uses_first_image_file():
    r = _resource()
    _file(r, file=SimpleUploadedFile("a.mp3", b"AUDIO"), file_kind="audio", display_order=0)
    _file(r, file=SimpleUploadedFile("first.png", b"IMG1"), file_kind="image", display_order=1)
    _file(r, file=SimpleUploadedFile("second.png", b"IMG2"), file_kind="image", display_order=2)
    assert r._og_cover_bytes() == b"IMG1"


def test_og_cover_none_without_images_or_previews():
    r = _resource()
    _file(r, file=SimpleUploadedFile("a.mp3", b"AUDIO"), file_kind="audio")
    assert r._og_cover_bytes() is None


def test_og_cover_uses_locked_preview_image_regardless_of_kind():
    r = _resource()
    _file(
        r,
        file=SimpleUploadedFile("doc.pdf", b"PDF"),
        file_kind="document",
        is_locked=True,
        preview_image=SimpleUploadedFile("thumb.png", b"THUMB"),
    )
    assert r._og_cover_bytes() == b"THUMB"


def test_og_cover_skips_locked_file_without_preview():
    r = _resource()
    _file(
        r,
        file=SimpleUploadedFile("doc.pdf", b"PDF"),
        file_kind="document",
        is_locked=True,
        display_order=0,
    )
    _file(r, file=SimpleUploadedFile("pic.png", b"PIC"), file_kind="image", display_order=1)
    assert r._og_cover_bytes() == b"PIC"


def test_og_cover_does_not_leak_locked_image_bytes():
    """A locked image file with no preview must not expose its private bytes."""
    r = _resource()
    _file(
        r,
        file=SimpleUploadedFile("secret.png", b"SECRET"),
        file_kind="image",
        is_locked=True,
    )
    assert r._og_cover_bytes() is None


def test_og_card_supplies_cover_bytes():
    r = _resource()
    _file(r, file=SimpleUploadedFile("cover.png", b"IMG"), file_kind="image")
    _title, _subtitle, cover = r.og_card()
    assert cover == b"IMG"
