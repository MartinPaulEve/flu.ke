"""Zero-pad existing bare track numbers ("1".."9" → "01".."09", "A1" → "A01").

Going forward Track.save() normalises new values; this fixes the data already in
the database. Idempotent — re-running changes nothing.
"""

from django.db import migrations

from apps.core.text import normalize_track_number


def forwards(apps, schema_editor):
    Track = apps.get_model("discography", "Track")
    for pk, number in Track.objects.exclude(track_number="").values_list("pk", "track_number"):
        normalized = normalize_track_number(number)
        if normalized != number:
            Track.objects.filter(pk=pk).update(track_number=normalized)


class Migration(migrations.Migration):
    dependencies = [("discography", "0014_track_artist")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
