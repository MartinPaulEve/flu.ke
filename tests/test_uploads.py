"""A tracked Upload model + a hardened TinyMCE image-upload endpoint."""

import io
import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.core.admin import UploadAdminForm
from apps.core.models import Upload

pytestmark = pytest.mark.django_db

ORIGIN = "http://testserver"  # same origin as the test client's host


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), "red").save(buf, format="PNG")
    return buf.getvalue()


def test_upload_stores_file_under_a_uuid_name():
    up = Upload.objects.create(
        title="A pic", file=SimpleUploadedFile("My Photo.PNG", b"x" * 8)
    )
    assert up.file.name.startswith("uploads/")
    assert up.file.name.endswith(".png")  # lowercased original extension kept
    stem = up.file.name[len("uploads/"):-len(".png")]
    assert re.fullmatch(r"[0-9a-f]{32}", stem)  # a uuid, not the original name
    assert "My Photo" not in up.file.name


def _upload(admin_client, name, content, origin=ORIGIN):
    extra = {"HTTP_ORIGIN": origin} if origin else {}
    return admin_client.post(
        reverse("tinymce_upload"),
        {"file": SimpleUploadedFile(name, content)},
        **extra,
    )


def test_tinymce_upload_creates_an_upload_and_returns_its_location(admin_client):
    resp = _upload(admin_client, "logo.png", _png_bytes())
    assert resp.status_code == 200
    location = resp.json()["location"]
    assert location.endswith(".png")
    upload = Upload.objects.get()
    assert upload.file.url == location
    assert upload.title == "logo.png"  # original filename, for the admin


def test_tinymce_upload_rejects_non_image_content(admin_client):
    # An .png name but SVG/script bytes — Pillow verification rejects it.
    resp = _upload(admin_client, "evil.png", b"<svg onload=alert(1)></svg>")
    assert resp.status_code == 400
    assert Upload.objects.count() == 0


def test_tinymce_upload_refuses_cross_origin(admin_client):
    resp = _upload(admin_client, "logo.png", _png_bytes(), origin="https://evil.example")
    assert resp.status_code == 403
    assert Upload.objects.count() == 0


def test_tinymce_upload_requires_a_logged_in_staff_user(client):
    resp = _upload(client, "logo.png", _png_bytes())
    assert resp.status_code in (302, 403)  # bounced to the admin login
    assert Upload.objects.count() == 0


def test_tinymce_upload_rejects_a_request_with_no_file(admin_client):
    resp = admin_client.post(reverse("tinymce_upload"), HTTP_ORIGIN=ORIGIN)
    assert resp.status_code == 400
    assert Upload.objects.count() == 0


def test_admin_upload_form_rejects_scriptable_files():
    form = UploadAdminForm(
        data={"title": "logo"},
        files={"file": SimpleUploadedFile("logo.svg", b"<svg/>")},
    )
    assert not form.is_valid()
    assert "file" in form.errors
