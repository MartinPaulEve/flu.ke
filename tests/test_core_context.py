"""Tests for the site-identity context processor."""

from django.test import override_settings

from apps.core.context_processors import site


@override_settings(SITE_NAME="Fluke", SITE_BASE_URL="https://fluke.fm")
def test_site_context_exposes_name_and_base_url():
    ctx = site(request=None)
    assert ctx["site_name"] == "Fluke"
    assert ctx["site_base_url"] == "https://fluke.fm"
