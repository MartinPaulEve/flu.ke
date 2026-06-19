"""Discography pages carry schema.org structured data (JSON-LD + microdata)."""

import pytest

from apps.discography.models import Artist, Edition, Release, ReleaseType, Track

pytestmark = pytest.mark.django_db


@pytest.fixture
def release():
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    rt = ReleaseType.objects.create(name="Albums")
    rel = Release.objects.create(
        name="Risotto", slug="risotto", artist=fluke, type=rt, year=1997, is_published=True
    )
    ed = Edition.objects.create(release=rel, media="CD", catalogue_number="CIRCD20")
    Track.objects.create(edition=ed, name="Squelch", track_number="1", length="4:10")
    return rel


def test_release_page_has_musicalbum_jsonld_and_microdata(client, release):
    html = client.get(release.get_absolute_url()).content.decode()
    # JSON-LD
    assert '"@type": "MusicAlbum"' in html
    assert '"@type": "MusicRecording"' in html
    assert '"@type": "MusicRelease"' in html
    # microdata
    assert 'itemtype="https://schema.org/MusicAlbum"' in html
    assert 'itemprop="byArtist"' in html
    assert 'itemtype="https://schema.org/MusicRecording"' in html


def test_person_artist_uses_person_type(client):
    avery = Artist.objects.create(name="Daniel Avery", slug="daniel-avery", is_person=True)
    html = client.get(avery.get_absolute_url()).content.decode()
    assert '"@type": "Person"' in html
    assert 'itemtype="https://schema.org/Person"' in html


def test_group_artist_uses_musicgroup_type(client):
    fluke = Artist.objects.create(name="Fluke", slug="fluke")
    html = client.get(fluke.get_absolute_url()).content.decode()
    assert '"@type": "MusicGroup"' in html
    assert 'itemtype="https://schema.org/MusicGroup"' in html


def test_discography_index_has_collection_jsonld(client, release):
    html = client.get("/discography/").content.decode()
    assert '"@type": "CollectionPage"' in html
    assert '"@type": "ItemList"' in html
