"""Live public-site views.

Each view maps a url_path to a template and context, evaluating its querysets per
request and returning 404 for unpublished or missing content. The
``site_name``/``site_base_url`` template globals come from
``apps.core.context_processors.site``, so the views don't pass them.
"""

from __future__ import annotations

import datetime

from django.conf import settings
from django.db.models import Exists, OuterRef, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.blog.models import Category, Post
from apps.core.cache import cached_page
from apps.core.models import SiteConfiguration
from apps.core.seo import (
    blog_posting_jsonld,
    discography_jsonld,
    jsonld_dumps,
    music_album_jsonld,
    music_group_jsonld,
)
from apps.discography.models import (
    PRIMARY_ARTIST_NAME,
    Artist,
    Lyric,
    Release,
    ReleaseType,
)
from apps.discography.queries import linkable_artist_ids
from apps.pages.models import Page
from apps.resources.grouping import group_by_subcategory
from apps.resources.models import KIND_FAN, KIND_OFFICIAL, Resource, ResourceFile


def _ensure_og(obj):
    """Generate an object's OG image on first visit if it's missing (e.g. legacy
    content imported before OG generation). The OG-image-only save does not flush
    the page cache (see invalidate_on_content_change), and the response rendered
    here already carries the new image, so the cached page stays correct."""
    if obj.ensure_og_image():
        obj.save(update_fields=["og_image"])
    return obj


def _homepage_artists():
    """Flagged non-primary artists for the hero, each with a ``hero_url``.

    An artist links to its own discography page unless that page would be empty
    (no published releases of their own and no published featured credits), in
    which case it links to the discography root. Emptiness is resolved with two
    correlated EXISTS subqueries, so the whole list costs a single query
    regardless of how many artists there are.
    """
    has_own = Release.objects.filter(artist=OuterRef("pk"), is_published=True)
    has_feature = Release.objects.filter(
        featured_artists=OuterRef("pk"), is_published=True
    )
    artists = list(
        Artist.objects.filter(appears_on_homepage=True)
        .exclude(name=PRIMARY_ARTIST_NAME)
        .annotate(has_own=Exists(has_own), has_feature=Exists(has_feature))
        .order_by("name")
    )
    for artist in artists:
        artist.hero_url = (
            artist.get_absolute_url()
            if artist.has_own or artist.has_feature
            else "/discography/"
        )
    return artists


@cached_page
def landing(request):
    site_config = _ensure_og(SiteConfiguration.load())
    recent_posts = list(Post.objects.published()[:6])
    latest_resources = list(Resource.objects.published()[:8])
    other_homepage_artists = _homepage_artists()
    return render(
        request,
        "landing.html",
        {
            "site_config": site_config,
            "recent_posts": recent_posts,
            "latest_resources": latest_resources,
            "primary_artist_name": PRIMARY_ARTIST_NAME,
            "other_homepage_artists": other_homepage_artists,
        },
    )


@cached_page
def post_list(request):
    posts = list(Post.objects.published().prefetch_related("categories", "tags"))
    return render(
        request,
        "blog/post_list.html",
        {"posts": posts, "edit_changelist": Post, "api_url": reverse("post-list")},
    )


@cached_page
def post_category(request, slug):
    category = get_object_or_404(Category, slug=slug)
    posts = list(category.posts.published().prefetch_related("categories", "tags"))
    return render(
        request,
        "blog/post_list.html",
        {
            "posts": posts,
            "category": category,
            "edit_object": category,
            "api_url": reverse("post-list"),
        },
    )


@cached_page
def post_detail(request, year, slug):
    post = get_object_or_404(Post.objects.published(), slug=slug)
    _ensure_og(post)
    jsonld = jsonld_dumps(blog_posting_jsonld(post, settings.SITE_BASE_URL))
    # Side-rail links: only published releases get a live page; artists always do.
    related_releases = list(
        post.related_releases.published().select_related("artist", "type")
    )
    related_artists = list(post.related_artists.all())
    related_resources = list(post.related_resources.published().prefetch_related("files"))
    return render(
        request,
        "blog/post_detail.html",
        {
            "post": post,
            "jsonld": jsonld,
            "related_releases": related_releases,
            "related_artists": related_artists,
            "related_resources": related_resources,
            "edit_object": post,
            "api_url": reverse("post-detail", kwargs={"slug": post.slug}),
        },
    )


@cached_page
def discography_index(request):
    releases = list(
        Release.objects.published()
        .select_related("artist", "type")
        .prefetch_related("additional_artists", "featured_artists")
    )
    sections = []
    for release_type in ReleaseType.objects.all():
        type_releases = [r for r in releases if r.type_id == release_type.id]
        if type_releases:
            sections.append({"type": release_type, "releases": type_releases})
    has_lyrics = Lyric.objects.exclude(lyrics="").exists()
    jsonld = jsonld_dumps(discography_jsonld(releases, settings.SITE_BASE_URL))
    return render(
        request,
        "discography/index.html",
        {
            "sections": sections,
            "has_lyrics": has_lyrics,
            "jsonld": jsonld,
            "edit_changelist": Release,
            "api_url": reverse("discography-root"),
        },
    )


