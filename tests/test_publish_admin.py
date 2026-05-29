"""The admin Publish button rebuilds the site and clears the dirty flag."""

import pytest
from django.urls import reverse

from apps.staticgen.models import BuildState

pytestmark = pytest.mark.django_db


def test_changelist_shows_unpublished_banner(admin_client):
    BuildState.mark_dirty()
    resp = admin_client.get(reverse("admin:staticgen_buildstate_changelist"))
    assert resp.status_code == 200
    assert b"Unpublished changes" in resp.content
    assert b"Publish now" in resp.content


def test_publish_builds_site_and_clears_dirty(admin_client, tmp_path, settings):
    settings.BUILD_DIR = str(tmp_path)
    BuildState.mark_dirty()

    resp = admin_client.post(reverse("admin:staticgen_buildstate_publish"))

    assert resp.status_code == 302
    assert (tmp_path / "index.html").exists()
    assert BuildState.load().is_dirty is False
    assert BuildState.load().last_built is not None
