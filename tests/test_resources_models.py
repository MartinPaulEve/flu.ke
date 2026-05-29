import pytest

from apps.resources.models import KIND_FAN, KIND_OFFICIAL, Resource

pytestmark = pytest.mark.django_db


def test_official_resource_url_includes_kind():
    r = Resource.objects.create(title="Atom Bomb promo", kind=KIND_OFFICIAL)
    assert r.get_absolute_url() == "/resources/official/atom-bomb-promo/"


def test_fan_resource_url_includes_kind():
    r = Resource.objects.create(title="JC Tosh Remix", kind=KIND_FAN)
    assert r.get_absolute_url() == "/resources/fan/jc-tosh-remix/"


def test_published_manager_excludes_drafts():
    Resource.objects.create(title="Live", is_published=True)
    Resource.objects.create(title="Draft", is_published=False)
    titles = set(Resource.objects.published().values_list("title", flat=True))
    assert titles == {"Live"}
