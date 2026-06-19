import pytest
from django.utils import timezone

from apps.blog.models import Post
from apps.core.seo import (
    blog_posting_jsonld,
    discography_jsonld,
    music_album_jsonld,
    music_group_jsonld,
)
from apps.discography.models import Artist, Edition, Release, ReleaseType, Track

pytestmark = pytest.mark.django_db

BASE = "https://fluke.fm"


def test_blog_posting_jsonld():
    when = timezone.make_aware(timezone.datetime(2009, 6, 17, 7, 8))
    post = Post.objects.create(title="Dark Like Snow", published_at=when, meta_description="Out now")
    data = blog_posting_jsonld(post, BASE)
    assert data["@type"] == "BlogPosting"
    assert data["headline"] == "Dark Like Snow"
    assert data["url"] == f"{BASE}{post.get_absolute_url()}"
    assert data["datePublished"].startswith("2009-06-17")
    assert data["description"] == "Out now"


def test_music_album_jsonld_includes_artist_and_tracks():
    fluke = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    release = Release.objects.create(name="Risotto", artist=fluke, type=rtype, year=1997)
    edition = Edition.objects.create(release=release, media="CD")
    Track.objects.create(edition=edition, track_number="01", name="Squelch")
    Track.objects.create(edition=edition, track_number="02", name="Bullet", mix_info="Edit")

    data = music_album_jsonld(release, BASE)
    assert data["@type"] == "MusicAlbum"
    assert data["name"] == "Risotto"
    assert data["datePublished"] == "1997"
    # byArtist nodes are typed and carry a URL to the artist page.
    assert data["byArtist"] == [
        {"@type": "MusicGroup", "name": "Fluke", "url": f"{BASE}{fluke.get_absolute_url()}"}
    ]
    names = [t["name"] for t in data["track"]]
    assert "Squelch" in names
    assert "Bullet (Edit)" in names
    assert all(t["@type"] == "MusicRecording" for t in data["track"])
    assert data["numTracks"] == 2
    # tracks credit the album artist
    assert data["track"][0]["byArtist"] == data["byArtist"]


def test_music_album_jsonld_editions_durations_remixers_and_person():
    avery = Artist.objects.create(name="Daniel Avery", is_person=True)
    fluke = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Singles")
    release = Release.objects.create(name="Atom Bomb", artist=fluke, type=rtype, year=2026)
    edition = Edition.objects.create(
        release=release, media='12" Vinyl', catalogue_number="SR1", record_label="Surface", year=2026
    )
    track = Track.objects.create(edition=edition, track_number="1", name="Atom Bomb", length="3:16")
    track.remixers.add(avery)

    data = music_album_jsonld(release, BASE)
    # an edition becomes a MusicRelease with format/catalogue/label/date
    rel = data["albumRelease"][0]
    assert rel["@type"] == "MusicRelease"
    assert rel["musicReleaseFormat"] == "https://schema.org/VinylFormat"
    assert rel["catalogNumber"] == "SR1"
    assert rel["recordLabel"] == {"@type": "Organization", "name": "Surface"}
    # track duration is ISO 8601; remixer is a typed contributor (a Person here)
    t = data["track"][0]
    assert t["duration"] == "PT3M16S"
    assert t["contributor"] == [
        {"@type": "Person", "name": "Daniel Avery", "url": f"{BASE}{avery.get_absolute_url()}"}
    ]


def test_music_group_jsonld_for_person_alias():
    fluke = Artist.objects.create(name="Fluke")
    yuki = Artist.objects.create(
        name="Yuki", is_alias=True, primary_artist=fluke, is_person=True
    )
    rtype = ReleaseType.objects.create(name="Albums")
    rel = Release.objects.create(name="Yuki LP", artist=yuki, type=rtype, year=2000)

    data = music_group_jsonld(yuki, [rel], BASE)
    assert data["@type"] == "Person"
    assert data["name"] == "Yuki"
    assert data["url"] == f"{BASE}{yuki.get_absolute_url()}"
    assert data["memberOf"]["name"] == "Fluke"
    assert data["album"] == [
        {"@type": "MusicAlbum", "name": "Yuki LP", "url": f"{BASE}{rel.get_absolute_url()}"}
    ]


def test_discography_jsonld_is_an_item_list():
    fluke = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    r1 = Release.objects.create(name="Risotto", artist=fluke, type=rtype, year=1997)

    data = discography_jsonld([r1], BASE)
    assert data["@type"] == "CollectionPage"
    items = data["mainEntity"]["itemListElement"]
    assert items[0]["@type"] == "ListItem"
    assert items[0]["position"] == 1
    assert items[0]["url"] == f"{BASE}{r1.get_absolute_url()}"
