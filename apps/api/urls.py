"""Discography REST API URLs.

Registers the read-only resource viewsets on a router and exposes the OpenAPI
schema plus interactive docs:

* ``/discography/api/docs/``   — Swagger UI
* ``/discography/api/redoc/``  — ReDoc
* ``/discography/api/schema/`` — raw OpenAPI document

All resource endpoints (``/discography/api/releases/`` etc.) live alongside
these.
"""

from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import APIRootView, DefaultRouter

from .views import (
    ArtistViewSet,
    CoverImageViewSet,
    EditionViewSet,
    LyricViewSet,
    ReleaseTypeViewSet,
    ReleaseViewSet,
    TrackViewSet,
)


class DiscographyAPIRootView(APIRootView):
    """Fluke discography API — a read-only API for the Fluke discography: artists, release types, releases, editions, tracks, lyrics and cover art. Browse the interactive docs at /discography/api/docs/ (Swagger) or /discography/api/redoc/, or fetch the OpenAPI schema at /discography/api/schema/."""  # noqa: E501


class DiscographyAPIRouter(DefaultRouter):
    """DefaultRouter whose browsable root shows a descriptive overview."""

    APIRootView = DiscographyAPIRootView


router = DiscographyAPIRouter()
router.register("artists", ArtistViewSet, basename="artist")
router.register("release-types", ReleaseTypeViewSet, basename="releasetype")
router.register("releases", ReleaseViewSet, basename="release")
router.register("editions", EditionViewSet, basename="edition")
router.register("tracks", TrackViewSet, basename="track")
router.register("lyrics", LyricViewSet, basename="lyric")
router.register("cover-images", CoverImageViewSet, basename="coverimage")

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
] + router.urls
