"""Serializers for the read-only discography API.

Designed to keep payloads sane: list endpoints use compact serializers with
shallow references to related objects, while the release *detail* endpoint
nests its full editions -> (tracks, covers) tree so a single request renders
a whole release page. Nested track/cover serializers themselves reference
artists and lyrics by slug + name only, never recursing back into releases.
"""

from rest_framework import serializers
from rest_framework.reverse import reverse as drf_reverse

from apps.discography.models import (
    Artist,
    CoverImage,
    Edition,
    Lyric,
    Release,
    ReleaseType,
    Track,
)

HAL_JSON = "application/hal+json"
TEXT_HTML = "text/html"


def _api_link(view_name, kwargs, request):
    """Build a HAL link object pointing at an absolute API detail endpoint."""
    return {
        "href": drf_reverse(view_name, kwargs=kwargs, request=request),
        "type": HAL_JSON,
    }


def _self_link(view_name, kwargs, request):
    """The object's own API detail endpoint."""
    return _api_link(view_name, kwargs, request)


def _alternate_link(obj, request):
    """The object's public HTML page (for objects with ``get_absolute_url``)."""
    path = obj.get_absolute_url()
    href = request.build_absolute_uri(path) if request else path
    return {"href": href, "type": TEXT_HTML}


class HALLinksMixin:
    """Adds request-aware ``_links`` behaviour to a serializer.

    Subclasses declare ``_links = serializers.SerializerMethodField(
    method_name="get_links")`` (and add ``"_links"`` to their ``fields``) and
    implement :meth:`build_links` to return the dict of link objects. This mixin
    wires up the method and exposes the request from the serializer context.
    """

    @property
    def _request(self):
        return self.context.get("request")

    def get_links(self, obj):
        return self.build_links(obj, self._request)

    def build_links(self, obj, request):  # pragma: no cover - overridden
        raise NotImplementedError


