"""Shared abstract models and SEO scaffolding.

These abstract bases are reused by every public content type so that timestamps and
SEO/Open-Graph metadata are defined once. Concrete behaviour (slug generation,
published querysets, OG-image generation) lives on the concrete models and in
``apps.core.text`` / ``apps.core.seo``.
"""

from django.db import models

from apps.core.text import unique_slug


class PublishableQuerySet(models.QuerySet):
    """Reusable queryset exposing ``.published()`` for content with ``is_published``."""

    def published(self):
        return self.filter(is_published=True)


class SluggedModel(models.Model):
    """Abstract base giving a model a unique, auto-populated ``slug``.

    Set ``slug_source_field`` to the attribute the slug derives from (``title`` by
    default; discography models use ``name``). The slug is generated once on first
    save and left alone afterwards so published URLs stay stable.
    """

    slug = models.SlugField(max_length=200, unique=True, blank=True)
    slug_source_field = "title"

    class Meta:
        abstract = True

    def _slug_is_taken(self, candidate):
        qs = type(self)._default_manager.filter(slug=candidate)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        return qs.exists()

    def save(self, *args, **kwargs):
        if not self.slug:
            source = getattr(self, self.slug_source_field, "") or ""
            self.slug = unique_slug(source, exists=self._slug_is_taken, max_length=200)
        super().save(*args, **kwargs)


class TimeStampedModel(models.Model):
    """Abstract base adding self-managing ``created``/``modified`` timestamps."""

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SeoFieldsMixin(models.Model):
    """Abstract base adding SEO + Open Graph fields shared by all public content.

    Concrete models provide a ``title`` (and usually a body/description); the
    ``resolved_*`` helpers fall back to those when the SEO override is blank, so
    editors only fill in overrides when they want something different.
    """

    seo_title = models.CharField(
        max_length=200, blank=True, help_text="Overrides the <title>; defaults to the title."
    )
    meta_description = models.CharField(
        max_length=300, blank=True, help_text="Search-result snippet; ~150–160 chars ideal."
    )
    canonical_url = models.URLField(blank=True, help_text="Optional canonical override.")
    og_title = models.CharField(max_length=200, blank=True)
    og_description = models.CharField(max_length=300, blank=True)
    og_image = models.ImageField(
        upload_to="og/", blank=True, help_text="Auto-generated when blank (where supported)."
    )
    noindex = models.BooleanField(
        default=False, help_text="Exclude from sitemap and add a noindex tag."
    )

    class Meta:
        abstract = True

    def resolved_seo_title(self):
        return self.seo_title or getattr(self, "title", "") or ""

    def resolved_og_title(self):
        return self.og_title or self.resolved_seo_title()

    def resolved_og_description(self):
        return self.og_description or self.meta_description
