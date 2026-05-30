"""Backfill publish dates (and titles) onto UNPUBLISHED posts from a JSON file.

The JSON is a list of ``{"title": ..., "url": ..., "date": "YYYY-MM-DD"}``. Each
entry is matched to unpublished posts by URL path; the first match gets the date
(and, unless --no-titles, the title). Posts are NOT published — review and publish
them yourself. Idempotent; matched posts are flagged ``manually_edited`` so a later
Wayback re-import won't overwrite them.
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.blog.models import Post
from apps.importers.post_metadata import normalize_path


class Command(BaseCommand):
    help = "Backfill publish dates/titles on unpublished posts from a JSON metadata file."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to the JSON metadata file.")
        parser.add_argument("--dry-run", action="store_true", help="Report without writing.")
        parser.add_argument(
            "--no-titles", action="store_true", help="Only set dates; keep existing titles."
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"Metadata file not found: {path}")
        entries = json.loads(path.read_text(encoding="utf-8"))

        # Index unpublished posts by normalized URL path (per the user's instruction,
        # published posts are never touched).
        index = defaultdict(list)
        for post in Post.objects.filter(is_published=False):
            index[normalize_path(post.source_url)].append(post)

        dry_run = options["dry_run"]
        set_titles = not options["no_titles"]
        updated = dated = retitled = unmatched = duplicates = 0
        unmatched_urls = []

        for entry in entries:
            posts = sorted(index.get(normalize_path(entry["url"]), []), key=lambda p: p.pk)
            if not posts:
                unmatched += 1
                unmatched_urls.append(entry["url"])
                continue
            if len(posts) > 1:
                duplicates += 1

            post = posts[0]  # the canonical (earliest) draft for this URL
            when = timezone.make_aware(
                datetime.strptime(entry["date"], "%Y-%m-%d").replace(hour=12)
            )
            changed = []
            if post.published_at != when:
                post.published_at = when
                changed.append("published_at")
                dated += 1
            if set_titles and entry.get("title") and post.title != entry["title"]:
                post.title = entry["title"]
                post.og_image = ""  # regenerate the OG card with the corrected title
                changed += ["title", "og_image"]
                retitled += 1
            if not changed:
                continue
            if not post.manually_edited:
                post.manually_edited = True
                changed.append("manually_edited")
            updated += 1
            if not dry_run:
                post.save(update_fields=changed)

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Updated {updated} posts ({dated} dated, {retitled} retitled). "
                f"{duplicates} matched URLs had duplicates (only the first was updated). "
                f"{unmatched} entries matched no unpublished post."
            )
        )
        for url in unmatched_urls:
            self.stdout.write(f"  no match: {url}")
