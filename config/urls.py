"""Root URL configuration.

Django serves everything live: the admin (private editing), the read-only REST
API under ``/api/``, and the public site (``apps.frontend``). The frontend is
included last because it owns the ``/<slug>/`` page catch-all; the more specific
``api/`` include is therefore matched first.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from apps.core.views import tinymce_upload

urlpatterns = [
    path("admin/", admin.site.urls),
    path("admin-uploads/tinymce-image/", tinymce_upload, name="tinymce_upload"),
    path("tinymce/", include("tinymce.urls")),
    path("api/", include("apps.api.urls")),
]

# Serve uploaded media. In production a front web server should serve /media/
# directly for performance; this keeps the app self-contained meanwhile.
urlpatterns += [
    re_path(
        r"^media/(?P<path>.*)$",
        serve,
        {"document_root": settings.MEDIA_ROOT},
    ),
]

# Public site last: it owns the /<slug>/ page catch-all.
urlpatterns += [
    path("", include("apps.frontend.urls")),
]
