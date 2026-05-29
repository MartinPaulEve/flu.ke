"""Best-effort blog recovery from the Wayback Machine.

Queries the CDX API for captures under a domain, fetches the raw snapshot for each
likely post permalink, and upserts a Post. Posts already edited by hand are never
overwritten. Complete recoveries are published; partial/stub ones stay drafts for
editorial review.
"""

import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.blog.models import Post
from apps.importers.wayback import cdx_url, is_post_candidate, recover_post, snapshot_url


class Command(BaseCommand):
    help = "Recover blog posts from the Wayback Machine (best effort)."

    def add_arguments(self, parser):
        parser.add_argument("--domain", default="2bitpie.net")
        parser.add_argument("--limit", type=int, default=300)
        parser.add_argument("--delay", type=float, default=1.0, help="Politeness delay (s).")
        parser.add_argument("--timeout", type=float, default=30.0)

    def handle(self, *args, **options):
        session = requests.Session()
        session.headers["User-Agent"] = f"{settings.SITE_NAME}-cms blog recovery"

        rows = session.get(cdx_url(options["domain"]), timeout=options["timeout"]).json()
        candidates = []
        seen = set()
        for row in rows[1:]:  # row[0] is the header
            timestamp, original = row[0], row[1]
            if not is_post_candidate(original) or original in seen:
                continue
            seen.add(original)
            candidates.append((timestamp, original))

        created = updated = skipped = failed = 0
        for timestamp, original in candidates[: options["limit"]]:
            existing = Post.objects.filter(source_url=original).first()
            if existing and existing.manually_edited:
                skipped += 1
                continue
            try:
                response = session.get(snapshot_url(timestamp, original), timeout=options["timeout"])
            except requests.RequestException:
                failed += 1
                continue
            if response.status_code != 200:
                failed += 1
                continue

            recovered = recover_post(response.text, original)
            if not recovered.title:
                failed += 1
                continue

            published = recovered.import_confidence == "complete"
            if existing:
                existing.title = recovered.title
                existing.body = recovered.body
                existing.published_at = recovered.published_at
                existing.import_confidence = recovered.import_confidence
                existing.is_published = published
                existing.save()
                updated += 1
            else:
                Post.objects.create(
                    title=recovered.title,
                    body=recovered.body,
                    published_at=recovered.published_at,
                    is_published=published,
                    source_url=recovered.source_url,
                    import_confidence=recovered.import_confidence,
                )
                created += 1

            if options["delay"]:
                time.sleep(options["delay"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Recovered: {created} created, {updated} updated, "
                f"{skipped} protected, {failed} failed of {len(candidates)} candidates."
            )
        )
