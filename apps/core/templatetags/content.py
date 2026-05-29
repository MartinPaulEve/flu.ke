"""Template filters for rendering editor-authored content."""

import markdown as md
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def markdownify(text):
    """Render trusted, editor-authored Markdown to HTML.

    Content comes from authenticated CMS editors (not untrusted users), so the
    output is marked safe without HTML sanitising.
    """
    return mark_safe(md.markdown(text or "", extensions=["extra"]))
