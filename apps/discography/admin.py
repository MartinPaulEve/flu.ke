from django.contrib import admin

from apps.core.admin import OgCacheAdminMixin

from .models import (
    Artist,
    CoverImage,
    Edition,
    Lyric,
    Release,
    ReleaseType,
    Track,
)


class EditionInline(admin.TabularInline):
    model = Edition
    extra = 0
    show_change_link = True


class TrackInline(admin.TabularInline):
    model = Track
    extra = 0
    fields = ("track_number", "name", "mix_info", "remixer", "length", "sample", "lyric")
    autocomplete_fields = ("remixer", "lyric")


class CoverImageInline(admin.TabularInline):
    model = CoverImage
    extra = 0
    fields = ("kind", "display_name", "image", "alt_text", "display_order")


@admin.register(ReleaseType)
class ReleaseTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "display_order")
    list_editable = ("display_order",)
    search_fields = ("name",)


@admin.register(Artist)
class ArtistAdmin(OgCacheAdminMixin, admin.ModelAdmin):
    list_display = ("name", "is_alias", "primary_artist")
    list_filter = ("is_alias",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("primary_artist",)


@admin.register(Release)
class ReleaseAdmin(OgCacheAdminMixin, admin.ModelAdmin):
    list_display = ("name", "artist", "year", "type", "is_published")
    list_filter = ("type", "is_published", "artist")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("artist", "type")
    filter_horizontal = ("featured_artists",)
    inlines = [EditionInline]


@admin.register(Edition)
class EditionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "release", "year", "media", "record_label")
    search_fields = ("name", "catalogue_number", "release__name")
    autocomplete_fields = ("release",)
    inlines = [CoverImageInline, TrackInline]


@admin.register(Lyric)
class LyricAdmin(OgCacheAdminMixin, admin.ModelAdmin):
    list_display = ("title", "artist")
    search_fields = ("title", "lyrics")
    autocomplete_fields = ("artist",)


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ("name", "edition", "track_number", "mix_info", "remixer")
    search_fields = ("name", "edition__release__name")
    autocomplete_fields = ("edition", "remixer", "lyric")
