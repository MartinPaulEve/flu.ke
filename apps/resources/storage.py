"""Storage for locked resource files, kept outside the nginx-served MEDIA_ROOT.

Locked files live under ``settings.PRIVATE_MEDIA_ROOT`` — a directory the public
web server never sees — so they can only be fetched through the gated download
view, never by a direct URL. Location and base_url are read live (not cached via
the parent's ``cached_property``) so tests can point them at a throwaway dir.
"""

import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateMediaStorage(FileSystemStorage):
    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        # No public URL: these files are streamed, never linked directly.
        return None


private_storage = PrivateMediaStorage()
