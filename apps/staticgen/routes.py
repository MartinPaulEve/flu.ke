"""The route manifest: the single source of truth for which pages the site has.

``iter_routes`` yields one :class:`Route` per public page (landing, section indexes,
and every published page/post/release/artist/resource). The renderer turns each
route into a file under the build directory. Keeping route discovery here — derived
from the models' ``get_absolute_url`` — makes "what pages exist" directly testable.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field


@dataclass
class Route:
    url_path: str
    template: str
    context: dict = field(default_factory=dict)


def iter_routes() -> Iterator[Route]:
    """Yield every public route for the current published content."""
    from django.conf import settings

    from apps.blog.models import Post
    from apps.core.seo import blog_posting_jsonld, jsonld_dumps, music_album_jsonld
    from apps.discography.models import Artist, Lyric, Release, ReleaseType
    from apps.pages.models import Page
    from apps.resources.grouping import group_by_subcategory
    from apps.resources.models import KIND_FAN, KIND_OFFICIAL, Resource

    base_url = settings.SITE_BASE_URL

    posts = list(Post.objects.published().prefetch_related("categories", "tags"))
    resources = list(Resource.objects.published().select_related("subcategory"))
    releases = list(Release.objects.published().select_related("artist", "type"))
    # Only songs whose words we actually hold get a lyric page (the import
    # recovered some titles with no body; those stay pageless until filled in).
    lyrics = list(Lyric.objects.exclude(lyrics="").select_related("artist").order_by("title"))

    # Landing
    yield Route(
        "/",
        "landing.html",
        {"recent_posts": posts[:6], "latest_resources": resources[:8]},
    )

    # Blog / News
    yield Route("/news/", "blog/post_list.html", {"posts": posts})
    for post in posts:
        yield Route(
            post.get_absolute_url(),
            "blog/post_detail.html",
            {"post": post, "jsonld": jsonld_dumps(blog_posting_jsonld(post, base_url))},
        )

    # Discography
    sections = []
    for release_type in ReleaseType.objects.all():
        type_releases = [r for r in releases if r.type_id == release_type.id]
        if type_releases:
            sections.append({"type": release_type, "releases": type_releases})
    yield Route(
        "/discography/",
        "discography/index.html",
        {"sections": sections, "has_lyrics": bool(lyrics)},
    )

    artist_ids = {r.artist_id for r in releases}
    for artist in Artist.objects.filter(id__in=artist_ids):
        artist_releases = [r for r in releases if r.artist_id == artist.id]
        yield Route(
            artist.get_absolute_url(),
            "discography/artist_detail.html",
            {"artist": artist, "releases": artist_releases},
        )
    for release in releases:
        yield Route(
            release.get_absolute_url(),
            "discography/release_detail.html",
            {"release": release, "jsonld": jsonld_dumps(music_album_jsonld(release, base_url))},
        )

    # Lyrics
    if lyrics:
        yield Route("/lyrics/", "discography/lyric_index.html", {"lyrics": lyrics})
        for lyric in lyrics:
            yield Route(
                lyric.get_absolute_url(),
                "discography/lyric_detail.html",
                {"lyric": lyric},
            )

    # Resources
    yield Route(
        "/resources/",
        "resources/resource_list.html",
        {
            "sections": [
                {
                    "heading": "Official Resources",
                    "anchor": "official",
                    "groups": group_by_subcategory(
                        [r for r in resources if r.kind == KIND_OFFICIAL]
                    ),
                },
                {
                    "heading": "Fan Remixes & Resources",
                    "anchor": "fan",
                    "groups": group_by_subcategory(
                        [r for r in resources if r.kind == KIND_FAN]
                    ),
                },
            ]
        },
    )
    for resource in resources:
        yield Route(
            resource.get_absolute_url(),
            "resources/resource_detail.html",
            {"resource": resource},
        )

    # Arbitrary CMS pages
    for page in Page.objects.published():
        yield Route(page.get_absolute_url(), "pages/page_detail.html", {"page": page})
