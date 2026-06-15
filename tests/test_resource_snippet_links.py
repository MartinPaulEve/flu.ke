"""The credited artist in a resource snippet links to their page, unless empty."""

import pytest

from apps.discography.models import Artist, Release, ReleaseType
from apps.resources.models import KIND_OFFICIAL, Resource

pytestmark = pytest.mark.django_db


@pytest.fixture
def fluke_with_release():
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    Release.objects.create(
        name="Risotto", artist=fluke, type=rtype, year=1997, is_published=True
    )
    return fluke


def test_snippet_artist_links_to_a_non_empty_page(client, fluke_with_release):
    Resource.objects.create(
        title="Some live recording", kind=KIND_OFFICIAL,
        artist=fluke_with_release, is_published=True,
    )

    html = client.get("/resources/").content.decode()

    assert f'href="{fluke_with_release.get_absolute_url()}"' in html
    assert ">Fluke</a>" in html


def test_snippet_artist_with_empty_page_is_not_linked(client):
    ghost = Artist.objects.create(name="Ghost", slug="ghost")  # no releases
    Resource.objects.create(
        title="A ghost session", kind=KIND_OFFICIAL, artist=ghost, is_published=True,
    )

    html = client.get("/resources/").content.decode()

    assert "Ghost" in html  # still shown in the snippet text
    assert f'href="{ghost.get_absolute_url()}"' not in html  # but not linked
