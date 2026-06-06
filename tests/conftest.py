import pytest


@pytest.fixture(autouse=True)
def _isolate_media(tmp_path_factory, settings):
    """Point MEDIA_ROOT at a throwaway dir so tests never write into the repo's media/.

    Several models (e.g. blog.Post) generate files on save; this keeps that isolated.
    """
    settings.MEDIA_ROOT = str(tmp_path_factory.mktemp("media"))


@pytest.fixture(autouse=True)
def _clear_cache():
    """The cache is not transactional, so clear it around every test to keep page
    caching from leaking responses between tests."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
