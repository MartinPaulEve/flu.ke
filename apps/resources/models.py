"""Resources: Official Resources and Fan Remixes & Resources.

Every resource is fully catalogued with rich metadata. A resource may bundle
several files (e.g. a live-set archive plus its cover) and may link to discography
records (the artist/alias vocabulary lives in the discography app).
"""

import os
from collections import namedtuple

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    PublishableQuerySet,
    SeoFieldsMixin,
    SluggedModel,
    TimeStampedModel,
)
from apps.resources.partial_date import DAY, MONTH, YEAR, format_partial_date
from apps.resources.storage import private_storage

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


def _capitalize_first(text: str) -> str:
    """Upper-case the first character only, leaving the rest untouched."""
    return text[:1].upper() + text[1:] if text else text


def _content_phrase(resource, files, kind_word: str) -> str:
    """A noun phrase for the content, blending the kind, title hints and file kind.

    A subcategory may pin the descriptor (e.g. "music video") via its
    ``snippet_phrase``; that always wins over the heuristics below.
    """
    sub = resource.subcategory if resource.subcategory_id else None
    if sub and sub.snippet_phrase.strip():
        return f"{kind_word} {sub.snippet_phrase.strip()}"

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


SnippetParts = namedtuple("SnippetParts", ["lead", "artists", "tail"])


def _snippet_segments(resource) -> SnippetParts:
    """Build the snippet as ordered segments, with the credited artists separated.

    Returns ``(lead, artists, tail)`` where ``lead``/``tail`` are lists of text
    fragments and ``artists`` is the list of credited :class:`Artist` objects.
    Joined together they form the plain-text snippet; keeping the artists apart
    lets listings link each one. The shape is ``<content phrase>[ · supplied by X]
    [ · N files][ · size][ · subcategory][ · artists][ · source]`` — it always
    leads with the capitalised content phrase so every snippet reads consistently.
    """
    files = list(resource.files.all())
    kind_word = "Fan" if resource.kind == KIND_FAN else "Official"
    contributor = (resource.contributor or "").strip()

    lead: list[str] = [_content_phrase(resource, files, kind_word)]

    if contributor:
        lead.append(f"supplied by {contributor}")

    if files:
        n = len(files)
        dominant = _dominant_file_kind(files)
        kind_label = _FILE_KIND_LABELS.get(dominant, "") if dominant else ""
        # Only label the count with a file kind when the files are homogeneous,
        # so "1 archive file" stays accurate.
        homogeneous = len({f.file_kind for f in files}) == 1
        noun = "file" if n == 1 else "files"
        if kind_label and homogeneous:
            lead.append(f"{n} {kind_label} {noun}")
        else:
            lead.append(f"{n} {noun}")
        total = sum((f.display_byte_size or 0) for f in files)
        if total:
            lead.append(filesizeformat(total))

    if resource.subcategory_id and resource.subcategory:
        lead.append(resource.subcategory.name)

    artists = [a for a in resource.all_artists if a.name and a.name not in contributor]

    tail: list[str] = []
    source = (resource.source_attribution or "").strip()
    if source:
        tail.append(source)

    return SnippetParts(lead, artists, tail)


def build_snippet(resource) -> str:
    """Derive a best-effort one-line plain-text snippet from a resource's metadata.

    Everything is derived from real metadata — archive contents are never
    inspected, so track counts are never invented.
    """
    lead, artists, tail = _snippet_segments(resource)
    names = ", ".join(a.name for a in artists)
    parts = [*lead, *([names] if names else []), *tail]
    snippet = " · ".join(p for p in parts if p)
    return _capitalize_first(snippet)[:255]


