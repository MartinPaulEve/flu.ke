"""Behavioural tests for the live public site served by ``apps.frontend``.

These exercise the HTTP behaviour of every public page type via the Django test
client: published content returns 200 with its key content present, drafts and
missing content 404, and the news-category page lists its posts. We assert on
status and on content presence/absence, not on the view internals.
"""

import pytest
from django.utils import timezone

from apps.blog.models import Category, Post
from apps.discography.models import Artist, Lyric, Release, ReleaseType
from apps.pages.models import Page
from apps.resources.models import KIND_FAN, KIND_OFFICIAL, Resource

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded():
    """Minimal published + draft content covering every public page type."""
    fluke = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    release = Release.objects.create(
        name="Risotto", artist=fluke, type=rtype, year=1997, is_published=True
    )
    draft_release = Release.objects.create(
        name="Hidden Record", artist=fluke, type=rtype, year=2000, is_published=False
    )

    category = Category.objects.create(name="Releases")
    post = Post.objects.create(
        title="Hello World", excerpt="An announcement", is_published=True,
        published_at=timezone.now(),
    )
    post.categories.add(category)
    draft_post = Post.objects.create(title="Draft Post", is_published=False)

    official = Resource.objects.create(
        title="Live Set", kind=KIND_OFFICIAL, is_published=True
    )
    fan = Resource.objects.create(title="Fan Remix", kind=KIND_FAN, is_published=True)
    draft_resource = Resource.objects.create(
        title="Hidden Resource", kind=KIND_FAN, is_published=False
    )

    page = Page.objects.create(title="About", body="All about us", is_published=True)
    draft_page = Page.objects.create(title="Secret Draft", is_published=False)

    lyric = Lyric.objects.create(
        title="You Got Me", artist=fluke, lyrics="You got me, baby"
    )
    bodyless = Lyric.objects.create(title="Empty One", artist=fluke, lyrics="")

    return {
        "fluke": fluke,
        "rtype": rtype,
        "release": release,
        "draft_release": draft_release,
        "category": category,
        "post": post,
        "draft_post": draft_post,
        "official": official,
        "fan": fan,
        "draft_resource": draft_resource,
        "page": page,
        "draft_page": draft_page,
        "lyric": lyric,
        "bodyless": bodyless,
    }


