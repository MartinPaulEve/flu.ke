"""The site's favicon is referenced in the page head."""

import pytest

pytestmark = pytest.mark.django_db


def test_favicon_links_in_head(client):
    html = client.get("/").content.decode()
    assert 'rel="icon"' in html
    assert "favicon.svg" in html
    assert "apple-touch-icon" in html
