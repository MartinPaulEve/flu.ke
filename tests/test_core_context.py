"""Tests for the site-identity context processor."""

import pytest
from django.test import override_settings

from apps.core.context_processors import site
from apps.pages.models import Page


@override_settings(SITE_NAME="Fluke", SITE_BASE_URL="https://fluke.fm")
def test_site_context_exposes_name_and_base_url():
    ctx = site(request=None)
    assert ctx["site_name"] == "Fluke"
    assert ctx["site_base_url"] == "https://fluke.fm"


@pytest.mark.django_db
def test_menu_pages_lists_published_ordered_and_excludes_hidden():
    Page.objects.create(title="About", slug="about", is_published=True, menu_order=4)
    Page.objects.create(title="Contact", slug="contact", is_published=True, menu_order=2)
    Page.objects.create(title="Draft", slug="draft", is_published=False, menu_order=1)
    Page.objects.create(title="Hidden", slug="hidden", is_published=True, menu_order=0)

    titles = [p.title for p in site(request=None)["menu_pages"]]

    # Ordered by menu_order; unpublished (Draft) and menu_order=0 (Hidden) excluded.
    assert titles == ["Contact", "About"]


@pytest.mark.django_db
def test_published_menu_page_renders_in_nav(client):
    Page.objects.create(title="About", slug="about", is_published=True, menu_order=4)
    Page.objects.create(title="Secret", slug="secret", is_published=False, menu_order=1)

    html = client.get("/").content.decode()

    assert 'href="/about/"' in html
    assert 'href="/secret/"' not in html
