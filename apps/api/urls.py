"""REST API URLs, mounted at ``/api/``.

The API entry point ``/api/`` links to four content sections:

* ``/api/discography/`` — a sub-API of artists, releases, editions, tracks,
  lyrics, cover art and release types;
* ``/api/resources/``   — official material and fan resources;
* ``/api/pages/``       — CMS pages;
* ``/api/news/``        — blog posts.

Plus the OpenAPI schema (``/api/schema/``) and interactive docs
(``/api/docs/`` Swagger, ``/api/redoc/`` ReDoc).
"""

from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import APIRootView, DefaultRouter

from .views import (
    ApiRootView,
    ArtistViewSet,
    CoverImageViewSet,
    EditionViewSet,
    LyricViewSet,
    PageViewSet,
    PostViewSet,
    ReleaseTypeViewSet,
    ReleaseViewSet,
    ResourceViewSet,
    TrackViewSet,
)


class DiscographyAPIRootView(APIRootView):
    """The Fluke discography — a read-only API of artists, release types, releases, editions, tracks, lyrics and cover art."""  # noqa: E501


class DiscographyAPIRouter(DefaultRouter):
    """DefaultRouter whose browsable root shows a descriptive overview."""

    APIRootView = DiscographyAPIRootView


discography = DiscographyAPIRouter()
discography.root_view_name = "discography-root"
discography.register("artists", ArtistViewSet, basename="artist")
discography.register("release-types", ReleaseTypeViewSet, basename="releasetype")
discography.register("releases", ReleaseViewSet, basename="release")
discography.register("editions", EditionViewSet, basename="edition")
discography.register("tracks", TrackViewSet, basename="track")
discography.register("lyrics", LyricViewSet, basename="lyric")
discography.register("cover-images", CoverImageViewSet, basename="coverimage")

urlpatterns = [
    path("", ApiRootView.as_view(), name="api-root"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("discography/", include(discography.urls)),
    # Single-type sections: the prefix is the list, <slug> is the detail.
    path("resources/", ResourceViewSet.as_view({"get": "list"}), name="resource-list"),
    path("resources/<slug:slug>/", ResourceViewSet.as_view({"get": "retrieve"}), name="resource-detail"),
    path("pages/", PageViewSet.as_view({"get": "list"}), name="page-list"),
    path("pages/<slug:slug>/", PageViewSet.as_view({"get": "retrieve"}), name="page-detail"),
    path("news/", PostViewSet.as_view({"get": "list"}), name="post-list"),
    path("news/<slug:slug>/", PostViewSet.as_view({"get": "retrieve"}), name="post-detail"),
]
