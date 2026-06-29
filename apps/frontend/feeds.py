"""Syndication feeds for published blog posts: RSS at ``/feed.xml`` and the same
content as Atom at ``/feed.atom``."""

from __future__ import annotations

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed

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


class AtomPostsFeed(LatestPostsFeed):
    """The same posts as :class:`LatestPostsFeed`, emitted as Atom 1.0.

    Reuses all of the RSS feed's item logic; Django renders the inherited
    ``description`` as the Atom ``<subtitle>``.
    """

    feed_type = Atom1Feed

    def author_name(self):
        # Atom feeds should name an author; reuse the site name.
        return settings.SITE_NAME
