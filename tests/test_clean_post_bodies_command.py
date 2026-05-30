"""Integration test for the clean_post_bodies command (real temp media/ingest)."""

import pytest
from django.core.management import call_command

from apps.blog.models import Post

pytestmark = pytest.mark.django_db

SHARE = '<div class="sharedaddy"><h3 class="sd-title">Share this:</h3></div>'


def _setup(tmp_path, settings):
    media = tmp_path / "media"
    media.mkdir()
    files = tmp_path / "ingest" / "public_html" / "Files"
    files.mkdir(parents=True)
    (files / "orange_flower.jpg").write_bytes(b"a fake image")
    settings.MEDIA_ROOT = str(media)
    settings.MEDIA_URL = "/media/"
    settings.INGEST_DIR = str(tmp_path / "ingest")
    return media


def test_strips_share_and_remaps_and_copies(tmp_path, settings):
    media = _setup(tmp_path, settings)
    post = Post.objects.create(
        title="P",
        body='<p>Hi <img src="http://www.2bitpie.net/2bitpie/Files/orange_flower.jpg"/></p>' + SHARE,
    )
    call_command("clean_post_bodies")

    post.refresh_from_db()
    assert "sharedaddy" not in post.body
    assert "Share this" not in post.body
    assert "/media/posts/orange_flower.jpg" in post.body
    assert "2bitpie.net" not in post.body
    assert (media / "posts" / "orange_flower.jpg").exists()  # copied from Ingest


def test_dry_run_makes_no_changes(tmp_path, settings):
    _setup(tmp_path, settings)
    post = Post.objects.create(title="P", body="<p>x</p>" + SHARE)
    call_command("clean_post_bodies", dry_run=True)
    post.refresh_from_db()
    assert "sharedaddy" in post.body


def test_is_idempotent(tmp_path, settings):
    _setup(tmp_path, settings)
    post = Post.objects.create(title="P", body="<p>x</p>" + SHARE)
    call_command("clean_post_bodies")
    after_first = Post.objects.get(pk=post.pk).body
    call_command("clean_post_bodies")
    assert Post.objects.get(pk=post.pk).body == after_first
