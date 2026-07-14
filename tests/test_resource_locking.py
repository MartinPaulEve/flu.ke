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


# ---------------------------------------------------------------------------
# display_name fix: locked file (no original_filename) still shows a name
# ---------------------------------------------------------------------------


def test_locked_file_display_name_is_non_empty():
    """A locked file with no original_filename must return a non-empty display_name."""
    rf = ResourceFile.objects.create(
        resource=_resource(),
        file=SimpleUploadedFile("set.flac", b"AUDIO"),
        is_locked=True,
    )
    # After locking, file is empty and locked_file holds the bytes.
    assert not rf.file
    assert rf.locked_file
    assert rf.display_name != ""


# ---------------------------------------------------------------------------
# Gated download view
# ---------------------------------------------------------------------------

from django.contrib.auth import get_user_model  # noqa: E402
from django.urls import reverse  # noqa: E402


def _staff_client(client):
    user = get_user_model().objects.create_user("ed", password="x", is_staff=True)
    client.force_login(user)
    return client


def test_locked_download_404_for_anonymous(client):
    rf = ResourceFile.objects.create(
        resource=_resource(), file=SimpleUploadedFile("s.flac", b"AUDIO"), is_locked=True
    )
    resp = client.get(reverse("resource_file_download", args=[rf.pk]))
    assert resp.status_code == 404


def test_locked_download_streams_for_staff(client):
    rf = ResourceFile.objects.create(
        resource=_resource(), file=SimpleUploadedFile("s.flac", b"AUDIO"), is_locked=True
    )
    resp = _staff_client(client).get(reverse("resource_file_download", args=[rf.pk]))
    assert resp.status_code == 200
    assert b"".join(resp.streaming_content) == b"AUDIO"


def test_download_url_is_gated_when_locked(client):
    rf = ResourceFile.objects.create(
        resource=_resource(), file=SimpleUploadedFile("s.flac", b"AUDIO"), is_locked=True
    )
    assert rf.download_url == reverse("resource_file_download", args=[rf.pk])


def test_download_url_unchanged_when_unlocked():
    rf = ResourceFile.objects.create(
        resource=_resource(), file=SimpleUploadedFile("s.flac", b"AUDIO")
    )
    assert rf.download_url == rf.file.url


def test_gated_view_redirects_unlocked_to_public_url(client):
    rf = ResourceFile.objects.create(
        resource=_resource(), file=SimpleUploadedFile("s.flac", b"AUDIO")
    )
    resp = client.get(reverse("resource_file_download", args=[rf.pk]))
    assert resp.status_code == 302
    assert resp["Location"] == rf.file.url


# ---------------------------------------------------------------------------
# Detail page: locked file rendering
# ---------------------------------------------------------------------------


def test_detail_hides_link_and_shows_notice_for_locked_anon(client):
    r = _resource()
    ResourceFile.objects.create(
        resource=r, file=SimpleUploadedFile("s.flac", b"AUDIO"), is_locked=True
    )
    html = client.get(r.get_absolute_url()).content.decode()
    assert reverse("resource_file_download", args=[r.files.first().pk]) not in html
    assert "Archived" in html


def test_detail_shows_link_for_locked_staff(client):
    r = _resource()
    rf = ResourceFile.objects.create(
        resource=r, file=SimpleUploadedFile("s.flac", b"AUDIO"), is_locked=True
    )
    html = _staff_client(client).get(r.get_absolute_url()).content.decode()
    assert reverse("resource_file_download", args=[rf.pk]) in html


# ---------------------------------------------------------------------------
# Detail page: explainer for resources holding locked files
# ---------------------------------------------------------------------------


def test_has_locked_files_true_when_any_file_is_locked():
    r = _resource()
    ResourceFile.objects.create(resource=r, file=SimpleUploadedFile("a.mp3", b"x"))
    ResourceFile.objects.create(
        resource=r, file=SimpleUploadedFile("b.flac", b"y"), is_locked=True
    )
    assert r.has_locked_files is True


def test_has_locked_files_false_when_no_file_is_locked():
    r = _resource()
    ResourceFile.objects.create(resource=r, file=SimpleUploadedFile("a.mp3", b"x"))
    assert r.has_locked_files is False


def test_has_locked_files_false_without_files():
    assert _resource().has_locked_files is False


def test_detail_explains_locked_items_when_resource_has_them(client):
    r = _resource()
    ResourceFile.objects.create(
        resource=r, file=SimpleUploadedFile("s.flac", b"AUDIO"), is_locked=True
    )
    html = client.get(r.get_absolute_url()).content.decode()
    assert "preservation purposes" in html


def test_detail_omits_locked_explainer_when_no_locked_files(client):
    r = _resource()
    ResourceFile.objects.create(resource=r, file=SimpleUploadedFile("s.mp3", b"AUDIO"))
    html = client.get(r.get_absolute_url()).content.decode()
    assert "preservation purposes" not in html


# ---------------------------------------------------------------------------
# Admin: locking fields surfaced in inline and list views
# ---------------------------------------------------------------------------


def test_admin_inline_exposes_locking_fields():
    from apps.resources.admin import ResourceFileInline

    assert "is_locked" in ResourceFileInline.fields
    assert "preview_image" in ResourceFileInline.fields
