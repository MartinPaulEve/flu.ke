"""The relink_posts command rewrites 2bitpie.net links in post body and excerpt."""

import pytest
from django.core.management import call_command

from apps.blog.models import Post

pytestmark = pytest.mark.django_db


def test_rewrites_links_in_body():
    post = Post.objects.create(title="Old", body='<a href="https://www.2bitpie.net/news/x/">x</a>')
    call_command("relink_posts")
    post.refresh_from_db()
    assert post.body == '<a href="/news/x/">x</a>'


def test_rewrites_links_in_excerpt():
    post = Post.objects.create(title="E", excerpt="see http://2bitpie.net/z", body="b")
    call_command("relink_posts")
    post.refresh_from_db()
    assert post.excerpt == "see /z"


def test_dry_run_reports_without_writing():
    post = Post.objects.create(title="Old", body="link http://2bitpie.net/y")
    call_command("relink_posts", dry_run=True)
    post.refresh_from_db()
    assert post.body == "link http://2bitpie.net/y"  # unchanged


def test_leaves_unrelated_posts_alone():
    post = Post.objects.create(title="Clean", body='<a href="/news/keep/">keep</a>')
    call_command("relink_posts")
    post.refresh_from_db()
    assert post.body == '<a href="/news/keep/">keep</a>'