class AbsoluteURLField(serializers.CharField):
    """A read-only URL field that returns a fully-qualified (absolute) URI.

    ``source`` should resolve to a path (e.g. ``get_absolute_url``); the field
    makes it absolute using the request in context. This keeps the API
    consistent with the request-aware links DRF builds for the router root, and
    means the browsable API renders the value as a clickable link (it only
    linkifies absolute http(s) URLs). Falls back to the path when there's no
    request (e.g. rendering outside a view)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("read_only", True)
        super().__init__(**kwargs)

    def to_representation(self, value):
        path = super().to_representation(value)
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path


class ArtistRefSerializer(HALLinksMixin, serializers.ModelSerializer):
    """Compact artist reference used when nesting inside other payloads."""

    _links = serializers.SerializerMethodField(method_name="get_links")

    class Meta:
        model = Artist
        fields = ["slug", "name", "_links"]

    def build_links(self, obj, request):
        return {
            "self": _self_link("artist-detail", {"slug": obj.slug}, request),
            "alternate": _alternate_link(obj, request),
        }


class LyricRefSerializer(HALLinksMixin, serializers.ModelSerializer):
    """Compact lyric reference (slug + title) used inside tracks."""

    _links = serializers.SerializerMethodField(method_name="get_links")

    class Meta:
        model = Lyric
        fields = ["slug", "title", "_links"]

    def build_links(self, obj, request):
        return {
            "self": _self_link("lyric-detail", {"slug": obj.slug}, request),
            "alternate": _alternate_link(obj, request),
        }


class ReleaseTypeRefSerializer(HALLinksMixin, serializers.ModelSerializer):
    _links = serializers.SerializerMethodField(method_name="get_links")

    class Meta:
        model = ReleaseType
        fields = ["name", "_links"]

    def build_links(self, obj, request):
        return {
            "self": _self_link("releasetype-detail", {"pk": obj.pk}, request),
        }


class ArtistSerializer(HALLinksMixin, serializers.ModelSerializer):
    primary_artist = ArtistRefSerializer(read_only=True)
    url = AbsoluteURLField(source="get_absolute_url")
    _links = serializers.SerializerMethodField(method_name="get_links")

    class Meta:
        model = Artist
        fields = [
            "id",
            "slug",
            "name",
            "is_alias",
            "primary_artist",
            "biography",
            "url",
            "_links",
        ]

    def build_links(self, obj, request):
        return {
            "self": _self_link("artist-detail", {"slug": obj.slug}, request),
            "alternate": _alternate_link(obj, request),
        }


class ReleaseTypeSerializer(HALLinksMixin, serializers.ModelSerializer):
    _links = serializers.SerializerMethodField(method_name="get_links")

    class Meta:
        model = ReleaseType
        fields = ["id", "name", "display_order", "_links"]

    def build_links(self, obj, request):
        return {
            "self": _self_link("releasetype-detail", {"pk": obj.pk}, request),
        }


class LyricSerializer(HALLinksMixin, serializers.ModelSerializer):
    artist = ArtistRefSerializer(read_only=True)
    url = AbsoluteURLField(source="get_absolute_url")
    _links = serializers.SerializerMethodField(method_name="get_links")

    class Meta:
        model = Lyric
        fields = ["id", "slug", "title", "artist", "lyrics", "comments", "url", "_links"]

    def build_links(self, obj, request):
        return {
            "self": _self_link("lyric-detail", {"slug": obj.slug}, request),
            "alternate": _alternate_link(obj, request),
        }


class TrackSerializer(HALLinksMixin, serializers.ModelSerializer):
    remixer = ArtistRefSerializer(read_only=True)
    lyric = LyricRefSerializer(read_only=True)
    sample = serializers.FileField(read_only=True)
    display_title = serializers.CharField(read_only=True)
    _links = serializers.SerializerMethodField(method_name="get_links")

    class Meta:
        model = Track
        fields = [
            "id",
            "name",
            "display_title",
            "track_number",
            "mix_info",
            "remixer",
            "length",
            "sample",
            "sample_source_url",
            "lyric",
            "display_order",
            "edition",
            "_links",
        ]

    def build_links(self, obj, request):
        links = {
            "self": _self_link("track-detail", {"pk": obj.pk}, request),
            "edition": _self_link("edition-detail", {"pk": obj.edition_id}, request),
        }
        if obj.lyric_id:
            links["lyric"] = _self_link(
                "lyric-detail", {"slug": obj.lyric.slug}, request
            )
        return links


class CoverImageSerializer(HALLinksMixin, serializers.ModelSerializer):
    image = serializers.ImageField(read_only=True)
    _links = serializers.SerializerMethodField(method_name="get_links")

    class Meta:
        model = CoverImage
        fields = [
            "id",
            "display_name",
            "image",
            "kind",
            "alt_text",
            "source_url",
            "display_order",
            "edition",
            "_links",
        ]

    def build_links(self, obj, request):
        return {
            "self": _self_link("coverimage-detail", {"pk": obj.pk}, request),
            "edition": _self_link("edition-detail", {"pk": obj.edition_id}, request),
        }


class EditionSerializer(HALLinksMixin, serializers.ModelSerializer):
    tracks = TrackSerializer(many=True, read_only=True)
    covers = CoverImageSerializer(many=True, read_only=True)
    _links = serializers.SerializerMethodField(method_name="get_links")

    class Meta:
        model = Edition
        fields = [
            "id",
            "release",
            "name",
            "catalogue_number",
            "record_label",
            "year",
            "media",
            "purchase_link",
            "display_order",
            "tracks",
            "covers",
            "_links",
        ]

    def build_links(self, obj, request):
        return {
            "self": _self_link("edition-detail", {"pk": obj.pk}, request),
            "release": _self_link(
                "release-detail", {"slug": obj.release.slug}, request
            ),
        }


class ReleaseSerializer(HALLinksMixin, serializers.ModelSerializer):
    """Compact release serializer for list endpoints."""

    artist = ArtistRefSerializer(read_only=True)
    artists = ArtistRefSerializer(source="all_artists", many=True, read_only=True)
    type = ReleaseTypeRefSerializer(read_only=True)
    display_title = serializers.CharField(read_only=True)
    url = AbsoluteURLField(source="get_absolute_url")
    _links = serializers.SerializerMethodField(method_name="get_links")

    class Meta:
        model = Release
        fields = [
            "id",
            "slug",
            "name",
            "display_title",
            "year",
            "artist",
            "artists",
            "type",
            "url",
            "_links",
        ]

    def build_links(self, obj, request):
        return {
            "self": _self_link("release-detail", {"slug": obj.slug}, request),
            "alternate": _alternate_link(obj, request),
        }


class ReleaseDetailSerializer(HALLinksMixin, serializers.ModelSerializer):
    """Full release payload nesting editions -> tracks + covers."""

    artist = ArtistRefSerializer(read_only=True)
    artists = ArtistRefSerializer(source="all_artists", many=True, read_only=True)
    type = ReleaseTypeRefSerializer(read_only=True)
    display_title = serializers.CharField(read_only=True)
    url = AbsoluteURLField(source="get_absolute_url")
    editions = EditionSerializer(many=True, read_only=True)
    _links = serializers.SerializerMethodField(method_name="get_links")

    class Meta:
        model = Release
        fields = [
            "id",
            "slug",
            "name",
            "display_title",
            "year",
            "artist",
            "artists",
            "type",
            "order",
            "purchase_link",
            "url",
            "editions",
            "_links",
        ]

    def build_links(self, obj, request):
        return {
            "self": _self_link("release-detail", {"slug": obj.slug}, request),
            "alternate": _alternate_link(obj, request),
        }