class ResourceSubcategory(SluggedModel, TimeStampedModel):
    slug_source_field = "name"
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_OFFICIAL)
    description = models.TextField(blank=True)
    snippet_phrase = models.CharField(
        max_length=100,
        blank=True,
        help_text=(
            "How a resource in this subcategory is described in its auto snippet, "
            "after the kind word — e.g. “music video” gives “Official music video”. "
            "Leave blank to derive it automatically."
        ),
    )
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
    additional_artists = models.ManyToManyField(
        "discography.Artist",
        blank=True,
        related_name="additional_resources",
        help_text="Other artists credited alongside the primary artist "
        "(shown comma-separated wherever the artist appears).",
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

    # --- Print-article metadata (magazine / journal interviews etc.) --------
    # All optional; populated only for resources that represent a print article.
    article_authors = models.CharField(
        max_length=300, blank=True, help_text="Article author(s), free text."
    )
    publication_title = models.CharField(
        max_length=200, blank=True, help_text="Magazine or journal title."
    )
    article_date = models.DateField(null=True, blank=True)
    article_date_precision = models.CharField(
        max_length=5,
        choices=[(YEAR, "Year"), (MONTH, "Month"), (DAY, "Day")],
        default=DAY,
    )
    page_numbers = models.CharField(
        max_length=50, blank=True, help_text='e.g. "pp. 34–37".'
    )
    article_url = models.URLField(blank=True, help_text="Link to the article online.")

    # --- Commerce (any resource, not only print) ----------------------------
    purchase_url = models.URLField(
        blank=True, help_text="Where to buy this, if it's for sale."
    )

    is_published = models.BooleanField(default=False)

    objects = PublishableQuerySet.as_manager()

    class Meta:
        ordering = ["-uploaded_at", "title"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return f"/resources/{self.kind}/{self.slug}/"

    @property
    def all_artists(self):
        """Primary artist (if any) followed by additional artists, de-duplicated."""
        artists = [self.artist] if self.artist_id else []
        seen = {a.pk for a in artists}
        for extra in self.additional_artists.all():
            if extra.pk not in seen:
                artists.append(extra)
                seen.add(extra.pk)
        return artists

    @property
    def artists_display(self) -> str:
        """Comma-separated names of every credited artist."""
        return ", ".join(a.name for a in self.all_artists)

    @property
    def display_snippet(self) -> str:
        """The snippet to show in listings: the stored one, else a derived fallback."""
        if self.snippet:
            return self.snippet
        return build_snippet(self)

    @property
    def content_descriptor(self) -> str:
        """A short 'what this is' phrase, e.g. 'Official live recording'."""
        files = list(self.files.all())
        kind_word = "Fan" if self.kind == KIND_FAN else "Official"
        return _content_phrase(self, files, kind_word)

    @property
    def total_byte_size(self) -> int:
        """Combined download size across all files (best-known per file)."""
        return sum((f.display_byte_size or 0) for f in self.files.all())

    @property
    def rail_summary(self) -> str:
        """A one-line ``what it is · size · year`` summary for compact listings."""
        parts = [self.content_descriptor]
        total = self.total_byte_size
        if total:
            parts.append(filesizeformat(total))
        if self.display_date:
            parts.append(str(self.display_date.year))
        return " · ".join(p for p in parts if p)

    @property
    def snippet_display(self) -> SnippetParts:
        """``(lead, artist, tail)`` for listings that link the credited artist.

        A hand-written snippet is shown verbatim (no artist link); a derived one
        keeps its trailing artist separate so the template can link it. ``lead``
        and ``tail`` are pre-joined, capitalised strings.
        """
        if self.snippet:
            return SnippetParts(self.snippet, [], "")
        lead, artists, tail = _snippet_segments(self)
        return SnippetParts(
            _capitalize_first(" · ".join(p for p in lead if p)),
            artists,
            " · ".join(p for p in tail if p),
        )

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

    @property
    def has_print_metadata(self) -> bool:
        """True when any print-article field is populated.

        ``purchase_url`` is deliberately excluded: it applies to any resource
        (a CD, a print, a book) and is surfaced on its own, so a purchase link
        alone must not flag a resource as a print article.
        """
        return any(
            [
                self.article_authors,
                self.publication_title,
                self.article_date,
                self.page_numbers,
                self.article_url,
            ]
        )

    @property
    def article_date_display(self) -> str:
        """The article date shown only as precisely as it's known."""
        return format_partial_date(self.article_date, self.article_date_precision)

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
    file = models.FileField(upload_to="resources/", blank=True)
    external_url = models.URLField(
        blank=True,
        help_text="Link to an off-site copy instead of uploading a file. "
        "Provide either a file or a URL.",
    )
    is_locked = models.BooleanField(
        default=False,
        help_text="Archived: stored but downloadable only by staff. The file is "
        "moved to private storage and is not publicly reachable.",
    )
    locked_file = models.FileField(
        upload_to="resources/",
        storage=private_storage,
        blank=True,
        help_text="Internal: holds the bytes while locked. Managed automatically.",
    )
    preview_image = models.ImageField(
        upload_to="resources/previews/",
        blank=True,
        help_text="Optional public preview shown for a locked file.",
    )
    original_filename = models.CharField(max_length=300, blank=True)
    purchase_url = models.URLField(
        blank=True, help_text="Where to buy this file/item, if it's for sale."
    )
    file_kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="audio")
    byte_size = models.BigIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)
    duration = models.DurationField(null=True, blank=True)
    checksum = models.CharField(max_length=64, blank=True, help_text="sha256, for dedupe.")
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self):
        return self.display_name

    def clean(self):
        super().clean()
        if not self.file and not self.locked_file and not self.external_url:
            raise ValidationError("Provide either an uploaded file or an external URL.")

    @property
    def is_external(self) -> bool:
        """True when this is a remote link rather than stored bytes (public or private)."""
        return not self.file and not self.locked_file and bool(self.external_url)

    @property
    def stored_file(self):
        """The field holding the uploaded bytes, whichever side they're on."""
        return self.locked_file if self.locked_file else self.file

    @property
    def download_url(self) -> str:
        """Where the file can be fetched. Locked files go through the gated view;
        unlocked files keep their direct public URL (unchanged)."""
        if self.is_locked:
            return reverse("resource_file_download", args=[self.pk])
        return self.file.url if self.file else self.external_url

    @property
    def image_preview_url(self) -> str | None:
        """URL of an image to render inline under this file, or ``None``.

        Public image files preview themselves (their own bytes). Locked files
        expose only an explicitly-uploaded ``preview_image`` — never their real,
        privately-stored bytes."""
        if self.is_locked:
            return self.preview_image.url if self.preview_image else None
        if self.file_kind == "image":
            if self.file:
                return self.file.url
            if self.is_external:
                return self.external_url
        return None

    @property
    def display_name(self) -> str:
        """The label shown for this file: a given filename, the uploaded file's
        name (public or private storage), else the last path segment of the remote URL."""
        if self.original_filename:
            return self.original_filename
        if self.stored_file:
            return self.stored_file.name
        return self.external_url.rstrip("/").rsplit("/", 1)[-1] or self.external_url

    @property
    def display_byte_size(self):
        """Best-known download size: the recorded ``byte_size``, else the actual
        size of the stored file. ``None`` when neither is available (e.g. a remote
        link without a recorded size)."""
        if self.byte_size:
            return self.byte_size
        try:
            return self.stored_file.size or None
        except (ValueError, OSError):
            return None

    def _reconcile_lock_storage(self):
        """Keep the bytes on the side that matches ``is_locked``.

        Idempotent: only acts when a move is actually needed. External-URL rows
        have no bytes and are left alone.
        """
        if self.is_locked and self.file:
            data = self.file.read()
            name = os.path.basename(self.file.name)
            self.locked_file.save(name, ContentFile(data), save=False)
            self.file.delete(save=False)
        elif not self.is_locked and self.locked_file:
            data = self.locked_file.read()
            name = os.path.basename(self.locked_file.name)
            self.file.save(name, ContentFile(data), save=False)
            self.locked_file.delete(save=False)

    def save(self, *args, **kwargs):
        self._reconcile_lock_storage()
        super().save(*args, **kwargs)
