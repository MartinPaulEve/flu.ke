"""End-to-end test that the resources index renders kinds and subcategory groups."""

import pytest

from apps.resources.models import Resource, ResourceSubcategory

pytestmark = pytest.mark.django_db


def test_resources_page_groups_by_kind_and_subcategory(client):
    live = ResourceSubcategory.objects.create(name="Live Sets", kind="official", display_order=1)
    Resource.objects.create(
        title="Glastonbury 98", kind="official", subcategory=live, is_published=True
    )
    Resource.objects.create(
        title="JC Tosh Remix", kind="fan", contributor="JC", is_published=True
    )
    Resource.objects.create(title="Hidden draft", kind="fan", is_published=False)

    response = client.get("/resources/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "Official Resources" in html
    assert "Fan Remixes &amp; Resources" in html  # autoescaped ampersand
    assert "Live Sets" in html  # subcategory heading
    assert "Glastonbury 98" in html
    assert "JC Tosh Remix" in html
    assert "Hidden draft" not in html  # drafts excluded
