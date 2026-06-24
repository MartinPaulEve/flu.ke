"""Optional print-article metadata on resources (magazine/journal interviews)."""

import datetime

import pytest

from apps.resources.models import Resource

pytestmark = pytest.mark.django_db


def test_print_fields_blank_by_default():
    r = Resource.objects.create(title="Just a file", kind="official")
    assert r.article_authors == ""
    assert r.publication_title == ""
    assert r.article_date is None
    assert r.has_print_metadata is False


def test_has_print_metadata_true_when_any_field_set():
    r = Resource.objects.create(title="Interview", publication_title="Mixmag")
    assert r.has_print_metadata is True


def test_article_date_display_respects_month_precision():
    r = Resource.objects.create(
        title="Interview",
        article_date=datetime.date(2005, 6, 1),
        article_date_precision="month",
    )
    assert r.article_date_display == "Jun 2005"
    assert "1" not in r.article_date_display.replace("2005", "")


def test_admin_form_parses_partial_article_date():
    from apps.resources.forms import ResourceAdminForm

    form = ResourceAdminForm(
        data={
            "title": "Interview",
            "kind": "official",
            "slug": "interview",
            "recorded": "",
            "article_date_input": "2005-06",
            "recorded_precision": "day",
            "uploaded_at": "2024-01-01 00:00:00",
        }
    )
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert obj.article_date == datetime.date(2005, 6, 1)
    assert obj.article_date_precision == "month"


def test_detail_shows_print_block_when_populated(client):
    r = Resource.objects.create(
        title="Interview",
        kind="official",
        is_published=True,
        publication_title="Mixmag",
        article_authors="Jane Smith",
        page_numbers="pp. 34–37",
    )
    html = client.get(r.get_absolute_url()).content.decode()
    assert "Mixmag" in html
    assert "Jane Smith" in html
    assert "pp. 34" in html


def test_detail_hides_print_block_when_empty(client):
    r = Resource.objects.create(title="Plain", kind="official", is_published=True)
    html = client.get(r.get_absolute_url()).content.decode()
    assert "Print article" not in html
