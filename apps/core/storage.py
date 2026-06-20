"""Upload-path helpers for tracked media (kept here so core has no app deps)."""

import os
import uuid

from django.utils.deconstruct import deconstructible


@deconstructible
class uuid_upload_to:
    """An ``upload_to`` callable storing files as ``<folder>/<uuid><ext>``.

    The original (often colliding, often user-supplied) filename is discarded;
    only the lowercased extension is kept. Deconstructible so migrations can
    serialise it by import path + argument.
    """

    def __init__(self, folder):
        self.folder = folder

    def __call__(self, instance, filename):
        ext = os.path.splitext(filename)[1].lower()
        return f"{self.folder}/{uuid.uuid4().hex}{ext}"
