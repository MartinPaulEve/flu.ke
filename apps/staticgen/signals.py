"""Mark the static site dirty whenever publishable content changes.

Only flips a flag (cheap); the actual rebuild happens on Publish / build_site.
"""

from django.db.models.signals import post_delete, post_save

from apps.blog.models import Category, Post, Tag
from apps.discography.models import (
    Artist,
    CoverImage,
    Edition,
    Lyric,
    Release,
    ReleaseType,
    Track,
)
from apps.pages.models import Page
from apps.resources.models import Resource, ResourceFile, ResourceSubcategory
from apps.staticgen.models import BuildState

WATCHED = [
    Post, Category, Tag,
    Page,
    Resource, ResourceFile, ResourceSubcategory,
    Artist, ReleaseType, Release, Edition, Track, Lyric, CoverImage,
]


def _mark_dirty(sender, **kwargs):
    BuildState.mark_dirty()


def connect():
    for model in WATCHED:
        name = model._meta.label_lower
        post_save.connect(_mark_dirty, sender=model, dispatch_uid=f"dirty:{name}:save")
        post_delete.connect(_mark_dirty, sender=model, dispatch_uid=f"dirty:{name}:delete")
