"""Posts can surface related resources in their side rail, with concise metadata."""

import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.blog.models import Post
from apps.resources.models import (
    KIND_OFFICIAL,
    Resource,
    ResourceFile,
    ResourceSubcategory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def post():
    return Post.objects.create(
        title="An interview is up",
        body="Words.",
        is_published=True,
        published_at=timezone.now(),
    )


# -- the concise summary used in the rail --------------------------------


def test_rail_summary_describes_kind_size_and_year():
    sub = ResourceSubcategory.objects.create(
        name="Interviews", kind=KIND_OFFICIAL, snippet_phrase="interview"
    )
    r = Resource.objects.create(
        title="Mixmag Interview", kind=KIND_OFFICIAL, subcategory=sub,
        recorded_date=datetime.date(2014, 1, 1), recorded_precision="year",
    )
    ResourceFile.objects.create(
        resource=r,
        file=SimpleUploadedFile("a.mp3", b"x" * 2048),
        file_kind="audio",
        byte_size=0,  # falls back to the real file size
    )

    summary = r.rail_summary
    assert "Official interview" in summary  # what it is (from the subcategory phrase)
    assert "KB" in summary                  # its size (2048 bytes -> 2.0 KB)
    assert "2014" in summary                # its date


# -- rendered in the post rail -------------------------------------------


def test_related_resource_appears_in_the_rail_with_metadata(client, post):
    r = Resource.objects.create(
        title="Mixmag Interview", kind=KIND_OFFICIAL, is_published=True,
        recorded_date=datetime.date(2014, 1, 1), recorded_precision="year",
    )
    ResourceFile.objects.create(
        resource=r, file="resources/x.mp3", file_kind="audio", byte_size=2_000_000
    )
    post.related_resources.add(r)

    html = client.get(post.get_absolute_url()).content.decode()

    assert "Related resources" in html
    assert "Mixmag Interview" in html
    assert f'href="{r.get_absolute_url()}"' in html
    assert "MB" in html   # size
    assert "2014" in html  # date


def test_unpublished_related_resource_is_hidden(client, post):
    r = Resource.objects.create(
        title="Secret Resource", kind=KIND_OFFICIAL, is_published=False
    )
    post.related_resources.add(r)

    html = client.get(post.get_absolute_url()).content.decode()

    assert "Secret Resource" not in html


def test_post_without_related_resources_omits_the_heading(client, post):
    html = client.get(post.get_absolute_url()).content.decode()
    assert "Related resources" not in html
