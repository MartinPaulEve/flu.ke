"""Behavioural tests for the read-only discography REST API.

These exercise the public contract of the API — status codes, response
shape (paginated lists, nested detail), filtering/search results and the
read-only guarantee — rather than any particular implementation. Only
published releases (and their editions/tracks/covers) should be exposed.
"""

import pytest
from rest_framework.test import APIClient

from apps.discography.models import (
    Artist,
    Edition,
    Lyric,
    Release,
    ReleaseType,
    Track,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def discography():
    """Seed a small but representative slice of the discography.

    A published Fluke release with one edition, one track and a lyric, plus
    an unpublished release that must never leak through the public API.
    """
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

    unpublished = Release.objects.create(
        name="Lost Tape",
        artist=fluke,
        type=album,
        year=2099,
        is_published=False,
    )

    return {
        "fluke": fluke,
        "album": album,
        "published": published,
        "edition": edition,
        "lyric": lyric,
        "track": track,
        "unpublished": unpublished,
    }


# --- Releases list: pagination + published-only ----------------------------

def test_releases_list_is_paginated_and_excludes_unpublished(client, discography):
    resp = client.get("/discography/api/releases/")
    assert resp.status_code == 200

    body = resp.json()
    assert "results" in body  # PageNumberPagination envelope

    slugs = {item["slug"] for item in body["results"]}
    assert discography["published"].slug in slugs
    assert discography["unpublished"].slug not in slugs


# --- Release detail: nested editions -> tracks ------------------------------

def test_release_detail_nests_editions_and_tracks(client, discography):
    release = discography["published"]
    resp = client.get(f"/discography/api/releases/{release.slug}/")
    assert resp.status_code == 200

    body = resp.json()
    assert body["slug"] == release.slug
    assert "editions" in body
    assert len(body["editions"]) == 1

    edition = body["editions"][0]
    assert "tracks" in edition
    track_names = {t["name"] for t in edition["tracks"]}
    assert discography["track"].name in track_names


def test_release_detail_404_for_unpublished(client, discography):
    resp = client.get(f"/discography/api/releases/{discography['unpublished'].slug}/")
    assert resp.status_code == 404


# --- Filtering --------------------------------------------------------------

def test_releases_filter_by_artist_slug(client, discography):
    resp = client.get(f"/discography/api/releases/?artist={discography['fluke'].slug}")
    assert resp.status_code == 200
    slugs = {item["slug"] for item in resp.json()["results"]}
    assert discography["published"].slug in slugs


def test_releases_filter_by_artist_slug_no_match_is_empty(client, discography):
    resp = client.get("/discography/api/releases/?artist=no-such-artist")
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_releases_filter_by_year(client, discography):
    resp = client.get("/discography/api/releases/?year=1997")
    assert resp.status_code == 200
    slugs = {item["slug"] for item in resp.json()["results"]}
    assert discography["published"].slug in slugs


def test_releases_filter_by_year_no_match_is_empty(client, discography):
    resp = client.get("/discography/api/releases/?year=1066")
    assert resp.status_code == 200
    assert resp.json()["results"] == []


# --- Artists ----------------------------------------------------------------

def test_artist_detail_by_slug(client, discography):
    resp = client.get(f"/discography/api/artists/{discography['fluke'].slug}/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == discography["fluke"].slug
    assert body["name"] == "Fluke"


# --- Lyrics -----------------------------------------------------------------

def test_lyric_detail_by_slug_includes_text(client, discography):
    lyric = discography["lyric"]
    resp = client.get(f"/discography/api/lyrics/{lyric.slug}/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == lyric.slug
    assert body["lyrics"] == "These are the lyrics to Tosh."


# --- Tracks search ----------------------------------------------------------

def test_tracks_search_returns_matching_track(client, discography):
    resp = client.get("/discography/api/tracks/?search=Tosh")
    assert resp.status_code == 200
    names = {item["name"] for item in resp.json()["results"]}
    assert discography["track"].name in names


# --- Read-only guarantee ----------------------------------------------------

def test_releases_post_is_not_allowed(client, discography):
    resp = client.post("/discography/api/releases/", {"name": "Hacked"}, format="json")
    assert resp.status_code == 405


# --- OpenAPI schema + Swagger UI --------------------------------------------

def test_openapi_schema_is_served(client):
    resp = client.get("/discography/api/schema/")
    assert resp.status_code == 200


def test_openapi_schema_advertises_no_authentication(client):
    """The public, read-only API must not present itself as requiring login.

    drf-spectacular derives ``securitySchemes`` from the authentication classes;
    if any are declared, Swagger/ReDoc render an "Authorize" control that makes
    the open API look gated. An open API advertises no security schemes.
    """
    import yaml

    resp = client.get("/discography/api/schema/")
    doc = yaml.safe_load(resp.content.decode())

    # No security schemes => Swagger/ReDoc render no "Authorize" control.
    assert not doc.get("components", {}).get("securitySchemes")
    # No operation may demand a named scheme; an empty requirement ({}) is the
    # OpenAPI way of saying "anonymous access is allowed", which is fine.
    for methods in doc.get("paths", {}).values():
        for operation in methods.values():
            if isinstance(operation, dict):
                for requirement in operation.get("security", []):
                    assert requirement == {}


def test_swagger_ui_is_served(client):
    resp = client.get("/discography/api/docs/")
    assert resp.status_code == 200
    assert "swagger" in resp.content.decode().lower()


# --- Browsable API root description -----------------------------------------

def test_api_root_is_served(client):
    resp = client.get("/discography/api/")
    assert resp.status_code == 200


def test_api_root_has_descriptive_text_not_default(client):
    resp = client.get(
        "/discography/api/", HTTP_ACCEPT="text/html"
    )
    assert resp.status_code == 200

    html = resp.content.decode()
    assert "The default basic root view" not in html
    assert "Fluke discography API" in html
