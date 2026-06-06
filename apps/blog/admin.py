from django.contrib import admin
from django.db import models
from tinymce.widgets import TinyMCE

from apps.core.admin import OgCacheAdminMixin

from .models import Category, Post, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Post)
class PostAdmin(OgCacheAdminMixin, admin.ModelAdmin):
    list_display = ("title", "published_at", "is_published", "import_confidence")
    list_filter = ("is_published", "import_confidence", "categories")
    search_fields = ("title", "excerpt", "body")
    prepopulated_fields = {"slug": ("title",)}
    # Rich-text editing for the Body and Excerpt text fields.
    formfield_overrides = {models.TextField: {"widget": TinyMCE()}}
    filter_horizontal = ("categories", "tags")
    date_hierarchy = "published_at"
    fieldsets = (
        (None, {"fields": ("title", "slug", "excerpt", "body", "cover_image")}),
        ("Publishing", {"fields": ("is_published", "published_at", "categories", "tags")}),
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
        (
            "Import provenance",
            {
                "classes": ("collapse",),
                "fields": ("source_url", "import_confidence", "manually_edited"),
            },
        ),
    )
