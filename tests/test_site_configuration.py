"""SiteConfiguration singleton: homepage OG card + copy, with admin controls."""

import pytest
from django.urls import reverse

from apps.core.models import SiteConfiguration

pytestmark = pytest.mark.django_db


def test_load_creates_and_returns_the_singleton():
    a = SiteConfiguration.load()
    b = SiteConfiguration.load()
    assert a.pk == 1 and b.pk == 1
    assert SiteConfiguration.objects.count() == 1


def test_editing_and_saving_keeps_one_row():
    config = SiteConfiguration.load()
    config.og_title = "Changed title"
    config.save()
    assert SiteConfiguration.objects.count() == 1
    assert SiteConfiguration.load().og_title == "Changed title"


def test_generates_a_homepage_og_image():
    config = SiteConfiguration.load()
    assert config.og_image.name and config.og_image.name.endswith(".jpg")


def test_get_absolute_url_is_the_homepage():
    assert SiteConfiguration.load().get_absolute_url() == "/"


def test_homepage_og_uses_the_singleton(client):
    html = client.get("/").content.decode()
    assert "og/siteconfiguration-" in html          # the singleton's generated card
    assert 'property="og:title"' in html


def test_admin_changelist_redirects_to_the_single_object(admin_client):
    resp = admin_client.get(reverse("admin:core_siteconfiguration_changelist"))
    assert resp.status_code == 302
    assert "/change/" in resp.url


def test_admin_regenerate_button_rebuilds_the_homepage_card(admin_client):
    config = SiteConfiguration.load()
    config.og_image.delete(save=False)
    SiteConfiguration.objects.filter(pk=1).update(og_image="")

    admin_client.get(reverse("admin:core_siteconfiguration_regenerate_og", args=[config.pk]))

    config.refresh_from_db()
    assert config.og_image.name


def test_footer_tagline_has_a_sensible_default():
    assert SiteConfiguration.load().footer_tagline == "Black & red since the rave."


def test_footer_renders_the_configurable_tagline(client):
    config = SiteConfiguration.load()
    config.footer_tagline = "Loud & proud since forever"
    config.save()
    html = client.get("/news/").content.decode()
    # Django autoescapes the ampersand in HTML output.
    assert "Loud &amp; proud since forever" in html


def test_header_kicker_defaults_match_the_current_copy():
    config = SiteConfiguration.load()
    assert config.header_kicker_lead == "Est. on the dancefloor"
    assert config.header_kicker_detail == "official & fan archive"


def test_homepage_renders_the_configurable_header_kicker(client):
    config = SiteConfiguration.load()
    config.header_kicker_lead = "Born in the booth"
    config.header_kicker_detail = "a complete history"
    config.save()
    html = client.get("/").content.decode()
    assert "Born in the booth" in html
    assert "a complete history" in html


def test_header_kicker_drops_the_dash_when_one_part_is_blank(client):
    config = SiteConfiguration.load()
    config.header_kicker_lead = "Just the lead"
    config.header_kicker_detail = ""
    config.save()
    html = client.get("/").content.decode()
    assert "Just the lead" in html
    assert "Just the lead —" not in html  # no dangling separator
