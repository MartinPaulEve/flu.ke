"""Purchase URL is available for any resource, not just print articles, and is
shown with type-neutral language."""

import pytest

from apps.resources.models import Resource

pytestmark = pytest.mark.django_db


def test_purchase_url_alone_is_not_print_metadata():
    """A purchase link on its own must not flag a resource as a print article."""
    r = Resource.objects.create(
        title="Boxed CD", kind="official", purchase_url="https://shop.example/cd"
    )
    assert r.has_print_metadata is False


def test_real_print_fields_still_count_as_print_metadata():
    r = Resource.objects.create(title="Interview", publication_title="Mixmag")
    assert r.has_print_metadata is True


def test_detail_shows_purchase_link_for_non_print_resource(client):
    r = Resource.objects.create(
        title="Boxed CD",
        kind="official",
        is_published=True,
        purchase_url="https://shop.example/cd",
    )
    html = client.get(r.get_absolute_url()).content.decode()
    assert 'href="https://shop.example/cd"' in html


def test_purchase_link_does_not_trigger_print_section(client):
    r = Resource.objects.create(
        title="Boxed CD",
        kind="official",
        is_published=True,
        purchase_url="https://shop.example/cd",
    )
    html = client.get(r.get_absolute_url()).content.decode()
    assert "Print article" not in html


def test_purchase_link_rendered_once_on_print_resource(client):
    """A print article that also has a purchase link shows that link exactly
    once (it is no longer duplicated inside the print block)."""
    r = Resource.objects.create(
        title="Interview",
        kind="official",
        is_published=True,
        publication_title="Mixmag",
        purchase_url="https://shop.example/issue",
    )
    html = client.get(r.get_absolute_url()).content.decode()
    assert html.count('href="https://shop.example/issue"') == 1
