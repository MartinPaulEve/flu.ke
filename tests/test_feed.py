import pytest
from django.utils import timezone

from apps.blog.models import Post
from apps.staticgen.feeds import build_feed

pytestmark = pytest.mark.django_db


def test_feed_has_channel_and_items():
    when = timezone.make_aware(timezone.datetime(2009, 6, 17, 7, 8))
    post = Post.objects.create(
        title="Dark Like Snow", excerpt="Out now", published_at=when, is_published=True
    )
    xml = build_feed([post], "https://flu.ke", "Fluke")
    assert "<rss" in xml and "</rss>" in xml
    assert "<title>Fluke</title>" in xml
    assert "<item>" in xml
    assert "<title>Dark Like Snow</title>" in xml
    assert f"https://flu.ke{post.get_absolute_url()}" in xml
    assert "2009" in xml  # RFC822 pubDate present


def test_feed_escapes_special_characters():
    post = Post.objects.create(title="Tom & Jerry", published_at=timezone.now(), is_published=True)
    xml = build_feed([post], "https://flu.ke", "Fluke")
    assert "Tom &amp; Jerry" in xml
    assert "Tom & Jerry" not in xml


def test_empty_feed_is_valid():
    xml = build_feed([], "https://flu.ke", "Fluke")
    assert "<rss" in xml and "<item>" not in xml
