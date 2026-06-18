"""Optional Resource -> blog Post link and its rendering on the resource page."""

import pytest
from django.utils import timezone

from apps.blog.models import Post
from apps.resources.models import Resource

pytestmark = pytest.mark.django_db


def test_resource_links_to_a_post():
    post = Post.objects.create(title="Samples are up", is_published=True, published_at=timezone.now())
    resource = Resource.objects.create(title="2 Pie Island samples", related_post=post)
    assert resource.related_post == post
    assert list(post.resources.all()) == [resource]


def _resource_html(client, resource):
    response = client.get(resource.get_absolute_url())
    assert response.status_code == 200
    return response.content.decode()


def test_resource_page_renders_live_related_post(client):
    post = Post.objects.create(
        title="Samples are up",
        body="**Grab them** on the discography page.",
        is_published=True,
        published_at=timezone.now(),
    )
    resource = Resource.objects.create(
        title="2 Pie Island samples", kind="official", is_published=True, related_post=post
    )
    html = _resource_html(client, resource)
    assert "Samples are up" in html  # the post title
    assert "Grab them" in html  # the post content pulled in
    assert post.get_absolute_url() in html  # link to the original post


def test_resource_page_shows_the_related_posts_cover_image(client):
    post = Post.objects.create(
        title="Samples are up",
        body="words",
        cover_image="blog/sleeve.jpg",
        is_published=True,
        published_at=timezone.now(),
    )
    resource = Resource.objects.create(
        title="2 Pie Island samples", kind="official", is_published=True, related_post=post
    )
    html = _resource_html(client, resource)
    assert post.cover_image.url in html  # the post's featured image is shown


def test_resource_page_without_cover_has_no_related_post_image(client):
    post = Post.objects.create(
        title="No picture", body="words", is_published=True, published_at=timezone.now()
    )
    resource = Resource.objects.create(
        title="Plain", kind="official", is_published=True, related_post=post
    )
    html = _resource_html(client, resource)
    assert "related-post__cover" not in html


def test_resource_page_hides_draft_related_post(client):
    draft = Post.objects.create(title="Unannounced", body="secret", is_published=False)
    resource = Resource.objects.create(
        title="Quiet upload", kind="fan", is_published=True, related_post=draft
    )
    html = _resource_html(client, resource)
    assert "Unannounced" not in html
    assert "secret" not in html
