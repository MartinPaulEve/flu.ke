"""A release can credit multiple artists, shown comma-separated throughout.

The primary ``artist`` stays the canonical act (it drives the URL and grouping);
``additional_artists`` holds any co-credited acts. ``all_artists`` is the ordered,
de-duplicated set and ``artists_display`` the comma-joined names.
"""

import pytest
from rest_framework.test import APIClient

from apps.core.seo import music_album_jsonld
from apps.discography.models import Artist, Release, ReleaseType

pytestmark = pytest.mark.django_db


@pytest.fixture
def duo():
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    tcm = Artist.objects.create(name="The Crystal Method", slug="the-crystal-method")
    rtype = ReleaseType.objects.create(name="Singles")
    rel = Release.objects.create(
        name="Absurd Trip", artist=fluke, type=rtype, year=2013, is_published=True
    )
    rel.additional_artists.add(tcm)
    return {"fluke": fluke, "tcm": tcm, "rel": rel, "rtype": rtype}


# -- model ----------------------------------------------------------------


def test_all_artists_is_primary_then_additional(duo):
    assert [a.name for a in duo["rel"].all_artists] == ["Fluke", "The Crystal Method"]


def test_all_artists_dedups_primary_listed_again_as_additional(duo):
    duo["rel"].additional_artists.add(duo["fluke"])
    names = [a.name for a in duo["rel"].all_artists]
    assert names.count("Fluke") == 1


def test_artists_display_is_comma_joined(duo):
    assert duo["rel"].artists_display == "Fluke, The Crystal Method"


def test_display_title_lists_all_credited_artists(duo):
    assert duo["rel"].display_title == "Absurd Trip (Fluke, The Crystal Method)"


def test_display_title_still_omits_the_suffix_for_solo_fluke():
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    rel = Release.objects.create(name="Risotto", artist=fluke, type=rtype, year=1997)
    assert rel.display_title == "Risotto"


# -- rendered pages -------------------------------------------------------


def test_release_page_links_every_artist(client, duo):
    html = client.get(duo["rel"].get_absolute_url()).content.decode()
    assert f'href="{duo["fluke"].get_absolute_url()}"' in html
    assert f'href="{duo["tcm"].get_absolute_url()}"' in html
    assert "The Crystal Method" in html


def test_discography_index_shows_all_artists(client, duo):
    html = client.get("/discography/").content.decode()
    assert "Absurd Trip (Fluke, The Crystal Method)" in html


def test_release_appears_on_an_additional_artists_page(client, duo):
    html = client.get(duo["tcm"].get_absolute_url()).content.decode()
    assert "Absurd Trip" in html
    assert f'href="{duo["rel"].get_absolute_url()}"' in html


# -- API + JSON-LD --------------------------------------------------------


def test_api_release_detail_lists_all_artists(duo):
    resp = APIClient().get(f'/discography/api/releases/{duo["rel"].slug}/')
    assert resp.status_code == 200
    slugs = [a["slug"] for a in resp.json()["artists"]]
    assert slugs == ["fluke", "the-crystal-method"]


def test_jsonld_byartist_lists_all_artists(duo):
    data = music_album_jsonld(duo["rel"], "https://fluke.fm")
    names = [a["name"] for a in data["byArtist"]]
    assert names == ["Fluke", "The Crystal Method"]
