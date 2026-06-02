"""Production settings for the Fluke CMS.

The live site is served by gunicorn behind a Traefik reverse proxy, which in turn
sits behind Pangolin. Pangolin terminates TLS and forwards plain HTTP, setting an
``X-Forwarded-Proto`` header — so Django must trust that header to know the
original request arrived over HTTPS, but must NOT do its own HTTP→HTTPS redirect
(the app listens on HTTP only and the edge already enforces TLS, so a redirect
would loop).

SQLite is the production database (chosen for trivial file-level backups); the
pragmas below tune it for a concurrent web workload per
https://alldjango.com/articles/definitive-guide-to-using-django-sqlite-in-production

Activate with ``DJANGO_SETTINGS_MODULE=config.settings_production``.
"""

from django.core.exceptions import ImproperlyConfigured

from config.settings import *  # noqa: F401,F403
from config.settings import env

# --- Debug -----------------------------------------------------------------
# Hard-off in production, regardless of the environment.
DEBUG = False

# --- Secret key guard ------------------------------------------------------
# Refuse to boot with the insecure dev default. Re-read the key freshly (rather
# than trusting the value the base module computed) so this stays testable and
# can never silently fall back to a shared placeholder.
SECRET_KEY = env("DJANGO_SECRET_KEY", default="")
if not SECRET_KEY or SECRET_KEY == "insecure-dev-key-override-in-env":
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a real value in production."
    )

# --- Hosts / CSRF ----------------------------------------------------------
# Allow both the canonical domain and the test/staging domain, merged with any
# hosts/origins supplied via the environment (de-duplicated, order preserved).
_DEFAULT_ALLOWED_HOSTS = ["fluke.fm", "www.fluke.fm", "fluke.eve.gd"]
_DEFAULT_CSRF_TRUSTED_ORIGINS = [
    "https://fluke.fm",
    "https://www.fluke.fm",
    "https://fluke.eve.gd",
]


def _merge(*lists):
    """Concatenate the given lists, dropping duplicates while keeping order."""
    seen = {}
    for values in lists:
        for value in values:
            seen.setdefault(value, None)
    return list(seen)


ALLOWED_HOSTS = _merge(
    _DEFAULT_ALLOWED_HOSTS,
    env("DJANGO_ALLOWED_HOSTS"),
)
CSRF_TRUSTED_ORIGINS = _merge(
    _DEFAULT_CSRF_TRUSTED_ORIGINS,
    env("CSRF_TRUSTED_ORIGINS"),
)

# --- Security (behind an SSL-terminating proxy) ----------------------------
# Pangolin terminates TLS and forwards plain HTTP with X-Forwarded-Proto, so
# Django learns the original scheme from that header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# The app speaks HTTP only and the edge already enforces HTTPS, so the app-level
# redirect stays off by default (it would otherwise loop). Still env-overridable.
SECURE_SSL_REDIRECT = env.bool("DJANGO_SSL_REDIRECT", default=False)

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_HSTS_SECONDS = 31536000  # one year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# --- Database (SQLite production tuning) -----------------------------------
# Only touch the SQLite backend; leave any other engine exactly as the base
# settings configured it. Merge into any existing OPTIONS rather than clobbering it.
if "sqlite" in DATABASES["default"]["ENGINE"].lower():  # noqa: F405
    _options = DATABASES["default"].setdefault("OPTIONS", {})  # noqa: F405
    _options.update(
        {
            "init_command": (
                "PRAGMA journal_mode=WAL;"
                "PRAGMA synchronous=NORMAL;"
                "PRAGMA busy_timeout=5000;"
                "PRAGMA temp_store=MEMORY;"
                "PRAGMA mmap_size=134217728;"
                "PRAGMA journal_size_limit=67108864;"
                "PRAGMA cache_size=2000;"
            ),
            "transaction_mode": "IMMEDIATE",
        }
    )
    DATABASES["default"]["timeout"] = 5  # noqa: F405
