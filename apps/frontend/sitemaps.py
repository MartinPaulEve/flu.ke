"""Sitemap classes for the live public site.

The domain and scheme are pinned to ``settings.SITE_BASE_URL`` (rather than the
request host) so the canonical site URL is emitted regardless of how the app is
reached. Only published content — plus the section index pages — is listed.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap

from apps.blog.models import Post
from apps.discography.models import Artist, Lyric, Release
from apps.pages.models import Page
from apps.resources.models import Resource


def _base_parts():
    parts = urlsplit(settings.SITE_BASE_URL)
    return parts.scheme or "https", parts.netloc


class _PinnedDomainSitemap(Sitemap):
    """A sitemap whose protocol/domain come from ``SITE_BASE_URL``."""

    def get_urls(self, page=1, site=None, protocol=None):
        scheme, netloc = _base_parts()

        class _FixedSite:
            domain = netloc
            name = netloc

        return super().get_urls(page=page, site=_FixedSite(), protocol=scheme)


class PostSitemap(_PinnedDomainSitemap):
    changefreq = "weekly"

    def items(self):
        return Post.objects.published()

    def lastmod(self, obj):
        return obj.modified


class ReleaseSitemap(_PinnedDomainSitemap):
    changefreq = "monthly"

    def items(self):
        return Release.objects.published().select_related("artist")

    def lastmod(self, obj):
        return obj.modified


class ArtistSitemap(_PinnedDomainSitemap):
    changefreq = "monthly"

    def items(self):
        artist_ids = (
            Release.objects.published().values_list("artist_id", flat=True).distinct()
        )
        return Artist.objects.filter(id__in=artist_ids)


class ResourceSitemap(_PinnedDomainSitemap):
    changefreq = "monthly"

    def items(self):
        return Resource.objects.published()

    def lastmod(self, obj):
        return obj.modified


class PageSitemap(_PinnedDomainSitemap):
    changefreq = "monthly"

    def items(self):
        return Page.objects.published()

    def lastmod(self, obj):
        return obj.modified


class LyricSitemap(_PinnedDomainSitemap):
    changefreq = "yearly"

    def items(self):
        return Lyric.objects.exclude(lyrics="").select_related("artist").order_by("title")

    def lastmod(self, obj):
        return obj.modified


class StaticViewSitemap(_PinnedDomainSitemap):
    """The section index pages, which have no model of their own."""

    changefreq = "weekly"

    def items(self):
        paths = ["/", "/news/", "/discography/", "/resources/"]
        if Lyric.objects.exclude(lyrics="").exists():
            paths.append("/lyrics/")
        return paths

    def location(self, item):
        return item


sitemaps = {
    "static": StaticViewSitemap,
    "posts": PostSitemap,
    "releases": ReleaseSitemap,
    "artists": ArtistSitemap,
    "resources": ResourceSitemap,
    "pages": PageSitemap,
    "lyrics": LyricSitemap,
}