@cached_page
def artist_detail(request, artist_slug):
    artist = get_object_or_404(Artist, slug=artist_slug)
    _ensure_og(artist)
    # Releases this artist is credited on — as the primary act or alongside it.
    releases = list(
        Release.objects.published()
        .filter(Q(artist=artist) | Q(additional_artists=artist))
        .distinct()
        .select_related("artist", "type")
        .prefetch_related("additional_artists", "featured_artists")
    )
    shown = {r.id for r in releases}
    # Releases where this artist only guests, minus any already shown above.
    featured_on = [
        r
        for r in artist.featured_on.published()
        .select_related("artist", "type")
        .prefetch_related("additional_artists")
        if r.id not in shown
    ]
    shown |= {r.id for r in featured_on}
    # Releases (e.g. Various Artists comps) where the artist is credited only on a
    # track, not as the release/feature artist — minus anything already shown.
    appears_on = [
        r
        for r in Release.objects.published()
        .filter(editions__tracks__artist=artist)
        .distinct()
        .select_related("artist", "type")
        .prefetch_related("additional_artists")
        if r.id not in shown
    ]
    jsonld = jsonld_dumps(music_group_jsonld(artist, releases, settings.SITE_BASE_URL))
    return render(
        request,
        "discography/artist_detail.html",
        {
            "artist": artist,
            "releases": releases,
            "featured_on": featured_on,
            "appears_on": appears_on,
            "jsonld": jsonld,
            "edit_object": artist,
            "api_url": reverse("artist-detail", kwargs={"slug": artist.slug}),
        },
    )


@cached_page
def release_detail(request, artist_slug, release_slug):
    release = get_object_or_404(
        Release.objects.published()
        .select_related("artist", "type")
        .prefetch_related(
            "additional_artists",
            "editions__covers",
            "editions__tracks__lyric",
            "editions__tracks__remixers",
        ),
        artist__slug=artist_slug,
        slug=release_slug,
    )
    _ensure_og(release)
    jsonld = jsonld_dumps(music_album_jsonld(release, settings.SITE_BASE_URL))
    return render(
        request,
        "discography/release_detail.html",
        {
            "release": release,
            "jsonld": jsonld,
            "edit_object": release,
            "api_url": reverse("release-detail", kwargs={"slug": release.slug}),
        },
    )


@cached_page
def lyric_index(request):
    lyrics = list(
        Lyric.objects.exclude(lyrics="").select_related("artist").order_by("title")
    )
    return render(
        request,
        "discography/lyric_index.html",
        {"lyrics": lyrics, "edit_changelist": Lyric},
    )


@cached_page
def lyric_detail(request, slug):
    lyric = get_object_or_404(Lyric.objects.exclude(lyrics=""), slug=slug)
    _ensure_og(lyric)
    return render(
        request,
        "discography/lyric_detail.html",
        {
            "lyric": lyric,
            "edit_object": lyric,
            "api_url": reverse("lyric-detail", kwargs={"slug": lyric.slug}),
        },
    )


@cached_page
def resource_list(request):
    # Newest first by the shown content date (recorded/released); resources with
    # no content date sort last, by most-recently-added. Grouping preserves this
    # order within each subcategory.
    resources = sorted(
        Resource.objects.published()
        .select_related("subcategory", "artist")
        .prefetch_related("files", "additional_artists"),
        key=lambda r: (r.display_date or datetime.date.min, r.uploaded_at),
        reverse=True,
    )
    # Which credited artists have a non-empty page, so the snippet can link them
    # (resolved in one query for the whole listing).
    linkable_artists = linkable_artist_ids(
        a.id for r in resources for a in r.all_artists
    )
    sections = [
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
    return render(
        request,
        "resources/resource_list.html",
        {
            "sections": sections,
            "linkable_artist_ids": linkable_artists,
            "edit_changelist": Resource,
            "api_url": reverse("resource-list"),
        },
    )


@cached_page
def resource_detail(request, kind, slug):
    resource = get_object_or_404(
        Resource.objects.published()
        .select_related("artist", "related_release")
        .prefetch_related("additional_artists", "files"),
        kind=kind,
        slug=slug,
    )
    _ensure_og(resource)
    # Link each credited artist only when their discography page isn't empty.
    linkable_artists = linkable_artist_ids(a.id for a in resource.all_artists)
    return render(
        request,
        "resources/resource_detail.html",
        {
            "resource": resource,
            "linkable_artist_ids": linkable_artists,
            "edit_object": resource,
            "api_url": reverse("resource-detail", kwargs={"slug": resource.slug}),
        },
    )


def resource_file_download(request, pk):
    """Serve a resource file. Locked files require staff and are streamed from
    private storage; unlocked files just redirect to their public URL."""
    rf = get_object_or_404(ResourceFile, pk=pk)
    if rf.is_locked and not request.user.is_staff:
        raise Http404
    if rf.is_external:
        return redirect(rf.external_url)
    if rf.is_locked:
        return FileResponse(
            rf.locked_file.open("rb"), as_attachment=True, filename=rf.display_name
        )
    return redirect(rf.file.url)


@cached_page
def page_detail(request, slug):
    page = get_object_or_404(Page.objects.published(), slug=slug)
    _ensure_og(page)
    return render(
        request,
        "pages/page_detail.html",
        {
            "page": page,
            "edit_object": page,
            "api_url": reverse("page-detail", kwargs={"slug": page.slug}),
        },
    )


def robots_txt(request):
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {settings.SITE_BASE_URL}/sitemap.xml\n"
    )
    return HttpResponse(body, content_type="text/plain")
