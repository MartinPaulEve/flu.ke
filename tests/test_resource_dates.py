"""Resources surface their content date (recorded, else released) prominently.

``display_date`` is the meaningful date for a resource: when it was *recorded*,
falling back to when it was *released* (``uploaded_at`` is site housekeeping, not
a content date). It drives the prominent date shown in the listing and on the page.
"""

import datetime

import pytest

from apps.resources.models import KIND_OFFICIAL, Resource, ResourceSubcategory

pytestmark = pytest.mark.django_db


def test_display_date_prefers_recorded_over_released():
    r = Resource(
        recorded_date=datetime.date(2014, 3, 14),
        released_date=datetime.date(2016, 1, 1),
    )
    assert r.display_date == datetime.date(2014, 3, 14)
    assert r.display_date_label == "Recorded"


def test_display_date_falls_back_to_released():
    r = Resource(released_date=datetime.date(2016, 1, 1))
    assert r.display_date == datetime.date(2016, 1, 1)
    assert r.display_date_label == "Released"


def test_display_date_is_none_without_recorded_or_released():
    r = Resource()
    assert r.display_date is None
    assert r.display_date_label == ""


def test_resource_list_shows_the_content_year_even_with_a_contributor(client):
    """An interview recorded in 2014 shows its year in the list, not hidden behind
    the contributor credit as it was before."""
    sub = ResourceSubcategory.objects.create(
        name="Interviews", kind=KIND_OFFICIAL, display_order=1
    )
    Resource.objects.create(
        title="Mixmag Interview",
        kind=KIND_OFFICIAL,
        subcategory=sub,
        contributor="Mixmag",
        recorded_date=datetime.date(2014, 3, 14),
        is_published=True,
    )

    html = client.get("/resources/").content.decode()

    assert "2014" in html


def test_resource_detail_shows_the_recorded_date(client):
    r = Resource.objects.create(
        title="Radio One Session",
        kind=KIND_OFFICIAL,
        recorded_date=datetime.date(2014, 3, 14),
        is_published=True,
    )

    html = client.get(r.get_absolute_url()).content.decode()

    assert "2014" in html
