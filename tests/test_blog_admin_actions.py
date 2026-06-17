"""Bulk publish/unpublish admin actions on the blog Post changelist."""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.blog.admin import PostAdmin
from apps.blog.models import Post

pytestmark = pytest.mark.django_db


def test_mark_unpublished_action_unpublishes_selected(admin_client):
    p1 = Post.objects.create(
        title="One", is_published=True, published_at=timezone.now()
    )
    p2 = Post.objects.create(
        title="Two", is_published=True, published_at=timezone.now()
    )

    admin_client.post(
        reverse("admin:blog_post_changelist"),
        {"action": "mark_unpublished", "_selected_action": [p1.pk, p2.pk]},
    )

    p1.refresh_from_db()
    p2.refresh_from_db()
    assert p1.is_published is False
    assert p2.is_published is False


def test_mark_published_action_publishes_selected(admin_client):
    p1 = Post.objects.create(
        title="One", is_published=False, published_at=timezone.now()
    )
    p2 = Post.objects.create(
        title="Two", is_published=False, published_at=timezone.now()
    )

    admin_client.post(
        reverse("admin:blog_post_changelist"),
        {"action": "mark_published", "_selected_action": [p1.pk, p2.pk]},
    )

    p1.refresh_from_db()
    p2.refresh_from_db()
    assert p1.is_published is True
    assert p2.is_published is True


def test_import_confidence_not_in_list_display():
    assert "import_confidence" not in PostAdmin.list_display
