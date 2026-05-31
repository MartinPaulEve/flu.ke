"""Serializers for the read-only discography API.

Designed to keep payloads sane: list endpoints use compact serializers with
shallow references to related objects, while the release *detail* endpoint
nests its full editions -> (tracks, covers) tree so a single request renders
a whole release page. Nested track/cover serializers themselves reference
artists and lyrics by slug + name only, never recursing back into releases.
"""

from rest_framework import serializers

from apps.discography.models import (
    Artist,
    CoverImage,
    Edition,
    Lyric,
    Release,
    ReleaseType,
    Track,
)


class ArtistRefSerializer(serializers.ModelSerializer):
    """Compact artist reference used when nesting inside other payloads."""

    class Meta:
        model = Artist
        fields = ["slug", "name"]


class LyricRefSerializer(serializers.ModelSerializer):
    """Compact lyric reference (slug + title) used inside tracks."""

    class Meta:
        model = Lyric
        fields = ["slug", "title"]


class ReleaseTypeRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReleaseType
        fields = ["name"]


class ArtistSerializer(serializers.ModelSerializer):
    primary_artist = ArtistRefSerializer(read_only=True)
    url = serializers.CharField(source="get_absolute_url", read_only=True)

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
        ]


class ReleaseTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReleaseType
        fields = ["id", "name", "display_order"]


class LyricSerializer(serializers.ModelSerializer):
    artist = ArtistRefSerializer(read_only=True)
    url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = Lyric
        fields = ["id", "slug", "title", "artist", "lyrics", "comments", "url"]


class TrackSerializer(serializers.ModelSerializer):
    remixer = ArtistRefSerializer(read_only=True)
    lyric = LyricRefSerializer(read_only=True)
    sample = serializers.FileField(read_only=True)
    display_title = serializers.CharField(read_only=True)

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
        ]


class CoverImageSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(read_only=True)

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
        ]


class EditionSerializer(serializers.ModelSerializer):
    tracks = TrackSerializer(many=True, read_only=True)
    covers = CoverImageSerializer(many=True, read_only=True)

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
        ]


class ReleaseSerializer(serializers.ModelSerializer):
    """Compact release serializer for list endpoints."""

    artist = ArtistRefSerializer(read_only=True)
    type = ReleaseTypeRefSerializer(read_only=True)
    display_title = serializers.CharField(read_only=True)
    url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = Release
        fields = [
            "id",
            "slug",
            "name",
            "display_title",
            "year",
            "artist",
            "type",
            "url",
        ]


class ReleaseDetailSerializer(serializers.ModelSerializer):
    """Full release payload nesting editions -> tracks + covers."""

    artist = ArtistRefSerializer(read_only=True)
    type = ReleaseTypeRefSerializer(read_only=True)
    display_title = serializers.CharField(read_only=True)
    url = serializers.CharField(source="get_absolute_url", read_only=True)
    editions = EditionSerializer(many=True, read_only=True)

    class Meta:
        model = Release
        fields = [
            "id",
            "slug",
            "name",
            "display_title",
            "year",
            "artist",
            "type",
            "order",
            "purchase_link",
            "url",
            "editions",
        ]
