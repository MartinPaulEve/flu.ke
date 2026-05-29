"""BuildState model behaviour and the content-change dirty signal."""

import pytest
from django.utils import timezone

from apps.blog.models import Post
from apps.discography.models import Artist
from apps.staticgen.models import BuildState

pytestmark = pytest.mark.django_db


def test_load_is_a_singleton():
    a = BuildState.load()
    b = BuildState.load()
    assert a.pk == b.pk
    assert BuildState.objects.count() == 1


def test_mark_dirty_sets_flag_and_timestamp():
    BuildState.mark_built()  # start clean
    BuildState.mark_dirty()
    state = BuildState.load()
    assert state.is_dirty is True
    assert state.dirty_since is not None


def test_mark_dirty_preserves_original_dirty_since():
    BuildState.mark_built()
    BuildState.mark_dirty()
    first = BuildState.load().dirty_since
    BuildState.mark_dirty()
    assert BuildState.load().dirty_since == first


def test_mark_built_clears_flag_and_records_time():
    BuildState.mark_dirty()
    BuildState.mark_built()
    state = BuildState.load()
    assert state.is_dirty is False
    assert state.last_built is not None


def test_saving_content_marks_site_dirty():
    BuildState.mark_built()  # clean
    Artist.objects.create(name="Fluke")
    assert BuildState.load().is_dirty is True


def test_saving_a_post_marks_site_dirty():
    BuildState.mark_built()
    Post.objects.create(title="News", is_published=True, published_at=timezone.now())
    assert BuildState.load().is_dirty is True
