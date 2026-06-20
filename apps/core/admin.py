"""Shared admin tooling for content with SEO/Open Graph fields and page caching.

Mix ``OgCacheAdminMixin`` into any ModelAdmin whose model uses SeoFieldsMixin and
has ``get_absolute_url``. It adds:

* per-object buttons on the change page — "Regenerate OG image" (rebuilds the card
  even if one exists, then the post_save signal invalidates the page cache so the
  new card shows up) and "Clear this page's cache";
* the same operations as bulk changelist actions, plus "Invalidate the ENTIRE
  site cache".
"""

import os

from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html

from apps.core.cache import invalidate_path, invalidate_site_cache
from apps.core.models import SiteConfiguration, Upload

# File types browsers execute when served inline — rejected to avoid stored XSS.
_SCRIPTABLE_EXTENSIONS = frozenset(
    {"svg", "svgz", "html", "htm", "xhtml", "xht", "xml", "mhtml", "htc"}
)


class UploadAdminForm(forms.ModelForm):
    class Meta:
        model = Upload
        fields = "__all__"

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        ext = os.path.splitext(getattr(uploaded, "name", ""))[1].lower().lstrip(".")
        if ext in _SCRIPTABLE_EXTENSIONS:
            raise forms.ValidationError(
                f"“.{ext}” files can run scripts in the browser and aren't allowed."
            )
        return uploaded


@admin.register(Upload)
class UploadAdmin(admin.ModelAdmin):
    """A simple media library: upload a file (stored under a UUID name) and copy
    its URL to embed in posts/pages. Not shown anywhere on the public site."""

    form = UploadAdminForm
    list_display = ("title", "file", "created")
    search_fields = ("title", "description")
    readonly_fields = ("file_link",)
    fields = ("title", "description", "file", "file_link")

    @admin.display(description="File URL")
    def file_link(self, obj):
        if not obj.file:
            return "—"
        return format_html('<a href="{0}" target="_blank">{0}</a>', obj.file.url)


class OgCacheAdminMixin:
    change_form_template = "admin/og_cache_change_form.html"
    actions = ["regenerate_og_image", "invalidate_page_cache", "invalidate_whole_site_cache"]

    # --- per-object change-page buttons --------------------------------------
    def get_urls(self):
        app, model = self.model._meta.app_label, self.model._meta.model_name
        custom = [
            path(
                "<path:object_id>/regenerate-og/",
                self.admin_site.admin_view(self.regenerate_og_view),
                name=f"{app}_{model}_regenerate_og",
            ),
            path(
                "<path:object_id>/clear-cache/",
                self.admin_site.admin_view(self.clear_cache_view),
                name=f"{app}_{model}_clear_cache",
            ),
        ]
        return custom + super().get_urls()

    def _back_to_change(self, object_id):
        meta = self.model._meta
        return redirect(f"admin:{meta.app_label}_{meta.model_name}_change", object_id)

    def regenerate_og_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            self.message_user(request, "Object not found.", level=messages.ERROR)
            return redirect("..")
        obj.og_image.delete(save=False)  # force a fresh card even if one exists
        obj.og_image = ""
        if obj.ensure_og_image():
            obj.save(update_fields=["og_image"])
            getter = getattr(obj, "get_absolute_url", None)
            if callable(getter):
                invalidate_path(getter())  # so the new card shows on the next visit
            self.message_user(request, "Regenerated the Open Graph image.")
        else:
            self.message_user(
                request, "Could not generate an Open Graph image.", level=messages.WARNING
            )
        return self._back_to_change(object_id)

    def clear_cache_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            self.message_user(request, "Object not found.", level=messages.ERROR)
            return redirect("..")
        getter = getattr(obj, "get_absolute_url", None)
        if callable(getter):
            invalidate_path(getter())
            self.message_user(request, "Cleared the cached page for this object.")
        return self._back_to_change(object_id)

    # --- bulk changelist actions ---------------------------------------------
    @admin.action(description="Regenerate Open Graph image")
    def regenerate_og_image(self, request, queryset):
        count = 0
        for obj in queryset:
            obj.og_image.delete(save=False)  # drop the old file so the name is reused
            obj.og_image = ""
            if obj.ensure_og_image():
                obj.save(update_fields=["og_image"])
                count += 1
        if count:
            invalidate_site_cache()  # refresh the affected cached pages
        self.message_user(request, f"Regenerated {count} Open Graph image(s).")

    @admin.action(description="Invalidate cached page for selected")
    def invalidate_page_cache(self, request, queryset):
        count = 0
        for obj in queryset:
            getter = getattr(obj, "get_absolute_url", None)
            if callable(getter):
                invalidate_path(getter())
                count += 1
        self.message_user(request, f"Invalidated the cached page for {count} object(s).")

    @admin.action(description="Invalidate the ENTIRE site cache")
    def invalidate_whole_site_cache(self, request, queryset):
        invalidate_site_cache()
        self.message_user(request, "Invalidated the entire site cache.")


class PublishActionsMixin:
    """Bulk publish/unpublish changelist actions for models with ``is_published``.

    ``queryset.update()`` bypasses the post_save signal that flushes the page
    cache, so these invalidate the whole site cache after toggling. List the
    actions in the admin's ``actions`` (alongside any inherited from
    ``OgCacheAdminMixin``)."""

    @admin.action(description="Mark selected as published")
    def mark_published(self, request, queryset):
        count = queryset.update(is_published=True)
        invalidate_site_cache()
        self.message_user(request, f"Marked {count} item(s) as published.")

    @admin.action(description="Mark selected as unpublished")
    def mark_unpublished(self, request, queryset):
        count = queryset.update(is_published=False)
        invalidate_site_cache()
        self.message_user(request, f"Marked {count} item(s) as unpublished.")


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(OgCacheAdminMixin, admin.ModelAdmin):
    """Singleton admin: the changelist jumps straight to editing the one row, which
    carries the OG-regenerate and clear-homepage-cache buttons (its page is ``/``)."""

    def has_add_permission(self, request):
        return not SiteConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        config = SiteConfiguration.load()
        return redirect(reverse("admin:core_siteconfiguration_change", args=[config.pk]))
