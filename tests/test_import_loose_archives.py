"""Behavioural tests for the import_loose_archives command.

Exercises the three guarantees in isolation against a throwaway Ingest tree and
seeded ResourceFiles: backup exclusion, straggler import, dedupe, publish, and
idempotency. Nothing here touches the real 30 GB Ingest tree.
"""

import pytest
from django.core.management import call_command
from django.test import override_settings

from apps.resources.management.commands.import_loose_archives import prettify_title
from apps.resources.models import Resource, ResourceFile

pytestmark = pytest.mark.django_db


# -- fixtures / helpers ----------------------------------------------------


def _make_public_html(root):
    """A tmp public_html/ with two content archives plus a backup to exclude."""
    pub = root / "public_html"
    pub.mkdir(parents=True)
    (pub / "Fatal-Occupied.zip").write_bytes(b"PK-fatal-occupied-archive")
    (pub / "X-Files.zip").write_bytes(b"PK-x-files-archive")
    (pub / "2bitpie.zip").write_bytes(b"PK-huge-site-backup")
    # A nested Files/ tree should be ignored by the straggler step (import_media
    # owns that); only loose top-level zips are stragglers here.
    files = pub / "Files"
    files.mkdir()
    (files / "Buried.zip").write_bytes(b"PK-nested-not-a-straggler")
    return pub


def _run(public_html, media_root, dry_run=False):
    with override_settings(MEDIA_ROOT=str(media_root)):
        call_command(
            "import_loose_archives",
            public_html=str(public_html),
            dry_run=dry_run,
        )


def _seed_archive(file_name, original_filename, published=False, title="seed"):
    """Create a Resource + archive ResourceFile pointing at ``file_name``."""
    resource = Resource.objects.create(title=title, is_published=published)
    return ResourceFile.objects.create(
        resource=resource,
        file=file_name,
        original_filename=original_filename,
        file_kind="archive",
    )


# -- prettify_title --------------------------------------------------------


def test_prettify_title_replaces_separators_and_strips_extension():
    assert prettify_title("Fluke-Live_At_Waserwerk-2002.zip") == "Fluke Live At Waserwerk 2002"


def test_prettify_title_handles_no_extension():
    assert prettify_title("Some_Set") == "Some Set"


def test_prettify_title_does_not_crash_on_empty():
    # Odd input must not raise; any string result is acceptable.
    assert isinstance(prettify_title(""), str)


# -- step 1: import stragglers ---------------------------------------------


def test_imports_loose_stragglers_as_published_resources(tmp_path):
    pub = _make_public_html(tmp_path)
    media_root = tmp_path / "media"

    _run(pub, media_root)

    names = set(ResourceFile.objects.values_list("original_filename", flat=True))
    assert "Fatal-Occupied.zip" in names
    assert "X-Files.zip" in names
    for of in ("Fatal-Occupied.zip", "X-Files.zip"):
        rf = ResourceFile.objects.get(original_filename=of)
        assert rf.resource.is_published is True
        assert rf.file_kind == "archive"


def test_straggler_files_are_copied_into_media_resources(tmp_path):
    pub = _make_public_html(tmp_path)
    media_root = tmp_path / "media"

    _run(pub, media_root)

    assert (media_root / "resources" / "Fatal-Occupied.zip").exists()
    assert (media_root / "resources" / "X-Files.zip").exists()


def test_straggler_resourcefile_records_size_mime_and_checksum(tmp_path):
    pub = _make_public_html(tmp_path)
    media_root = tmp_path / "media"

    _run(pub, media_root)

    rf = ResourceFile.objects.get(original_filename="Fatal-Occupied.zip")
    assert rf.byte_size == len(b"PK-fatal-occupied-archive")
    assert len(rf.checksum) == 64
    assert rf.mime_type  # zip has a known mime type


def test_backup_zip_is_never_imported(tmp_path):
    pub = _make_public_html(tmp_path)
    media_root = tmp_path / "media"

    _run(pub, media_root)

    assert not ResourceFile.objects.filter(original_filename="2bitpie.zip").exists()
    assert not (media_root / "resources" / "2bitpie.zip").exists()


def test_nested_files_archives_are_not_treated_as_stragglers(tmp_path):
    pub = _make_public_html(tmp_path)
    media_root = tmp_path / "media"

    _run(pub, media_root)

    assert not ResourceFile.objects.filter(original_filename="Buried.zip").exists()


