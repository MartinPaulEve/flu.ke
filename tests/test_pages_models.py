import pytest

from apps.pages.models import Page

pytestmark = pytest.mark.django_db


def test_page_get_absolute_url():
    page = Page.objects.create(title="About")
    assert page.get_absolute_url() == "/about/"


def test_page_published_manager_excludes_drafts():
    Page.objects.create(title="Live", is_published=True)
    Page.objects.create(title="Draft", is_published=False)
    titles = set(Page.objects.published().values_list("title", flat=True))
    assert titles == {"Live"}
