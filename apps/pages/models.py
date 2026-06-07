"""Arbitrary CMS-managed pages (About, etc.)."""

from django.db import models

from apps.core.models import (
    PublishableQuerySet,
    SeoFieldsMixin,
    SluggedModel,
    TimeStampedModel,
)


class Page(SluggedModel, SeoFieldsMixin, TimeStampedModel):
    TEMPLATE_STANDARD = "standard"
    TEMPLATE_CHOICES = [
        (TEMPLATE_STANDARD, "Standard"),
        ("full", "Full width"),
    ]

    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, help_text="Rich text (HTML), edited with TinyMCE.")
    template_key = models.CharField(
        max_length=20, choices=TEMPLATE_CHOICES, default=TEMPLATE_STANDARD
    )
    is_published = models.BooleanField(default=False)
    menu_order = models.IntegerField(
        default=0, help_text="Order in the main navigation; 0 hides it from the menu."
    )

    objects = PublishableQuerySet.as_manager()

    class Meta:
        ordering = ["menu_order", "title"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return f"/{self.slug}/"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.ensure_og_image():
            super().save(update_fields=["og_image"])
