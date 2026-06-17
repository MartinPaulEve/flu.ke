"""The API root groups four sections, and resources/pages/news are addressable."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.blog.models import Category, Post
from apps.pages.models import Page
from apps.resources.models import KIND_OFFICIAL, Resource, ResourceFile, ResourceSubcategory

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


# --- the /api/ root ---------------------------------------------------------

def test_api_root_lists_the_four_sections(client):
    body = client.get("/api/").json()
    assert set(body) == {"discography", "resources", "pages", "news"}
    assert body["discography"].endswith("/api/discography/")
    assert body["resources"].endswith("/api/resources/")
    assert body["pages"].endswith("/api/pages/")
    assert body["news"].endswith("/api/news/")
    for href in body.values():
        assert href.startswith("http://")


def test_discography_root_lists_its_endpoints(client):
    body = client.get("/api/discography/").json()
    assert {"artists", "releases", "editions", "tracks", "lyrics", "cover-images"} <= set(body)


# --- resources --------------------------------------------------------------

def test_resources_are_addressable_and_published_only(client):
    sub = ResourceSubcategory.objects.create(name="Live Sets", kind=KIND_OFFICIAL)
    res = Resource.objects.create(
        title="Glastonbury 98", slug="glastonbury-98", kind=KIND_OFFICIAL,
        subcategory=sub, is_published=True,
    )
    ResourceFile.objects.create(
        resource=res, external_url="https://archive.org/a.mp3", file_kind="audio"
    )
    Resource.objects.create(title="Hidden", slug="hidden", kind=KIND_OFFICIAL, is_published=False)

    listed = client.get("/api/resources/").json()["results"]
    slugs = {r["slug"] for r in listed}
    assert "glastonbury-98" in slugs and "hidden" not in slugs

    detail = client.get("/api/resources/glastonbury-98/").json()
    assert detail["title"] == "Glastonbury 98"
    assert detail["subcategory"] == "Live Sets"
    assert detail["files"][0]["download_url"] == "https://archive.org/a.mp3"
    assert detail["_links"]["self"]["href"].endswith("/api/resources/glastonbury-98/")
    assert detail["_links"]["alternate"]["href"].endswith(res.get_absolute_url())
    assert detail["_links"]["collection"]["href"].endswith("/api/resources/")


def test_unpublished_resource_detail_404(client):
    Resource.objects.create(title="Hidden", slug="hidden", kind=KIND_OFFICIAL, is_published=False)
    assert client.get("/api/resources/hidden/").status_code == 404


# --- pages ------------------------------------------------------------------

def test_pages_are_addressable(client):
    Page.objects.create(title="About", slug="about", body="<p>Hi</p>", is_published=True)
    Page.objects.create(title="Secret", slug="secret", is_published=False)

    slugs = {p["slug"] for p in client.get("/api/pages/").json()["results"]}
    assert "about" in slugs and "secret" not in slugs

    detail = client.get("/api/pages/about/").json()
    assert detail["title"] == "About"
    assert detail["_links"]["self"]["href"].endswith("/api/pages/about/")
    assert client.get("/api/pages/secret/").status_code == 404


# --- news (posts) -----------------------------------------------------------

def test_posts_are_addressable(client):
    cat = Category.objects.create(name="Releases")
    post = Post.objects.create(
        title="A find", slug="a-find", body="words", is_published=True,
        published_at=timezone.now(),
    )
    post.categories.add(cat)
    Post.objects.create(title="Draft", slug="draft", is_published=False)

    slugs = {p["slug"] for p in client.get("/api/news/").json()["results"]}
    assert "a-find" in slugs and "draft" not in slugs

    detail = client.get("/api/news/a-find/").json()
    assert detail["title"] == "A find"
    assert detail["categories"][0]["name"] == "Releases"
    assert detail["_links"]["self"]["href"].endswith("/api/news/a-find/")
    assert detail["_links"]["alternate"]["href"].endswith(post.get_absolute_url())
    assert client.get("/api/news/draft/").status_code == 404
