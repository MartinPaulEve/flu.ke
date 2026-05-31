"""Give Lyric a unique, URL-friendly slug so it can have its own public page.

Existing rows are backfilled with slugs derived from their titles before the
unique constraint is applied, so the migration is safe on the populated database.
"""

from django.db import migrations, models
from django.utils.text import slugify


def populate_slugs(apps, schema_editor):
    Lyric = apps.get_model("discography", "Lyric")
    seen = set()
    for lyric in Lyric.objects.order_by("pk"):
        base = slugify(lyric.title)[:200] or "item"
        candidate = base
        suffix = 1
        while candidate in seen:
            suffix += 1
            tail = f"-{suffix}"
            candidate = f"{base[: 200 - len(tail)]}{tail}"
        seen.add(candidate)
        lyric.slug = candidate
        lyric.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("discography", "0003_alter_track_sample"),
    ]

    operations = [
        migrations.AddField(
            model_name="lyric",
            name="slug",
            field=models.SlugField(blank=True, default="", max_length=200),
            preserve_default=False,
        ),
        migrations.RunPython(populate_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="lyric",
            name="slug",
            field=models.SlugField(blank=True, max_length=200, unique=True),
        ),
    ]
