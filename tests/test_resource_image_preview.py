"""Image resource files render an inline preview of themselves, mirroring the
existing locked-file ``preview_image`` behaviour."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.resources.models import Resource, ResourceFile

pytestmark = pytest.mark.django_db


def _resource():
    return Resource.objects.create(title="Sleeve scan", kind="fan", is_published=True)


# ---------------------------------------------------------------------------
# image_preview_url property
# ---------------------------------------------------------------------------


def test_public_image_file_previews_its_own_url():
    rf = ResourceFile.objects.create(
        resource=_resource(),
        file=SimpleUploadedFile("cover.jpg", b"IMG"),
        file_kind="image",
    )
    assert rf.image_preview_url == rf.file.url


def test_external_image_previews_via_its_url():
    rf = ResourceFile.objects.create(
        resource=_resource(),
        external_url="https://example.com/cover.jpg",
        file_kind="image",
    )
    assert rf.image_preview_url == "https://example.com/cover.jpg"


def test_non_image_file_has_no_preview():
    rf = ResourceFile.objects.create(
        resource=_resource(),
        file=SimpleUploadedFile("track.mp3", b"AUDIO"),
        file_kind="audio",
    )
    assert rf.image_preview_url is None


def test_locked_image_uses_preview_image_not_private_bytes():
    rf = ResourceFile.objects.create(
        resource=_resource(),
        file=SimpleUploadedFile("scan.png", b"IMG"),
        file_kind="image",
        preview_image=SimpleUploadedFile("thumb.png", b"THUMB"),
        is_locked=True,
    )
    # Locked: the real bytes live in private storage; only the public thumbnail
    # may be shown.
    assert rf.image_preview_url == rf.preview_image.url


def test_locked_image_without_preview_image_has_no_preview():
    rf = ResourceFile.objects.create(
        resource=_resource(),
        file=SimpleUploadedFile("scan.png", b"IMG"),
        file_kind="image",
        is_locked=True,
    )
    assert rf.image_preview_url is None


# ---------------------------------------------------------------------------
# Detail page rendering
# ---------------------------------------------------------------------------


def test_detail_renders_img_for_public_image_file(client):
    r = _resource()
    rf = ResourceFile.objects.create(
        resource=r, file=SimpleUploadedFile("cover.jpg", b"IMG"), file_kind="image"
    )
    html = client.get(r.get_absolute_url()).content.decode()
    assert f'src="{rf.file.url}"' in html


def test_detail_does_not_render_img_for_audio_file(client):
    r = _resource()
    rf = ResourceFile.objects.create(
        resource=r, file=SimpleUploadedFile("track.mp3", b"AUDIO"), file_kind="audio"
    )
    html = client.get(r.get_absolute_url()).content.decode()
    assert f'src="{rf.file.url}"' not in html
