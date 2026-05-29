"""The blog Post should auto-generate an Open Graph image on first save."""

import pytest
from django.utils import timezone

from apps.blog.models import Post

pytestmark = pytest.mark.django_db


def test_saving_a_post_generates_an_og_image():
    post = Post.objects.create(title="Atom Bomb reissue", is_published=True, published_at=timezone.now())
    assert post.og_image.name
    assert post.og_image.name.endswith(".png")


def test_existing_og_image_is_not_regenerated():
    post = Post.objects.create(title="Original")
    original = post.og_image.name
    post.title = "Edited title"
    post.save()
    post.refresh_from_db()
    assert post.og_image.name == original
