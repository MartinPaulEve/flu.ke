"""The blog Post admin should edit Body and Excerpt with TinyMCE."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_post_admin_loads_tinymce_for_richtext_fields(admin_client):
    resp = admin_client.get(reverse("admin:blog_post_add"))
    assert resp.status_code == 200
    content = resp.content.decode()
    # the body and excerpt fields are present...
    assert 'name="body"' in content
    assert 'name="excerpt"' in content
    # ...and the TinyMCE editor assets are loaded for them (self-hosted).
    assert "tinymce.min.js" in content


def test_post_admin_form_uses_tinymce_widget(rf, admin_user):
    from django.contrib.admin.sites import site
    from tinymce.widgets import TinyMCE

    from apps.blog.models import Post

    request = rf.get("/admin/blog/post/add/")
    request.user = admin_user
    form_class = site._registry[Post].get_form(request)
    form = form_class()
    assert isinstance(form.fields["body"].widget, TinyMCE)
    assert isinstance(form.fields["excerpt"].widget, TinyMCE)


def test_edition_admin_uses_tinymce_for_notes(rf, admin_user):
    from django.contrib.admin.sites import site
    from tinymce.widgets import TinyMCE

    from apps.discography.models import Edition

    request = rf.get("/admin/discography/edition/add/")
    request.user = admin_user
    form_class = site._registry[Edition].get_form(request)
    form = form_class()
    assert isinstance(form.fields["notes"].widget, TinyMCE)
