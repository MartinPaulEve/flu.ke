"""Resources list newest-first by their content date within each subcategory."""

import datetime

import pytest

from apps.resources.models import KIND_OFFICIAL, Resource, ResourceSubcategory

pytestmark = pytest.mark.django_db


def _positions(html, *titles):
    return [html.index(t) for t in titles]


def test_resources_are_listed_newest_content_date_first(client):
    sub = ResourceSubcategory.objects.create(
        name="Interviews", kind=KIND_OFFICIAL, display_order=1
    )
    # Created in an order that does NOT match their content dates, so a naive
    # upload-order sort would get it wrong.
    Resource.objects.create(
        title="Older 2010", kind=KIND_OFFICIAL, subcategory=sub,
        released_date=datetime.date(2010, 5, 1), is_published=True,
    )
    Resource.objects.create(
        title="Newest 2020", kind=KIND_OFFICIAL, subcategory=sub,
        released_date=datetime.date(2020, 5, 1), is_published=True,
    )
    Resource.objects.create(
        title="Middle 2015", kind=KIND_OFFICIAL, subcategory=sub,
        recorded_date=datetime.date(2015, 5, 1), is_published=True,
    )

    html = client.get("/resources/").content.decode()
    newest, middle, older = _positions(html, "Newest 2020", "Middle 2015", "Older 2010")

    assert newest < middle < older


def test_undated_resources_sort_after_dated_ones(client):
    sub = ResourceSubcategory.objects.create(
        name="Live", kind=KIND_OFFICIAL, display_order=1
    )
    Resource.objects.create(
        title="No date here", kind=KIND_OFFICIAL, subcategory=sub, is_published=True,
    )
    Resource.objects.create(
        title="Dated 2018", kind=KIND_OFFICIAL, subcategory=sub,
        released_date=datetime.date(2018, 1, 1), is_published=True,
    )

    html = client.get("/resources/").content.decode()
    dated, undated = _positions(html, "Dated 2018", "No date here")

    assert dated < undated
