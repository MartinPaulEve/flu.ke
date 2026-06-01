"""Live public-site views.

Each view maps a url_path to a template and context, evaluating its querysets per
request and returning 404 for unpublished or missing content. The
``site_name``/``site_base_url`` template globals come from
``apps.core.context_processors.site``, so the views don't pass them.
"""

from __future__ import annotations

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from apps.blog.models import Category, Post
from apps.core.seo import blog_posting_jsonld, jsonld_dumps, music_album_jsonld
from apps.discography.models import (
    PRIMARY_ARTIST_NAME,
    Artist,
    Lyric,
    Release,
    ReleaseType,
)
from apps.pages.models import Page
from apps.resources.grouping import group_by_subcategory
from apps.resources.models import KIND_FAN, KIND_OFFICIAL, Resource


def _join_names(names):
    """Join names with commas and " & " before the final one.

    ["A"] -> "A"; ["A", "B"] -> "A & B"; ["A", "B", "C"] -> "A, B & C".
    """
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} & {names[-1]}"


def landing(request):
    recent_posts = list(Post.objects.published()[:6])
    latest_resources = list(Resource.objects.published()[:8])
    other_homepage_artists = list(
        Artist.objects.filter(appears_on_homepage=True)
        .exclude(name=PRIMARY_ARTIST_NAME)
        .order_by("name")
    )
    hero_aliases = _join_names([a.name for a in other_homepage_artists])
    return render(
        request,
        "landing.html",
        {
            "recent_posts": recent_posts,
            "latest_resources": latest_resources,
            "primary_artist_name": PRIMARY_ARTIST_NAME,
            "other_homepage_artists": other_homepage_artists,
            "hero_aliases": hero_aliases,
        },
    )


def post_list(request):
    posts = list(Post.objects.published().prefetch_related("categories", "tags"))
    return render(request, "blog/post_list.html", {"posts": posts, "edit_changelist": Post})


def post_category(request, slug):
    category = get_object_or_404(Category, slug=slug)
    posts = list(category.posts.published().prefetch_related("categories", "tags"))
    return render(
        request,
        "blog/post_list.html",
        {"posts": posts, "category": category, "edit_object": category},
    )


def post_detail(request, year, slug):
    post = get_object_or_404(Post.objects.published(), slug=slug)
    jsonld = jsonld_dumps(blog_posting_jsonld(post, settings.SITE_BASE_URL))
    return render(
        request,
        "blog/post_detail.html",
        {"post": post, "jsonld": jsonld, "edit_object": post},
    )


def discography_index(request):
    releases = list(Release.objects.published().select_related("artist", "type"))
    sections = []
    for release_type in ReleaseType.objects.all():
        type_releases = [r for r in releases if r.type_id == release_type.id]
        if type_releases:
            sections.append({"type": release_type, "releases": type_releases})
    has_lyrics = Lyric.objects.exclude(lyrics="").exists()
    return render(
        request,
        "discography/index.html",
        {"sections": sections, "has_lyrics": has_lyrics, "edit_changelist": Release},
    )


def artist_detail(request, artist_slug):
    artist = get_object_or_404(Artist, slug=artist_slug)
    releases = list(
        artist.releases.published().select_related("artist", "type")
    )
    return render(
        request,
        "discography/artist_detail.html",
        {"artist": artist, "releases": releases, "edit_object": artist},
    )


def release_detail(request, artist_slug, release_slug):
    release = get_object_or_404(
        Release.objects.published().select_related("artist", "type"),
        artist__slug=artist_slug,
        slug=release_slug,
    )
    jsonld = jsonld_dumps(music_album_jsonld(release, settings.SITE_BASE_URL))
    return render(
        request,
        "discography/release_detail.html",
        {"release": release, "jsonld": jsonld, "edit_object": release},
    )


def lyric_index(request):
    lyrics = list(
        Lyric.objects.exclude(lyrics="").select_related("artist").order_by("title")
    )
    return render(
        request,
        "discography/lyric_index.html",
        {"lyrics": lyrics, "edit_changelist": Lyric},
    )


def lyric_detail(request, slug):
    lyric = get_object_or_404(Lyric.objects.exclude(lyrics=""), slug=slug)
    return render(
        request,
        "discography/lyric_detail.html",
        {"lyric": lyric, "edit_object": lyric},
    )


def resource_list(request):
    resources = list(Resource.objects.published().select_related("subcategory"))
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
        {"sections": sections, "edit_changelist": Resource},
    )


def resource_detail(request, kind, slug):
    resource = get_object_or_404(Resource.objects.published(), kind=kind, slug=slug)
    return render(
        request,
        "resources/resource_detail.html",
        {"resource": resource, "edit_object": resource},
    )


def page_detail(request, slug):
    page = get_object_or_404(Page.objects.published(), slug=slug)
    return render(request, "pages/page_detail.html", {"page": page, "edit_object": page})


def robots_txt(request):
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {settings.SITE_BASE_URL}/sitemap.xml\n"
    )
    return HttpResponse(body, content_type="text/plain")
