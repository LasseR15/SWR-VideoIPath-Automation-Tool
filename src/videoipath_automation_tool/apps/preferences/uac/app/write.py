from __future__ import annotations

import logging
from typing import Protocol

from videoipath_automation_tool.apps.preferences.uac.api import UacAPI
from videoipath_automation_tool.apps.preferences.uac.domain import (
    UacDomain,
    UacPermissionTemplate,
    UacRole,
    UacUser,
)
from videoipath_automation_tool.apps.preferences.uac.errors import UacRequestError
from videoipath_automation_tool.apps.preferences.uac.model import (
    UacAuthMethod,
    UacDomainPermissions,
    UacLdapSelection,
    UacRolePermissions,
    UacUserPermissions,
)
from videoipath_automation_tool.apps.preferences.uac.snapshot import UacSnapshot
from videoipath_automation_tool.apps.preferences.uac.transaction import (
    UacCommitResult,
    UacOperationResult,
    UacTransaction,
)


class _HasUacWriteState(Protocol):
    _uac_api: UacAPI
    _snapshot: UacSnapshot | None
    _logger: logging.Logger

    def _get_snapshot(self) -> UacSnapshot: ...


class UacWriteMixin:
    _uac_api: UacAPI
    _snapshot: UacSnapshot | None
    _logger: logging.Logger

    def transaction(self: _HasUacWriteState) -> UacTransaction:
        """Open a staged, non-atomic UAC unit of work."""
        return UacTransaction(self._uac_api, self._get_snapshot(), logger=self._logger)

    # --- Users ---

    def create_user(
        self: _HasUacWriteState,
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
    ) -> UacUser:
        with self.transaction() as transaction:
            transaction.create_user(
                name,
                password=password,
                active=active,
                auth_method=auth_method,
                description=description,
                email=email,
                full_name=full_name,
                home_domain=home_domain,
                is_admin=is_admin,
                no_session=no_session,
                organization=organization,
                phone=phone,
                ldap_servers=ldap_servers,
                permissions=permissions,
            )
            result = transaction.commit()
        _raise_failure(result)
        user = self._get_snapshot().find_user_by_name(name)
        if user is None:
            raise UacRequestError(f"Created user '{name}' could not be reloaded.")
        return user

    def update_user(
        self: _HasUacWriteState,
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
        check_conflicts: bool = True,
    ) -> UacUser:
        with self.transaction() as transaction:
            transaction.update_user(
                user,
                active=active,
                auth_method=auth_method,
                description=description,
                email=email,
                full_name=full_name,
                home_domain=home_domain,
                is_admin=is_admin,
                no_session=no_session,
                organization=organization,
                phone=phone,
                ldap_servers=ldap_servers,
                password=password,
                permissions=permissions,
            )
            result = transaction.commit(check_conflicts=check_conflicts)
        operation = _raise_failure(result)
        updated = self._get_snapshot().get_user(operation.entity_id)
        if updated is None:
            raise UacRequestError(f"Updated user '{operation.entity_id}' could not be reloaded.")
        return updated

    def delete_user(
        self: _HasUacWriteState,
        user: UacUser | str,
        *,
        check_conflicts: bool = True,
    ) -> None:
        with self.transaction() as transaction:
            transaction.delete_user(user)
            result = transaction.commit(check_conflicts=check_conflicts)
        _raise_failure(result)

    # --- Domains ---

    def create_domain(self: _HasUacWriteState, name: str, description: str = "") -> UacDomain:
        with self.transaction() as transaction:
            transaction.create_domain(name, description)
            result = transaction.commit()
        operation = _raise_failure(result)
        domain = self._get_snapshot().get_domain(operation.entity_id)
        if domain is None:
            raise UacRequestError(f"Created domain '{name}' could not be reloaded.")
        return domain

    def update_domain(
        self: _HasUacWriteState,
        domain: UacDomain | str,
        *,
        name: str | None = None,
        description: str | None = None,
        check_conflicts: bool = True,
    ) -> UacDomain:
        with self.transaction() as transaction:
            transaction.update_domain(domain, name=name, description=description)
            result = transaction.commit(check_conflicts=check_conflicts)
        operation = _raise_failure(result)
        updated = self._get_snapshot().get_domain(operation.entity_id)
        if updated is None:
            raise UacRequestError(f"Updated domain '{operation.entity_id}' could not be reloaded.")
        return updated

    def delete_domain(
        self: _HasUacWriteState,
        domain: UacDomain | str,
        *,
        check_conflicts: bool = True,
    ) -> None:
        with self.transaction() as transaction:
            transaction.delete_domain(domain)
            result = transaction.commit(check_conflicts=check_conflicts)
        _raise_failure(result)

    # --- Roles ---

    def create_role(
        self: _HasUacWriteState,
        name: str,
        *,
        description: str = "",
        permissions: UacRolePermissions | None = None,
        role_type: str = "domainRole",
    ) -> UacRole:
        with self.transaction() as transaction:
            transaction.create_role(
                name,
                description=description,
                permissions=permissions,
                role_type=role_type,
            )
            result = transaction.commit()
        operation = _raise_failure(result)
        role = self._get_snapshot().get_role(operation.entity_id)
        if role is None:
            raise UacRequestError(f"Created role '{name}' could not be reloaded.")
        return role

    def update_role(
        self: _HasUacWriteState,
        role: UacRole | str,
        *,
        name: str | None = None,
        description: str | None = None,
        permissions: UacRolePermissions | None = None,
        role_type: str | None = None,
        check_conflicts: bool = True,
    ) -> UacRole:
        with self.transaction() as transaction:
            transaction.update_role(
                role,
                name=name,
                description=description,
                permissions=permissions,
                role_type=role_type,
            )
            result = transaction.commit(check_conflicts=check_conflicts)
        operation = _raise_failure(result)
        updated = self._get_snapshot().get_role(operation.entity_id)
        if updated is None:
            raise UacRequestError(f"Updated role '{operation.entity_id}' could not be reloaded.")
        return updated

    def delete_role(
        self: _HasUacWriteState,
        role: UacRole | str,
        *,
        check_conflicts: bool = True,
    ) -> None:
        with self.transaction() as transaction:
            transaction.delete_role(role)
            result = transaction.commit(check_conflicts=check_conflicts)
        _raise_failure(result)

    # --- Permission templates ---

    def create_permission_template(
        self: _HasUacWriteState,
        name: str,
        *,
        description: str = "",
        permissions: UacDomainPermissions | None = None,
    ) -> UacPermissionTemplate:
        with self.transaction() as transaction:
            transaction.create_permission_template(name, description=description, permissions=permissions)
            result = transaction.commit()
        operation = _raise_failure(result)
        template = self._get_snapshot().get_permission_template(operation.entity_id)
        if template is None:
            raise UacRequestError(f"Created permission template '{name}' could not be reloaded.")
        return template

    def update_permission_template(
        self: _HasUacWriteState,
        template: UacPermissionTemplate | str,
        *,
        name: str | None = None,
        description: str | None = None,
        permissions: UacDomainPermissions | None = None,
        check_conflicts: bool = True,
    ) -> UacPermissionTemplate:
        with self.transaction() as transaction:
            transaction.update_permission_template(
                template,
                name=name,
                description=description,
                permissions=permissions,
            )
            result = transaction.commit(check_conflicts=check_conflicts)
        operation = _raise_failure(result)
        updated = self._get_snapshot().get_permission_template(operation.entity_id)
        if updated is None:
            raise UacRequestError(f"Updated permission template '{operation.entity_id}' could not be reloaded.")
        return updated

    def delete_permission_template(
        self: _HasUacWriteState,
        template: UacPermissionTemplate | str,
        *,
        check_conflicts: bool = True,
    ) -> None:
        with self.transaction() as transaction:
            transaction.delete_permission_template(template)
            result = transaction.commit(check_conflicts=check_conflicts)
        _raise_failure(result)


def _raise_failure(result: UacCommitResult) -> UacOperationResult:
    if result.failed:
        failure = result.failed[0]
        if failure.error is not None:
            raise failure.error
        raise UacRequestError(failure.message or "UAC operation failed.")
    if not result.applied:
        raise UacRequestError("UAC transaction returned no applied operation.")
    if result.refresh_errors:
        raise result.refresh_errors[0]
    return result.applied[0]


__all__ = ["UacWriteMixin"]
