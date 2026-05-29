"""Behavioural tests for importing the parsed snapshot into the database."""

from pathlib import Path

import pytest
from django.core.management import call_command

from apps.discography.models import Artist, CoverImage, Edition, Release, Track

pytestmark = pytest.mark.django_db

FIXTURE = Path(__file__).parent / "fixtures" / "discography_snippet.html"


def _import():
    call_command("import_discography", file=str(FIXTURE))


def test_import_creates_releases_editions_tracks():
    _import()
    assert set(Release.objects.values_list("name", flat=True)) == {"Dark Like Snow", "Fly"}
    dls = Release.objects.get(name="Dark Like Snow")
    assert dls.editions.count() == 2
    assert dls.year == 2009
    assert Track.objects.filter(edition__release=dls).count() == 3


def test_import_marks_release_artists_as_aliases_of_fluke():
    _import()
    fluke = Artist.objects.get(name="Fluke")
    assert fluke.is_alias is False
    yuki = Artist.objects.get(name="Yuki")
    assert yuki.is_alias is True
    assert yuki.primary_artist == fluke


def test_import_does_not_mark_external_remixers_as_aliases():
    _import()
    myagi = Artist.objects.get(name="Myagi")
    assert myagi.is_alias is False
    fly = Track.objects.get(name="Fly", edition__name="")
    assert fly.remixer == myagi


def test_import_attaches_lyrics_by_song_title():
    _import()
    you_got_me = Track.objects.get(name="You Got Me")
    assert you_got_me.lyric is not None
    assert you_got_me.lyric.title == "You Got Me"


def test_import_records_cover_metadata():
    _import()
    dls_promo = Edition.objects.get(release__name="Dark Like Snow", name="Promo")
    fronts = dls_promo.covers.filter(kind="front")
    assert fronts.count() == 1
    assert fronts.first().alt_text  # accessible alt text populated
    assert fronts.first().source_url.endswith("DarklikesnowFront.jpg")


def test_import_is_idempotent():
    _import()
    _import()
    assert Release.objects.count() == 2
    assert Edition.objects.count() == 4
    assert Track.objects.count() == 5  # DLS: 2 + 1 instrumental; Fly: 1 + 1 promo
    assert CoverImage.objects.count() == 4  # 3 on DLS promo + 1 on Fly CD
