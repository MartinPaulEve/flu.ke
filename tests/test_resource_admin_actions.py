"""Bulk publish/unpublish admin actions on the Resource changelist."""

import pytest
from django.urls import reverse

from apps.resources.models import Resource

pytestmark = pytest.mark.django_db


def test_mark_unpublished_action_unpublishes_selected(admin_client):
    r1 = Resource.objects.create(title="One", kind="official", is_published=True)
    r2 = Resource.objects.create(title="Two", kind="official", is_published=True)

    admin_client.post(
        reverse("admin:resources_resource_changelist"),
        {"action": "mark_unpublished", "_selected_action": [r1.pk, r2.pk]},
    )

    r1.refresh_from_db()
    r2.refresh_from_db()
    assert r1.is_published is False
    assert r2.is_published is False


def test_mark_published_action_publishes_selected(admin_client):
    r1 = Resource.objects.create(title="One", kind="official", is_published=False)
    r2 = Resource.objects.create(title="Two", kind="official", is_published=False)

    admin_client.post(
        reverse("admin:resources_resource_changelist"),
        {"action": "mark_published", "_selected_action": [r1.pk, r2.pk]},
    )

    r1.refresh_from_db()
    r2.refresh_from_db()
    assert r1.is_published is True
    assert r2.is_published is True
