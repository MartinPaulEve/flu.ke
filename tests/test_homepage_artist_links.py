"""Homepage artists link to their discography pages."""

import pytest

from apps.discography.models import Artist

pytestmark = pytest.mark.django_db


def test_homepage_artists_link_to_their_discography_pages(client):
    fluke = Artist.objects.create(name="Fluke")  # primary, excluded from the alias list
    yuki = Artist.objects.create(
        name="Yuki", slug="yuki", is_alias=True, primary_artist=fluke, appears_on_homepage=True
    )

    html = client.get("/").content.decode()

    assert f'href="{yuki.get_absolute_url()}"' in html   # /discography/yuki/
    assert ">Yuki</a>" in html                           # the name is the link text
