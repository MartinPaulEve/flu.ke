"""Edition summary line: name/media lead plus media · year · label · cat number."""

import pytest

from apps.discography.models import Artist, Edition, Release, ReleaseType

pytestmark = pytest.mark.django_db


def _edition(**kw):
    # Slugs auto-generate uniquely, so this helper can be called several times
    # within one test without colliding.
    fluke = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    rel = Release.objects.create(
        name="Risotto", artist=fluke, type=rtype, year=1997, is_published=True
    )
    return Edition.objects.create(release=rel, **kw)


def test_summary_lead_is_the_name_when_present():
    assert _edition(name="Deluxe", media="2xLP").summary_lead == "Deluxe"


def test_summary_lead_falls_back_to_media_then_catalogue_then_generic():
    assert _edition(media="2xLP", catalogue_number="ABC").summary_lead == "2xLP"
    assert _edition(catalogue_number="ABC").summary_lead == "ABC"
    assert _edition().summary_lead == "Edition"


def test_summary_meta_lists_year_label_cat_without_repeating_the_media_lead():
    e = _edition(media="2xLP", year=2026, record_label="Astralwerks", catalogue_number="ASW-1")
    # Lead is the media, so it isn't repeated in the meta pieces.
    assert e.summary_meta == ["2026", "Astralwerks", "ASW-1"]


def test_summary_meta_includes_media_when_a_name_is_the_lead():
    e = _edition(
        name="Deluxe", media="2xLP", year=2026, record_label="WEA", catalogue_number="X1"
    )
    assert e.summary_meta == ["2xLP", "2026", "WEA", "X1"]


def test_release_page_shows_label_and_catalogue_in_the_summary(client):
    e = _edition(media="2xLP", year=2026, record_label="Astralwerks", catalogue_number="ASW-1")

    html = client.get(e.release.get_absolute_url()).content.decode()
    summary = html.split("<summary>")[1].split("</summary>")[0]

    assert "Astralwerks" in summary
    assert "ASW-1" in summary
    assert "2xLP" in summary


def test_summary_groups_name_and_meta_in_one_block(client):
    """Regression: the name and the meta pieces share a single ``edition__info``
    container so they flow/wrap as one text block. When each meta piece was its
    own flex child of <summary> it got squeezed to ~1ch wide on mobile and its
    text stacked vertically (unreadable)."""
    e = _edition(name="Deluxe", media="2xLP", year=2026, record_label="Astralwerks")
    html = client.get(e.release.get_absolute_url()).content.decode()
    summary = html.split("<summary>")[1].split("</summary>")[0]

    # The wrapper opens before, and so contains, both the name and the meta pieces.
    assert summary.index('class="edition__info"') < summary.index('itemprop="name"')
    assert summary.index('itemprop="name"') < summary.index('class="entry__meta"')
