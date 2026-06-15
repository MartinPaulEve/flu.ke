"""Resources: Official Resources and Fan Remixes & Resources.

Every resource is fully catalogued with rich metadata. A resource may bundle
several files (e.g. a live-set archive plus its cover) and may link to discography
records (the artist/alias vocabulary lives in the discography app).
"""

from django.db import models
from django.template.defaultfilters import filesizeformat
from django.utils import timezone

from apps.core.models import (
    PublishableQuerySet,
    SeoFieldsMixin,
    SluggedModel,
    TimeStampedModel,
)
from apps.resources.partial_date import DAY, MONTH, YEAR, format_partial_date

KIND_OFFICIAL = "official"
KIND_FAN = "fan"
KIND_CHOICES = [
    (KIND_OFFICIAL, "Official Resources"),
    (KIND_FAN, "Fan Remixes & Resources"),
]


_FILE_KIND_LABELS = {
    "audio": "audio",
    "archive": "archive",
    "image": "image",
    "video": "video",
    "document": "document",
}

# Title fragments that tell us more than the bare metadata does.
_LIVE_HINTS = ("live", "tribal gathering", "glastonbury", "festival", "tabernacle")
_INTERVIEW_HINTS = ("interview", "interviewed", "radio")
_REMIX_HINTS = ("remix", "rmx", "remixes", "bootleg", "rework")


def _dominant_file_kind(files) -> str | None:
    """Return the most common ``file_kind`` across a resource's files (or None)."""
    counts: dict[str, int] = {}
    for f in files:
        counts[f.file_kind] = counts.get(f.file_kind, 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda k: (counts[k], k))


def _content_phrase(resource, files, kind_word: str) -> str:
    """A noun phrase for the content, blending the kind, title hints and file kind."""
    title = (resource.title or "").lower()
    dominant = _dominant_file_kind(files)

    if any(hint in title for hint in _LIVE_HINTS):
        return f"{kind_word} live recording"
    if any(hint in title for hint in _INTERVIEW_HINTS):
        return f"{kind_word} interview"
    if any(hint in title for hint in _REMIX_HINTS) or resource.kind == KIND_FAN:
        if dominant == "archive":
            return f"{kind_word} remix archive"
        if dominant == "audio":
            return f"{kind_word} remix"
    if dominant:
        return f"{kind_word} {_FILE_KIND_LABELS.get(dominant, dominant)}"
    return kind_word


def build_snippet(resource) -> str:
    """Derive a best-effort one-line snippet for a resource from its metadata.

    The shape is roughly ``[supplied by X · ] <content phrase>[ · N files][ · size]
    [ · subcategory][ · artist][ · source]``. Everything is derived from real
    metadata — archive contents are never inspected, so track counts are never
    invented.
    """
    files = list(resource.files.all())
    kind_word = "Fan" if resource.kind == KIND_FAN else "Official"

    parts: list[str] = []

    contributor = (resource.contributor or "").strip()
    if contributor:
        parts.append(f"supplied by {contributor}")

    parts.append(_content_phrase(resource, files, kind_word))

    if files:
        n = len(files)
        dominant = _dominant_file_kind(files)
        kind_label = _FILE_KIND_LABELS.get(dominant, "") if dominant else ""
        # Only label the count with a file kind when the files are homogeneous,
        # so "1 archive file" stays accurate.
        homogeneous = len({f.file_kind for f in files}) == 1
        noun = "file" if n == 1 else "files"
        if kind_label and homogeneous:
            parts.append(f"{n} {kind_label} {noun}")
        else:
            parts.append(f"{n} {noun}")
        total = sum(f.byte_size or 0 for f in files)
        if total:
            parts.append(filesizeformat(total))

    if resource.subcategory_id and resource.subcategory:
        parts.append(resource.subcategory.name)

    if resource.artist_id and resource.artist:
        artist_name = resource.artist.name
        if artist_name and artist_name not in contributor:
            parts.append(artist_name)

    source = (resource.source_attribution or "").strip()
    if source:
        parts.append(source)

    snippet = " · ".join(p for p in parts if p)
    return snippet[:255]


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
    snippet = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Snippet explanation",
        help_text="One-line description shown in resource listings.",
    )
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
    related_post = models.ForeignKey(
        "blog.Post",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resources",
        help_text="Optional blog post that announces or discusses this resource.",
    )
    contributor = models.CharField(
        max_length=200, blank=True, help_text="Fan / remixer credit."
    )
    source_attribution = models.CharField(max_length=300, blank=True)
    license = models.CharField(max_length=200, blank=True)
    recorded_date = models.DateField(null=True, blank=True)
    # How precise recorded_date is. Unknown parts are stored as 1 but not shown,
    # so the field stays a real date for sorting/filtering. See partial_date.py.
    recorded_precision = models.CharField(
        max_length=5,
        choices=[(YEAR, "Year"), (MONTH, "Month"), (DAY, "Day")],
        default=DAY,
    )
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

    @property
    def display_snippet(self) -> str:
        """The snippet to show in listings: the stored one, else a derived fallback."""
        if self.snippet:
            return self.snippet
        return build_snippet(self)

    @property
    def display_date(self):
        """The meaningful content date: when recorded, else when released.

        ``uploaded_at`` is site housekeeping, not a content date, so it is not
        used here. Returns ``None`` when neither date is set.
        """
        return self.recorded_date or self.released_date

    @property
    def display_date_label(self) -> str:
        """Label for :attr:`display_date` — 'Recorded', 'Released' or ''."""
        if self.recorded_date:
            return "Recorded"
        if self.released_date:
            return "Released"
        return ""

    @property
    def recorded_display(self) -> str:
        """The recorded date shown only as precisely as it's known (year/month/day)."""
        return format_partial_date(self.recorded_date, self.recorded_precision)

    def og_card(self):
        subtitle = "Fan" if self.kind == KIND_FAN else "Official"
        return (self.resolved_og_title(), subtitle, None)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.ensure_og_image():
            super().save(update_fields=["og_image"])


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

    @property
    def display_byte_size(self):
        """Best-known download size: the recorded ``byte_size``, else the actual
        size of the stored file. ``None`` when neither is available."""
        if self.byte_size:
            return self.byte_size
        try:
            return self.file.size or None
        except (ValueError, OSError):
            return None
