"""Create short fading audio samples from a folder of tracks, optionally
uploading them as an Edition's tracklist onto an existing Release.

    manage.py audio_samples ./in ./out
    manage.py audio_samples ./in ./out --upload risotto

Each input file (flac/mp3) yields a 40-second sample taken from the middle of
the track, fading in and out, keeping the source format and metadata (with
"(sample)" appended to the title). The output is named from the metadata. The
sampling itself needs no database. With ``--upload <release-slug>`` the samples
are also attached to a new (unpublished) Edition of that Release for review.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.discography import sampler
from apps.discography.sampler import AUDIO_EXTENSIONS, format_duration, output_filename


class Command(BaseCommand):
    help = "Make 40s fading samples from a folder of audio files (optionally upload as an Edition)."

    def add_arguments(self, parser):
        parser.add_argument("input_dir", help="Folder of source audio files (flac/mp3).")
        parser.add_argument("output_dir", help="Output folder (must NOT already exist).")
        parser.add_argument(
            "--upload",
            metavar="RELEASE_SLUG",
            help="Attach the samples to a new Edition of this Release (held unpublished).",
        )
        parser.add_argument("--length", type=float, default=40.0, help="Sample length, seconds.")
        parser.add_argument("--fade", type=float, default=2.0, help="Fade in/out, seconds.")

    def handle(self, *args, **options):
        input_dir = Path(options["input_dir"])
        output_dir = Path(options["output_dir"])
        if not input_dir.is_dir():
            raise CommandError(f"Input folder {input_dir} does not exist.")
        if output_dir.exists():
            raise CommandError(f"Output folder {output_dir} already exists — pass a new one.")

        files = sorted(
            p for p in input_dir.iterdir() if p.suffix.lower() in AUDIO_EXTENSIONS
        )
        if not files:
            raise CommandError(f"No .flac/.mp3 files found in {input_dir}.")

        output_dir.mkdir(parents=True)
        samples = []  # (meta, output_path), in tracklist order
        for path in files:
            meta = sampler.read_metadata(path)
            out_path = output_dir / output_filename(meta)
            sampler.make_sample(
                path, out_path, meta,
                sample_seconds=options["length"], fade_seconds=options["fade"],
            )
            samples.append((meta, out_path))
            self.stdout.write(f"  {path.name}  ->  {out_path.name}")

        self.stdout.write(
            self.style.SUCCESS(f"Wrote {len(samples)} sample(s) to {output_dir}.")
        )

        if options["upload"]:
            self._upload(options["upload"], samples)

    def _upload(self, slug, samples):
        # Imported here so the command runs offline (no DB) without --upload.
        from django.conf import settings
        from django.core.files import File
        from django.urls import reverse

        from apps.discography.models import Edition, Release, Track

        try:
            release = Release.objects.select_related("artist").get(slug=slug)
        except Release.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(
                    f"!!! No Release with slug {slug!r} — samples were written but NOT uploaded."
                )
            )
            return
        if release.artist_id is None:
            self.stderr.write(
                self.style.ERROR(
                    f"!!! Release {slug!r} has no artist — cannot link. "
                    "Samples were written but NOT uploaded."
                )
            )
            return

        year = next((int(m.year) for m, _ in samples if m.year.isdigit()), None)
        edition = Edition.objects.create(release=release, year=year)
        for order, (meta, out_path) in enumerate(samples):
            track = Track(
                edition=edition,
                name=meta.title,  # the "(sample)" suffix lives only in the file's tags
                track_number=meta.track_number,
                length=format_duration(meta.duration),
                display_order=order,
            )
            with open(out_path, "rb") as handle:
                track.sample.save(out_path.name, File(handle), save=False)
            track.save()

        # Hold the release back so the new edition can be reviewed first.
        release.is_published = False
        release.save(update_fields=["is_published"])

        url = f"{settings.SITE_BASE_URL}{reverse('admin:discography_edition_change', args=[edition.pk])}"
        self.stdout.write(
            self.style.SUCCESS(
                f"Created Edition #{edition.pk} ({len(samples)} track(s)) on "
                f"“{release.name}” by {release.artist.name}; release set to unpublished for review."
            )
        )
        self.stdout.write(self.style.MIGRATE_HEADING(f"Review it here: {url}"))
