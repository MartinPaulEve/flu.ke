"""End-to-end test of the build_site command against a temp build dir."""

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from apps.blog.models import Post
from apps.discography.models import Artist, Edition, Release, ReleaseType, Track
from apps.pages.models import Page

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded():
    fluke = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    release = Release.objects.create(name="Risotto", artist=fluke, type=rtype, year=1997)
    edition = Edition.objects.create(release=release, media="CD")
    Track.objects.create(edition=edition, track_number="01", name="Squelch")
    Page.objects.create(title="About", body="# Hello\n\nWe run this.", is_published=True)
    Post.objects.create(
        title="Hello world", body="**hi**", is_published=True, published_at=timezone.now()
    )


def _build(tmp_path, **kwargs):
    with override_settings(BUILD_DIR=str(tmp_path)):
        call_command("build_site", **kwargs)


def test_build_writes_expected_pages(tmp_path, seeded):
    _build(tmp_path, no_media=True)
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "news" / "index.html").exists()
    assert (tmp_path / "discography" / "index.html").exists()
    assert (tmp_path / "discography" / "fluke" / "risotto" / "index.html").exists()
    assert (tmp_path / "about" / "index.html").exists()
    assert (tmp_path / "sitemap.xml").exists()
    assert (tmp_path / "robots.txt").exists()


def test_release_page_contains_rendered_content(tmp_path, seeded):
    _build(tmp_path, no_media=True)
    html = (tmp_path / "discography" / "fluke" / "risotto" / "index.html").read_text()
    assert "Risotto" in html
    assert "Squelch" in html  # track rendered


def test_markdown_body_is_rendered_to_html(tmp_path, seeded):
    _build(tmp_path, no_media=True)
    html = (tmp_path / "about" / "index.html").read_text()
    assert "<h1" in html and "Hello" in html  # markdown heading rendered


def test_incremental_rebuild_skips_unchanged(tmp_path, seeded, capsys):
    _build(tmp_path, no_media=True)
    _build(tmp_path, no_media=True)
    out = capsys.readouterr().out
    assert "0 pages" in out  # second run rebuilt nothing
