"""Pure HTML cleaning for imported post bodies.

Two jobs, both pure (no IO) so they unit-test easily; the management command
supplies the ``resolver`` that does the media lookups/copies:

* strip WordPress social-share and "Related posts" cruft (Jetpack ``sharedaddy`` /
  ``jp-relatedposts`` blocks and standalone "Tweet This" share-image buttons);
* rewrite ``…/Files/…`` image/link URLs to a local media path when we have the file.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

_SHARE_CLASS_RE = re.compile(
    r"\b(sharedaddy|sd-block|sd-sharing|sd-social|robots-nocontent|"
    r"jp-relatedposts|jp-relatedposts-headline)\b"
)
_SHARE_IMG_RE = re.compile(r"tt-twitter|tweet-this|sharethis|addthis|share-icon", re.I)


def _strip_share_related(soup) -> int:
    removed = 0
    # Whole share/related containers.
    for el in soup.find_all(class_=_SHARE_CLASS_RE):
        if el.parent is not None:
            el.decompose()
            removed += 1
    # "Tweet This"-style image share buttons: drop the link (and an emptied <p>).
    for img in soup.find_all("img", src=_SHARE_IMG_RE):
        target = img.find_parent("a") or img
        wrapper = target.find_parent("p")
        if target.parent is not None:
            target.decompose()
            removed += 1
        if (
            wrapper is not None
            and wrapper.parent is not None
            and not wrapper.get_text(strip=True)
            and not wrapper.find(["img", "a", "iframe"])
        ):
            wrapper.decompose()
    # Standalone "Share this:" heading left behind by other plugins.
    for el in soup.find_all(["h2", "h3", "h4", "p", "strong", "div"]):
        if el.parent is not None and el.get_text(strip=True).lower() in {
            "share this:",
            "share this",
        }:
            el.decompose()
            removed += 1
    return removed


def clean_body_html(html: str, resolver) -> tuple[str, int, int]:
    """Return (cleaned_html, share_blocks_removed, urls_remapped).

    ``resolver(url) -> str | None`` maps a ``…/Files/…`` URL to a local media URL,
    or None to leave it unchanged.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    removed = _strip_share_related(soup)
    remapped = 0
    for tag, attr in (("img", "src"), ("a", "href")):
        for el in soup.find_all(tag):
            url = el.get(attr)
            if url and "/Files/" in url:
                local = resolver(url)
                if local and local != url:
                    el[attr] = local
                    remapped += 1
    return str(soup).strip(), removed, remapped
