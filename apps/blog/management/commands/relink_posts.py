"""Rewrite hard-coded 2bitpie.net links in posts to site-relative paths.

Imported posts carry absolute links to the retired 2bitpie.net domain. This
rewrites them in post bodies and excerpts to site-relative paths (e.g.
``https://www.2bitpie.net/news/x/`` -> ``/news/x/``) so they resolve on fluke.fm
and any other host. Idempotent; ``--dry-run`` reports what would change without
saving.
"""

from django.core.management.base import BaseCommand

from apps.blog.links import relativize_2bitpie_links
from apps.blog.models import Post


class Command(BaseCommand):
    help = "Rewrite 2bitpie.net links in posts to site-relative paths."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without saving.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        changed = 0
        for post in Post.objects.all():
            new_body = relativize_2bitpie_links(post.body)
            new_excerpt = relativize_2bitpie_links(post.excerpt)
            if new_body == post.body and new_excerpt == post.excerpt:
                continue
            changed += 1
            if not dry_run:
                post.body = new_body
                post.excerpt = new_excerpt
                post.save(update_fields=["body", "excerpt"])
        verb = "Would rewrite" if dry_run else "Rewrote"
        self.stdout.write(self.style.SUCCESS(f"{verb} 2bitpie.net links in {changed} post(s)."))
