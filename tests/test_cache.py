"""Behaviour of the page cache and its invalidation hooks."""

import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpResponse
from django.test import RequestFactory

from apps.core.cache import cached_page, invalidate_path, invalidate_site_cache

pytestmark = pytest.mark.django_db


def _counter_view():
    """A cached view that counts how many times its body actually runs."""
    calls = {"n": 0}

    @cached_page
    def view(request):
        calls["n"] += 1
        return HttpResponse(f"body {calls['n']}")

    return view, calls


def _get(view, path="/x/", user=None):
    request = RequestFactory().get(path)
    request.user = user or AnonymousUser()
    return view(request)


def test_anonymous_get_served_from_cache_on_second_request():
    view, calls = _counter_view()
    first = _get(view)
    second = _get(view)
    assert calls["n"] == 1                 # body ran once
    assert first.content == second.content


def test_authenticated_user_bypasses_cache():
    view, calls = _counter_view()
    staff = User(username="ed", is_staff=True)
    _get(view, user=staff)
    _get(view, user=staff)
    assert calls["n"] == 2


def test_invalidate_site_cache_forces_regeneration():
    view, calls = _counter_view()
    _get(view)
    invalidate_site_cache()
    _get(view)
    assert calls["n"] == 2


def test_invalidate_path_drops_only_that_page():
    view, calls = _counter_view()
    _get(view, path="/a/")
    _get(view, path="/b/")
    assert calls["n"] == 2
    invalidate_path("/a/")
    _get(view, path="/a/")                  # regenerated
    _get(view, path="/b/")                  # still cached
    assert calls["n"] == 3


def test_saving_content_invalidates_the_site_cache():
    from apps.pages.models import Page

    view, calls = _counter_view()
    _get(view)
    assert calls["n"] == 1
    Page.objects.create(title="A brand new page")   # post_save -> invalidate
    _get(view)
    assert calls["n"] == 2
