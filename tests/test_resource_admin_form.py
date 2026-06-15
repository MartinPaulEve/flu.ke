"""The Resource admin form parses an imprecise 'recorded' value into date+precision."""

import datetime

import pytest

from apps.resources.forms import ResourceAdminForm
from apps.resources.models import Resource

pytestmark = pytest.mark.django_db


def _data(**over):
    data = {
        "title": "My Resource",
        "slug": "my-resource",
        "kind": "official",
        "snippet": "",
        "description": "",
        "contributor": "",
        "source_attribution": "",
        "license": "",
        "released_date": "",
        "uploaded_at": "2024-01-01 00:00:00",
        "external_url": "",
        "recorded": "",
        "seo_title": "",
        "meta_description": "",
        "canonical_url": "",
        "og_title": "",
        "og_description": "",
        "subcategory": "",
        "artist": "",
        "related_release": "",
        "related_edition": "",
        "related_post": "",
    }
    data.update(over)
    return data


@pytest.mark.parametrize(
    "text,expected_date,expected_precision",
    [
        ("2014", datetime.date(2014, 1, 1), "year"),
        ("2014-02", datetime.date(2014, 2, 1), "month"),
        ("2014-02-10", datetime.date(2014, 2, 10), "day"),
    ],
)
def test_recorded_value_sets_date_and_precision(text, expected_date, expected_precision):
    form = ResourceAdminForm(data=_data(recorded=text))
    assert form.is_valid(), form.errors
    resource = form.save()
    assert resource.recorded_date == expected_date
    assert resource.recorded_precision == expected_precision


def test_blank_recorded_clears_the_date():
    form = ResourceAdminForm(data=_data(recorded=""))
    assert form.is_valid(), form.errors
    resource = form.save()
    assert resource.recorded_date is None


def test_invalid_recorded_is_a_form_error():
    form = ResourceAdminForm(data=_data(recorded="not-a-date"))
    assert not form.is_valid()
    assert "recorded" in form.errors


def test_existing_value_is_shown_back_in_the_input():
    resource = Resource.objects.create(
        title="Old", kind="official",
        recorded_date=datetime.date(2014, 2, 1), recorded_precision="month",
    )
    form = ResourceAdminForm(instance=resource)
    assert form.fields["recorded"].initial == "2014-02"
