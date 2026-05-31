"""RSS feed for published blog posts, served live at ``/feed.xml``."""

from __future__ import annotations

from django.conf import settings
from django.contrib.syndication.views import Feed

from apps.blog.models import Post


class LatestPostsFeed(Feed):
    description_template = None

    def title(self):
        return settings.SITE_NAME

    def link(self):
        return "/news/"

    def description(self):
        return f"{settings.SITE_NAME} — latest news"

    def items(self):
        return Post.objects.published()[:20]

    def item_title(self, item):
        return item.title

    def item_link(self, item):
        return item.get_absolute_url()

    def item_description(self, item):
        return item.excerpt or ""

    def item_pubdate(self, item):
        return item.published_at
