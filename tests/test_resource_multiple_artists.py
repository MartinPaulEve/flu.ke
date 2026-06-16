"""A resource can credit multiple artists, shown wherever the artist appears."""

import pytest

from apps.discography.models import Artist, Release, ReleaseType
from apps.resources.models import KIND_FAN, KIND_OFFICIAL, Resource, build_snippet

pytestmark = pytest.mark.django_db


def _with_release(name, slug):
    artist = Artist.objects.create(name=name, slug=slug)
    rtype = ReleaseType.objects.create(name=f"T-{slug}")
    Release.objects.create(name=f"R-{slug}", artist=artist, type=rtype, year=2000, is_published=True)
    return artist


# -- model ----------------------------------------------------------------


def test_all_artists_is_primary_then_additional():
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    tcm = Artist.objects.create(name="The Crystal Method", slug="tcm")
    r = Resource.objects.create(title="Mashup", kind=KIND_FAN, artist=fluke)
    r.additional_artists.add(tcm)
    assert [a.name for a in r.all_artists] == ["Fluke", "The Crystal Method"]
    assert r.artists_display == "Fluke, The Crystal Method"


def test_all_artists_is_empty_without_any():
    r = Resource.objects.create(title="Anon", kind=KIND_OFFICIAL)
    assert r.all_artists == []


# -- snippet --------------------------------------------------------------


def test_build_snippet_lists_all_credited_artists():
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    tcm = Artist.objects.create(name="The Crystal Method", slug="tcm")
    r = Resource.objects.create(title="Mashup", kind=KIND_FAN, artist=fluke)
    r.additional_artists.add(tcm)
    assert "Fluke, The Crystal Method" in build_snippet(r)


# -- rendered pages -------------------------------------------------------


def test_detail_meta_bar_links_each_artist_per_page(client):
    fluke = _with_release("Fluke", "fluke")
    ghost = Artist.objects.create(name="Ghost", slug="ghost")  # empty page
    r = Resource.objects.create(
        title="A collab", kind=KIND_OFFICIAL, artist=fluke, is_published=True
    )
    r.additional_artists.add(ghost)

    html = client.get(r.get_absolute_url()).content.decode()

    assert f'href="{fluke.get_absolute_url()}"' in html   # linked (has a page)
    assert "Ghost" in html                                # shown
    assert f'href="{ghost.get_absolute_url()}"' not in html  # but not linked


def test_listing_snippet_links_each_credited_artist(client):
    fluke = _with_release("Fluke", "fluke")
    tcm = _with_release("The Crystal Method", "tcm")
    r = Resource.objects.create(
        title="A mashup", kind=KIND_FAN, artist=fluke, is_published=True
    )
    r.additional_artists.add(tcm)

    html = client.get("/resources/").content.decode()

    assert f'href="{fluke.get_absolute_url()}"' in html
    assert f'href="{tcm.get_absolute_url()}"' in html
    assert "The Crystal Method" in html
