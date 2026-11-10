from videoipath_automation_tool.apps import InspectApiUpdateTopologyResponse


class GeneralApiError(Exception):
    """Base class for all API errors."""


class ApiQueryTooLongError(GeneralApiError):
    """A scoped collector query URL exceeds the server/proxy URI length limit (HTTP 414).

    The lib trims its skeleton projections to stay within the limit; this is
    raised only if a caller-built query is too long. Fall back to ``refresh(load="full")``.
    """

    def __init__(self, length: int, limit: int) -> None:
        self.length = length
        self.limit = limit
        super().__init__(
            f"Collector query URL is {length} characters, exceeding the {limit}-character limit. "
            f"Use a shorter projection or '.refresh(load=\"full\")'."
        )


class ApiEntityNotFoundError(GeneralApiError):
    """A device, vertex, edge, ... referenced by a read or write does not exist on the server."""

    def __init__(self, entity_id: str, kind: str = "entity") -> None:
        self.entity_id = entity_id
        self.kind = kind
        super().__init__(f"API {kind} '{entity_id}' was not found on the server.")


class ApiCommitError(GeneralApiError):
    """A commit failed (validation gate or apply gate).

    HTTP/envelope success is not commit success: the server can return ``header.ok == true``
    while ``data.res.ok`` or ``data.validation.result.ok`` is ``false``. This carries the full
    typed response so callers can inspect ``validation.details`` and ``res.msg``.
    """

    # TODO: Remove import and usage of this InspectApiUpdateTopologyResponse model and implement own one
    def __init__(self, response: "InspectApiUpdateTopologyResponse") -> None:
        self.response = response
        self.result = response.data.res
        self.validation = response.data.validation
        messages = list(self.result.msg) + list(self.validation.result.msg)
        detail = "; ".join(m for m in messages if m) or "commit rejected by the server"
        super().__init__(f"API commit failed: {detail}")


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
