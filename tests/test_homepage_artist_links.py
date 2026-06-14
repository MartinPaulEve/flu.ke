"""Homepage artists link to their discography pages.

Each flagged homepage artist links to its own discography page — unless that page
would be empty (no published releases of their own and no published featured
credits), in which case the link points at the discography root instead. The
emptiness check must not scale its query count with the number of artists.
"""

import pytest

from apps.discography.models import Artist, Release, ReleaseType
from apps.frontend.views import _homepage_artists

pytestmark = pytest.mark.django_db


def _album():
    return ReleaseType.objects.create(name="Albums")


def test_artist_with_own_releases_links_to_their_page(client):
    fluke = Artist.objects.create(name="Fluke")
    yuki = Artist.objects.create(
        name="Yuki", slug="yuki", is_alias=True, primary_artist=fluke,
        appears_on_homepage=True,
    )
    Release.objects.create(
        name="Yuki LP", artist=yuki, type=_album(), year=2000, is_published=True
    )

    html = client.get("/").content.decode()

    assert f'href="{yuki.get_absolute_url()}"' in html   # /discography/yuki/
    assert ">Yuki</a>" in html


def test_artist_with_an_empty_page_links_to_the_discography_root(client):
    fluke = Artist.objects.create(name="Fluke")
    ghost = Artist.objects.create(
        name="Ghost", slug="ghost", is_alias=True, primary_artist=fluke,
        appears_on_homepage=True,
    )

    html = client.get("/").content.decode()

    # No releases and no features -> their page is empty -> link to the root.
    assert f'href="{ghost.get_absolute_url()}"' not in html
    assert '<a class="alias-link" href="/discography/">Ghost</a>' in html


def test_artist_with_only_a_featured_credit_links_to_their_page(client):
    fluke = Artist.objects.create(name="Fluke")
    guest = Artist.objects.create(
        name="Guest", slug="guest", is_alias=True, primary_artist=fluke,
        appears_on_homepage=True,
    )
    release = Release.objects.create(
        name="Collab", artist=fluke, type=_album(), year=1999, is_published=True
    )
    release.featured_artists.add(guest)

    html = client.get("/").content.decode()

    # Their page shows the featured release, so it isn't empty.
    assert f'href="{guest.get_absolute_url()}"' in html


def test_unpublished_releases_do_not_count_as_entries(client):
    fluke = Artist.objects.create(name="Fluke")
    draft = Artist.objects.create(
        name="Draft", slug="draft", is_alias=True, primary_artist=fluke,
        appears_on_homepage=True,
    )
    Release.objects.create(
        name="Hidden", artist=draft, type=_album(), year=2001, is_published=False
    )

    html = client.get("/").content.decode()

    assert '<a class="alias-link" href="/discography/">Draft</a>' in html


def test_emptiness_is_resolved_in_a_single_query(django_assert_num_queries):
    fluke = Artist.objects.create(name="Fluke")
    for i in range(6):
        Artist.objects.create(
            name=f"Alias {i}", slug=f"alias-{i}", is_alias=True,
            primary_artist=fluke, appears_on_homepage=True,
        )

    # One query for any number of artists — the per-artist link target is decided
    # by annotations, not a query per artist.
    with django_assert_num_queries(1):
        artists = _homepage_artists()
        _ = [a.hero_url for a in artists]
