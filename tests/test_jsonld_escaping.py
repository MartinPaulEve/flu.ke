"""jsonld_dumps must make JSON-LD safe to embed inline without breaking out."""

import json

from apps.core.seo import jsonld_dumps


def test_escapes_script_breakout_sequences():
    payload = {"headline": "</script><script>alert(1)</script>", "x": "a & b", "y": "<!--"}
    out = jsonld_dumps(payload)
    assert "</" not in out
    assert "<script" not in out
    assert "<!--" not in out
    assert "&" not in out  # raw ampersand escaped too


def test_remains_valid_json_and_roundtrips():
    payload = {"headline": "</script>", "name": "Tom & Jerry <fixed>"}
    out = jsonld_dumps(payload)
    assert json.loads(out) == payload  # unicode escapes decode back to the originals
