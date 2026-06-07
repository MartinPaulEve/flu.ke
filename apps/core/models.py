"""Shared abstract models and SEO scaffolding.

These abstract bases are reused by every public content type so that timestamps and
SEO/Open-Graph metadata are defined once. Concrete behaviour (slug generation,
published querysets, OG-image generation) lives on the concrete models and in
``apps.core.text`` / ``apps.core.seo``.
"""

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
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
    # Slugs that must never be assigned (e.g. they collide with a fixed URL such
    # as /discography/api/). Auto-generation skips them; manual entry is rejected.
    reserved_slugs = frozenset()

    class Meta:
        abstract = True

    def _slug_is_taken(self, candidate):
        if candidate in self.reserved_slugs:
            return True
        qs = type(self)._default_manager.filter(slug=candidate)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        return qs.exists()

    def clean(self):
        super().clean()
        if self.slug and self.slug in self.reserved_slugs:
            raise ValidationError(
                {"slug": f"“{self.slug}” is a reserved slug and can’t be used."}
            )

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
        max_length=200,
        blank=True,
        # NB: admin renders help_text as raw HTML, so avoid literal tags like <title>.
        help_text="Overrides the HTML page title; defaults to the title.",
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
        # Content models use either `title` (posts, pages, resources, lyrics) or
        # `name` (releases, artists); fall back through both.
        return self.seo_title or getattr(self, "title", "") or getattr(self, "name", "") or ""

    def resolved_og_title(self):
        return self.og_title or self.resolved_seo_title()

    def resolved_og_description(self):
        return self.og_description or self.meta_description

    def og_card(self):
        """Return ``(title, subtitle, cover_bytes)`` for the generated OG image.

        Subclasses override to add a subtitle (e.g. the artist) or composite a
        cover (e.g. album art). Default is a plain branded card of the title.
        """
        return (self.resolved_og_title(), "", None)

    def ensure_og_image(self):
        """Generate and attach an OG image from :meth:`og_card` when blank.

        Returns ``True`` if it set one (so the caller can persist it). The image
        is built in memory and saved with ``save=False`` so the caller controls
        the database write. Requires a saved instance (uses ``pk`` in the name).
        """
        if self.og_image:
            return False
        title, subtitle, cover = self.og_card()
        if not title:
            return False
        from apps.core.og import render_og_image

        data = render_og_image(title, subtitle, cover=cover)
        self.og_image.save(f"{self._meta.model_name}-{self.pk}.jpg", ContentFile(data), save=False)
        return True
