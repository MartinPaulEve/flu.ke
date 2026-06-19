"""A 'Purchase' link shows on the edition summary line when a purchase URL is set."""

import pytest

from apps.discography.models import Artist, Edition, Release, ReleaseType

pytestmark = pytest.mark.django_db


def _edition(purchase_link=""):
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    rt = ReleaseType.objects.create(name="Singles")
    rel = Release.objects.create(
        name="Atom Bomb", slug="atom-bomb", artist=fluke, type=rt, year=2026, is_published=True
    )
    Edition.objects.create(release=rel, media="CD", purchase_link=purchase_link)
    return rel


def test_purchase_link_shown_when_set(client):
    rel = _edition(purchase_link="https://store.example.com/atom-bomb")
    html = client.get(rel.get_absolute_url()).content.decode()
    assert 'href="https://store.example.com/atom-bomb"' in html
    assert ">Purchase</a>" in html


def test_no_purchase_link_when_unset(client):
    rel = _edition()
    html = client.get(rel.get_absolute_url()).content.decode()
    assert 'class="edition__buy"' not in html  # no rendered Purchase link
