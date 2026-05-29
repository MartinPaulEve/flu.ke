import pytest

from apps.resources.grouping import group_by_subcategory
from apps.resources.models import Resource, ResourceSubcategory

pytestmark = pytest.mark.django_db


def test_groups_ordered_by_subcategory_with_uncategorised_last():
    live = ResourceSubcategory.objects.create(name="Live Sets", display_order=1)
    mixes = ResourceSubcategory.objects.create(name="DJ Mixes", display_order=2)
    r_live = Resource.objects.create(title="Glastonbury 98", subcategory=live)
    r_mix = Resource.objects.create(title="Annie Nightingale", subcategory=mixes)
    r_none = Resource.objects.create(title="Loose file")

    groups = group_by_subcategory([r_none, r_mix, r_live])

    assert [g["subcategory"] for g in groups] == [live, mixes, None]
    assert groups[0]["resources"] == [r_live]
    assert groups[2]["resources"] == [r_none]


def test_preserves_input_order_within_a_group():
    sub = ResourceSubcategory.objects.create(name="Remixes", display_order=1)
    a = Resource.objects.create(title="A", subcategory=sub)
    b = Resource.objects.create(title="B", subcategory=sub)
    groups = group_by_subcategory([b, a])
    assert groups[0]["resources"] == [b, a]


def test_empty_input_returns_empty_list():
    assert group_by_subcategory([]) == []
