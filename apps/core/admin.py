"""Shared admin tooling for content with SEO/Open Graph fields and page caching.

Mix ``OgCacheAdminMixin`` into any ModelAdmin whose model uses SeoFieldsMixin and
has ``get_absolute_url``. It adds:

* per-object buttons on the change page — "Regenerate OG image" (rebuilds the card
  even if one exists, then the post_save signal invalidates the page cache so the
  new card shows up) and "Clear this page's cache";
* the same operations as bulk changelist actions, plus "Invalidate the ENTIRE
  site cache".
"""

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path

from apps.core.cache import invalidate_path, invalidate_site_cache


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
