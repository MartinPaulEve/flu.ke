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
from apps.core.text import normalize_track_number
from apps.discography.storage import uuid_upload_to

# The canonical primary act. Any release by an artist other than this one is
# rendered with the artist name in parentheses (see Release.display_title).
PRIMARY_ARTIST_NAME = "Fluke"

# A "Various Artists" release groups tracks by many artists; it is never itself
# shown as a track's performing artist (see Track.display_artist).
VARIOUS_ARTISTS_NAME = "Various Artists"


class ReleaseType(models.Model):
    """A discography section, e.g. Albums / Live Albums / Best Ofs / Singles."""

    name = models.CharField(max_length=200)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "release type"

    def __str__(self):
        return self.name


class Artist(SluggedModel, SeoFieldsMixin, TimeStampedModel):
    slug_source_field = "name"
    reserved_slugs = frozenset({"api"})

    name = models.CharField(max_length=200)
    biography = models.TextField(blank=True)
    is_alias = models.BooleanField(
        default=False, help_text="True for a Fluke alias / side-project."
    )
    is_person = models.BooleanField(
        default=False,
        verbose_name="Is a person",
        help_text="An individual person (schema.org Person) rather than a band/"
        "group (MusicGroup). Affects the structured-data type in markup.",
    )
    primary_artist = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="aliases",
        help_text="For an alias, the primary act it belongs to (usually Fluke).",
    )
    appears_on_homepage = models.BooleanField(
        default=False,
        help_text="Show in the homepage hero list of aliases & other projects "
        "(Fluke always leads, regardless of this).",
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

    @property
    def schema_type(self) -> str:
        """schema.org type: 'Person' for an individual, else 'MusicGroup'."""
        return "Person" if self.is_person else "MusicGroup"

    def get_absolute_url(self):
        return f"/discography/{self.slug}/"

    def og_card(self):
        return (self.name, "Alias" if self.is_alias else "Artist", None)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.ensure_og_image():
            super().save(update_fields=["og_image"])


class Release(SluggedModel, SeoFieldsMixin, TimeStampedModel):
    slug_source_field = "name"
    reserved_slugs = frozenset({"api"})

    name = models.CharField(max_length=200)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="releases")
    year = models.IntegerField(null=True, blank=True)
    type = models.ForeignKey(ReleaseType, on_delete=models.PROTECT, related_name="releases")
    order = models.IntegerField(default=0)
    purchase_link = models.URLField(blank=True)
    mbid = models.UUIDField(null=True, blank=True, help_text="MusicBrainz release-group id.")
    is_published = models.BooleanField(default=True)
    featured_artists = models.ManyToManyField(
        Artist,
        blank=True,
        related_name="featured_on",
        help_text="Guest/featured artists, shown as “(feat. …)” after the title.",
    )
    additional_artists = models.ManyToManyField(
        Artist,
        blank=True,
        related_name="additional_releases",
        help_text=(
            "Other acts credited alongside the primary artist (e.g. a “vs.” "
            "collaboration). Shown comma-separated after the primary artist; the "
            "primary artist still owns the URL and grouping."
        ),
    )
    hide_artist_list = models.BooleanField(
        default=False,
        verbose_name="Do not display additional artist list on discography page",
        help_text="Drop the '(artist, …)' suffix after the title on the discography listing.",
    )

    objects = PublishableQuerySet.as_manager()

    class Meta:
        ordering = ["-year", "order", "name"]

    def __str__(self):
        return f"{self.year or '????'} – {self.artist.name} – {self.name}"

    def get_absolute_url(self):
        return f"/discography/{self.artist.slug}/{self.slug}/"

    @property
    def featured_credit(self):
        """'feat. …' credit for the featured artists, or '' when there are none."""
        names = list(self.featured_artists.order_by("name").values_list("name", flat=True))
        if not names:
            return ""
        joined = names[0] if len(names) == 1 else f"{', '.join(names[:-1])} & {names[-1]}"
        return f"feat. {joined}"

    @property
    def display_name(self):
        """Release name with a '(feat. …)' suffix when featured artists are credited."""
        credit = self.featured_credit
        return f"{self.name} ({credit})" if credit else self.name

    @property
    def all_artists(self):
        """Primary artist followed by any additional artists, de-duplicated.

        Fluke is never listed as an *additional* (secondary) credit: this is a
        Fluke site, so crediting Fluke alongside the act whose release it is would
        be redundant. Fluke as the *primary* artist is unaffected.
        """
        artists = [self.artist] if self.artist_id else []
        seen = {a.pk for a in artists}
        for extra in self.additional_artists.all():
            if extra.pk not in seen and extra.name != PRIMARY_ARTIST_NAME:
                artists.append(extra)
                seen.add(extra.pk)
        return artists

    @property
    def artists_display(self):
        """Comma-separated names of every credited artist."""
        return ", ".join(a.name for a in self.all_artists)

    @property
    def display_title(self):
        """Display name, suffixed with the credited artist(s) unless that's just Fluke
        (or the release opts out via ``hide_artist_list``)."""
        names = self.artists_display
        if self.hide_artist_list or names == PRIMARY_ARTIST_NAME:
            return self.display_name
        return f"{self.display_name} ({names})"

    def resolved_seo_title(self):
        # Fold the (feat. …) credit into the page/OG title (an explicit seo_title wins).
        return self.seo_title or self.display_name

    def og_card(self):
        subtitle = self.artists_display
        if self.year:
            subtitle = f"{subtitle} · {self.year}".strip(" ·")
        return (self.display_name, subtitle, self._og_cover_bytes())

    def _og_cover_bytes(self):
        """Front cover image bytes for the OG card (any cover if no front), or None."""
        covers = CoverImage.objects.filter(edition__release=self).exclude(image="")
        cover = covers.filter(kind=CoverImage.KIND_FRONT).first() or covers.first()
        if not cover or not cover.image:
            return None
        try:
            with cover.image.open("rb") as fh:
                return fh.read()
        except (FileNotFoundError, OSError, ValueError):
            return None

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.ensure_og_image():
            super().save(update_fields=["og_image"])


