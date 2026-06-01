"""Behavioural tests for the staff-only "Edit this page" footer link.

The public site is served live by Django and shares the admin session, so a
logged-in staff user browsing a public page has ``request.user.is_staff`` and
should see an "Edit this page" link in the footer pointing at the relevant
Django admin change page (for detail pages) or changelist (for list pages).
Anonymous and non-staff visitors must see none of this.

These tests assert on behaviour: the presence/absence of the link and the href
it resolves to. They do not depend on view internals or template structure.
"""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.blog.models import Category, Post
from apps.discography.models import Artist, Lyric, Release, ReleaseType
from apps.frontend.templatetags.editlinks import (
    admin_change_url,
    admin_changelist_url,
)
from apps.pages.models import Page
from apps.resources.models import KIND_FAN, KIND_OFFICIAL, Resource

pytestmark = pytest.mark.django_db

EDIT_LINK_TEXT = "Edit this page"
ADMIN_FALLBACK_TEXT = "Edit in admin"


@pytest.fixture
def seeded():
    """Minimal published content covering the page types under test."""
    fluke = Artist.objects.create(name="Fluke")
    rtype = ReleaseType.objects.create(name="Albums")
    release = Release.objects.create(
        name="Risotto", artist=fluke, type=rtype, year=1997, is_published=True
    )
    category = Category.objects.create(name="Releases")
    post = Post.objects.create(
        title="Hello World",
        excerpt="An announcement",
        is_published=True,
        published_at=timezone.now(),
    )
    post.categories.add(category)
    official = Resource.objects.create(
        title="Live Set", kind=KIND_OFFICIAL, is_published=True
    )
    Resource.objects.create(title="Fan Remix", kind=KIND_FAN, is_published=True)
    page = Page.objects.create(title="About", body="All about us", is_published=True)
    lyric = Lyric.objects.create(
        title="You Got Me", artist=fluke, lyrics="You got me, baby"
    )
    return {
        "fluke": fluke,
        "release": release,
        "category": category,
        "post": post,
        "official": official,
        "page": page,
        "lyric": lyric,
    }


@pytest.fixture
def staff_client(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="editor", password="x", is_staff=True
    )
    client.force_login(user)
    return client


# --- Template tags -------------------------------------------------------


def test_admin_change_url_returns_reverse_for_instance(seeded):
    post = seeded["post"]
    expected = reverse("admin:blog_post_change", args=[post.pk])
    assert admin_change_url(post) == expected
    assert f"/admin/blog/post/{post.pk}/change/" == admin_change_url(post)


def test_admin_changelist_url_accepts_model_class():
    expected = reverse("admin:resources_resource_changelist")
    assert admin_changelist_url(Resource) == expected
    assert admin_changelist_url(Resource) == "/admin/resources/resource/"


def test_admin_changelist_url_accepts_instance(seeded):
    expected = reverse("admin:discography_release_changelist")
    assert admin_changelist_url(seeded["release"]) == expected


def test_admin_change_url_returns_empty_string_when_unreversible():
    class NotRegistered:
        class _meta:
            app_label = "nope"
            model_name = "nope"

        pk = 1

    assert admin_change_url(NotRegistered()) == ""


def test_admin_changelist_url_returns_empty_string_when_unreversible():
    class NotRegistered:
        class _meta:
            app_label = "nope"
            model_name = "nope"

    assert admin_changelist_url(NotRegistered) == ""


# --- Detail pages: staff sees a change-URL "Edit this page" link ---------


def test_post_detail_shows_edit_link_to_admin_change_for_staff(staff_client, seeded):
    post = seeded["post"]
    response = staff_client.get(post.get_absolute_url())
    body = response.content.decode()
    assert EDIT_LINK_TEXT in body
    assert f'href="/admin/blog/post/{post.pk}/change/"' in body


def test_release_detail_shows_edit_link_to_admin_change_for_staff(
    staff_client, seeded
):
    release = seeded["release"]
    response = staff_client.get(release.get_absolute_url())
    body = response.content.decode()
    assert EDIT_LINK_TEXT in body
    assert f'href="/admin/discography/release/{release.pk}/change/"' in body


def test_page_detail_shows_edit_link_to_admin_change_for_staff(staff_client, seeded):
    page = seeded["page"]
    response = staff_client.get(page.get_absolute_url())
    body = response.content.decode()
    assert EDIT_LINK_TEXT in body
    assert f'href="/admin/pages/page/{page.pk}/change/"' in body


# --- List pages: staff sees a changelist "Edit this page" link -----------


def test_resource_list_shows_edit_link_to_changelist_for_staff(staff_client, seeded):
    response = staff_client.get("/resources/")
    body = response.content.decode()
    assert EDIT_LINK_TEXT in body
    assert 'href="/admin/resources/resource/"' in body


def test_news_list_shows_edit_link_to_changelist_for_staff(staff_client, seeded):
    response = staff_client.get("/news/")
    body = response.content.decode()
    assert EDIT_LINK_TEXT in body
    assert 'href="/admin/blog/post/"' in body


def test_landing_shows_admin_fallback_link_for_staff(staff_client, seeded):
    response = staff_client.get("/")
    body = response.content.decode()
    assert ADMIN_FALLBACK_TEXT in body
    assert 'href="/admin/"' in body


# --- Anonymous / non-staff: nothing at all -------------------------------


def test_anonymous_post_detail_has_no_edit_link(client, seeded):
    response = client.get(seeded["post"].get_absolute_url())
    body = response.content.decode()
    assert EDIT_LINK_TEXT not in body
    assert ADMIN_FALLBACK_TEXT not in body


def test_anonymous_resource_list_has_no_edit_link(client, seeded):
    response = client.get("/resources/")
    body = response.content.decode()
    assert EDIT_LINK_TEXT not in body
    assert ADMIN_FALLBACK_TEXT not in body


def test_anonymous_landing_has_no_admin_link(client, seeded):
    response = client.get("/")
    body = response.content.decode()
    assert EDIT_LINK_TEXT not in body
    assert ADMIN_FALLBACK_TEXT not in body


def test_non_staff_user_post_detail_has_no_edit_link(client, django_user_model, seeded):
    user = django_user_model.objects.create_user(
        username="reader", password="x", is_staff=False
    )
    client.force_login(user)
    response = client.get(seeded["post"].get_absolute_url())
    body = response.content.decode()
    assert EDIT_LINK_TEXT not in body
    assert ADMIN_FALLBACK_TEXT not in body
