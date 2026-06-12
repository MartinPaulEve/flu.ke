"""Template context processors."""

from django.conf import settings
from django.utils.functional import SimpleLazyObject


def site(request):
    """Expose site-wide identity and the navigation pages to every template."""
    # Imported lazily so the module stays importable without the app registry
    # ready (e.g. the name/base-url unit test). The queryset is lazy too, so it
    # only hits the database when a template iterates it.
    from apps.pages.models import Page

    def _load_config():
        from apps.core.models import SiteConfiguration

        return SiteConfiguration.load()

    return {
        "site_name": settings.SITE_NAME,
        "site_base_url": settings.SITE_BASE_URL,
        "static_version": settings.STATIC_VERSION,
        # Published pages with menu_order > 0, in menu order (0 hides a page).
        "menu_pages": (
            Page.objects.published().filter(menu_order__gt=0).order_by("menu_order", "title")
        ),
        # Lazy so non-DB unit tests of this processor don't hit the database, and
        # so pages that don't reference it (or override it) pay nothing.
        "site_config": SimpleLazyObject(_load_config),
    }
