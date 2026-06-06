from django.contrib import admin

from apps.core.admin import OgCacheAdminMixin

from .models import Page


@admin.register(Page)
class PageAdmin(OgCacheAdminMixin, admin.ModelAdmin):
    list_display = ("title", "is_published", "menu_order", "template_key")
    list_editable = ("menu_order",)
    list_filter = ("is_published", "template_key")
    search_fields = ("title", "body")
    prepopulated_fields = {"slug": ("title",)}
    fieldsets = (
        (None, {"fields": ("title", "slug", "body", "template_key")}),
        ("Publishing", {"fields": ("is_published", "menu_order")}),
        (
            "SEO & Open Graph",
            {
                "classes": ("collapse",),
                "fields": (
                    "seo_title",
                    "meta_description",
                    "canonical_url",
                    "og_title",
                    "og_description",
                    "og_image",
                    "noindex",
                ),
            },
        ),
    )
