"""Unit tests for the renderer helpers (output mapping, fingerprint, tree sync)."""

import pytest

from apps.staticgen.renderer import fingerprint, output_path_for, sync_tree


@pytest.mark.parametrize(
    "url_path,expected",
    [
        ("/", "index.html"),
        ("/news/", "news/index.html"),
        ("/news/2009/dark-like-snow/", "news/2009/dark-like-snow/index.html"),
        ("/discography/fluke/risotto/", "discography/fluke/risotto/index.html"),
        ("/sitemap.xml", "sitemap.xml"),
        ("/robots.txt", "robots.txt"),
    ],
)
def test_output_path_for(url_path, expected):
    assert output_path_for(url_path) == expected


def test_fingerprint_is_stable_and_sensitive():
    a = fingerprint("base.html", ["post"], "<p>hello</p>")
    assert a == fingerprint("base.html", ["post"], "<p>hello</p>")
    assert a != fingerprint("base.html", ["post"], "<p>changed</p>")
    assert a != fingerprint("other.html", ["post"], "<p>hello</p>")


def test_sync_tree_copies_then_skips_unchanged(tmp_path):
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "a.txt").write_bytes(b"alpha")
    (src / "sub" / "b.txt").write_bytes(b"beta")
    dest = tmp_path / "dest"

    assert sync_tree(src, dest) == 2
    assert (dest / "a.txt").read_bytes() == b"alpha"
    assert (dest / "sub" / "b.txt").read_bytes() == b"beta"

    # nothing changed -> nothing copied
    assert sync_tree(src, dest) == 0


def test_sync_tree_recopies_changed_file(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_bytes(b"alpha")
    dest = tmp_path / "dest"
    sync_tree(src, dest)

    (src / "a.txt").write_bytes(b"alpha-but-longer")  # size differs
    assert sync_tree(src, dest) == 1
    assert (dest / "a.txt").read_bytes() == b"alpha-but-longer"
