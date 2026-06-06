"""Template context processors."""

from django.conf import settings


def site(request):
    """Expose site-wide identity and the navigation pages to every template."""
    # Imported lazily so the module stays importable without the app registry
    # ready (e.g. the name/base-url unit test). The queryset is lazy too, so it
    # only hits the database when a template iterates it.
    from apps.pages.models import Page

    return {
        "site_name": settings.SITE_NAME,
        "site_base_url": settings.SITE_BASE_URL,
        "static_version": settings.STATIC_VERSION,
        # Published pages with menu_order > 0, in menu order (0 hides a page).
        "menu_pages": (
            Page.objects.published().filter(menu_order__gt=0).order_by("menu_order", "title")
        ),
    }
