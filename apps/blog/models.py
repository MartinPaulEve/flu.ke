"""Blog / News models."""

from django.core.files.base import ContentFile
from django.db import models
from django.utils import timezone

from apps.blog.og import render_og_image
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
    categories = models.ManyToManyField(Category, blank=True, related_name="posts")
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
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

    def get_absolute_url(self):
        return f"/news/{self.display_date.year}/{self.slug}/"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.title and not self.og_image:
            data = render_og_image(self.title)
            self.og_image.save(f"{self.pk}.png", ContentFile(data), save=False)
            super().save(update_fields=["og_image"])
