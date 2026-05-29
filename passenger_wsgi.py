"""Passenger entrypoint for cPanel hosts (e.g. Reclaim Hosting).

cPanel's "Setup Python App" looks for an ``application`` callable in this file.
We just delegate to the project's WSGI application.
"""

import os
import sys

# Ensure the project root is importable regardless of Passenger's working dir.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.wsgi import application  # noqa: E402,F401  (Passenger reads `application`)
