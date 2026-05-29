from django.contrib import admin

from .models import Resource, ResourceFile, ResourceSubcategory


class ResourceFileInline(admin.TabularInline):
    model = ResourceFile
    extra = 0
    fields = ("file", "file_kind", "original_filename", "byte_size", "duration", "display_order")
    readonly_fields = ("byte_size",)


@admin.register(ResourceSubcategory)
class ResourceSubcategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "display_order")
    list_filter = ("kind",)
    list_editable = ("display_order",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "subcategory", "is_published", "uploaded_at")
    list_filter = ("kind", "is_published", "subcategory")
    search_fields = ("title", "description", "contributor")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("artist", "related_release", "related_edition", "subcategory")
    date_hierarchy = "uploaded_at"
    inlines = [ResourceFileInline]
    fieldsets = (
        (None, {"fields": ("title", "slug", "kind", "subcategory", "description")}),
        (
            "Metadata",
            {
                "fields": (
                    "artist",
                    "related_release",
                    "related_edition",
                    "contributor",
                    "source_attribution",
                    "license",
                    "recorded_date",
                    "released_date",
                    "uploaded_at",
                    "external_url",
                )
            },
        ),
        ("Publishing", {"fields": ("is_published",)}),
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
