"""Build an RSS 2.0 feed for the blog."""

from __future__ import annotations

from email.utils import format_datetime
from xml.sax.saxutils import escape


def build_feed(posts, base_url: str, site_name: str) -> str:
    """Return an RSS 2.0 document for the given (published, dated) posts."""
    base = base_url.rstrip("/")
    items = []
    for post in posts:
        link = f"{base}{post.get_absolute_url()}"
        parts = [
            f"<title>{escape(post.title)}</title>",
            f"<link>{escape(link)}</link>",
            f"<guid>{escape(link)}</guid>",
        ]
        if post.published_at:
            parts.append(f"<pubDate>{format_datetime(post.published_at)}</pubDate>")
        if post.excerpt:
            parts.append(f"<description>{escape(post.excerpt)}</description>")
        items.append("    <item>" + "".join(parts) + "</item>")
    body = "\n".join(items)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n  <channel>\n'
        f"    <title>{escape(site_name)}</title>\n"
        f"    <link>{escape(base)}/news/</link>\n"
        f"    <description>{escape(site_name)} — latest news</description>\n"
        f"{body}\n"
        "  </channel>\n</rss>\n"
    )
