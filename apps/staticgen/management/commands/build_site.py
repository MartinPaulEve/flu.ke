"""Render the whole public site to static files under ``BUILD_DIR``.

This is the "Publish" action: the private CMS edits content in the database, and
this command renders every route to HTML, copies the static and media trees, and
writes sitemap.xml / robots.txt. The output directory is the deployable site.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

from apps.staticgen.models import BuildState
from apps.staticgen.renderer import (
    fingerprint,
    load_manifest,
    output_path_for,
    save_manifest,
    sync_tree,
)
from apps.staticgen.routes import iter_routes
from apps.staticgen.sitemap import build_robots, build_sitemap

MANIFEST_NAME = ".buildmanifest.json"


def base_context() -> dict:
    """Site-wide template context, injected into every route."""
    return {"site_name": settings.SITE_NAME, "site_base_url": settings.SITE_BASE_URL}


class Command(BaseCommand):
    help = "Render the public site to static files in BUILD_DIR."

    def add_arguments(self, parser):
        parser.add_argument("--full", action="store_true", help="Rebuild every page, ignoring the manifest.")
        parser.add_argument("--clean", action="store_true", help="Delete BUILD_DIR first (implies --full).")
        parser.add_argument("--no-media", action="store_true", help="Skip syncing the media tree.")

    def handle(self, *args, **options):
        build_dir = Path(settings.BUILD_DIR)
        full = options["full"] or options["clean"]

        if options["clean"] and build_dir.exists():
            import shutil

            shutil.rmtree(build_dir)
        build_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = build_dir / MANIFEST_NAME
        manifest = {} if full else load_manifest(manifest_path)
        new_manifest: dict = {}

        rendered = 0
        skipped = 0
        url_paths = []
        base = base_context()

        for route in iter_routes():
            url_paths.append(route.url_path)
            context = {**base, **route.context}
            html = render_to_string(route.template, context)
            out = output_path_for(route.url_path)
            fp = fingerprint(route.template, route.context.keys(), html)
            new_manifest[out] = fp
            if manifest.get(out) == fp:
                skipped += 1
                continue
            target = build_dir / out
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(html, encoding="utf-8")
            rendered += 1

        # Non-HTML outputs (always written; cheap).
        from apps.blog.models import Post
        from apps.staticgen.feeds import build_feed

        (build_dir / "sitemap.xml").write_text(
            build_sitemap(url_paths, settings.SITE_BASE_URL), encoding="utf-8"
        )
        (build_dir / "robots.txt").write_text(
            build_robots(settings.SITE_BASE_URL), encoding="utf-8"
        )
        (build_dir / "feed.xml").write_text(
            build_feed(list(Post.objects.published()), settings.SITE_BASE_URL, settings.SITE_NAME),
            encoding="utf-8",
        )

        # Static assets.
        static_copied = 0
        for static_dir in settings.STATICFILES_DIRS:
            static_copied += sync_tree(Path(static_dir), build_dir / "static")

        # Media library.
        media_copied = 0
        if not options["no_media"]:
            media_copied = sync_tree(Path(settings.MEDIA_ROOT), build_dir / "media")

        save_manifest(manifest_path, new_manifest)
        BuildState.mark_built()
        self.stdout.write(
            self.style.SUCCESS(
                f"Built {rendered} pages ({skipped} unchanged) into {build_dir}. "
                f"Synced {static_copied} static and {media_copied} media files."
            )
        )
