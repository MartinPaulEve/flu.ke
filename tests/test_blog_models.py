from datetime import timedelta

import pytest
from django.utils import timezone

from apps.blog.models import Post

pytestmark = pytest.mark.django_db


def test_post_get_absolute_url_uses_publish_year():
    when = timezone.make_aware(timezone.datetime(2009, 6, 17, 7, 8))
    post = Post.objects.create(title="Dark Like Snow announced", published_at=when)
    assert post.get_absolute_url() == "/news/2009/dark-like-snow-announced/"


def test_published_excludes_unpublished_flag():
    Post.objects.create(title="Hidden", is_published=False, published_at=timezone.now())
    assert not Post.objects.published().exists()


def test_published_excludes_future_dated():
    future = timezone.now() + timedelta(days=1)
    Post.objects.create(title="Scheduled", is_published=True, published_at=future)
    assert not Post.objects.published().exists()


def test_published_excludes_posts_without_a_date():
    Post.objects.create(title="No date", is_published=True, published_at=None)
    assert not Post.objects.published().exists()


def test_published_includes_past_dated_published():
    past = timezone.now() - timedelta(days=1)
    Post.objects.create(title="Live one", is_published=True, published_at=past)
    assert list(Post.objects.published().values_list("title", flat=True)) == ["Live one"]


def test_is_live_true_only_for_published_and_past_dated():
    past = timezone.now() - timedelta(days=1)
    future = timezone.now() + timedelta(days=1)
    assert Post(title="a", is_published=True, published_at=past).is_live is True
    assert Post(title="b", is_published=False, published_at=past).is_live is False
    assert Post(title="c", is_published=True, published_at=future).is_live is False
    assert Post(title="d", is_published=True, published_at=None).is_live is False
