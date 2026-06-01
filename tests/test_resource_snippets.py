"""Tests for the Resource snippet explanation field, its display, and seeding.

Covers:
- the model field exists and defaults to ""
- the ``build_snippet`` heuristic derives sensible text from metadata
- the ``seed_resource_snippets`` command fills empty snippets, is idempotent,
  respects --force and --dry-run
- the rendered /resources/ page surfaces a resource's snippet text
"""

import pytest

from apps.discography.models import Artist
from apps.resources.models import (
    KIND_FAN,
    KIND_OFFICIAL,
    Resource,
    ResourceFile,
    ResourceSubcategory,
    build_snippet,
)

pytestmark = pytest.mark.django_db


# -- the field ------------------------------------------------------------


def test_snippet_field_defaults_to_empty_string():
    r = Resource.objects.create(title="Atom Bomb promo", kind=KIND_OFFICIAL)
    r.refresh_from_db()
    assert r.snippet == ""


def test_snippet_field_stores_a_value():
    r = Resource.objects.create(
        title="Atom Bomb promo", kind=KIND_OFFICIAL, snippet="A hand written note"
    )
    r.refresh_from_db()
    assert r.snippet == "A hand written note"


# -- the build_snippet heuristic -----------------------------------------


def test_build_snippet_describes_official_archive_with_size():
    r = Resource.objects.create(title="Some live set", kind=KIND_OFFICIAL)
    ResourceFile.objects.create(
        resource=r, file="resources/x.zip", file_kind="archive", byte_size=120_000_000
    )
    snippet = build_snippet(r)
    assert "Official" in snippet
    assert "archive" in snippet.lower()
    # Exactly one file is described (e.g. "1 archive file").
    assert "1 " in snippet and "file" in snippet
    assert "files" not in snippet
    # Human readable size, ~114 MB for 120,000,000 bytes
    assert "MB" in snippet


def test_build_snippet_describes_fan_audio():
    r = Resource.objects.create(title="A remix", kind=KIND_FAN)
    ResourceFile.objects.create(
        resource=r, file="resources/x.mp3", file_kind="audio", byte_size=1_336_532
    )
    snippet = build_snippet(r)
    assert "Fan" in snippet
    assert "audio" in snippet.lower()


def test_build_snippet_credits_contributor_when_present():
    r = Resource.objects.create(
        title="mINDFLOWER pROMO EP", kind=KIND_FAN, contributor="jUSTIN cREDIBLE"
    )
    ResourceFile.objects.create(
        resource=r, file="resources/x.zip", file_kind="archive", byte_size=47_061_128
    )
    snippet = build_snippet(r)
    assert "jUSTIN cREDIBLE" in snippet
    assert snippet.lower().startswith("supplied by")


def test_build_snippet_includes_artist_when_present():
    artist = Artist.objects.create(name="Fluke")
    r = Resource.objects.create(title="Some thing", kind=KIND_OFFICIAL, artist=artist)
    ResourceFile.objects.create(
        resource=r, file="resources/x.mp3", file_kind="audio", byte_size=1_000_000
    )
    snippet = build_snippet(r)
    assert "Fluke" in snippet


def test_build_snippet_uses_source_attribution_when_present():
    r = Resource.objects.create(
        title="A rip", kind=KIND_OFFICIAL, source_attribution="ripped from vinyl"
    )
    ResourceFile.objects.create(
        resource=r, file="resources/x.mp3", file_kind="audio", byte_size=1_000_000
    )
    snippet = build_snippet(r)
    assert "ripped from vinyl" in snippet


def test_build_snippet_recognises_live_sets_from_title():
    r = Resource.objects.create(
        title="Fluke - Live at Tribal Gathering", kind=KIND_OFFICIAL
    )
    ResourceFile.objects.create(
        resource=r, file="resources/x.zip", file_kind="archive", byte_size=13_000_000
    )
    snippet = build_snippet(r)
    assert "live" in snippet.lower()


def test_build_snippet_never_invents_track_counts_for_archives():
    r = Resource.objects.create(title="An archive", kind=KIND_OFFICIAL)
    ResourceFile.objects.create(
        resource=r, file="resources/x.zip", file_kind="archive", byte_size=13_000_000
    )
    snippet = build_snippet(r)
    assert "track" not in snippet.lower()


def test_display_snippet_prefers_stored_snippet_over_fallback():
    r = Resource.objects.create(
        title="Has a snippet", kind=KIND_OFFICIAL, snippet="A curated description"
    )
    ResourceFile.objects.create(
        resource=r, file="resources/x.mp3", file_kind="audio", byte_size=1_000_000
    )
    assert r.display_snippet == "A curated description"


def test_display_snippet_falls_back_to_build_when_empty():
    r = Resource.objects.create(title="No snippet", kind=KIND_OFFICIAL)
    ResourceFile.objects.create(
        resource=r, file="resources/x.mp3", file_kind="audio", byte_size=1_000_000
    )
    assert r.display_snippet
    assert r.display_snippet == build_snippet(r)


# -- the seed command -----------------------------------------------------


def _run_seed(**kwargs):
    from django.core.management import call_command

    call_command("seed_resource_snippets", **kwargs)


def test_seed_fills_empty_snippet_from_metadata():
    r = Resource.objects.create(title="Some live set", kind=KIND_OFFICIAL)
    ResourceFile.objects.create(
        resource=r, file="resources/x.zip", file_kind="archive", byte_size=120_000_000
    )
    assert r.snippet == ""

    _run_seed()

    r.refresh_from_db()
    assert r.snippet != ""
    assert r.snippet == build_snippet(r)


def test_seed_is_idempotent_and_preserves_hand_set_snippets():
    r = Resource.objects.create(
        title="Curated", kind=KIND_OFFICIAL, snippet="A hand-written description"
    )
    ResourceFile.objects.create(
        resource=r, file="resources/x.mp3", file_kind="audio", byte_size=1_000_000
    )

    _run_seed()
    r.refresh_from_db()
    assert r.snippet == "A hand-written description"

    # Re-running must not change anything either.
    _run_seed()
    r.refresh_from_db()
    assert r.snippet == "A hand-written description"


def test_seed_force_overwrites_existing_snippets():
    r = Resource.objects.create(
        title="Curated", kind=KIND_OFFICIAL, snippet="An old description"
    )
    ResourceFile.objects.create(
        resource=r, file="resources/x.mp3", file_kind="audio", byte_size=1_000_000
    )

    _run_seed(force=True)
    r.refresh_from_db()
    assert r.snippet != "An old description"
    assert r.snippet == build_snippet(r)


def test_seed_dry_run_does_not_write():
    r = Resource.objects.create(title="Some live set", kind=KIND_OFFICIAL)
    ResourceFile.objects.create(
        resource=r, file="resources/x.zip", file_kind="archive", byte_size=120_000_000
    )

    _run_seed(dry_run=True)
    r.refresh_from_db()
    assert r.snippet == ""


# -- the rendered page ----------------------------------------------------


def test_resources_page_shows_snippet_text(client):
    sub = ResourceSubcategory.objects.create(
        name="Live Sets", kind=KIND_OFFICIAL, display_order=1
    )
    r = Resource.objects.create(
        title="Glastonbury 98",
        kind=KIND_OFFICIAL,
        subcategory=sub,
        is_published=True,
        snippet="Official live set captured at Glastonbury",
    )
    ResourceFile.objects.create(
        resource=r, file="resources/x.zip", file_kind="archive", byte_size=120_000_000
    )

    response = client.get("/resources/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "Official live set captured at Glastonbury" in html
