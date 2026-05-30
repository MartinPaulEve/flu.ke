"""reconcile_posts: dedupe + retitle/redate posts from the comprehensive list."""

import json

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.blog.models import Post

pytestmark = pytest.mark.django_db


def _meta(tmp_path, entries):
    f = tmp_path / "m.json"
    f.write_text(json.dumps(entries))
    return str(f)


def test_updates_canonical_and_deletes_unpublished_duplicates(tmp_path):
    Post.objects.create(title="raw a", source_url="http://www.x/2015/07/18/p/", is_published=False)
    Post.objects.create(title="raw b", source_url="https://x/2015/07/18/p/", is_published=False)
    meta = _meta(tmp_path, [{"title": "Power Animals", "url": "https://x/2015/07/18/p/", "date": "2015-07-18"}])

    call_command("reconcile_posts", file=meta)

    assert Post.objects.count() == 1
    p = Post.objects.get()
    assert p.title == "Power Animals"
    assert p.published_at.year == 2015
    assert p.manually_edited is True


def test_prefers_published_post_as_canonical(tmp_path):
    pub = Post.objects.create(
        title="live", source_url="http://x/2015/07/18/p/", is_published=True, published_at=timezone.now()
    )
    draft = Post.objects.create(title="draft", source_url="https://x/2015/07/18/p/", is_published=False)
    meta = _meta(tmp_path, [{"title": "P", "url": "https://x/2015/07/18/p/", "date": "2015-07-18"}])

    call_command("reconcile_posts", file=meta)

    assert not Post.objects.filter(pk=draft.pk).exists()  # duplicate draft removed
    pub.refresh_from_db()
    assert pub.is_published is True  # published kept as canonical
    assert pub.title == "P"


def test_creates_missing_post(tmp_path):
    meta = _meta(tmp_path, [{"title": "Brand New", "url": "https://x/2015/07/18/new/", "date": "2015-07-18"}])
    call_command("reconcile_posts", file=meta)
    p = Post.objects.get(source_url="https://x/2015/07/18/new/")
    assert p.title == "Brand New"
    assert p.published_at.year == 2015


def test_prune_junk_removes_unpublished_nonposts(tmp_path):
    junk = Post.objects.create(title="2bitpie.net", source_url="http://x/month-list.aspx", is_published=False)
    real = Post.objects.create(title="raw", source_url="https://x/2015/07/18/p/", is_published=False)
    meta = _meta(tmp_path, [{"title": "P", "url": "https://x/2015/07/18/p/", "date": "2015-07-18"}])

    call_command("reconcile_posts", file=meta, prune_junk=True)

    assert not Post.objects.filter(pk=junk.pk).exists()
    assert Post.objects.filter(pk=real.pk).exists()


def test_prune_junk_never_deletes_published(tmp_path):
    junk = Post.objects.create(
        title="About", source_url="http://x/about/", is_published=True, published_at=timezone.now()
    )
    call_command("reconcile_posts", file=_meta(tmp_path, []), prune_junk=True)
    assert Post.objects.filter(pk=junk.pk).exists()


def test_dry_run_changes_nothing(tmp_path):
    Post.objects.create(title="raw", source_url="http://x/2015/07/18/p/", is_published=False)
    Post.objects.create(title="raw2", source_url="https://x/2015/07/18/p/", is_published=False)
    meta = _meta(tmp_path, [{"title": "P", "url": "https://x/2015/07/18/p/", "date": "2015-07-18"}])
    call_command("reconcile_posts", file=meta, dry_run=True)
    assert Post.objects.count() == 2
