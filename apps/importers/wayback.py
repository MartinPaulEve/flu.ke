"""Best-effort recovery of old blog posts from the Wayback Machine.

No WordPress database survived, so post text is reconstructed from archived HTML.
Parsing/classification here is pure (testable without network); the import_blog
command does the CDX query and snapshot fetches.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from bs4 import BeautifulSoup
from django.utils import timezone

# Paths that are clearly not individual posts.
_REJECT = re.compile(
    r"(/feed|/category/|/tag/|/author/|/page/|wp-content|wp-admin|wp-includes|"
    r"xmlrpc|/comments|\.(xml|css|js|jpg|jpeg|png|gif|ico|php))",
    re.IGNORECASE,
)


@dataclass
class RecoveredPost:
    title: str
    body: str
    published_at: datetime | None
    source_url: str
    import_confidence: str  # "complete" | "partial" | "stub"


def is_post_candidate(url: str) -> bool:
    """True if a captured URL looks like an individual post permalink."""
    from urllib.parse import urlsplit

    path = urlsplit(url).path
    if not path or path == "/":
        return False
    return not _REJECT.search(path)


def _parse_date(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = timezone.make_aware(parsed)
    return parsed


def _title(soup):
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()
    for selector in ("h1.entry-title", "h2.entrytitle", ".posttitle", "h1.posttitle"):
        element = soup.select_one(selector)
        if element and element.get_text(strip=True):
            return element.get_text(strip=True)
    if soup.title and soup.title.string:
        text = soup.title.string
        for separator in (" | ", " — ", " - "):
            if separator in text:
                text = text.split(separator)[0]
        return text.strip()
    return ""


def _body(soup):
    for selector in (".entry-content", ".entry", ".post-content", ".post", "article", "main"):
        element = soup.select_one(selector)
        if element:
            inner = element.decode_contents().strip()
            if inner:
                return inner
    return ""


def _date(soup):
    meta = soup.find("meta", property="article:published_time")
    if meta and meta.get("content"):
        return _parse_date(meta["content"])
    time_el = soup.find("time", datetime=True)
    if time_el:
        return _parse_date(time_el["datetime"])
    published = soup.select_one("abbr.published, .published")
    if published:
        return _parse_date(published.get("title") or published.get_text(strip=True))
    return None


def recover_post(html: str, source_url: str) -> RecoveredPost:
    """Extract a post (title, body, date, confidence) from archived HTML."""
    soup = BeautifulSoup(html, "lxml")
    title = _title(soup)
    body = _body(soup)
    published_at = _date(soup)

    if title and body and published_at:
        confidence = "complete"
    elif title and body:
        confidence = "partial"
    else:
        confidence = "stub"

    return RecoveredPost(
        title=title,
        body=body,
        published_at=published_at,
        source_url=source_url,
        import_confidence=confidence,
    )


def snapshot_url(timestamp: str, original: str) -> str:
    """Raw (un-rewritten) Wayback capture URL for an original page."""
    return f"https://web.archive.org/web/{timestamp}id_/{original}"


def cdx_url(domain: str) -> str:
    """Wayback CDX API query for all 200-status captures under a domain."""
    return (
        "https://web.archive.org/cdx/search/cdx?"
        f"url={domain}*&output=json&fl=timestamp,original&"
        "filter=statuscode:200&filter=mimetype:text/html&collapse=urlkey"
    )
