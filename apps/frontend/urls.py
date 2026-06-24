"""Public site URLs.

Specific routes come first; the ``/<slug>/`` CMS-page catch-all is last so it
never shadows the section indexes or detail pages.
"""

from django.contrib.sitemaps.views import sitemap
from django.urls import path

from apps.frontend import views
from apps.frontend.feeds import LatestPostsFeed
from apps.frontend.sitemaps import sitemaps

urlpatterns = [
    path("", views.landing, name="landing"),
    path("news/", views.post_list, name="post_list"),
    path("news/category/<slug:slug>/", views.post_category, name="post_category"),
    path("news/<int:year>/<slug:slug>/", views.post_detail, name="post_detail"),
    path("discography/", views.discography_index, name="discography_index"),
    path("discography/<slug:artist_slug>/", views.artist_detail, name="artist_detail"),
    path(
        "discography/<slug:artist_slug>/<slug:release_slug>/",
        views.release_detail,
        name="release_detail",
    ),
    path("lyrics/", views.lyric_index, name="lyric_index"),
    path("lyrics/<slug:slug>/", views.lyric_detail, name="lyric_detail"),
    path("resources/", views.resource_list, name="resource_list"),
    path(
        "resources/file/<int:pk>/download/",
        views.resource_file_download,
        name="resource_file_download",
    ),
    path(
        "resources/<slug:kind>/<slug:slug>/",
        views.resource_detail,
        name="resource_detail",
    ),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("feed.xml", LatestPostsFeed(), name="feed"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    # CMS-page catch-all MUST be last.
    path("<slug:slug>/", views.page_detail, name="page_detail"),
]
