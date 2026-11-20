from __future__ import annotations

from typing import Any

from videoipath_automation_tool.utils.cross_app_errors import GeneralApiError


class UacError(GeneralApiError):
    """Base class for User Access Control errors."""


class UacEntityNotFoundError(UacError):
    """A UAC entity could not be found."""

    def __init__(self, entity_id: str, kind: str) -> None:
        self.entity_id = entity_id
        self.kind = kind
        super().__init__(f"UAC {kind} '{entity_id}' was not found.")


class UacRevisionConflictError(UacError):
    """The UAC entity was modified after it was read."""

    def __init__(self, entity_id: str, kind: str, expected: str, actual: str) -> None:
        self.entity_id = entity_id
        self.kind = kind
        self.expected = expected
        self.actual = actual
        super().__init__(f"UAC {kind} '{entity_id}' has revision '{expected}', but revision '{actual}' was supplied.")


class UacRequestError(UacError):
    """A UAC action was rejected by VideoIPath."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: Any = None,
        status_code: int | None = None,
    ) -> None:
        self.code = code
        self.details = details
        self.status_code = status_code
        super().__init__(message)


__all__ = [
    "UacEntityNotFoundError",
    "UacError",
    "UacRequestError",
    "UacRevisionConflictError",
]
