"""Generate sitemap.xml and robots.txt for the static site."""

from __future__ import annotations

from xml.sax.saxutils import escape


def build_sitemap(url_paths, base_url: str) -> str:
    """Return a sitemap.xml document listing ``base_url`` + each path."""
    base = base_url.rstrip("/")
    entries = "\n".join(
        f"  <url><loc>{escape(base + path)}</loc></url>" for path in url_paths
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )


def build_robots(base_url: str) -> str:
    """Return a robots.txt that allows all and points at the sitemap."""
    base = base_url.rstrip("/")
    return f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n"
