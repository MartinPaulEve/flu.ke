"""Discography models.

Mirrors the proven hierarchy of the old "Djiscography" app
(ReleaseType -> Release -> Edition -> Track, plus Artist), with three fixes:

* ``Track.remixer`` is optional (the old model wrongly required it);
* lyrics attach to tracks through a real FK and are de-duplicated per song
  (the old model matched by free-text track name, which silently lost data);
* covers and samples are local ``FileField``/``ImageField`` storage rather than
  dead remote URLs, since we host all media on-site.

Fluke is the canonical primary act; 2 Bit Pie, Lucky Monkeys, Syntax, Yuki and
Fatal are modelled as aliases that point at it via ``Artist.primary_artist``.
"""

from django.db import models

from apps.core.models import (
    PublishableQuerySet,
    SeoFieldsMixin,
    SluggedModel,
    TimeStampedModel,
)

# The canonical primary act. Any release by an artist other than this one is
# rendered with the artist name in parentheses (see Release.display_title).
PRIMARY_ARTIST_NAME = "Fluke"


class ReleaseType(models.Model):
    """A discography section, e.g. Albums / Live Albums / Best Ofs / Singles."""

    name = models.CharField(max_length=200)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "release type"

    def __str__(self):
        return self.name


class Artist(SluggedModel, TimeStampedModel):
    slug_source_field = "name"

    name = models.CharField(max_length=200)
    biography = models.TextField(blank=True)
    is_alias = models.BooleanField(
        default=False, help_text="True for a Fluke alias / side-project."
    )
    primary_artist = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="aliases",
        help_text="For an alias, the primary act it belongs to (usually Fluke).",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def canonical(self):
        """Return the primary act this artist represents (self if not an alias)."""
        if self.is_alias and self.primary_artist_id:
            return self.primary_artist
        return self

    def get_absolute_url(self):
        return f"/discography/{self.slug}/"


class Release(SluggedModel, SeoFieldsMixin, TimeStampedModel):
    slug_source_field = "name"

    name = models.CharField(max_length=200)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="releases")
    year = models.IntegerField(null=True, blank=True)
    type = models.ForeignKey(ReleaseType, on_delete=models.PROTECT, related_name="releases")
    order = models.IntegerField(default=0)
    purchase_link = models.URLField(blank=True)
    mbid = models.UUIDField(null=True, blank=True, help_text="MusicBrainz release-group id.")
    is_published = models.BooleanField(default=True)

    objects = PublishableQuerySet.as_manager()

    class Meta:
        ordering = ["-year", "order", "name"]

    def __str__(self):
        return f"{self.year or '????'} – {self.artist.name} – {self.name}"

    def get_absolute_url(self):
        return f"/discography/{self.artist.slug}/{self.slug}/"

    @property
    def display_title(self):
        """Release name, suffixed with the artist unless the artist is Fluke."""
        return (
            f"{self.name} ({self.artist.name})"
            if self.artist.name != PRIMARY_ARTIST_NAME
            else self.name
        )


class Edition(TimeStampedModel):
    """A specific physical/digital version of a release (CD, vinyl, promo, …)."""

    release = models.ForeignKey(Release, on_delete=models.CASCADE, related_name="editions")
    name = models.CharField(max_length=200, blank=True)
    catalogue_number = models.CharField(max_length=200, blank=True)
    record_label = models.CharField(max_length=200, blank=True)
    year = models.IntegerField(null=True, blank=True)
    media = models.CharField(max_length=100, blank=True, help_text="e.g. CD, 2xCD, Vinyl, CD-R.")
    purchase_link = models.URLField(blank=True)
    display_order = models.IntegerField(default=0)
    mbid = models.UUIDField(null=True, blank=True, help_text="MusicBrainz release id.")

    class Meta:
        ordering = ["display_order", "-year", "catalogue_number"]

    def __str__(self):
        bits = [self.name or self.release.name]
        if self.catalogue_number:
            bits.append(self.catalogue_number)
        return " – ".join(bits)


class Lyric(TimeStampedModel):
    """Lyrics for a song, shared by every track that performs it (de-duplicated)."""

    title = models.CharField(max_length=300)
    artist = models.ForeignKey(
        Artist, null=True, blank=True, on_delete=models.SET_NULL, related_name="lyrics"
    )
    lyrics = models.TextField(blank=True)
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class Track(TimeStampedModel):
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE, related_name="tracks")
    name = models.CharField(max_length=300)
    track_number = models.CharField(max_length=20, blank=True)
    mix_info = models.CharField(
        max_length=200, blank=True, help_text="e.g. Instrumental, Radio Edit."
    )
    remixer = models.ForeignKey(
        Artist, null=True, blank=True, on_delete=models.SET_NULL, related_name="remixes"
    )
    length = models.CharField(max_length=20, blank=True, help_text="m:ss")
    sample = models.FileField(upload_to="samples/", blank=True)
    sample_source_url = models.URLField(blank=True)
    lyric = models.ForeignKey(
        Lyric, null=True, blank=True, on_delete=models.SET_NULL, related_name="tracks"
    )
    display_order = models.IntegerField(default=0)
    mbid = models.UUIDField(null=True, blank=True)
    recording_mbid = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["display_order", "track_number"]

    def __str__(self):
        return f"{self.track_number} {self.display_title}".strip()

    @property
    def display_title(self):
        """Track title with its mix qualifier, e.g. 'Blue (Instrumental)'."""
        if self.mix_info:
            return f"{self.name} ({self.mix_info})"
        return self.name


class CoverImage(TimeStampedModel):
    KIND_FRONT = "front"
    KIND_CHOICES = [
        (KIND_FRONT, "Front"),
        ("back", "Back"),
        ("cd", "CD"),
        ("inlay", "Inlay"),
        ("booklet", "Booklet"),
        ("other", "Other"),
    ]

    edition = models.ForeignKey(Edition, on_delete=models.CASCADE, related_name="covers")
    display_name = models.CharField(max_length=100, blank=True)
    image = models.ImageField(upload_to="covers/", blank=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="other")
    alt_text = models.CharField(max_length=300, blank=True)
    source_url = models.URLField(blank=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"{self.edition} [{self.display_name or self.kind}]"