class Edition(TimeStampedModel):
    """A specific physical/digital version of a release (CD, vinyl, promo, …)."""

    release = models.ForeignKey(Release, on_delete=models.CASCADE, related_name="editions")
    name = models.CharField(max_length=200, blank=True)
    catalogue_number = models.CharField(max_length=200, blank=True)
    record_label = models.CharField(max_length=200, blank=True)
    year = models.IntegerField(null=True, blank=True)
    media = models.CharField(max_length=100, blank=True, help_text="e.g. CD, 2xCD, Vinyl, CD-R.")
    notes = models.TextField(
        blank=True,
        help_text="Rich text (HTML), edited with TinyMCE. A few words about this specific "
        "edition (e.g. how rare it is, the source for the entry). Shown under the edition "
        "heading when expanded.",
    )
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

    @property
    def summary_lead(self) -> str:
        """The headline for the edition row: its name, else media, else cat#."""
        return self.name or self.media or self.catalogue_number or "Edition"

    @property
    def summary_meta(self) -> list[str]:
        """Secondary summary pieces shown inline after the lead, in order:
        media, year, record label, catalogue number — minus whatever is already
        the lead, and without duplicates."""
        lead = self.summary_lead
        out: list[str] = []
        for value in (self.media, self.year, self.record_label, self.catalogue_number):
            text = str(value).strip() if value not in (None, "") else ""
            if text and text != lead and text not in out:
                out.append(text)
        return out


class Lyric(SluggedModel, SeoFieldsMixin, TimeStampedModel):
    """Lyrics for a song, shared by every track that performs it (de-duplicated)."""

    slug_source_field = "title"

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

    def get_absolute_url(self):
        return f"/lyrics/{self.slug}/"

    def og_card(self):
        subtitle = f"Lyrics · {self.artist.name}" if self.artist_id else "Lyrics"
        return (self.title, subtitle, None)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.ensure_og_image():
            super().save(update_fields=["og_image"])


class Track(TimeStampedModel):
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE, related_name="tracks")
    name = models.CharField(max_length=300)
    artist = models.ForeignKey(
        Artist,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="performed_tracks",
        help_text="Performing artist for this track (useful on Various Artists comps). "
        "Blank inherits the release's artist; that inherited artist isn't repeated on "
        "each track, and “Various Artists” is never shown.",
    )
    track_number = models.CharField(max_length=20, blank=True)
    mix_info = models.CharField(
        max_length=200, blank=True, help_text="e.g. Instrumental, Radio Edit."
    )
    remixers = models.ManyToManyField(
        Artist,
        blank=True,
        related_name="remixed_tracks",
        help_text="Artist(s) who remixed this track.",
    )
    length = models.CharField(max_length=20, blank=True, help_text="m:ss")
    sample = models.FileField(upload_to=uuid_upload_to("samples"), blank=True)
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

    def save(self, *args, **kwargs):
        # Silently enforce zero-padded track numbers ("1" → "01", "A1" → "A01").
        self.track_number = normalize_track_number(self.track_number)
        super().save(*args, **kwargs)

    @property
    def display_title(self):
        """Track title with its mix qualifier, e.g. 'Blue (Instrumental)'."""
        if self.mix_info:
            return f"{self.name} ({self.mix_info})"
        return self.name

    @property
    def display_artist(self):
        """The artist to show for this track, or ``None`` to show none.

        An explicitly-set track artist is shown; otherwise the track inherits its
        release's artist, which the heading already shows, so it isn't repeated.
        “Various Artists” is never shown as a track artist.
        """
        release = self.edition.release
        artist = self.artist or (release.artist if release else None)
        if artist is None or artist.name == VARIOUS_ARTISTS_NAME:
            return None
        if self.artist_id is None and artist.pk == release.artist_id:
            return None  # inherited the release's own artist — already in the heading
        return artist


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
