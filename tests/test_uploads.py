"""A tracked Upload model + a TinyMCE image-upload endpoint for the admin editor."""

import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.core.models import Upload

pytestmark = pytest.mark.django_db


def test_upload_stores_file_under_a_uuid_name():
    up = Upload.objects.create(
        title="A pic", file=SimpleUploadedFile("My Photo.PNG", b"x" * 8)
    )
    assert up.file.name.startswith("uploads/")
    assert up.file.name.endswith(".png")  # lowercased original extension kept
    stem = up.file.name[len("uploads/"):-len(".png")]
    assert re.fullmatch(r"[0-9a-f]{32}", stem)  # a uuid, not the original name
    assert "My Photo" not in up.file.name


def test_tinymce_upload_creates_an_upload_and_returns_its_location(admin_client):
    resp = admin_client.post(
        reverse("tinymce_upload"),
        {"file": SimpleUploadedFile("logo.png", b"img-bytes")},
    )
    assert resp.status_code == 200
    location = resp.json()["location"]
    assert location.endswith(".png")
    upload = Upload.objects.get()
    assert upload.file.url == location
    assert upload.title == "logo.png"  # original filename, for the admin


def test_tinymce_upload_requires_a_logged_in_staff_user(client):
    resp = client.post(
        reverse("tinymce_upload"), {"file": SimpleUploadedFile("x.png", b"i")}
    )
    assert resp.status_code in (302, 403)  # bounced to the admin login
    assert Upload.objects.count() == 0


def test_tinymce_upload_rejects_a_request_with_no_file(admin_client):
    resp = admin_client.post(reverse("tinymce_upload"))
    assert resp.status_code == 400
    assert Upload.objects.count() == 0
