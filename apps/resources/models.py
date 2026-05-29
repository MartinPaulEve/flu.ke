"""Resources: Official Resources and Fan Remixes & Resources.

Every resource is fully catalogued with rich metadata. A resource may bundle
several files (e.g. a live-set archive plus its cover) and may link to discography
records (the artist/alias vocabulary lives in the discography app).
"""

from django.db import models
from django.utils import timezone

from apps.core.models import (
    PublishableQuerySet,
    SeoFieldsMixin,
    SluggedModel,
    TimeStampedModel,
)

KIND_OFFICIAL = "official"
KIND_FAN = "fan"
KIND_CHOICES = [
    (KIND_OFFICIAL, "Official Resources"),
    (KIND_FAN, "Fan Remixes & Resources"),
]


class ResourceSubcategory(SluggedModel, TimeStampedModel):
    slug_source_field = "name"
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_OFFICIAL)
    description = models.TextField(blank=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["kind", "display_order", "name"]
        verbose_name_plural = "resource subcategories"

    def __str__(self):
        return f"{self.get_kind_display()} / {self.name}"


class Resource(SluggedModel, SeoFieldsMixin, TimeStampedModel):
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_OFFICIAL)
    subcategory = models.ForeignKey(
        ResourceSubcategory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resources",
    )
    description = models.TextField(blank=True, help_text="Markdown.")
    # Optional links into the discography (shared artist/alias vocabulary).
    artist = models.ForeignKey(
        "discography.Artist",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resources",
    )
    related_release = models.ForeignKey(
        "discography.Release",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resources",
    )
    related_edition = models.ForeignKey(
        "discography.Edition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resources",
    )
    contributor = models.CharField(
        max_length=200, blank=True, help_text="Fan / remixer credit."
    )
    source_attribution = models.CharField(max_length=300, blank=True)
    license = models.CharField(max_length=200, blank=True)
    recorded_date = models.DateField(null=True, blank=True)
    released_date = models.DateField(null=True, blank=True)
    uploaded_at = models.DateTimeField(
        default=timezone.now, help_text="When this was added to the site."
    )
    external_url = models.URLField(blank=True, help_text="Used when not hosted on-site.")
    is_published = models.BooleanField(default=False)

    objects = PublishableQuerySet.as_manager()

    class Meta:
        ordering = ["-uploaded_at", "title"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return f"/resources/{self.kind}/{self.slug}/"


class ResourceFile(TimeStampedModel):
    KIND_CHOICES = [
        ("audio", "Audio"),
        ("archive", "Archive"),
        ("image", "Image"),
        ("video", "Video"),
        ("document", "Document"),
    ]

    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to="resources/")
    original_filename = models.CharField(max_length=300, blank=True)
    file_kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="audio")
    byte_size = models.BigIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)
    duration = models.DurationField(null=True, blank=True)
    checksum = models.CharField(max_length=64, blank=True, help_text="sha256, for dedupe.")
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self):
        return self.original_filename or self.file.name
