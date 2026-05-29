"""Build state: tracks whether the published static site is stale.

Content edits flip this to "dirty" (via signals) and the admin surfaces an
"Unpublished changes" prompt; a successful ``build_site`` clears it. The full build
never runs inside a model save — only when the editor publishes or runs the command.
"""

from django.db import models
from django.utils import timezone


class BuildState(models.Model):
    """A single row tracking whether the static site needs rebuilding."""

    singleton_id = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    is_dirty = models.BooleanField(default=False)
    dirty_since = models.DateTimeField(null=True, blank=True)
    last_built = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "build state"
        verbose_name_plural = "build state"

    def __str__(self):
        return "Unpublished changes" if self.is_dirty else "Published"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(singleton_id=1)
        return obj

    @classmethod
    def mark_dirty(cls):
        state = cls.load()
        if not state.is_dirty:
            state.is_dirty = True
            state.dirty_since = timezone.now()
            state.save(update_fields=["is_dirty", "dirty_since"])

    @classmethod
    def mark_built(cls):
        state = cls.load()
        state.is_dirty = False
        state.last_built = timezone.now()
        state.save(update_fields=["is_dirty", "last_built"])
