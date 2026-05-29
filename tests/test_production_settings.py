"""Guard the production static-serving wiring.

With DEBUG=False (a real web server), the admin's own CSS/JS must still be served.
WhiteNoise does that; these tests prevent the wiring from silently regressing.
"""

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
