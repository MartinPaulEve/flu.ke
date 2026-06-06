"""Tests for the regenerate_og command."""

from io import BytesIO

import pytest
from django.core.management import call_command
from PIL import Image

from apps.blog.models import Post

pytestmark = pytest.mark.django_db


def test_regenerates_a_valid_og_image():
    post = Post.objects.create(title="Some Title")
    post.og_image.delete(save=False)
    post.og_image = ""
    Post.objects.filter(pk=post.pk).update(og_image="")  # simulate a missing image

    call_command("regenerate_og")

    post.refresh_from_db()
    assert post.og_image.name
    img = Image.open(BytesIO(post.og_image.read()))
    assert img.size == (1200, 630)


def test_does_not_accumulate_files_on_rerun():
    post = Post.objects.create(title="Title")
    call_command("regenerate_og")
    first = Post.objects.get(pk=post.pk).og_image.name
    call_command("regenerate_og")
    # the filename is reused (old file deleted first), not suffixed _xyz each run
    assert Post.objects.get(pk=post.pk).og_image.name == first


def test_missing_only_skips_posts_with_an_image():
    post = Post.objects.create(title="Has image")  # save() generates one
    existing = Post.objects.get(pk=post.pk).og_image.name
    call_command("regenerate_og", missing_only=True)
    assert Post.objects.get(pk=post.pk).og_image.name == existing


def test_regenerates_across_all_content_types():
    from apps.discography.models import Artist, Lyric, Release, ReleaseType
    from apps.pages.models import Page

    artist = Artist.objects.create(name="Fluke")
    release = Release.objects.create(
        name="Risotto", artist=artist, type=ReleaseType.objects.create(name="Albums")
    )
    lyric = Lyric.objects.create(title="Bullet", lyrics="x")
    page = Page.objects.create(title="About")

    # Clear every image so the command has to repopulate them.
    targets = [(Artist, artist.pk), (Release, release.pk), (Lyric, lyric.pk), (Page, page.pk)]
    for model, pk in targets:
        obj = model.objects.get(pk=pk)
        obj.og_image.delete(save=False)
        model.objects.filter(pk=pk).update(og_image="")

    call_command("regenerate_og")

    for model, pk in targets:
        assert model.objects.get(pk=pk).og_image.name, f"{model.__name__} not regenerated"
