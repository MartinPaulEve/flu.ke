"""Shared admin actions for content with SEO/Open Graph fields and page caching.

Mix ``OgCacheAdminMixin`` into any ModelAdmin whose model uses SeoFieldsMixin and
has ``get_absolute_url``. It adds three admin actions: regenerate the OG image for
the selected objects, invalidate the cached page(s) for the selected objects, and
invalidate the entire site cache.
"""

from django.contrib import admin

from apps.core.cache import invalidate_path, invalidate_site_cache


class OgCacheAdminMixin:
    actions = ["regenerate_og_image", "invalidate_page_cache", "invalidate_whole_site_cache"]

    @admin.action(description="Regenerate Open Graph image")
    def regenerate_og_image(self, request, queryset):
        count = 0
        for obj in queryset:
            obj.og_image.delete(save=False)  # drop the old file so the name is reused
            obj.og_image = ""
            if obj.ensure_og_image():
                obj.save(update_fields=["og_image"])
                count += 1
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
