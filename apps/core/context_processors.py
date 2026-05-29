"""Template context processors."""

from django.conf import settings


def site(request):
    """Expose site-wide identity (name, canonical base URL) to every template."""
    return {
        "site_name": settings.SITE_NAME,
        "site_base_url": settings.SITE_BASE_URL,
    }
