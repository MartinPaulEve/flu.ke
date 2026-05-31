"""Guard the production static-serving wiring.

With DEBUG=False (a real web server), the admin's own CSS/JS must still be served.
WhiteNoise does that; these tests prevent the wiring from silently regressing.

The ``config.settings_production`` module hardens the base settings for the live
site (served by gunicorn behind Traefik, behind Pangolin which terminates TLS).
It refuses to import without a real ``DJANGO_SECRET_KEY``, so the tests below set
one before (re)loading the module.
"""

import importlib

import pytest
from django.conf import settings


def test_whitenoise_middleware_runs_right_after_security():
    mw = settings.MIDDLEWARE
    assert "whitenoise.middleware.WhiteNoiseMiddleware" in mw
    security = mw.index("django.middleware.security.SecurityMiddleware")
    whitenoise = mw.index("whitenoise.middleware.WhiteNoiseMiddleware")
    assert whitenoise == security + 1


def test_staticfiles_storage_is_whitenoise():
    backend = settings.STORAGES["staticfiles"]["BACKEND"]
    assert "whitenoise" in backend.lower()


# --- Production settings module --------------------------------------------

VALID_KEY = "x" * 50


def _load_production(monkeypatch, secret_key=VALID_KEY):
    """Import (or reload) config.settings_production with a chosen secret key.

    Returns the freshly imported module. The base ``config.settings`` reads the
    key via ``env``, which consults ``os.environ`` live, so setting the env var
    before import is enough — no fixture file is touched.
    """
    if secret_key is None:
        monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("DJANGO_SECRET_KEY", secret_key)
    import config.settings_production as prod

    return importlib.reload(prod)


def test_production_debug_is_false(monkeypatch):
    prod = _load_production(monkeypatch)
    assert prod.DEBUG is False


def test_production_allowed_hosts_cover_test_and_real_domains(monkeypatch):
    prod = _load_production(monkeypatch)
    assert "flu.ke" in prod.ALLOWED_HOSTS
    assert "www.flu.ke" in prod.ALLOWED_HOSTS
    assert "fluke.eve.gd" in prod.ALLOWED_HOSTS


def test_production_allowed_hosts_merge_env_override(monkeypatch):
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "extra.example.com")
    prod = _load_production(monkeypatch)
    assert "extra.example.com" in prod.ALLOWED_HOSTS
    assert "flu.ke" in prod.ALLOWED_HOSTS


def test_production_csrf_trusted_origins(monkeypatch):
    prod = _load_production(monkeypatch)
    assert "https://flu.ke" in prod.CSRF_TRUSTED_ORIGINS
    assert "https://www.flu.ke" in prod.CSRF_TRUSTED_ORIGINS
    assert "https://fluke.eve.gd" in prod.CSRF_TRUSTED_ORIGINS


def test_production_csrf_trusted_origins_merge_env_override(monkeypatch):
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "https://extra.example.com")
    prod = _load_production(monkeypatch)
    assert "https://extra.example.com" in prod.CSRF_TRUSTED_ORIGINS
    assert "https://flu.ke" in prod.CSRF_TRUSTED_ORIGINS


def test_production_proxy_ssl_header(monkeypatch):
    prod = _load_production(monkeypatch)
    assert prod.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")


def test_production_secure_cookies(monkeypatch):
    prod = _load_production(monkeypatch)
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True


def test_production_hsts_and_hardening(monkeypatch):
    prod = _load_production(monkeypatch)
    assert prod.SECURE_HSTS_SECONDS == 31536000
    assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert prod.SECURE_HSTS_PRELOAD is True
    assert prod.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert prod.X_FRAME_OPTIONS == "DENY"


def test_production_ssl_redirect_off_by_default(monkeypatch):
    # The edge (Pangolin) enforces HTTPS; an app-level redirect risks loops
    # because the app listens on plain HTTP only.
    prod = _load_production(monkeypatch)
    assert prod.SECURE_SSL_REDIRECT is False


def test_production_sqlite_pragmas(monkeypatch):
    prod = _load_production(monkeypatch)
    default = prod.DATABASES["default"]
    # The dev/CI default DB is SQLite, so the production pragmas must apply.
    assert "sqlite" in default["ENGINE"].lower()
    options = default["OPTIONS"]
    assert "journal_mode=WAL" in options["init_command"]
    assert "synchronous=NORMAL" in options["init_command"]
    assert "busy_timeout=5000" in options["init_command"]
    assert options["transaction_mode"] == "IMMEDIATE"
    assert default["timeout"] == 5


def test_production_secret_key_guard_rejects_missing_key(monkeypatch):
    from django.core.exceptions import ImproperlyConfigured

    with pytest.raises(ImproperlyConfigured):
        _load_production(monkeypatch, secret_key=None)


def test_production_secret_key_guard_rejects_dev_default(monkeypatch):
    from django.core.exceptions import ImproperlyConfigured

    with pytest.raises(ImproperlyConfigured):
        _load_production(monkeypatch, secret_key="insecure-dev-key-override-in-env")
