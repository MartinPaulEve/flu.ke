"""Template tags for linking public pages to their Django admin counterparts.

``admin_change_url`` resolves the admin change page for a model instance, and
``admin_changelist_url`` resolves the admin changelist for a model class or
instance. Both return "" if the URL cannot be reversed (e.g. the model isn't
registered in the admin) so a missing registration never 500s a public page.

The module is named ``editlinks`` (not ``admin_urls``) so it doesn't shadow
Django's built-in ``django.contrib.admin.templatetags.admin_urls`` library.
"""

from __future__ import annotations

from django import template
from django.urls import NoReverseMatch, reverse

register = template.Library()


@register.simple_tag
def admin_change_url(obj):
    """Return the admin change URL for ``obj`` (a model instance), or ""."""
    if obj is None:
        return ""
    meta = obj._meta
    try:
        return reverse(f"admin:{meta.app_label}_{meta.model_name}_change", args=[obj.pk])
    except NoReverseMatch:
        return ""


@register.simple_tag
def admin_changelist_url(model):
    """Return the admin changelist URL for ``model`` (class or instance), or ""."""
    if model is None:
        return ""
    meta = model._meta
    try:
        return reverse(f"admin:{meta.app_label}_{meta.model_name}_changelist")
    except NoReverseMatch:
        return ""
