from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from videoipath_automation_tool.apps.preferences.uac.api import UacAPI
from videoipath_automation_tool.apps.preferences.uac.snapshot import UacSection, UacSnapshot

if TYPE_CHECKING:
    from videoipath_automation_tool.apps.preferences.uac.domain import (
        UacDomain,
        UacLdapServer,
        UacPasswordPolicy,
        UacPermissionTemplate,
        UacRole,
        UacUser,
    )


class _HasUacReadState(Protocol):
    _uac_api: UacAPI
    _snapshot: UacSnapshot | None


class UacReadMixin:
    _uac_api: UacAPI
    _snapshot: UacSnapshot | None

    def refresh(self: _HasUacReadState, section: UacSection | None = None) -> None:
        """Refresh a loaded UAC section, or all sections that have already been loaded."""
        self._get_snapshot().refresh(section)

    @property
    def users(self: _HasUacReadState) -> list[UacUser]:
        return self._get_snapshot().users

    def get_users(self: _HasUacReadState, *, detail: bool = False) -> list[UacUser]:
        return self._get_snapshot().get_users(detail=detail)

    def get_user(self: _HasUacReadState, user_id: str) -> UacUser | None:
        return self._get_snapshot().get_user(user_id)

    def find_user_by_name(self: _HasUacReadState, name: str) -> UacUser | None:
        return self._get_snapshot().find_user_by_name(name)

    @property
    def domains(self: _HasUacReadState) -> list[UacDomain]:
        return self._get_snapshot().domains

    def get_domain(self: _HasUacReadState, domain_id: str) -> UacDomain | None:
        return self._get_snapshot().get_domain(domain_id)

    def find_domain_by_name(self: _HasUacReadState, name: str) -> UacDomain | None:
        return self._get_snapshot().find_domain_by_name(name)

    @property
    def roles(self: _HasUacReadState) -> list[UacRole]:
        return self._get_snapshot().roles

    def get_role(self: _HasUacReadState, role_id: str) -> UacRole | None:
        return self._get_snapshot().get_role(role_id)

    def find_role_by_name(self: _HasUacReadState, name: str) -> UacRole | None:
        return self._get_snapshot().find_role_by_name(name)

    @property
    def permission_templates(self: _HasUacReadState) -> list[UacPermissionTemplate]:
        return self._get_snapshot().permission_templates

    def get_permission_template(self: _HasUacReadState, template_id: str) -> UacPermissionTemplate | None:
        return self._get_snapshot().get_permission_template(template_id)

    def find_permission_template_by_name(self: _HasUacReadState, name: str) -> UacPermissionTemplate | None:
        return self._get_snapshot().find_permission_template_by_name(name)

    @property
    def ldap_servers(self: _HasUacReadState) -> list[UacLdapServer]:
        return self._get_snapshot().ldap_servers

    @property
    def password_policy(self: _HasUacReadState) -> UacPasswordPolicy:
        return self._get_snapshot().password_policy

    def _get_snapshot(self: _HasUacReadState) -> UacSnapshot:
        if self._snapshot is None:
            self._snapshot = UacSnapshot(fetcher=self._uac_api)
        return self._snapshot


__all__ = ["UacReadMixin"]