def test_landing_page_renders_recent_posts_and_resources(client, seeded):
    response = client.get("/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "Hello World" in body
    assert "Live Set" in body


@pytest.fixture
def homepage_artists():
    """Fluke (primary, unflagged) plus flagged and unflagged other artists."""
    fluke = Artist.objects.create(name="Fluke", appears_on_homepage=False)
    syntax = Artist.objects.create(
        name="Syntax", is_alias=True, primary_artist=fluke, appears_on_homepage=True
    )
    yuki = Artist.objects.create(
        name="Yuki", is_alias=True, primary_artist=fluke, appears_on_homepage=True
    )
    fatal = Artist.objects.create(
        name="Fatal", is_alias=True, primary_artist=fluke, appears_on_homepage=True
    )
    hidden = Artist.objects.create(
        name="Hidden Project", is_alias=True, primary_artist=fluke,
        appears_on_homepage=False,
    )
    return {
        "fluke": fluke,
        "syntax": syntax,
        "yuki": yuki,
        "fatal": fatal,
        "hidden": hidden,
    }


def test_hero_lists_flagged_other_artists(client, homepage_artists):
    response = client.get("/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "Fatal" in body
    assert "Syntax" in body
    assert "Yuki" in body


def test_hero_excludes_unflagged_artists(client, homepage_artists):
    response = client.get("/")
    body = response.content.decode()
    assert "Hidden Project" not in body


def test_hero_does_not_list_fluke_among_aliases(client, homepage_artists):
    """Fluke is the subject ("Everything Fluke"), not an item in the alias list."""
    response = client.get("/")
    body = response.content.decode()
    # The alias list ends with " & <last name>"; Fluke must not be the join tail
    # nor appear in the comma-separated alias enumeration.
    assert "& Fluke" not in body
    assert ", Fluke" not in body
    # Fluke is still the lead subject.
    assert "Everything Fluke" in body


def test_hero_joins_with_ampersand_before_last_name(client, homepage_artists):
    """Flagged others ordered by name: Fatal, Syntax, Yuki -> "Fatal, Syntax & Yuki",
    each name now a link. Django autoescapes the ampersand, so it appears as ``&amp;``.
    """
    response = client.get("/")
    body = response.content.decode()
    assert ">Fatal</a>, <a" in body           # comma between non-final names
    assert ">Syntax</a> &amp; <a" in body      # ampersand before the final name
    assert ">Yuki</a>" in body


def test_hero_uses_aliases_and_other_projects_wording(client, homepage_artists):
    response = client.get("/")
    body = response.content.decode()
    assert "aliases and other projects" in body


def test_hero_second_sentence_has_four_destination_links(client, homepage_artists):
    response = client.get("/")
    body = response.content.decode()
    assert 'href="/news/"' in body
    assert 'href="/discography/"' in body
    assert 'href="/resources/#official"' in body
    assert 'href="/resources/#fan"' in body


def test_footer_links_to_discography_api(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.content.decode()
    assert 'href="/discography/api/"' in body
    assert "Discography API" in body


def test_news_list_shows_published_posts_only(client, seeded):
    response = client.get("/news/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "Hello World" in body
    assert "Draft Post" not in body


def test_post_detail_returns_200_for_published(client, seeded):
    response = client.get(seeded["post"].get_absolute_url())
    assert response.status_code == 200
    body = response.content.decode()
    assert "Hello World" in body
    # post_detail template embeds JSON-LD from the view context.
    assert "application/ld+json" in body
    assert "BlogPosting" in body


def test_post_detail_404_for_draft(client, seeded):
    response = client.get(seeded["draft_post"].get_absolute_url())
    assert response.status_code == 404


def test_news_category_lists_its_published_posts(client, seeded):
    response = client.get(seeded["category"].get_absolute_url())
    assert response.status_code == 200
    body = response.content.decode()
    assert "Hello World" in body
    assert "Draft Post" not in body


def test_news_category_404_for_unknown_slug(client, seeded):
    response = client.get("/news/category/does-not-exist/")
    assert response.status_code == 404


def test_discography_index_lists_published_release(client, seeded):
    response = client.get("/discography/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "Risotto" in body
    assert "Hidden Record" not in body
    # has_lyrics is True (a lyric has a body), so the lyrics link shows.
    assert "/lyrics/" in body


def test_artist_detail_returns_200(client, seeded):
    response = client.get(seeded["fluke"].get_absolute_url())
    assert response.status_code == 200
    body = response.content.decode()
    assert "Risotto" in body
    assert "Hidden Record" not in body


def test_release_detail_returns_200_for_published(client, seeded):
    response = client.get(seeded["release"].get_absolute_url())
    assert response.status_code == 200
    body = response.content.decode()
    assert "Risotto" in body
    assert "application/ld+json" in body
    assert "MusicAlbum" in body


def test_release_detail_404_for_draft(client, seeded):
    response = client.get(seeded["draft_release"].get_absolute_url())
    assert response.status_code == 404


def test_lyric_index_returns_200(client, seeded):
    response = client.get("/lyrics/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "You Got Me" in body
    assert "Empty One" not in body


def test_lyric_detail_returns_200_for_lyric_with_body(client, seeded):
    response = client.get(seeded["lyric"].get_absolute_url())
    assert response.status_code == 200
    assert "You got me, baby" in response.content.decode()


def test_lyric_detail_404_for_bodyless_lyric(client, seeded):
    response = client.get(seeded["bodyless"].get_absolute_url())
    assert response.status_code == 404


def test_resource_list_groups_official_and_fan(client, seeded):
    response = client.get("/resources/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "Live Set" in body
    assert "Fan Remix" in body
    assert "Official Resources" in body
    # The heading contains an ampersand, which Django escapes in HTML output.
    assert "Fan Remixes &amp; Resources" in body


def test_resource_detail_returns_200_for_published(client, seeded):
    response = client.get(seeded["official"].get_absolute_url())
    assert response.status_code == 200
    assert "Live Set" in response.content.decode()


def test_resource_detail_404_for_draft(client, seeded):
    response = client.get(seeded["draft_resource"].get_absolute_url())
    assert response.status_code == 404


def test_page_detail_returns_200_for_published(client, seeded):
    response = client.get(seeded["page"].get_absolute_url())
    assert response.status_code == 200
    assert "About" in response.content.decode()


def test_page_detail_404_for_draft(client, seeded):
    response = client.get(seeded["draft_page"].get_absolute_url())
    assert response.status_code == 404


def test_unknown_slug_404(client, seeded):
    response = client.get("/no-such-page/")
    assert response.status_code == 404
