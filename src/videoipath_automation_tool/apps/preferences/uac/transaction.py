from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal, Self

import requests
from pydantic import BaseModel, Field, ValidationError

from videoipath_automation_tool.apps.preferences.uac.errors import UacEntityNotFoundError, UacError, UacRequestError
from videoipath_automation_tool.apps.preferences.uac.model import (
    UacApiDomainWrite,
    UacApiPermissionTemplateWrite,
    UacApiRoleWrite,
    UacApiUser,
    UacApiUserWrite,
    UacAuthMethod,
    UacDescription,
    UacDomainPermissions,
    UacLdapSelection,
    UacRolePermissions,
    UacUserPermissions,
)
from videoipath_automation_tool.connector.models.request_rest_v2 import Action, RequestV2Patch
from videoipath_automation_tool.connector.models.response_rest_v2 import ResponseV2Patch
from videoipath_automation_tool.utils.cross_app_errors import (
    ApiCommitConflict,
    ApiCommitConflictError,
    GeneralApiError,
)
from videoipath_automation_tool.utils.cross_app_models import FrozenModel, InternalModel
from videoipath_automation_tool.utils.cross_app_utils import field_diffs, format_repr

if TYPE_CHECKING:
    from videoipath_automation_tool.apps.preferences.uac.api import UacAPI
    from videoipath_automation_tool.apps.preferences.uac.domain import (
        UacDomain,
        UacPermissionTemplate,
        UacRole,
        UacUser,
    )
    from videoipath_automation_tool.apps.preferences.uac.snapshot import UacSection, UacSnapshot

UacKind = Literal["user", "domain", "role", "permission_template"]
UacAction = Literal["add", "update", "remove"]
_KIND_SECTIONS: dict[UacKind, UacSection] = {
    "user": "users",
    "domain": "domains",
    "role": "roles",
    "permission_template": "permission_templates",
}


class UacOperationResult(FrozenModel):
    """Outcome of one staged UAC operation."""

    kind: UacKind
    action: UacAction
    entity_id: str
    applied: bool
    revision: str | None = None
    message: str | None = None
    error: Exception | None = Field(default=None, exclude=True, repr=False)

    @property
    def ok(self) -> bool:
        return self.applied

    def __repr__(self) -> str:
        return format_repr(
            self,
            kind=self.kind,
            action=self.action,
            id=self.entity_id,
            applied=self.applied,
            message=self.message,
        )

    __str__ = __repr__


class UacCommitResult(FrozenModel):
    """Outcome of a UAC unit of work.

    This result is partial by design. User actions execute independently, and a failed
    operation does not abort later operations.
    """

    operations: list[UacOperationResult]
    refresh_errors: list[Exception] = Field(default_factory=list, exclude=True, repr=False)

    @property
    def ok(self) -> bool:
        return all(operation.applied for operation in self.operations) and not self.refresh_errors

    @property
    def applied(self) -> list[UacOperationResult]:
        return [operation for operation in self.operations if operation.applied]

    @property
    def failed(self) -> list[UacOperationResult]:
        return [operation for operation in self.operations if not operation.applied]

    @property
    def applied_ids(self) -> list[str]:
        return [operation.entity_id for operation in self.applied]

    @property
    def created_ids(self) -> list[str]:
        return [operation.entity_id for operation in self.applied if operation.action == "add"]

    def __repr__(self) -> str:
        return format_repr(
            self,
            applied=len(self.applied),
            failed=len(self.failed),
        )

    __str__ = __repr__


class _StagedOperation(InternalModel):
    kind: UacKind
    action: UacAction
    entity_id: str
    baseline: BaseModel | None = None
    payload: BaseModel | None = None


