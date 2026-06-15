"""Resources without a subcategory list under an 'Uncategorised' heading."""

import pytest

from apps.resources.models import KIND_OFFICIAL, Resource, ResourceSubcategory

pytestmark = pytest.mark.django_db


def test_uncategorised_resources_appear_under_an_uncategorised_heading(client):
    Resource.objects.create(title="Loose Track", kind=KIND_OFFICIAL, is_published=True)

    html = client.get("/resources/").content.decode()

    assert "Uncategorised" in html
    assert "Loose Track" in html


def test_no_uncategorised_heading_when_everything_is_categorised(client):
    sub = ResourceSubcategory.objects.create(name="Live Sets", kind=KIND_OFFICIAL)
    Resource.objects.create(
        title="A Set", kind=KIND_OFFICIAL, subcategory=sub, is_published=True
    )

    html = client.get("/resources/").content.decode()

    assert "Uncategorised" not in html
