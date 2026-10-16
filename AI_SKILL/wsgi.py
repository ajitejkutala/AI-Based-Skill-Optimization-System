"""
WSGI entry for hosts that expect ``wsgi:application`` (e.g. some PaaS panels).

Prefer ``main:app`` or the Procfile command when your platform allows it.
"""

from main import app as application
