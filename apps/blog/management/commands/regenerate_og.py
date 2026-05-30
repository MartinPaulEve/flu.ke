"""Regenerate blog post Open Graph images from their current titles.

Needed after a bulk title change (e.g. reconcile_posts) that updated titles
without re-rendering the OG cards. Overwrites the existing image rather than
accumulating files. --missing-only fills only posts without an image.
"""

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.blog.models import Post
from apps.blog.og import render_og_image


class Command(BaseCommand):
    help = "Regenerate Open Graph images for blog posts from their current titles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--missing-only",
            action="store_true",
            help="Only generate for posts that have no OG image yet.",
        )

    def handle(self, *args, **options):
        missing_only = options["missing_only"]
        count = 0
        for post in Post.objects.all():
            if missing_only and post.og_image:
                continue
            if not post.title:
                continue
            data = render_og_image(post.title)
            post.og_image.delete(save=False)  # drop the stale file, don't accumulate
            post.og_image.save(f"{post.pk}.png", ContentFile(data), save=False)
            post.save(update_fields=["og_image"])
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Regenerated {count} OG images."))
