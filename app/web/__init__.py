"""Server rendered pages.

All HTML lives under ``/ui`` (plus ``/`` which redirects there) so the JSON API
at ``/users`` and ``/health`` keeps working untouched.
"""

from __future__ import annotations

from .forms import csrf_protect, generate_csrf_token
from .views import ui_bp

__all__ = ["ui_bp", "csrf_protect", "generate_csrf_token"]
