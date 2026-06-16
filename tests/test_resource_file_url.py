"""A resource file can be a remote URL instead of an uploaded file."""

import pytest
from django.core.exceptions import ValidationError

from apps.resources.models import KIND_OFFICIAL, Resource, ResourceFile

pytestmark = pytest.mark.django_db


def test_external_url_file_exposes_a_remote_download():
    r = Resource.objects.create(title="A set", kind=KIND_OFFICIAL)
    f = ResourceFile.objects.create(
        resource=r,
        external_url="https://archive.org/download/set/set.mp3",
        file_kind="audio",
    )
    assert f.is_external is True
    assert f.download_url == "https://archive.org/download/set/set.mp3"
    assert f.display_name == "set.mp3"  # derived from the URL when no filename given


def test_uploaded_file_is_not_external():
    r = Resource.objects.create(title="A set", kind=KIND_OFFICIAL)
    f = ResourceFile.objects.create(
        resource=r, file="resources/set.mp3", file_kind="audio"
    )
    assert f.is_external is False
    assert f.download_url == f.file.url


def test_a_file_must_have_either_an_upload_or_a_url():
    r = Resource.objects.create(title="A set", kind=KIND_OFFICIAL)
    f = ResourceFile(resource=r, file_kind="audio")  # neither file nor url
    with pytest.raises(ValidationError):
        f.full_clean()


def test_resource_page_links_an_external_file(client):
    r = Resource.objects.create(title="Live Set", kind=KIND_OFFICIAL, is_published=True)
    ResourceFile.objects.create(
        resource=r,
        external_url="https://archive.org/download/set/set.mp3",
        original_filename="set.mp3",
        file_kind="audio",
    )

    html = client.get(r.get_absolute_url()).content.decode()

    assert 'href="https://archive.org/download/set/set.mp3"' in html
    assert "set.mp3" in html
    assert "Audio" in html  # presented like any other file (its kind on the right)
