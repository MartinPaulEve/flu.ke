"""Regression: a hostile title/name must not break out of the JSON-LD script."""

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from apps.blog.models import Post
from apps.discography.models import Artist, Release, ReleaseType

pytestmark = pytest.mark.django_db

PAYLOAD = "</script><script>alert(1)</script>"


def _built_html(tmp_path):
    with override_settings(BUILD_DIR=str(tmp_path)):
        call_command("build_site", no_media=True)
    return "\n".join(p.read_text() for p in tmp_path.rglob("*.html"))


def test_release_name_cannot_break_out_of_jsonld(tmp_path):
    fluke = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    Release.objects.create(name=PAYLOAD, artist=fluke, type=rtype)
    assert "<script>alert(1)" not in _built_html(tmp_path)


def test_post_title_cannot_break_out_of_jsonld(tmp_path):
    Post.objects.create(title=PAYLOAD, is_published=True, published_at=timezone.now())
    assert "<script>alert(1)" not in _built_html(tmp_path)
