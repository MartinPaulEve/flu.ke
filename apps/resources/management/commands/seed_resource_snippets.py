"""Pre-seed the per-resource ``snippet`` explanation from existing metadata.

Idempotent: by default only fills resources whose snippet is empty. ``--force``
overwrites every snippet; ``--dry-run`` reports the plan without writing.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.resources.models import Resource, build_snippet


class Command(BaseCommand):
    help = "Generate a one-line snippet explanation for resources from their metadata."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing snippets instead of only filling empty ones.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        dry_run = options["dry_run"]

        resources = Resource.objects.all().prefetch_related("files").select_related(
            "subcategory", "artist"
        )

        seeded = 0
        skipped = 0
        for resource in resources:
            if resource.snippet and not force:
                skipped += 1
                continue

            new_snippet = build_snippet(resource)
            if new_snippet == resource.snippet:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f"[dry-run] {resource.title!r} -> {new_snippet!r}")
                seeded += 1
                continue

            resource.snippet = new_snippet
            resource.save(update_fields=["snippet"])
            seeded += 1

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Seeded {seeded} snippet(s); left {skipped} unchanged."
            )
        )
