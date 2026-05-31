"""Discography REST API URLs.

Registers the read-only resource viewsets on a DefaultRouter and exposes the
OpenAPI schema plus interactive docs:

* ``/api/docs/``   — Swagger UI
* ``/api/redoc/``  — ReDoc
* ``/api/schema/`` — raw OpenAPI document

All resource endpoints (``/api/releases/`` etc.) live alongside these.
"""

from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter

from .views import (
    ArtistViewSet,
    CoverImageViewSet,
    EditionViewSet,
    LyricViewSet,
    ReleaseTypeViewSet,
    ReleaseViewSet,
    TrackViewSet,
)

router = DefaultRouter()
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
