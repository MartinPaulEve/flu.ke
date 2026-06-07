"""Pure helpers for rewriting links in blog content."""

import re

# Absolute (or protocol-relative) links to the retired 2bitpie.net domain, with an
# optional path/query/fragment captured so it can be kept as a site-relative URL.
_OLD_DOMAIN = re.compile(
    r"""(?:https?:)?//(?:www\.)?2bitpie\.net(/[^\s"'<>]*)?""",
    re.IGNORECASE,
)


def relativize_2bitpie_links(text):
    """Rewrite absolute 2bitpie.net links in ``text`` to site-relative paths.

    ``https://www.2bitpie.net/news/x/`` -> ``/news/x/``; a bare domain becomes
    ``/``. Other domains are left untouched. Empty/None input is returned as-is.
    """
    if not text:
        return text
    return _OLD_DOMAIN.sub(lambda match: match.group(1) or "/", text)
