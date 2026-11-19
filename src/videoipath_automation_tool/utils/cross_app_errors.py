
class GeneralApiError(Exception):
    """Base class for all API errors."""


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
    """A concurrent modification was detected before the commit was sent; nothing was written.

    The commit is aborted as a whole (matching the server's all-or-nothing apply). Callers can
    inspect ``conflicts``, then either ``transaction.rebase()`` onto fresh state and retry, or
    re-commit with ``check_conflicts=False`` to force last-writer-wins.
    """

    def __init__(self, conflicts: list[ApiCommitConflict]) -> None:
        self.conflicts = conflicts
        ids = ", ".join(c.entity_id for c in conflicts)
        super().__init__(
            f"Concurrent modification detected for {len(conflicts)} entity(ies) [{ids}]; commit aborted. "
            f"Rebase the transaction or commit with check_conflicts=False to override."
        )
