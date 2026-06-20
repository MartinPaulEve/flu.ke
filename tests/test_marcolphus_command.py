"""import_marcolphus management-command tests (filename argument, dry-run)."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.discography.models import Artist, Release, Track

pytestmark = pytest.mark.django_db

DOC = """\
::: Remixes :::
------------------------------------------------------------------------------

   [Horse: Celebrate]
        [on same]
           12": 1992 UK (MCA/Oxygen; GASPT 11)
                 6:10   Celebrate (magimix)
                 6:29   Celebrate (moulimix)
"""


def _write(tmp_path, text=DOC):
    path = tmp_path / "marcolphus.txt"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_command_imports_from_named_txt_file(tmp_path):
    call_command("import_marcolphus", _write(tmp_path))
    horse = Release.objects.get(name="Celebrate")
    assert horse.artist.name == "Horse"
    fluke = Artist.objects.get(name="Fluke")
    assert fluke in Track.objects.get(mix_info="magimix").remixers.all()


def test_command_missing_file_raises(tmp_path):
    with pytest.raises(CommandError):
        call_command("import_marcolphus", str(tmp_path / "nope.txt"))


def test_dry_run_writes_nothing_but_reports(tmp_path, capsys):
    call_command("import_marcolphus", _write(tmp_path), "--dry-run")
    assert Release.objects.count() == 0
    out = capsys.readouterr().out
    assert "Would import" in out
    assert "Celebrate" in out  # the change detail is printed
