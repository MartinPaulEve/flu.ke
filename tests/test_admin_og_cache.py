"""Per-object admin buttons: regenerate the OG image and clear the page cache."""

import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.core.cache import page_cache_key
from apps.discography.models import Artist
from apps.pages.models import Page

pytestmark = pytest.mark.django_db


def test_regenerate_og_button_generates_a_missing_image(admin_client):
    artist = Artist.objects.create(name="Yuki", slug="yuki")
    # Simulate a missing image (e.g. legacy data imported before OG generation).
    artist.og_image.delete(save=False)
    Artist.objects.filter(pk=artist.pk).update(og_image="")

    admin_client.get(reverse("admin:discography_artist_regenerate_og", args=[artist.pk]))

    artist.refresh_from_db()
    assert artist.og_image.name
    assert artist.og_image.name.endswith(".png")


def test_change_page_renders_both_buttons(admin_client):
    page = Page.objects.create(title="About", slug="about")
    html = admin_client.get(reverse("admin:pages_page_change", args=[page.pk])).content.decode()
    assert "Regenerate OG image" in html
    assert "Clear this page&#x27;s cache" in html or "Clear this page's cache" in html


def test_clear_cache_button_invalidates_that_page(admin_client):
    page = Page.objects.create(title="About", slug="about")
    key = page_cache_key("/about/")
    cache.set(key, {"content": b"cached", "content_type": "text/html"}, 600)

    admin_client.get(reverse("admin:pages_page_clear_cache", args=[page.pk]))

    assert cache.get(key) is None
