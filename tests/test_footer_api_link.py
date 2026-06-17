"""The footer's API link points at the API entry for the item on the page (a
release, artist or lyric), or the API root on pages with no specific entry."""

import pytest
from django.utils import timezone

from apps.blog.models import Post
from apps.discography.models import Artist, Lyric, Release, ReleaseType
from apps.pages.models import Page
from apps.resources.models import KIND_OFFICIAL, Resource

pytestmark = pytest.mark.django_db


def test_release_page_footer_links_to_its_api_entry(client):
    fluke = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    release = Release.objects.create(
        name="Risotto", artist=fluke, type=rtype, year=1997, is_published=True
    )
    response = client.get(release.get_absolute_url())
    assert response.status_code == 200
    html = response.content.decode()
    assert f'href="/api/discography/releases/{release.slug}/"' in html


def test_artist_page_footer_links_to_its_api_entry(client):
    artist = Artist.objects.create(name="Syntax")
    response = client.get(artist.get_absolute_url())
    assert response.status_code == 200
    html = response.content.decode()
    assert f'href="/api/discography/artists/{artist.slug}/"' in html


def test_lyric_page_footer_links_to_its_api_entry(client):
    fluke = Artist.objects.create(name="Fluke")
    lyric = Lyric.objects.create(title="You Got Me", artist=fluke, lyrics="words")
    response = client.get(lyric.get_absolute_url())
    assert response.status_code == 200
    html = response.content.decode()
    assert f'href="/api/discography/lyrics/{lyric.slug}/"' in html


def test_resource_page_footer_links_to_its_api_entry(client):
    resource = Resource.objects.create(
        title="Live Set", slug="live-set", kind=KIND_OFFICIAL, is_published=True
    )
    html = client.get(resource.get_absolute_url()).content.decode()
    assert 'href="/api/resources/live-set/"' in html


def test_resources_index_footer_links_to_the_resources_collection(client):
    html = client.get("/resources/").content.decode()
    assert 'href="/api/resources/"' in html


def test_page_footer_links_to_its_api_entry(client):
    page = Page.objects.create(title="About", slug="about", body="hi", is_published=True)
    html = client.get(page.get_absolute_url()).content.decode()
    assert 'href="/api/pages/about/"' in html


def test_post_page_footer_links_to_its_api_entry(client):
    post = Post.objects.create(
        title="A find", slug="a-find", body="x", is_published=True,
        published_at=timezone.now(),
    )
    html = client.get(post.get_absolute_url()).content.decode()
    assert 'href="/api/news/a-find/"' in html


def test_page_without_a_specific_entry_falls_back_to_the_api_root(client):
    # The homepage has no single API object, so it links to the API root.
    response = client.get("/")
    assert response.status_code == 200
    html = response.content.decode()
    assert 'href="/api/"' in html
