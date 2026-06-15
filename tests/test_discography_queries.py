"""linkable_artist_ids: which artists have a non-empty discography page."""

import pytest

from apps.discography.models import Artist, Release, ReleaseType
from apps.discography.queries import linkable_artist_ids

pytestmark = pytest.mark.django_db


@pytest.fixture
def cast():
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    with_own = Artist.objects.create(name="Owner", slug="owner")
    Release.objects.create(
        name="Owned", artist=with_own, type=rtype, year=2000, is_published=True
    )
    with_feature = Artist.objects.create(name="Guest", slug="guest")
    feat = Release.objects.create(
        name="Collab", artist=fluke, type=rtype, year=2001, is_published=True
    )
    feat.featured_artists.add(with_feature)
    empty = Artist.objects.create(name="Ghost", slug="ghost")
    return {"with_own": with_own, "with_feature": with_feature, "empty": empty}


def test_includes_artists_with_their_own_release(cast):
    ids = linkable_artist_ids([cast["with_own"].id])
    assert cast["with_own"].id in ids


def test_includes_artists_with_only_a_featured_credit(cast):
    ids = linkable_artist_ids([cast["with_feature"].id])
    assert cast["with_feature"].id in ids


def test_excludes_artists_whose_page_is_empty(cast):
    ids = linkable_artist_ids([cast["empty"].id])
    assert ids == set()


def test_empty_input_makes_no_query(django_assert_num_queries):
    with django_assert_num_queries(0):
        assert linkable_artist_ids([]) == set()
        assert linkable_artist_ids([None]) == set()


def test_resolves_many_artists_in_one_query(cast, django_assert_num_queries):
    all_ids = [cast["with_own"].id, cast["with_feature"].id, cast["empty"].id]
    with django_assert_num_queries(1):
        ids = linkable_artist_ids(all_ids)
    assert ids == {cast["with_own"].id, cast["with_feature"].id}