def test_straggler_import_skips_when_already_present(tmp_path):
    pub = _make_public_html(tmp_path)
    media_root = tmp_path / "media"
    # Pretend X-Files was already imported under a different original name but
    # the same checksum-bearing record by filename.
    _seed_archive("resources/X-Files.zip", "X-Files.zip", published=True)
    before = ResourceFile.objects.filter(original_filename="X-Files.zip").count()

    _run(pub, media_root)

    after = ResourceFile.objects.filter(original_filename="X-Files.zip").count()
    assert after == before  # not duplicated


def test_dry_run_imports_nothing(tmp_path):
    pub = _make_public_html(tmp_path)
    media_root = tmp_path / "media"

    _run(pub, media_root, dry_run=True)

    assert not ResourceFile.objects.filter(original_filename="Fatal-Occupied.zip").exists()
    assert not (media_root / "resources" / "Fatal-Occupied.zip").exists()


# -- step 2: dedupe --------------------------------------------------------


def test_dedupe_keeps_one_record_per_shared_media_file(tmp_path):
    pub = _make_public_html(tmp_path)
    media_root = tmp_path / "media"
    _seed_archive("resources/Set.zip", "Set.zip")
    _seed_archive("resources/Set.zip", "Files/Set.zip")

    _run(pub, media_root)

    remaining = ResourceFile.objects.filter(file="resources/Set.zip")
    assert remaining.count() == 1
    assert Resource.objects.filter(files__file="resources/Set.zip").distinct().count() == 1


def test_dedupe_prefers_the_non_files_prefixed_original(tmp_path):
    pub = _make_public_html(tmp_path)
    media_root = tmp_path / "media"
    _seed_archive("resources/Set.zip", "Set.zip")
    _seed_archive("resources/Set.zip", "Files/Set.zip")

    _run(pub, media_root)

    survivor = ResourceFile.objects.get(file="resources/Set.zip")
    assert survivor.original_filename == "Set.zip"


def test_dedupe_does_not_delete_the_shared_media_file(tmp_path):
    pub = _make_public_html(tmp_path)
    media_root = tmp_path / "media"
    (media_root / "resources").mkdir(parents=True)
    shared = media_root / "resources" / "Set.zip"
    shared.write_bytes(b"the-actual-archive-bytes")
    _seed_archive("resources/Set.zip", "Set.zip")
    _seed_archive("resources/Set.zip", "Files/Set.zip")

    _run(pub, media_root)

    assert shared.exists()  # kept record still needs it


def test_dedupe_leaves_unique_files_untouched(tmp_path):
    pub = _make_public_html(tmp_path)
    media_root = tmp_path / "media"
    _seed_archive("resources/Unique.zip", "Unique.zip")

    _run(pub, media_root)

    assert ResourceFile.objects.filter(file="resources/Unique.zip").count() == 1


# -- step 3: publish -------------------------------------------------------


def test_publish_flips_unpublished_archive_resources(tmp_path):
    pub = _make_public_html(tmp_path)
    media_root = tmp_path / "media"
    rf = _seed_archive("resources/Hidden.zip", "Hidden.zip", published=False)

    _run(pub, media_root)

    rf.resource.refresh_from_db()
    assert rf.resource.is_published is True


def test_dry_run_does_not_publish_or_dedupe(tmp_path):
    pub = _make_public_html(tmp_path)
    media_root = tmp_path / "media"
    rf = _seed_archive("resources/Set.zip", "Set.zip", published=False)
    _seed_archive("resources/Set.zip", "Files/Set.zip", published=False)

    _run(pub, media_root, dry_run=True)

    rf.resource.refresh_from_db()
    assert rf.resource.is_published is False
    assert ResourceFile.objects.filter(file="resources/Set.zip").count() == 2


# -- idempotency -----------------------------------------------------------


def test_full_rerun_is_a_no_op(tmp_path):
    pub = _make_public_html(tmp_path)
    media_root = tmp_path / "media"
    _seed_archive("resources/Set.zip", "Set.zip")
    _seed_archive("resources/Set.zip", "Files/Set.zip")

    _run(pub, media_root)
    resources_after_first = Resource.objects.count()
    files_after_first = ResourceFile.objects.count()

    _run(pub, media_root)

    assert Resource.objects.count() == resources_after_first
    assert ResourceFile.objects.count() == files_after_first
