"""Optional Resource -> blog Post link and its rendering on the resource page."""

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from apps.blog.models import Post
from apps.resources.models import Resource

pytestmark = pytest.mark.django_db


def test_resource_links_to_a_post():
    post = Post.objects.create(title="Samples are up", is_published=True, published_at=timezone.now())
    resource = Resource.objects.create(title="2 Pie Island samples", related_post=post)
    assert resource.related_post == post
    assert list(post.resources.all()) == [resource]


def _resource_html(tmp_path, resource):
    with override_settings(BUILD_DIR=str(tmp_path)):
        call_command("build_site", no_media=True)
    return (tmp_path / "resources" / resource.kind / f"{resource.slug}" / "index.html").read_text()


def test_resource_page_renders_live_related_post(tmp_path):
    post = Post.objects.create(
        title="Samples are up",
        body="**Grab them** on the discography page.",
        is_published=True,
        published_at=timezone.now(),
    )
    resource = Resource.objects.create(
        title="2 Pie Island samples", kind="official", is_published=True, related_post=post
    )
    html = _resource_html(tmp_path, resource)
    assert "Samples are up" in html  # the post title
    assert "Grab them" in html  # the post content pulled in
    assert post.get_absolute_url() in html  # link to the original post


def test_resource_page_hides_draft_related_post(tmp_path):
    draft = Post.objects.create(title="Unannounced", body="secret", is_published=False)
    resource = Resource.objects.create(
        title="Quiet upload", kind="fan", is_published=True, related_post=draft
    )
    html = _resource_html(tmp_path, resource)
    assert "Unannounced" not in html
    assert "secret" not in html
