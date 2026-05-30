"""Upload-path helpers for discography media.

Files keep no trace of their original (often colliding) names: each upload is
stored under a random UUID, preserving only the lowercased extension.
"""

import os
import uuid

from django.utils.deconstruct import deconstructible


@deconstructible
class uuid_upload_to:
    """An ``upload_to`` callable storing files as ``<folder>/<uuid><ext>``.

    Implemented as a deconstructible callable so Django's migration
    serialiser can reconstruct it by import path and argument.
    """

    def __init__(self, folder):
        self.folder = folder

    def __call__(self, instance, filename):
        ext = os.path.splitext(filename)[1].lower()
        return f"{self.folder}/{uuid.uuid4().hex}{ext}"
