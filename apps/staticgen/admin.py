from django.contrib import admin, messages
from django.core.management import call_command
from django.shortcuts import redirect
from django.urls import path

from .models import BuildState


@admin.register(BuildState)
class BuildStateAdmin(admin.ModelAdmin):
    change_list_template = "admin/staticgen/buildstate_changelist.html"
    list_display = ("__str__", "dirty_since", "last_built")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        custom = [
            path(
                "publish/",
                self.admin_site.admin_view(self.publish_view),
                name="staticgen_buildstate_publish",
            )
        ]
        return custom + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["build_state"] = BuildState.load()
        return super().changelist_view(request, extra_context=extra_context)

    def publish_view(self, request):
        if request.method == "POST":
            try:
                call_command("build_site")
                messages.success(request, "Published — the static site was rebuilt.")
            except Exception as exc:  # surface the failure to the editor
                messages.error(request, f"Build failed: {exc}")
        return redirect("admin:staticgen_buildstate_changelist")
