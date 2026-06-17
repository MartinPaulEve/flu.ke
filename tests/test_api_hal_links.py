"""Behavioural tests for HATEOAS / HAL ``_links`` in the discography API.

Every serialized object should expose a top-level ``_links`` dict whose values
are link objects of the form ``{"href": <absolute url>, "type": <media type>}``.
These tests exercise the public contract (absolute URLs, self/alternate and
relationship back-links) rather than any particular implementation.
"""

import pytest
from rest_framework.test import APIClient

from apps.discography.models import (
    Artist,
    CoverImage,
    Edition,
    Lyric,
    Release,
    ReleaseType,
    Track,
)

pytestmark = pytest.mark.django_db

HAL = "application/hal+json"
HTML = "text/html"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def discography():
    """A published Fluke release with edition, track (+ lyric) and a cover."""
    fluke = Artist.objects.create(name="Fluke")
    album = ReleaseType.objects.create(name="Album", display_order=1)

    published = Release.objects.create(
        name="Risotto",
        artist=fluke,
        type=album,
        year=1997,
        is_published=True,
    )
    edition = Edition.objects.create(release=published, name="UK CD", media="CD")
    lyric = Lyric.objects.create(
        title="Tosh",
        artist=fluke,
        lyrics="These are the lyrics to Tosh.",
    )
    track = Track.objects.create(
        edition=edition,
        name="Tosh",
        track_number="1",
        length="5:30",
        lyric=lyric,
    )
    cover = CoverImage.objects.create(
        edition=edition,
        display_name="Front cover",
        kind="front",
    )

    return {
        "fluke": fluke,
        "album": album,
        "published": published,
        "edition": edition,
        "lyric": lyric,
        "track": track,
        "cover": cover,
    }


def _assert_absolute(href):
    assert href.startswith("http://") or href.startswith("https://"), href


# --- Collection links (RFC 6573 'collection' rel) ---------------------------

def test_objects_link_to_their_collection(client, discography):
    """Every object carries a 'collection' link to its own list endpoint, so a
    client can navigate from any item up to the full list."""
    body = client.get(f"/discography/api/releases/{discography['published'].slug}/").json()

    release_coll = body["_links"]["collection"]
    _assert_absolute(release_coll["href"])
    assert release_coll["href"].endswith("/discography/api/releases/")
    assert release_coll["type"] == "application/hal+json"

    edition = body["editions"][0]
    assert edition["_links"]["collection"]["href"].endswith("/discography/api/editions/")

    track = edition["tracks"][0]
    assert track["_links"]["collection"]["href"].endswith("/discography/api/tracks/")

    cover = edition["covers"][0]
    assert cover["_links"]["collection"]["href"].endswith("/discography/api/cover-images/")


def test_artist_and_lyric_link_to_their_collections(client, discography):
    artist = client.get(f"/discography/api/artists/{discography['fluke'].slug}/").json()
    assert artist["_links"]["collection"]["href"].endswith("/discography/api/artists/")

    lyric = client.get(f"/discography/api/lyrics/{discography['lyric'].slug}/").json()
    assert lyric["_links"]["collection"]["href"].endswith("/discography/api/lyrics/")


# --- Release detail tree ----------------------------------------------------


def test_release_detail_has_self_and_alternate_links(client, discography):
    release = discography["published"]
    body = client.get(f"/discography/api/releases/{release.slug}/").json()

    links = body["_links"]
    _assert_absolute(links["self"]["href"])
    assert links["self"]["href"].endswith(
        f"/discography/api/releases/{release.slug}/"
    )
    assert links["self"]["type"] == HAL

    _assert_absolute(links["alternate"]["href"])
    assert links["alternate"]["href"].endswith(release.get_absolute_url())
    assert links["alternate"]["type"] == HTML


