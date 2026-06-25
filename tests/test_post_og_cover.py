"""A blog Post with a cover_image composites it into its OG card."""

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.defaultfilters import date as date_filter
from django.utils import timezone
from PIL import Image

from apps.blog.models import Post

pytestmark = pytest.mark.django_db


def _solid_png(color=(0, 120, 200), size=(600, 600)):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _cover_upload():
    return SimpleUploadedFile("cover.png", _solid_png(), content_type="image/png")


def test_og_card_has_published_date_subtitle_and_cover_bytes():
    when = timezone.now()
    post = Post.objects.create(
        title="Atom Bomb reissue",
        is_published=True,
        published_at=when,
        cover_image=_cover_upload(),
    )
    title, subtitle, cover = post.og_card()

    assert title == post.resolved_og_title()
    assert subtitle == date_filter(when, "j F Y")
    assert isinstance(cover, bytes) and len(cover) > 0


def test_og_card_blank_subtitle_and_no_cover_when_unpublished_and_coverless():
    post = Post.objects.create(title="Draft, no cover")
    title, subtitle, cover = post.og_card()

    assert title == post.resolved_og_title()
    assert subtitle == ""
    assert cover is None


def test_cover_changes_the_generated_card():
    when = timezone.now()
    with_cover = Post.objects.create(
        title="Same Title", published_at=when, cover_image=_cover_upload()
    )
    without_cover = Post.objects.create(title="Same Title", published_at=when)

    with with_cover.og_image.open("rb") as fh:
        a = fh.read()
    with without_cover.og_image.open("rb") as fh:
        b = fh.read()
    assert a != b  # the cover is actually composited


def test_unreadable_cover_falls_back_to_none_without_crashing():
    post = Post.objects.create(title="Broken cover", cover_image=_cover_upload())
    # Point the field at a file that doesn't exist on disk.
    post.cover_image.name = "blog/does-not-exist.png"

    assert post._og_cover_bytes() is None
    assert post.og_card()[2] is None
    post.save()  # must not raise; falls back to a text-only card
