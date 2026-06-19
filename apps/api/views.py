"""Read-only viewsets for the discography API.

Every viewset is a :class:`~rest_framework.viewsets.ReadOnlyModelViewSet`, so
only ``GET`` (list/retrieve) is allowed — write methods return 405. Releases
and everything reachable through them (editions, tracks, covers) are scoped to
*published* releases only; artists, release types and lyrics are reference data
and are exposed unfiltered.
"""

import django_filters
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from apps.blog.models import Post
from apps.discography.models import (
    Artist,
    CoverImage,
    Edition,
    Lyric,
    Release,
    ReleaseType,
    Track,
)
from apps.pages.models import Page
from apps.resources.models import Resource

from .serializers import (
    ArtistSerializer,
    CoverImageSerializer,
    EditionSerializer,
    LyricSerializer,
    PageSerializer,
    PostSerializer,
    ReleaseDetailSerializer,
    ReleaseSerializer,
    ReleaseTypeSerializer,
    ResourceSerializer,
    TrackSerializer,
)


class ReleaseFilter(django_filters.FilterSet):
    """Filter releases by year, type and artist slug."""

    artist = django_filters.CharFilter(field_name="artist__slug")

    class Meta:
        model = Release
        fields = ["year", "type", "artist"]


# Base for every API viewset: read-only and open to everyone. The discography
# API is public reference data, so it requires no authentication. Declaring no
# ``authentication_classes`` also keeps the OpenAPI schema free of security
# schemes, so Swagger/ReDoc present the API as open (no "Authorize" prompt)
# instead of looking login-gated. (Kept as a comment, not a docstring, so it
# doesn't leak into the generated per-operation API descriptions.)
class PublicReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = []
    permission_classes = [AllowAny]


class ArtistViewSet(PublicReadOnlyViewSet):
    queryset = Artist.objects.select_related("primary_artist").all()
    serializer_class = ArtistSerializer
    lookup_field = "slug"
    search_fields = ["name"]
    ordering_fields = ["name"]
    ordering = ["name"]


class ReleaseTypeViewSet(PublicReadOnlyViewSet):
    queryset = ReleaseType.objects.all()
    serializer_class = ReleaseTypeSerializer
    ordering_fields = ["display_order", "name"]
    ordering = ["display_order", "name"]


class ReleaseViewSet(PublicReadOnlyViewSet):
    queryset = (
        Release.objects.published()
        .select_related("artist", "type")
        .prefetch_related("additional_artists", "editions__tracks", "editions__covers")
    )
    lookup_field = "slug"
    filterset_class = ReleaseFilter
    search_fields = ["name"]
    ordering_fields = ["year", "name", "order"]
    ordering = ["-year", "order", "name"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ReleaseDetailSerializer
        return ReleaseSerializer


class EditionViewSet(PublicReadOnlyViewSet):
    queryset = (
        Edition.objects.filter(release__is_published=True)
        .select_related("release")
        .prefetch_related("tracks", "covers")
    )
    serializer_class = EditionSerializer
    filterset_fields = {"release__slug": ["exact"]}
    ordering_fields = ["display_order", "year"]
    ordering = ["display_order"]


class TrackViewSet(PublicReadOnlyViewSet):
    queryset = (
        Track.objects.filter(edition__release__is_published=True)
        .select_related("lyric")
        .prefetch_related("remixers")
    )
    serializer_class = TrackSerializer
    filterset_fields = {"edition": ["exact"], "remixers__slug": ["exact"]}
    search_fields = ["name"]
    ordering_fields = ["display_order", "track_number", "name"]
    ordering = ["display_order", "track_number"]


class LyricViewSet(PublicReadOnlyViewSet):
    queryset = Lyric.objects.select_related("artist").all()
    serializer_class = LyricSerializer
    lookup_field = "slug"
    filterset_fields = {"artist__slug": ["exact"]}
    search_fields = ["title", "lyrics"]
    ordering_fields = ["title"]
    ordering = ["title"]


class CoverImageViewSet(PublicReadOnlyViewSet):
    queryset = CoverImage.objects.filter(
        edition__release__is_published=True
    ).select_related("edition")
    serializer_class = CoverImageSerializer
    filterset_fields = {"edition": ["exact"], "kind": ["exact"]}
    ordering_fields = ["display_order"]
    ordering = ["display_order"]


# --- other content sections -----------------------------------------------

class ResourceViewSet(PublicReadOnlyViewSet):
    queryset = (
        Resource.objects.published()
        .select_related("artist", "subcategory", "related_release")
        .prefetch_related("files", "additional_artists")
    )
    serializer_class = ResourceSerializer
    lookup_field = "slug"
    filterset_fields = {"kind": ["exact"]}
    search_fields = ["title"]
    ordering_fields = ["uploaded_at", "title"]
    ordering = ["-uploaded_at"]


class PageViewSet(PublicReadOnlyViewSet):
    queryset = Page.objects.published()
    serializer_class = PageSerializer
    lookup_field = "slug"
    ordering_fields = ["menu_order", "title"]
    ordering = ["menu_order", "title"]


class PostViewSet(PublicReadOnlyViewSet):
    serializer_class = PostSerializer
    lookup_field = "slug"
    search_fields = ["title", "excerpt"]
    ordering_fields = ["published_at", "title"]
    ordering = ["-published_at"]

    def get_queryset(self):
        # Evaluated per request: Post.published() filters published_at <= now(),
        # so it must not be frozen at import time on a class attribute.
        return Post.objects.published().prefetch_related(
            "categories", "tags", "related_releases__artist"
        )


class ApiRootView(APIView):
    """The API entry point: links to each content section."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return Response(
            {
                "discography": reverse("discography-root", request=request),
                "resources": reverse("resource-list", request=request),
                "pages": reverse("page-list", request=request),
                "news": reverse("post-list", request=request),
            }
        )
