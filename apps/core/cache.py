"""Page caching backed by the configured cache (Redis/Valkey in production).

A single global "site version" integer is folded into every page cache key, so
the whole site can be invalidated in O(1) by bumping it (done automatically on any
content change). Individual pages can be dropped by key. Authenticated users (staff
editing) and DEBUG always bypass the cache, so editors and local dev see live
content.
"""

from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

_SITE_VERSION_KEY = "site-cache-version"

# Model changes in these apps invalidate the whole site cache (see CoreConfig).
CONTENT_APPS = frozenset({"blog", "pages", "resources", "discography"})


def site_version():
    """Current global cache version, initialised to 1 on first use."""
    version = cache.get(_SITE_VERSION_KEY)
    if version is None:
        cache.add(_SITE_VERSION_KEY, 1)
        version = cache.get(_SITE_VERSION_KEY) or 1
    return version


def page_cache_key(path):
    # The release version is part of the key so a deploy (new version) serves
    # fresh pages even when no content changed (e.g. template/CSS updates); the
    # site version handles content changes between deploys.
    return f"page:{settings.STATIC_VERSION}:{site_version()}:{path}"


def invalidate_site_cache():
    """Invalidate every cached page by bumping the global version."""
    try:
        cache.incr(_SITE_VERSION_KEY)
    except ValueError:  # key absent/expired — start a fresh version
        cache.set(_SITE_VERSION_KEY, site_version() + 1)


def invalidate_path(path):
    """Drop the cached response for a single page path."""
    cache.delete(page_cache_key(path))


def invalidate_on_content_change(sender, **kwargs):
    """post_save/post_delete receiver: any content change clears the site cache."""
    if getattr(sender._meta, "app_label", None) in CONTENT_APPS:
        invalidate_site_cache()


def cached_page(view):
    """Cache a view's GET response per URL for anonymous visitors.

    Bypassed for non-GET, authenticated users (so staff see live content + edit
    links) and DEBUG. Cached entries are keyed by the global site version, so a
    single version bump invalidates everything.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if settings.DEBUG or request.method != "GET" or request.user.is_authenticated:
            return view(request, *args, **kwargs)

        key = page_cache_key(request.get_full_path())
        hit = cache.get(key)
        if hit is not None:
            return HttpResponse(hit["content"], content_type=hit["content_type"])

        response = view(request, *args, **kwargs)
        if hasattr(response, "render") and callable(response.render):
            response.render()  # TemplateResponse → realise content before caching
        if response.status_code == 200:
            cache.set(
                key,
                {
                    "content": response.content,
                    "content_type": response.get("Content-Type", "text/html; charset=utf-8"),
                },
                settings.PAGE_CACHE_SECONDS,
            )
        return response

    return wrapper
