"""Tests for backfilling post publish dates/titles from a metadata file."""

import json

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.blog.models import Post
from apps.importers.post_metadata import normalize_path

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.2bitpie.net/2015/07/18/foo/", "/2015/07/18/foo"),
        ("http://2bitpie.net/2015/07/18/foo", "/2015/07/18/foo"),
        ("https://x/Foo/Bar/", "/foo/bar"),
        ("", ""),
    ],
)
def test_normalize_path(url, expected):
    assert normalize_path(url) == expected


def _write(tmp_path, entries):
    f = tmp_path / "meta.json"
    f.write_text(json.dumps(entries))
    return str(f)


def test_backfills_date_and_title_on_matching_unpublished_post(tmp_path):
    post = Post.objects.create(
        title="raw recovered title",
        source_url="http://www.2bitpie.net/2015/07/18/power-animals/",
        is_published=False,
    )
    meta = _write(tmp_path, [
        {"title": "Power Animals", "url": "https://www.2bitpie.net/2015/07/18/power-animals/",
         "date": "2015-07-18"},
    ])
    call_command("backfill_post_dates", file=meta)

    post.refresh_from_db()
    assert post.published_at is not None
    assert post.published_at.year == 2015 and post.published_at.month == 7
    assert post.title == "Power Animals"
    assert post.manually_edited is True
    assert post.is_published is False  # not auto-published


def test_does_not_touch_published_posts(tmp_path):
    when = timezone.now()
    post = Post.objects.create(
        title="Already live", source_url="http://x/2015/07/18/power-animals/",
        is_published=True, published_at=when,
    )
    meta = _write(tmp_path, [
        {"title": "Power Animals", "url": "https://x/2015/07/18/power-animals/", "date": "2011-01-01"},
    ])
    call_command("backfill_post_dates", file=meta)

    post.refresh_from_db()
    assert post.title == "Already live"
    assert post.published_at == when


def test_duplicates_update_only_the_first(tmp_path):
    a = Post.objects.create(title="A", source_url="http://www.x/2015/07/18/p/", is_published=False)
    b = Post.objects.create(title="B", source_url="https://x/2015/07/18/p/", is_published=False)
    meta = _write(tmp_path, [
        {"title": "P", "url": "https://x/2015/07/18/p/", "date": "2015-07-18"},
    ])
    call_command("backfill_post_dates", file=meta)

    a.refresh_from_db()
    b.refresh_from_db()
    first, second = sorted([a, b], key=lambda p: p.pk)
    assert first.published_at is not None and first.title == "P"
    assert second.published_at is None  # duplicate left as-is


def test_dry_run_changes_nothing(tmp_path):
    post = Post.objects.create(
        title="raw", source_url="http://x/2015/07/18/p/", is_published=False
    )
    meta = _write(tmp_path, [{"title": "P", "url": "https://x/2015/07/18/p/", "date": "2015-07-18"}])
    call_command("backfill_post_dates", file=meta, dry_run=True)
    post.refresh_from_db()
    assert post.published_at is None and post.title == "raw"


def test_no_titles_flag_keeps_existing_title(tmp_path):
    post = Post.objects.create(
        title="keep me", source_url="http://x/2015/07/18/p/", is_published=False
    )
    meta = _write(tmp_path, [{"title": "Changed", "url": "https://x/2015/07/18/p/", "date": "2015-07-18"}])
    call_command("backfill_post_dates", file=meta, no_titles=True)
    post.refresh_from_db()
    assert post.title == "keep me"
    assert post.published_at is not None  # date still applied
