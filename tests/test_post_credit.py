"""A post can credit someone ('thanks to'), shown at the top of its sidebar."""

import pytest
from django.utils import timezone

from apps.blog.models import Post

pytestmark = pytest.mark.django_db


def _post(**kw):
    defaults = dict(title="A find", body="Words.", is_published=True, published_at=timezone.now())
    defaults.update(kw)
    return Post.objects.create(**defaults)


def test_credit_renders_a_thanks_block(client):
    post = _post(credit="peterbox")
    html = client.get(post.get_absolute_url()).content.decode()
    assert "Thanks for this post to peterbox" in html


def test_no_credit_means_no_thanks_block(client):
    post = _post()
    html = client.get(post.get_absolute_url()).content.decode()
    assert "Thanks for this post to" not in html


def test_thanks_block_sits_at_the_top_of_the_rail(client):
    post = _post(credit="peterbox")
    post.categories.create(name="News")
    html = client.get(post.get_absolute_url()).content.decode()
    # The credit appears before the first rail section heading.
    assert html.index("Thanks for this post to") < html.index("Filed under")
