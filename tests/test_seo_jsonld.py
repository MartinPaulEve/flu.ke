import pytest
from django.utils import timezone

from apps.blog.models import Post
from apps.core.seo import blog_posting_jsonld, music_album_jsonld
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
    # byArtist is a list so a release can credit more than one artist.
    assert data["byArtist"] == [{"@type": "MusicGroup", "name": "Fluke"}]
    names = [t["name"] for t in data["track"]]
    assert "Squelch" in names
    assert "Bullet (Edit)" in names
    assert all(t["@type"] == "MusicRecording" for t in data["track"])