def test_nested_edition_has_self_and_release_backlink(client, discography):
    release = discography["published"]
    edition = discography["edition"]
    body = client.get(f"/discography/api/releases/{release.slug}/").json()

    ed = body["editions"][0]
    links = ed["_links"]
    _assert_absolute(links["self"]["href"])
    assert links["self"]["href"].endswith(
        f"/discography/api/editions/{edition.id}/"
    )
    assert links["self"]["type"] == HAL

    _assert_absolute(links["release"]["href"])
    assert links["release"]["href"].endswith(
        f"/discography/api/releases/{release.slug}/"
    )
    assert links["release"]["type"] == HAL


def test_nested_track_has_self_edition_and_lyric_links(client, discography):
    release = discography["published"]
    edition = discography["edition"]
    track = discography["track"]
    lyric = discography["lyric"]
    body = client.get(f"/discography/api/releases/{release.slug}/").json()

    tr = body["editions"][0]["tracks"][0]
    links = tr["_links"]
    _assert_absolute(links["self"]["href"])
    assert links["self"]["href"].endswith(f"/discography/api/tracks/{track.id}/")
    assert links["self"]["type"] == HAL

    assert links["edition"]["href"].endswith(
        f"/discography/api/editions/{edition.id}/"
    )
    assert links["edition"]["type"] == HAL

    assert links["lyric"]["href"].endswith(
        f"/discography/api/lyrics/{lyric.slug}/"
    )
    assert links["lyric"]["type"] == HAL


def test_nested_cover_has_self_and_edition_link(client, discography):
    release = discography["published"]
    edition = discography["edition"]
    cover = discography["cover"]
    body = client.get(f"/discography/api/releases/{release.slug}/").json()

    cv = body["editions"][0]["covers"][0]
    links = cv["_links"]
    _assert_absolute(links["self"]["href"])
    assert links["self"]["href"].endswith(
        f"/discography/api/cover-images/{cover.id}/"
    )
    assert links["self"]["type"] == HAL

    assert links["edition"]["href"].endswith(
        f"/discography/api/editions/{edition.id}/"
    )
    assert links["edition"]["type"] == HAL


# --- Track without a lyric omits the lyric link -----------------------------


def test_track_without_lyric_omits_lyric_link(client, discography):
    track = discography["track"]
    track.lyric = None
    track.save()

    body = client.get(f"/discography/api/tracks/{track.id}/").json()
    links = body["_links"]
    assert "lyric" not in links
    assert links["self"]["type"] == HAL
    assert links["edition"]["href"].endswith(
        f"/discography/api/editions/{discography['edition'].id}/"
    )


# --- Artist / lyric detail --------------------------------------------------


def test_artist_detail_has_self_and_alternate(client, discography):
    fluke = discography["fluke"]
    body = client.get(f"/discography/api/artists/{fluke.slug}/").json()

    links = body["_links"]
    _assert_absolute(links["self"]["href"])
    assert links["self"]["href"].endswith(f"/discography/api/artists/{fluke.slug}/")
    assert links["self"]["type"] == HAL

    _assert_absolute(links["alternate"]["href"])
    assert links["alternate"]["href"].endswith(fluke.get_absolute_url())
    assert links["alternate"]["type"] == HTML


def test_lyric_detail_has_self_and_alternate(client, discography):
    lyric = discography["lyric"]
    body = client.get(f"/discography/api/lyrics/{lyric.slug}/").json()

    links = body["_links"]
    _assert_absolute(links["self"]["href"])
    assert links["self"]["href"].endswith(f"/discography/api/lyrics/{lyric.slug}/")
    assert links["self"]["type"] == HAL

    _assert_absolute(links["alternate"]["href"])
    assert links["alternate"]["href"].endswith(lyric.get_absolute_url())
    assert links["alternate"]["type"] == HTML


# --- Release-type detail (pk lookup, no alternate) --------------------------


def test_release_type_detail_has_self_only(client, discography):
    rt = discography["album"]
    body = client.get(f"/discography/api/release-types/{rt.id}/").json()

    links = body["_links"]
    assert links["self"]["href"].endswith(
        f"/discography/api/release-types/{rt.id}/"
    )
    assert links["self"]["type"] == HAL
    assert "alternate" not in links
