"""Reconcile blog posts against the comprehensive Wayback list.

For each entry ({title, url, date}) it keeps ONE canonical post per URL (preferring
an already-published one, else the earliest), sets the correct title and date, and
deletes the redundant *unpublished* duplicate rows. With --prune-junk it also
deletes unpublished posts whose URL isn't a real post (left over from the broad
Wayback import). Published posts are never deleted. Idempotent; supports --dry-run.
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
    help = "Dedupe posts and set proper titles/dates from a comprehensive JSON list."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--prune-junk",
            action="store_true",
            help="Also delete unpublished posts whose URL isn't in the list.",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"Metadata file not found: {path}")
        entries = json.loads(path.read_text(encoding="utf-8"))
        dry_run = options["dry_run"]

        index = defaultdict(list)
        for post in Post.objects.all():
            index[normalize_path(post.source_url)].append(post)
        scraped_paths = {normalize_path(e["url"]) for e in entries}

        updated = created = deleted = pruned = 0

        for entry in entries:
            key = normalize_path(entry["url"])
            when = timezone.make_aware(
                datetime.strptime(entry["date"], "%Y-%m-%d").replace(hour=12)
            )
            candidates = index.get(key, [])
            if not candidates:
                created += 1
                if not dry_run:
                    Post.objects.create(
                        title=entry["title"],
                        source_url=entry["url"],
                        published_at=when,
                        is_published=False,
                        manually_edited=True,
                        import_confidence="complete",
                    )
                continue

            # Canonical: a published post wins, otherwise the earliest row.
            ordered = sorted(candidates, key=lambda p: (not p.is_published, p.pk))
            canonical = ordered[0]
            self._update(canonical, entry["title"], when, dry_run)
            updated += 1
            for extra in ordered[1:]:
                if extra.is_published:
                    continue  # never delete a published post
                deleted += 1
                if not dry_run:
                    extra.delete()

        if options["prune_junk"]:
            for key, posts in index.items():
                if key in scraped_paths:
                    continue
                for post in posts:
                    if post.is_published:
                        continue
                    pruned += 1
                    if not dry_run:
                        post.delete()

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Reconciled {updated} posts ({created} created), "
                f"deleted {deleted} duplicates, pruned {pruned} junk posts."
            )
        )

    @staticmethod
    def _update(post, title, when, dry_run):
        # Use a bulk .update() (not .save()) so we don't trigger OG-image
        # regeneration / media writes during a pure data fix. OG cards can be
        # regenerated separately once the title is settled.
        fields = {}
        if title and post.title != title:
            fields["title"] = title
        if post.published_at != when:
            fields["published_at"] = when
        if post.import_confidence != "complete":
            fields["import_confidence"] = "complete"
        if not post.manually_edited:
            fields["manually_edited"] = True
        if fields and not dry_run:
            Post.objects.filter(pk=post.pk).update(**fields)