class UacTransaction:
    """Staged UAC unit of work with partial-commit semantics.

    Despite the name, a transaction spanning users is not atomic. User actions are sent
    one by one and failures are reported without stopping later actions. Domain, role and
    permission-template actions are grouped by collection into strict PATCH requests.
    """

    def __init__(
        self,
        api: UacAPI,
        snapshot: UacSnapshot,
        logger: logging.Logger | None = None,
    ) -> None:
        self._api = api
        self._snapshot = snapshot
        self._logger = logger or logging.getLogger("videoipath_automation_tool_uac_transaction")
        self._operations: dict[tuple[UacKind, str], _StagedOperation] = {}
        self._committed = False
        self._discarded = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if exc_type is not None:
            self.discard()
            return
        if not self._committed and not self._discarded:
            if self._operations:
                self._logger.warning(
                    "UAC transaction exited with %d staged operation(s) and no commit(); discarding.",
                    len(self._operations),
                )
            self.discard()

    @property
    def staged(self) -> list[tuple[UacKind, UacAction, str]]:
        return [(operation.kind, operation.action, operation.entity_id) for operation in self._operations.values()]

    def __len__(self) -> int:
        return len(self._operations)

    def __repr__(self) -> str:
        return format_repr(
            self,
            staged=len(self._operations),
            committed=self._committed or None,
            discarded=self._discarded or None,
        )

    __str__ = __repr__

    # --- User operations ---

    def create_user(
        self,
        name: str,
        *,
        password: str | None = None,
        active: bool = True,
        auth_method: UacAuthMethod = UacAuthMethod.LOCAL,
        description: str = "",
        email: str = "",
        full_name: str = "",
        home_domain: str = "grp:default",
        is_admin: bool = False,
        no_session: bool = False,
        organization: str = "",
        phone: str = "",
        ldap_servers: UacLdapSelection | None = None,
        permissions: UacUserPermissions | None = None,
    ) -> UacTransaction:
        payload = UacApiUserWrite(
            active=active,
            authMethod=auth_method,
            description=description,
            email=email,
            fullName=full_name,
            ldapServers=ldap_servers or UacLdapSelection(),
            noSession=no_session,
            organization=organization,
            phone=phone,
            isAdmin=is_admin,
            homeDomain=home_domain,
            password=password,
            permissions=permissions,
        )
        self._stage("user", "add", name, payload=payload)
        return self

    def update_user(
        self,
        user: UacUser | str,
        *,
        active: bool | None = None,
        auth_method: UacAuthMethod | None = None,
        description: str | None = None,
        email: str | None = None,
        full_name: str | None = None,
        home_domain: str | None = None,
        is_admin: bool | None = None,
        no_session: bool | None = None,
        organization: str | None = None,
        phone: str | None = None,
        ldap_servers: UacLdapSelection | None = None,
        password: str | None = None,
        permissions: UacUserPermissions | None = None,
    ) -> UacTransaction:
        resolved = self._resolve_user(user)
        baseline = self._api.get_users(detail=True)
        baseline_record = next((record for record in baseline if record.id == resolved.id), None)
        if baseline_record is None:
            raise UacEntityNotFoundError(resolved.id, "user")
        fields = {
            "active": active,
            "authMethod": auth_method,
            "description": description,
            "email": email,
            "fullName": full_name,
            "ldapServers": ldap_servers,
            "noSession": no_session,
            "organization": organization,
            "phone": phone,
            "isAdmin": is_admin,
            "homeDomain": home_domain,
            "password": password,
            "permissions": permissions,
        }
        selected = {key: value for key, value in fields.items() if value is not None}
        if not selected:
            raise ValueError("At least one user field must be supplied.")
        self._stage(
            "user",
            "update",
            resolved.id,
            baseline=baseline_record,
            payload=UacApiUserWrite.model_validate(selected),
        )
        return self

    def delete_user(self, user: UacUser | str) -> UacTransaction:
        resolved = self._resolve_user(user)
        baseline = self._api.get_users(detail=True)
        baseline_record = next((record for record in baseline if record.id == resolved.id), None)
        if baseline_record is None:
            raise UacEntityNotFoundError(resolved.id, "user")
        self._stage("user", "remove", resolved.id, baseline=baseline_record)
        return self

    # --- Domain operations ---

    def create_domain(self, name: str, description: str = "") -> UacTransaction:
        payload = UacApiDomainWrite(desc=UacDescription(label=name, desc=description))
        self._stage("domain", "add", name, payload=payload)
        return self

    def update_domain(
        self,
        domain: UacDomain | str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> UacTransaction:
        resolved = self._resolve_domain(domain)
        payload = UacApiDomainWrite(
            _id=resolved.id,
            _rev=resolved.revision,
            desc=UacDescription(
                label=name if name is not None else resolved.name,
                desc=description if description is not None else resolved.description,
            ),
        )
        self._stage("domain", "update", resolved.id, baseline=resolved.record, payload=payload)
        return self

    def delete_domain(self, domain: UacDomain | str) -> UacTransaction:
        resolved = self._resolve_domain(domain)
        self._stage("domain", "remove", resolved.id, baseline=resolved.record)
        return self

    # --- Role operations ---

    def create_role(
        self,
        name: str,
        *,
        description: str = "",
        permissions: UacRolePermissions | None = None,
        role_type: str = "domainRole",
    ) -> UacTransaction:
        payload = UacApiRoleWrite(
            desc=UacDescription(label=name, desc=description),
            permissions=permissions or UacRolePermissions(),
            type=role_type,
        )
        self._stage("role", "add", name, payload=payload)
        return self

    def update_role(
        self,
        role: UacRole | str,
        *,
        name: str | None = None,
        description: str | None = None,
        permissions: UacRolePermissions | None = None,
        role_type: str | None = None,
    ) -> UacTransaction:
        resolved = self._resolve_role(role)
        payload = UacApiRoleWrite(
            _id=resolved.id,
            _rev=resolved.revision,
            desc=UacDescription(
                label=name if name is not None else resolved.name,
                desc=description if description is not None else resolved.description,
            ),
            permissions=permissions or resolved.permissions,
            type=role_type or resolved.type,
        )
        self._stage("role", "update", resolved.id, baseline=resolved.record, payload=payload)
        return self

    def delete_role(self, role: UacRole | str) -> UacTransaction:
        resolved = self._resolve_role(role)
        self._stage("role", "remove", resolved.id, baseline=resolved.record)
        return self

    # --- Permission-template operations ---

    def create_permission_template(
        self,
        name: str,
        *,
        description: str = "",
        permissions: UacDomainPermissions | None = None,
    ) -> UacTransaction:
        payload = UacApiPermissionTemplateWrite(
            desc=UacDescription(label=name, desc=description),
            domainPermissions=permissions or UacDomainPermissions(),
        )
        self._stage("permission_template", "add", name, payload=payload)
        return self

    def update_permission_template(
        self,
        template: UacPermissionTemplate | str,
        *,
        name: str | None = None,
        description: str | None = None,
        permissions: UacDomainPermissions | None = None,
    ) -> UacTransaction:
        resolved = self._resolve_permission_template(template)
        payload = UacApiPermissionTemplateWrite(
            _id=resolved.id,
            _rev=resolved.revision,
            desc=UacDescription(
                label=name if name is not None else resolved.name,
                desc=description if description is not None else resolved.description,
            ),
            domainPermissions=permissions or resolved.domain_permissions,
        )
        self._stage(
            "permission_template",
            "update",
            resolved.id,
            baseline=resolved.record,
            payload=payload,
        )
        return self

    def delete_permission_template(self, template: UacPermissionTemplate | str) -> UacTransaction:
        resolved = self._resolve_permission_template(template)
        self._stage("permission_template", "remove", resolved.id, baseline=resolved.record)
        return self

    # --- Commit lifecycle ---

    def commit(self, *, check_conflicts: bool = True) -> UacCommitResult:
        """Execute staged operations and report every outcome.

        User writes are sequential and non-atomic. Collection PATCH actions are grouped
        by endpoint and sent as strict batches.
        """
        self._ensure_open()
        if not self._operations:
            raise ValueError("Nothing staged; commit aborted.")

        operation_results: list[UacOperationResult] = []
        operation_results.extend(self._commit_users(check_conflicts=check_conflicts))
        for kind in ("domain", "role", "permission_template"):
            operation_results.extend(self._commit_patch_group(kind, check_conflicts=check_conflicts))

        self._committed = True
        affected_sections = {_KIND_SECTIONS[result.kind] for result in operation_results}
        refresh_errors: list[Exception] = []
        for section in affected_sections:
            try:
                self._snapshot.refresh(section)
            except _OPERATION_ERRORS as error:
                self._logger.warning("Could not refresh UAC %s section after commit: %s", section, error)
                refresh_errors.append(error)
        return UacCommitResult(operations=operation_results, refresh_errors=refresh_errors)

    def discard(self) -> None:
        self._operations.clear()
        self._discarded = True

    # --- Internal: staging ---

    def _stage(
        self,
        kind: UacKind,
        action: UacAction,
        entity_id: str,
        *,
        baseline: BaseModel | None = None,
        payload: BaseModel | None = None,
    ) -> None:
        self._ensure_open()
        key = (kind, entity_id)
        if key in self._operations:
            raise ValueError(f"UAC {kind} '{entity_id}' is already staged.")
        self._operations[key] = _StagedOperation(
            kind=kind,
            action=action,
            entity_id=entity_id,
            baseline=baseline,
            payload=payload,
        )

    # --- Internal: user commits ---

    def _commit_users(self, *, check_conflicts: bool) -> list[UacOperationResult]:
        operations = [operation for operation in self._operations.values() if operation.kind == "user"]
        if not operations:
            return []
        try:
            current = {record.id: record for record in self._api.get_users(detail=True)}
        except _OPERATION_ERRORS as error:
            return [_failed_operation(operation, error) for operation in operations]
        results: list[UacOperationResult] = []
        for operation in operations:
            try:
                results.append(self._commit_user(operation, current, check_conflicts=check_conflicts))
            except _OPERATION_ERRORS as error:
                results.append(_failed_operation(operation, error))
        return results

    def _commit_user(
        self,
        operation: _StagedOperation,
        current: dict[str, UacApiUser],
        *,
        check_conflicts: bool,
    ) -> UacOperationResult:
        if operation.action == "add":
            payload = _as_model(operation.payload, UacApiUserWrite)
            self._api.add_user(operation.entity_id, payload)
            return _applied_operation(operation)

        record = self._preflight(operation, current, check_conflicts=check_conflicts)
        if operation.action == "update":
            payload = _as_model(operation.payload, UacApiUserWrite)
            self._api.update_user(record.name, record.revision, payload)
        else:
            self._api.delete_user(record.name, record.revision)
        return _applied_operation(operation, record.revision)

    # --- Internal: collection PATCH commits ---

    def _commit_patch_group(
        self,
        kind: UacKind,
        *,
        check_conflicts: bool,
    ) -> list[UacOperationResult]:
        operations = [operation for operation in self._operations.values() if operation.kind == kind]
        if not operations:
            return []

        try:
            current_models = self._fetch_patch_records(kind)
        except _OPERATION_ERRORS as error:
            return [_failed_operation(operation, error) for operation in operations]
        current = {str(record.id): record for record in current_models}
        eligible: list[tuple[_StagedOperation, Action]] = []
        results: list[UacOperationResult] = []

        for operation in operations:
            try:
                fresh = (
                    None
                    if operation.action == "add"
                    else self._preflight(
                        operation,
                        current,
                        check_conflicts=check_conflicts,
                    )
                )
                eligible.append((operation, _to_patch_action(operation, fresh)))
            except _OPERATION_ERRORS as error:
                results.append(_failed_operation(operation, error))

        if not eligible:
            return results

        request = RequestV2Patch(actions=[action for _, action in eligible])
        try:
            response = self._apply_patch_group(kind, request)
            results.extend(_patch_results(eligible, response))
        except _OPERATION_ERRORS as error:
            results.extend(_failed_operation(operation, error) for operation, _ in eligible)
        return results

    def _fetch_patch_records(self, kind: UacKind) -> list[BaseModel]:
        if kind == "domain":
            return list(self._api.get_domains())
        if kind == "role":
            return list(self._api.get_roles())
        if kind == "permission_template":
            return list(self._api.get_permission_templates())
        raise UacRequestError(f"Unknown PATCH collection kind '{kind}'.")

    def _apply_patch_group(self, kind: UacKind, request: RequestV2Patch) -> ResponseV2Patch:
        if kind == "domain":
            return self._api.apply_domain_actions(request)
        if kind == "role":
            return self._api.apply_role_actions(request)
        if kind == "permission_template":
            return self._api.apply_permission_template_actions(request)
        raise UacRequestError(f"Unknown PATCH collection kind '{kind}'.")

    # --- Internal: conflict handling and resolution ---

    def _preflight(
        self,
        operation: _StagedOperation,
        current: dict[str, BaseModel],
        *,
        check_conflicts: bool,
    ) -> BaseModel:
        record = current.get(operation.entity_id)
        if record is None:
            raise ApiCommitConflictError(
                [ApiCommitConflict(operation.entity_id, operation.kind, {"__exists__": (True, False)})]
            )
        if check_conflicts:
            if operation.baseline is None:
                raise UacRequestError(f"UAC {operation.kind} '{operation.entity_id}' has no conflict baseline.")
            baseline_dump = _conflict_dump(operation.baseline)
            current_dump = _conflict_dump(record)
            if current_dump != baseline_dump:
                raise ApiCommitConflictError(
                    [
                        ApiCommitConflict(
                            operation.entity_id,
                            operation.kind,
                            field_diffs(baseline_dump, current_dump),
                        )
                    ]
                )
        return record

    def _resolve_user(self, user: UacUser | str) -> UacUser:
        if not isinstance(user, str):
            return user
        resolved = self._snapshot.get_user(user) or self._snapshot.find_user_by_name(user)
        if resolved is None:
            raise UacEntityNotFoundError(user, "user")
        return resolved

    def _resolve_domain(self, domain: UacDomain | str) -> UacDomain:
        if not isinstance(domain, str):
            return domain
        resolved = self._snapshot.get_domain(domain) or self._snapshot.find_domain_by_name(domain)
        if resolved is None:
            raise UacEntityNotFoundError(domain, "domain")
        return resolved

    def _resolve_role(self, role: UacRole | str) -> UacRole:
        if not isinstance(role, str):
            return role
        resolved = self._snapshot.get_role(role) or self._snapshot.find_role_by_name(role)
        if resolved is None:
            raise UacEntityNotFoundError(role, "role")
        return resolved

    def _resolve_permission_template(
        self,
        template: UacPermissionTemplate | str,
    ) -> UacPermissionTemplate:
        if not isinstance(template, str):
            return template
        resolved = self._snapshot.get_permission_template(template) or self._snapshot.find_permission_template_by_name(
            template
        )
        if resolved is None:
            raise UacEntityNotFoundError(template, "permission template")
        return resolved

    def _ensure_open(self) -> None:
        if self._committed:
            raise RuntimeError("This transaction was already committed; open a new one.")
        if self._discarded:
            raise RuntimeError("This transaction was discarded; open a new one.")


def _conflict_dump(model: BaseModel) -> dict[str, object]:
    return model.model_dump(
        mode="json",
        by_alias=True,
        exclude={
            "id",
            "revision",
            "vid",
            "auth_state",
            "app_preferences",
            "permissions_info",
            "locale",
        },
    )


def _to_patch_action(operation: _StagedOperation, current: BaseModel | None) -> Action:
    if operation.action == "remove":
        revision = getattr(current, "revision", None)
        return Action(_action="remove", _id=operation.entity_id, _rev=revision)
    payload = _as_model(
        operation.payload,
        {
            "domain": UacApiDomainWrite,
            "role": UacApiRoleWrite,
            "permission_template": UacApiPermissionTemplateWrite,
        }[operation.kind],
    )
    values = payload.model_dump(mode="json", by_alias=True, exclude_none=True)
    if current is not None:
        values["_id"] = current.id
        values["_rev"] = current.revision
    return Action(_action=operation.action, **values)


def _patch_results(
    eligible: list[tuple[_StagedOperation, Action]],
    response: ResponseV2Patch,
) -> list[UacOperationResult]:
    by_index = {
        int(item.actionRef.get("idx", -1)): item for item in response.result.items if isinstance(item.actionRef, dict)
    }
    results: list[UacOperationResult] = []
    for index, (operation, _) in enumerate(eligible):
        item = by_index.get(index)
        if item is None:
            results.append(
                _failed_operation(
                    operation,
                    UacRequestError(f"No result returned for staged {operation.kind} '{operation.entity_id}'."),
                )
            )
            continue
        if item.res not in {"added", "updated", "removed"}:
            results.append(
                _failed_operation(
                    operation,
                    UacRequestError(item.msg or f"UAC {operation.kind} operation returned '{item.res}'."),
                )
            )
            continue
        results.append(_applied_operation(operation, item.rev, item.id))
    return results


def _applied_operation(
    operation: _StagedOperation,
    revision: str | None = None,
    entity_id: str | None = None,
) -> UacOperationResult:
    return UacOperationResult(
        kind=operation.kind,
        action=operation.action,
        entity_id=entity_id or operation.entity_id,
        applied=True,
        revision=revision or None,
    )


def _failed_operation(operation: _StagedOperation, error: Exception) -> UacOperationResult:
    return UacOperationResult(
        kind=operation.kind,
        action=operation.action,
        entity_id=operation.entity_id,
        applied=False,
        message=str(error),
        error=error,
    )


def _as_model(value: BaseModel | None, expected: type[BaseModel]) -> BaseModel:
    if not isinstance(value, expected):
        raise UacRequestError(f"Expected staged payload of type {expected.__name__}.")
    return value


_OPERATION_ERRORS = (
    UacError,
    GeneralApiError,
    ValidationError,
    OSError,
    requests.RequestException,
)


__all__ = [
    "UacCommitResult",
    "UacOperationResult",
    "UacTransaction",
]
