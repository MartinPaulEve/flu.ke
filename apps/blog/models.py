"""Blog / News models."""

from django.db import models
from django.utils import timezone

from apps.core.models import (
    PublishableQuerySet,
    SeoFieldsMixin,
    SluggedModel,
    TimeStampedModel,
)


class Category(SluggedModel, TimeStampedModel):
    slug_source_field = "name"
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"/news/category/{self.slug}/"


class Tag(SluggedModel, TimeStampedModel):
    slug_source_field = "name"
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PostQuerySet(PublishableQuerySet):
    def published(self):
        """Visible posts: flagged published AND with a publish date that has passed."""
        return self.filter(
            is_published=True,
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        )


class Post(SluggedModel, SeoFieldsMixin, TimeStampedModel):
    CONFIDENCE_CHOICES = [
        ("complete", "Complete"),
        ("partial", "Partial"),
        ("stub", "Stub"),
    ]

    title = models.CharField(max_length=200)
    excerpt = models.TextField(blank=True)
    body = models.TextField(blank=True, help_text="Markdown.")
    published_at = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    cover_image = models.ImageField(upload_to="blog/", blank=True)
    credit = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Thanks to",
        help_text="Who tipped off / supplied this post; shown as a 'Thanks for "
        "this post to …' note at the top of the sidebar.",
    )
    categories = models.ManyToManyField(Category, blank=True, related_name="posts")
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    # Discography links surfaced in the post's side rail. Optional, set per post.
    related_releases = models.ManyToManyField(
        "discography.Release",
        blank=True,
        related_name="related_posts",
        help_text="Releases to surface in this post's sidebar.",
    )
    related_artists = models.ManyToManyField(
        "discography.Artist",
        blank=True,
        related_name="related_posts",
        help_text="Artists to surface in this post's sidebar.",
    )
    related_resources = models.ManyToManyField(
        "resources.Resource",
        blank=True,
        related_name="related_posts",
        help_text="Resources to surface in this post's sidebar.",
    )
    # Provenance for Wayback-recovered posts.
    source_url = models.URLField(blank=True)
    import_confidence = models.CharField(
        max_length=20, choices=CONFIDENCE_CHOICES, default="complete"
    )
    manually_edited = models.BooleanField(
        default=False, help_text="Set once edited by hand; protects from re-import."
    )

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-created"]

    def __str__(self):
        return self.title

    @property
    def display_date(self):
        return self.published_at or self.created

    @property
    def is_live(self):
        """True when the post is on the static site (published, publish date passed).

        Mirrors ``PostQuerySet.published`` so links to a post are only shown when a
        page actually exists for it.
        """
        return bool(
            self.is_published
            and self.published_at is not None
            and self.published_at <= timezone.now()
        )

    def get_absolute_url(self):
        return f"/news/{self.display_date.year}/{self.slug}/"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.ensure_og_image():
            super().save(update_fields=["og_image"])
