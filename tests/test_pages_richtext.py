"""Pages edit their Body with TinyMCE and render it as HTML (not markdown)."""

import pytest

from apps.pages.models import Page

pytestmark = pytest.mark.django_db


def test_page_admin_form_uses_tinymce_for_body(rf, admin_user):
    from django.contrib.admin.sites import site
    from tinymce.widgets import TinyMCE

    request = rf.get("/admin/pages/page/add/")
    request.user = admin_user
    form_class = site._registry[Page].get_form(request)
    assert isinstance(form_class().fields["body"].widget, TinyMCE)


def test_page_body_renders_html_unescaped(client):
    Page.objects.create(
        title="About", slug="about", is_published=True, body="<p>Hi <strong>there</strong></p>"
    )
    html = client.get("/about/").content.decode()
    assert "<p>Hi <strong>there</strong></p>" in html


def test_page_body_is_treated_as_html_not_markdown(client):
    Page.objects.create(title="Raw", slug="raw", is_published=True, body="**not bold**")
    html = client.get("/raw/").content.decode()
    assert "**not bold**" in html                       # literal — HTML, not markdown
    assert "<strong>not bold</strong>" not in html
