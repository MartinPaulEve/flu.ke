"""Shared abstract models and SEO scaffolding.

These abstract bases are reused by every public content type so that timestamps and
SEO/Open-Graph metadata are defined once. Concrete behaviour (slug generation,
published querysets, OG-image generation) lives on the concrete models and in
``apps.core.text`` / ``apps.core.seo``.
"""

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models

from apps.core.storage import uuid_upload_to
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


class Upload(TimeStampedModel):
    """A tracked media file (e.g. an image embedded in a post).

    Stored under a random UUID name (keeping only the extension); the title and
    description are just so editors can recognise it in the admin. These are not
    Resource files — they have no resource, and aren't listed or shown publicly.
    """

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to=uuid_upload_to("uploads"))

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return self.title or self.file.name


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


class SiteConfiguration(SeoFieldsMixin, TimeStampedModel):
    """Site-wide configuration stored as a single row — the homepage's OG card + copy.

    Load it with :meth:`load`; ``save`` always keeps one row (pk=1). It reuses the
    SEO/Open-Graph fields and image generation, with the homepage (``/``) as its
    page, so the shared OG meta partial and admin cache/regenerate tools apply.
    """

    footer_tagline = models.CharField(
        max_length=200,
        default="Black & red since the rave.",
        help_text="The tagline shown in the site footer on every page.",
    )
    header_kicker_lead = models.CharField(
        max_length=120,
        default="Est. on the dancefloor",
        help_text="Homepage header kicker, first part (shown before the dash).",
    )
    header_kicker_detail = models.CharField(
        max_length=120,
        default="official & fan archive",
        help_text="Homepage header kicker, second part (shown after the dash).",
    )
    og_card_title = models.CharField(
        max_length=120,
        default="The fan source",
        help_text="Headline on the auto-generated homepage social-share (OG) image. "
        "Ignored if you upload your own image below.",
    )
    og_card_subtitle = models.CharField(
        max_length=160,
        blank=True,
        help_text="Optional smaller line under the headline on the generated OG image.",
    )
    og_card_image = models.ImageField(
        upload_to="og/",
        blank=True,
        help_text="Optional image composited into the right-hand square of the generated "
        "OG card (like album art on release cards). Leave blank for a text-only card.",
    )

    class Meta:
        verbose_name = "site configuration"
        verbose_name_plural = "site configuration"

    def __str__(self):
        return "Site configuration"

    @classmethod
    def load(cls):
        config, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "og_title": "Fluke — official & fan archive",
                "meta_description": (
                    "Everything Fluke and its aliases and other projects: news, the complete "
                    "discography, official material, and the things fans made."
                ),
            },
        )
        return config

    def _og_image_is_generated(self) -> bool:
        """True when ``og_image`` holds an auto-generated card (not a manual upload).

        Generated cards are saved as ``siteconfiguration-<pk>.jpg``; a custom
        upload keeps its own filename, which is how we tell them apart.
        """
        basename = (self.og_image.name or "").rsplit("/", 1)[-1]
        return basename.startswith(f"{self._meta.model_name}-")

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce a single row
        # Refresh the generated card from the (possibly edited) card text on save,
        # so changes take effect without a manual regenerate. A custom uploaded
        # image has a different filename and is left untouched.
        if self._og_image_is_generated():
            self.og_image.delete(save=False)
            self.og_image = ""
        super().save(*args, **kwargs)
        if self.ensure_og_image():
            super().save(update_fields=["og_image"])

    def get_absolute_url(self):
        return "/"

    def resolved_seo_title(self):
        return self.seo_title or "Fluke — official & fan archive"

    def _og_card_image_bytes(self):
        """Bytes of the image composited into the generated card, or ``None``."""
        if not self.og_card_image:
            return None
        try:
            with self.og_card_image.open("rb") as fh:
                return fh.read()
        except (FileNotFoundError, OSError, ValueError):
            return None

    def og_card(self):
        # The editable title/subtitle drive the auto-generated card and an optional
        # og_card_image is composited in on the right (the generator always adds the
        # FLUKE.FM mark). Upload an og_image to override the whole card instead; the
        # editable og_title/og_description still drive the <meta> tags.
        return (self.og_card_title, self.og_card_subtitle, self._og_card_image_bytes())
