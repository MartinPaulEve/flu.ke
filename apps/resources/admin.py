from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.shortcuts import render

from apps.core.admin import OgCacheAdminMixin, PublishActionsMixin
from apps.core.cache import invalidate_site_cache

from .forms import ResourceAdminForm
from .models import Resource, ResourceFile, ResourceSubcategory


class ResourceFileInline(admin.TabularInline):
    model = ResourceFile
    extra = 0
    fields = (
        "file", "external_url", "file_kind", "original_filename",
        "byte_size", "duration", "display_order",
    )
    readonly_fields = ("byte_size",)


@admin.register(ResourceFile)
class ResourceFileAdmin(admin.ModelAdmin):
    list_display = ("__str__", "resource", "file_kind", "byte_size")
    list_filter = ("file_kind",)
    search_fields = ("original_filename", "file", "resource__title")
    autocomplete_fields = ("resource",)
    actions = ["move_to_resource"]

    @admin.action(description="Move selected file(s) to another resource…")
    def move_to_resource(self, request, queryset):
        """Reassign files to a chosen resource. The file and all metadata travel
        with the row — only the resource foreign key changes."""
        if "apply" in request.POST:
            resource = Resource.objects.filter(pk=request.POST.get("resource")).first()
            if resource is None:
                self.message_user(request, "Choose a target resource.", level=messages.ERROR)
            else:
                moved = queryset.update(resource=resource)
                invalidate_site_cache()  # source + target resource pages change
                self.message_user(request, f"Moved {moved} file(s) to “{resource.title}”.")
                return None
        return render(
            request,
            "admin/resources/move_files.html",
            {
                **self.admin_site.each_context(request),
                "title": "Move files to another resource",
                "opts": self.model._meta,
                "files": queryset,
                "resources": Resource.objects.order_by("kind", "title"),
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
                "selected": list(queryset.values_list("pk", flat=True)),
            },
        )


@admin.register(ResourceSubcategory)
class ResourceSubcategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "snippet_phrase", "display_order")
    list_filter = ("kind",)
    list_editable = ("snippet_phrase", "display_order")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Resource)
class ResourceAdmin(OgCacheAdminMixin, PublishActionsMixin, admin.ModelAdmin):
    form = ResourceAdminForm
    actions = [*OgCacheAdminMixin.actions, "mark_published", "mark_unpublished"]
    list_display = ("title", "snippet", "kind", "subcategory", "is_published", "uploaded_at")
    list_filter = ("kind", "is_published", "subcategory")
    search_fields = ("title", "snippet", "description", "contributor")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = (
        "artist",
        "related_release",
        "related_edition",
        "related_post",
        "subcategory",
    )
    date_hierarchy = "uploaded_at"
    filter_horizontal = ("additional_artists",)
    inlines = [ResourceFileInline]
    fieldsets = (
        (None, {"fields": ("title", "slug", "kind", "subcategory", "snippet", "description")}),
        (
            "Metadata",
            {
                "fields": (
                    "artist",
                    "additional_artists",
                    "related_release",
                    "related_edition",
                    "related_post",
                    "contributor",
                    "source_attribution",
                    "license",
                    "recorded",
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
