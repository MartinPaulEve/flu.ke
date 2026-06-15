"""Reusable discography queries shared across the site."""

from __future__ import annotations

from django.db.models import Exists, OuterRef

from .models import Artist, Release


def linkable_artist_ids(artist_ids) -> set[int]:
    """Return the subset of ``artist_ids`` whose discography page isn't empty.

    An artist's page is "linkable" when they have a published release of their
    own or a published featured credit (the same emptiness rule the homepage
    uses). Resolved in a single query; an empty/all-falsy input returns an empty
    set without touching the database.
    """
    ids = {i for i in artist_ids if i}
    if not ids:
        return set()
    own = Release.objects.filter(artist=OuterRef("pk"), is_published=True)
    featured = Release.objects.filter(featured_artists=OuterRef("pk"), is_published=True)
    return set(
        Artist.objects.filter(pk__in=ids)
        .filter(Exists(own) | Exists(featured))
        .values_list("pk", flat=True)
    )
