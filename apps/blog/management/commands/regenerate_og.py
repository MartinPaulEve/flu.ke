"""Regenerate Open Graph card images for all public content.

Covers every model with SEO fields (posts, pages, resources, releases, artists,
lyrics) — discovered dynamically, so new content types are picked up too. Each
model's ``og_card()`` decides the card (e.g. releases composite their cover art),
so run this after a bulk title change or after importing cover media to refresh
the cards. Overwrites existing images in place rather than accumulating files;
``--missing-only`` fills only objects that have no image yet.
"""

from django.apps import apps as django_apps
from django.core.management.base import BaseCommand

from apps.core.models import SeoFieldsMixin


class Command(BaseCommand):
    help = "Regenerate Open Graph images for all content (posts, pages, resources, releases, artists, lyrics)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--missing-only",
            action="store_true",
            help="Only generate for objects that have no OG image yet.",
        )

    def handle(self, *args, **options):
        missing_only = options["missing_only"]
        models = sorted(
            (m for m in django_apps.get_models() if issubclass(m, SeoFieldsMixin)),
            key=lambda m: m._meta.label,
        )
        total = 0
        for model in models:
            count = 0
            for obj in model.objects.all():
                if missing_only and obj.og_image:
                    continue
                if not missing_only:
                    obj.og_image.delete(save=False)  # drop the stale file, don't accumulate
                    obj.og_image = ""
                if obj.ensure_og_image():
                    obj.save(update_fields=["og_image"])
                    count += 1
            if count:
                self.stdout.write(f"  {model._meta.label}: {count}")
            total += count
        self.stdout.write(self.style.SUCCESS(f"Regenerated {total} OG images."))
