"""Diagnostic: does the Post admin show Save/Delete for a superuser?"""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.blog.models import Post

pytestmark = pytest.mark.django_db


def test_post_add_page_has_save_button(admin_client):
    resp = admin_client.get(reverse("admin:blog_post_add"))
    assert resp.status_code == 200
    assert b'name="_save"' in resp.content


def test_post_change_page_has_save_and_delete(admin_client):
    post = Post.objects.create(title="Test post", published_at=timezone.now())
    resp = admin_client.get(reverse("admin:blog_post_change", args=[post.pk]))
    assert resp.status_code == 200
    assert b'name="_save"' in resp.content, "no Save button on change form"
    assert b"deletelink" in resp.content, "no Delete link on change form"


def test_view_only_user_gets_readonly_form_without_buttons(client, django_user_model):
    """A staff user with only 'view' permission sees a read-only form — no Save/Delete.

    This is the exact symptom of 'no save/delete button': it means the logged-in
    account is not a superuser and lacks change/delete permission, not a bug.
    """
    from django.contrib.auth.models import Permission

    user = django_user_model.objects.create_user("viewer", password="pw", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="view_post"))
    client.force_login(user)

    post = Post.objects.create(title="X", published_at=timezone.now())
    resp = client.get(reverse("admin:blog_post_change", args=[post.pk]))
    assert resp.status_code == 200
    assert b'name="_save"' not in resp.content
    assert b"deletelink" not in resp.content
