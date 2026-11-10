"""Typed exceptions for the Inspect app.

The Inspect surface has semantics that a raw HTTP envelope cannot express:
commit success is a three-flag check, concurrent writes are
detected client-side, and over-long projection URLs are
rejected by the proxy before they reach the server. These exceptions carry the
structured detail callers need to react without parsing raw responses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from videoipath_automation_tool.utils.cross_app_errors import GeneralApiError

if TYPE_CHECKING:
    pass


class InspectError(GeneralApiError):
    """Base class for all Inspect app errors."""


__all__ = [
    "InspectError",
]
