from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.shortcuts import redirect, render
from django.urls import path

from apps.core.admin import OgCacheAdminMixin
from apps.core.cache import invalidate_site_cache

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
    fields = ("track_number", "name", "mix_info", "remixers", "length", "sample", "lyric")
    autocomplete_fields = ("remixers", "lyric")


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
    filter_horizontal = ("featured_artists", "additional_artists")
    inlines = [EditionInline]


@admin.register(Edition)
class EditionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "release", "year", "media", "record_label")
    search_fields = ("name", "catalogue_number", "release__name")
    autocomplete_fields = ("release",)
    inlines = [CoverImageInline, TrackInline]
    change_form_template = "admin/discography/edition_change_form.html"

    def get_urls(self):
        custom = [
            path(
                "<path:object_id>/copy-tracklist/",
                self.admin_site.admin_view(self.copy_tracklist_view),
                name="discography_edition_copy_tracklist",
            ),
        ]
        return custom + super().get_urls()

    def copy_tracklist_view(self, request, object_id):
        target = self.get_object(request, object_id)
        if target is None:
            self.message_user(request, "Edition not found.", level=messages.ERROR)
            return redirect("..")
        if request.method == "POST":
            source = Edition.objects.filter(pk=request.POST.get("source")).first()
            if source is None or source.pk == target.pk:
                self.message_user(request, "Choose a different edition to copy from.", level=messages.ERROR)
            else:
                count = self._copy_tracklist(source, target)
                invalidate_site_cache()
                self.message_user(
                    request,
                    f"Replaced the tracklist with {count} track(s) copied from "
                    f"“{source}” ({source.release.name}).",
                )
                return redirect("admin:discography_edition_change", object_id)
        editions = (
            Edition.objects.exclude(pk=target.pk)
            .select_related("release")
            .order_by("release__name", "display_order", "id")
        )
        return render(
            request,
            "admin/discography/copy_tracklist.html",
            {
                **self.admin_site.each_context(request),
                "title": f"Copy a tracklist into {target}",
                "opts": self.model._meta,
                "target": target,
                "editions": editions,
            },
        )

    @staticmethod
    def _copy_tracklist(source, target):
        """Replace target's tracks with copies of source's (editorial fields only;
        the MusicBrainz track/recording ids are edition-specific, so left blank)."""
        target.tracks.all().delete()
        count = 0
        for track in source.tracks.all():
            new_track = Track.objects.create(
                edition=target,
                name=track.name,
                track_number=track.track_number,
                mix_info=track.mix_info,
                length=track.length,
                sample=track.sample.name,
                sample_source_url=track.sample_source_url,
                lyric=track.lyric,
                display_order=track.display_order,
            )
            new_track.remixers.set(track.remixers.all())
            count += 1
        return count


@admin.register(Lyric)
class LyricAdmin(OgCacheAdminMixin, admin.ModelAdmin):
    list_display = ("title", "artist")
    search_fields = ("title", "lyrics")
    autocomplete_fields = ("artist",)


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ("name", "edition", "track_number", "mix_info", "remixers_display")
    search_fields = ("name", "edition__release__name")
    autocomplete_fields = ("edition", "remixers", "lyric")
    actions = ["move_to_edition"]

    @admin.display(description="Remixers")
    def remixers_display(self, obj):
        return ", ".join(a.name for a in obj.remixers.all())

    @admin.action(description="Move selected track(s) to another edition…")
    def move_to_edition(self, request, queryset):
        """Reassign tracks to a chosen edition (i.e. move them to another release).

        The sample file and all metadata travel with the track row — only the
        edition foreign key changes. Shows an edition picker, then applies.
        """
        if "apply" in request.POST:
            edition = Edition.objects.filter(pk=request.POST.get("edition")).first()
            if edition is None:
                self.message_user(request, "Choose a target edition.", level=messages.ERROR)
            else:
                moved = queryset.update(edition=edition)
                invalidate_site_cache()  # source + target release pages change
                self.message_user(
                    request, f"Moved {moved} track(s) to “{edition}” ({edition.release.name})."
                )
                return None
        editions = Edition.objects.select_related("release").order_by(
            "release__name", "display_order", "id"
        )
        return render(
            request,
            "admin/discography/move_tracks.html",
            {
                **self.admin_site.each_context(request),
                "title": "Move tracks to another edition",
                "opts": self.model._meta,
                "tracks": queryset,
                "editions": editions,
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
                "selected": list(queryset.values_list("pk", flat=True)),
            },
        )
