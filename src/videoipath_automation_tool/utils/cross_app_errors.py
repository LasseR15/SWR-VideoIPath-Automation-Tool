from typing import Any


class GeneralApiError(Exception):
    """Base class for all API errors."""


class ApiHttpError(GeneralApiError):
    """An HTTP response was rejected before an app could process its body."""

    def __init__(
        self,
        *,
        method: str,
        url: str,
        status_code: int,
        reason: str,
        response_body: Any = None,
    ) -> None:
        self.method = method
        self.url = url
        self.status_code = status_code
        self.reason = reason
        self.response_body = response_body
        super().__init__(f"{method} request to '{url}' failed with HTTP {status_code}: {reason}")


class ApiResponseError(GeneralApiError):
    """A transport succeeded but VideoIPath reported an unsuccessful response header."""

    def __init__(self, path: str, code: str, messages: list[str], details: Any = None) -> None:
        self.path = path
        self.code = code
        self.messages = messages
        self.details = details
        message = "; ".join(messages) or code
        super().__init__(f"API request to '{path}' failed: {message}")


class ApiMalformedResponseError(GeneralApiError):
    """A successful API response did not contain the expected response shape."""

    def __init__(self, path: tuple[str, ...], expected: str) -> None:
        self.path = path
        self.expected = expected
        super().__init__(f"Malformed API response at '{'/'.join(path)}': expected {expected}.")


class ApiQueryTooLongError(GeneralApiError):
    """A request path exceeds the configured URI length limit.

    Callers may provide an app-specific recovery suggestion without coupling this
    shared exception to a particular endpoint or loading strategy.
    """

    def __init__(self, length: int, limit: int, suggestion: str | None = None) -> None:
        self.length = length
        self.limit = limit
        self.suggestion = suggestion
        message = f"Request path is {length} characters, exceeding the {limit}-character limit."
        if suggestion:
            message = f"{message} {suggestion}"
        super().__init__(message)


class ApiEntityNotFoundError(GeneralApiError):
    """A device, vertex, edge, ... referenced by a read or write does not exist on the server."""

    def __init__(self, entity_id: str, kind: str = "entity") -> None:
        self.entity_id = entity_id
        self.kind = kind
        super().__init__(f"API {kind} '{entity_id}' was not found on the server.")


class ApiCommitError(GeneralApiError):
    """An API commit was rejected."""


class ApiCommitConflict:
    """One entity whose server state changed between staging and commit."""

    def __init__(self, entity_id: str, kind: str, field_diffs: dict[str, tuple[object, object]]) -> None:
        self.entity_id = entity_id
        self.kind = kind
        # field -> (staged_baseline_value, current_server_value)
        self.field_diffs = field_diffs

    def __repr__(self) -> str:
        return f"ApiConflict(entity_id={self.entity_id!r}, kind={self.kind!r}, fields={list(self.field_diffs)})"


class ApiCommitConflictError(GeneralApiError):
    """A concurrent modification was detected before a write was sent; nothing was written.

    Callers can inspect ``conflicts``, refresh their baseline, and retry. Apps may optionally
    expose an explicit ``check_conflicts=False`` override for last-writer-wins behavior.
    """

    def __init__(self, conflicts: list[ApiCommitConflict]) -> None:
        self.conflicts = conflicts
        ids = ", ".join(c.entity_id for c in conflicts)
        super().__init__(
            f"Concurrent modification detected for {len(conflicts)} entity(ies) [{ids}]; commit aborted. "
            f"Refresh the baseline and retry, or explicitly override conflict checking."
        )
