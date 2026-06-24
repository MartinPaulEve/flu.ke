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
