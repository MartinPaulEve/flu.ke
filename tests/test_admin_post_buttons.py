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


def test_change_form_submit_row_survives_browser_parsing(admin_client):
    """The submit row must remain in the DOM after a real (browser-like) HTML parse.

    Regression: a field help_text containing a literal '<title>' opened an RCDATA
    element that swallowed everything after it (incl. Save/Delete) when a browser
    parsed the page, even though it was present in View Source.
    """
    from bs4 import BeautifulSoup

    post = Post.objects.create(title="X", published_at=timezone.now())
    resp = admin_client.get(reverse("admin:blog_post_change", args=[post.pk]))
    soup = BeautifulSoup(resp.content, "lxml")  # lxml parses <title> as RCDATA, like browsers
    submit_row = soup.select_one(".submit-row")
    assert submit_row is not None, "submit-row dropped during HTML parsing"
    assert submit_row.select_one('input[name="_save"]') is not None


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
