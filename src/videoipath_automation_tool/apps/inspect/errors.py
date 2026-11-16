"""Typed exceptions for the Inspect app.

The Inspect surface has semantics that a raw HTTP envelope cannot express:
commit success is a three-flag check, concurrent writes are
detected client-side, and over-long projection URLs are
rejected by the proxy before they reach the server. These exceptions carry the
structured detail callers need to react without parsing raw responses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from videoipath_automation_tool.utils.cross_app_errors import GeneralApiError, ApiCommitError


if TYPE_CHECKING:
    from videoipath_automation_tool.apps import InspectApiUpdateTopologyResponse


class InspectError(GeneralApiError):
    """Base class for all Inspect app errors."""


class InspectCommitError(ApiCommitError, InspectError):
    """A commit failed (validation gate or apply gate).

    HTTP/envelope success is not commit success: the server can return ``header.ok == true``
    while ``data.res.ok`` or ``data.validation.result.ok`` is ``false``. This carries the full
    typed response so callers can inspect ``validation.details`` and ``res.msg``.
    """

    def __init__(self, response: "InspectApiUpdateTopologyResponse") -> None:
        self.response = response
        self.result = response.data.res
        self.validation = response.data.validation
        messages = list(self.result.msg) + list(self.validation.result.msg)
        detail = "; ".join(m for m in messages if m) or "commit rejected by the server"
        super().__init__(f"API commit failed: {detail}")


__all__ = [
    "InspectError",
    "InspectCommitError",
]
