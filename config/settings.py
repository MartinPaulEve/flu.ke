"""
Django settings for the Fluke CMS.

Django serves the public site live (``apps.frontend``) and a read-only REST API
(``apps.api``, documented with Swagger), with the admin for private editing.
Secrets come from the environment / a ``.env`` file via django-environ — never
hard-coded.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["127.0.0.1", "localhost"]),
    DJANGO_SECURE=(bool, False),
    CSRF_TRUSTED_ORIGINS=(list, []),
    SITE_BASE_URL=(str, "https://fluke.fm"),
    SITE_NAME=(str, "Fluke"),
    MEDIA_ROOT=(str, "media"),
    MEDIA_URL=(str, "/media/"),
    MUSICBRAINZ_APP=(str, "flukecms"),
    MUSICBRAINZ_VERSION=(str, "1.0"),
    MUSICBRAINZ_CONTACT=(str, ""),
)

# Read .env if present (not required in CI/tests, which set sensible defaults).
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-override-in-env")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    # Third-party
    "tinymce",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    # First-party
    "apps.core",
    "apps.pages",
    "apps.blog",
    "apps.resources",
    "apps.discography",
    "apps.importers",
    "apps.frontend",
    "apps.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves the CMS's own static files (admin CSS/JS) when DEBUG is off, so the
    # admin works on a real web server without extra web-server config.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/London"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "assets"]
STATIC_ROOT = BASE_DIR / ".staticcollect"

# WhiteNoise serves the collected static files (run `collectstatic` on deploy).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

MEDIA_URL = env("MEDIA_URL")
MEDIA_ROOT = BASE_DIR / env("MEDIA_ROOT")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Security (enable on the public CMS host via DJANGO_SECURE=True) ---------
# Not tied to DEBUG: the test runner forces DEBUG=False, and we must not redirect
# test/local HTTP requests to HTTPS.
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
if env("DJANGO_SECURE"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# --- Project-specific settings ---------------------------------------------
SITE_BASE_URL = env("SITE_BASE_URL").rstrip("/")
SITE_NAME = env("SITE_NAME")


def _read_version():
    """Read the project version from __version__.py for static cache-busting."""
    try:
        text = (BASE_DIR / "__version__.py").read_text()
    except OSError:
        return "dev"
    for line in text.splitlines():
        if line.strip().startswith("__version__"):
            return line.split("=", 1)[1].strip().strip("\"'")
    return "dev"


# Cache-busting token for the site's own CSS/JS. Tied to the release version so
# each deployed build serves fresh assets, without hashing every static filename
# (which would break editors like TinyMCE that load assets by unhashed path).
STATIC_VERSION = _read_version()

# Source archive of the legacy site (used by the import_* management commands).
INGEST_DIR = BASE_DIR / "Ingest"

MUSICBRAINZ = {
    "app": env("MUSICBRAINZ_APP"),
    "version": env("MUSICBRAINZ_VERSION"),
    "contact": env("MUSICBRAINZ_CONTACT"),
}

# --- REST API (read-only public discography API) ---------------------------
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Fluke discography API",
    "DESCRIPTION": "Read-only API for the Fluke discography — artists, releases, "
    "editions, tracks, lyrics and cover art.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# TinyMCE rich-text editor (self-hosted; no external/CDN calls).
TINYMCE_DEFAULT_CONFIG = {
    "height": 420,
    "menubar": "edit view insert format table",
    "plugins": "advlist autolink lists link image charmap preview anchor "
    "searchreplace visualblocks code fullscreen insertdatetime media table help wordcount",
    "toolbar": "undo redo | blocks | bold italic underline | "
    "alignleft aligncenter alignright | bullist numlist | link image media | "
    "removeformat code",
    "branding": False,
    "promotion": False,
    "convert_urls": False,
}
