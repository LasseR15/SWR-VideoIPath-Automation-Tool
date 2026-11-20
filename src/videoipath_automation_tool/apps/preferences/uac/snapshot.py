from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from videoipath_automation_tool.apps.preferences.uac.errors import UacEntityNotFoundError
from videoipath_automation_tool.apps.preferences.uac.model import (
    UacApiDomain,
    UacApiLdapServer,
    UacApiPermissionTemplate,
    UacApiRole,
    UacApiUser,
)
from videoipath_automation_tool.utils.cross_app_utils import format_repr

if TYPE_CHECKING:
    from videoipath_automation_tool.apps.preferences.uac.api import UacAPI
    from videoipath_automation_tool.apps.preferences.uac.domain import (
        UacDomain,
        UacLdapServer,
        UacPasswordPolicy,
        UacPermissionTemplate,
        UacRole,
        UacUser,
    )

UacSection = Literal["users", "domains", "roles", "permission_templates", "ldap_servers", "password_policy"]


class UacSnapshot:
    """Lazily loaded, independently refreshable UAC state."""

    def __init__(self, fetcher: UacAPI) -> None:
        self._fetcher = fetcher
        self._lock = threading.RLock()
        self._created_at = datetime.now(UTC)
        self._loaded: dict[UacSection, bool] = {
            "users": False,
            "domains": False,
            "roles": False,
            "permission_templates": False,
            "ldap_servers": False,
            "password_policy": False,
        }
        self._fetched_at: dict[UacSection, datetime] = {}
        self._user_detail_loaded = False
        self._users: dict[str, UacApiUser] = {}
        self._domains: dict[str, UacApiDomain] = {}
        self._roles: dict[str, UacApiRole] = {}
        self._permission_templates: dict[str, UacApiPermissionTemplate] = {}
        self._ldap_servers: list[UacApiLdapServer] = []
        self._password_policy: UacPasswordPolicy | None = None
        self._user_cache: dict[str, UacUser] = {}
        self._domain_cache: dict[str, UacDomain] = {}
        self._role_cache: dict[str, UacRole] = {}
        self._template_cache: dict[str, UacPermissionTemplate] = {}

    @property
    def created_at(self) -> datetime:
        return self._created_at

    def fetched_at(self, section: UacSection) -> datetime | None:
        return self._fetched_at.get(section)

    def refresh(self, section: UacSection | None = None) -> None:
        if section is None:
            for loaded_section, loaded in self._loaded.items():
                if loaded:
                    self.refresh(loaded_section)
            return
        _REFRESHERS[section](self)

    # --- Users ---

    @property
    def users(self) -> list[UacUser]:
        return self.get_users()

    def get_users(self, *, detail: bool = False) -> list[UacUser]:
        if detail and not self._user_detail_loaded:
            self._user_detail_loaded = True
            self._refresh_users()
        self._ensure_users()
        return [self._wrap_user(user_id) for user_id in self._users]

    def get_user(self, user_id: str) -> UacUser | None:
        self._ensure_users()
        return self._wrap_user(user_id) if user_id in self._users else None

    def get_user_record(self, user_id: str) -> UacApiUser:
        self._ensure_users()
        try:
            return self._users[user_id]
        except KeyError as error:
            raise UacEntityNotFoundError(user_id, "user") from error

    def find_user_by_name(self, name: str) -> UacUser | None:
        self._ensure_users()
        user_id = next((record.id for record in self._users.values() if record.name == name), None)
        return self._wrap_user(user_id) if user_id is not None else None

    # --- Domains ---

    @property
    def domains(self) -> list[UacDomain]:
        self._ensure_domains()
        return [self._wrap_domain(domain_id) for domain_id in self._domains]

    def get_domain(self, domain_id: str) -> UacDomain | None:
        self._ensure_domains()
        return self._wrap_domain(domain_id) if domain_id in self._domains else None

    def get_domain_record(self, domain_id: str) -> UacApiDomain:
        self._ensure_domains()
        try:
            return self._domains[domain_id]
        except KeyError as error:
            raise UacEntityNotFoundError(domain_id, "domain") from error

    def find_domain_by_name(self, name: str) -> UacDomain | None:
        self._ensure_domains()
        domain_id = next(
            (record.id for record in self._domains.values() if record.description.label == name),
            None,
        )
        return self._wrap_domain(domain_id) if domain_id is not None else None

    # --- Roles ---

    @property
    def roles(self) -> list[UacRole]:
        self._ensure_roles()
        return [self._wrap_role(role_id) for role_id in self._roles]

    def get_role(self, role_id: str) -> UacRole | None:
        self._ensure_roles()
        return self._wrap_role(role_id) if role_id in self._roles else None

    def get_role_record(self, role_id: str) -> UacApiRole:
        self._ensure_roles()
        try:
            return self._roles[role_id]
        except KeyError as error:
            raise UacEntityNotFoundError(role_id, "role") from error

    def find_role_by_name(self, name: str) -> UacRole | None:
        self._ensure_roles()
        role_id = next((record.id for record in self._roles.values() if record.description.label == name), None)
        return self._wrap_role(role_id) if role_id is not None else None

    # --- Permission templates ---

    @property
    def permission_templates(self) -> list[UacPermissionTemplate]:
        self._ensure_permission_templates()
        return [self._wrap_template(template_id) for template_id in self._permission_templates]

    def get_permission_template(self, template_id: str) -> UacPermissionTemplate | None:
        self._ensure_permission_templates()
        return self._wrap_template(template_id) if template_id in self._permission_templates else None

    def get_permission_template_record(self, template_id: str) -> UacApiPermissionTemplate:
        self._ensure_permission_templates()
        try:
            return self._permission_templates[template_id]
        except KeyError as error:
            raise UacEntityNotFoundError(template_id, "permission template") from error

    def find_permission_template_by_name(self, name: str) -> UacPermissionTemplate | None:
        self._ensure_permission_templates()
        template_id = next(
            (record.id for record in self._permission_templates.values() if record.description.label == name),
            None,
        )
        return self._wrap_template(template_id) if template_id is not None else None

    # --- Read-only configuration ---

    @property
    def ldap_servers(self) -> list[UacLdapServer]:
        from videoipath_automation_tool.apps.preferences.uac.domain import UacLdapServer

        self._ensure_ldap_servers()
        return [UacLdapServer.from_api(record) for record in self._ldap_servers]

    @property
    def password_policy(self) -> UacPasswordPolicy:
        self._ensure_password_policy()
        if self._password_policy is None:
            raise UacEntityNotFoundError("passwordPolicy", "configuration")
        return self._password_policy

    def __repr__(self) -> str:
        return format_repr(
            self,
            users=len(self._users),
            domains=len(self._domains),
            roles=len(self._roles),
            permission_templates=len(self._permission_templates),
        )

    __str__ = __repr__

    # --- Internal ---

    def _ensure_users(self) -> None:
        if not self._loaded["users"]:
            self._refresh_users()

    def _refresh_users(self) -> None:
        with self._lock:
            records = self._fetcher.get_users(detail=self._user_detail_loaded)
            self._users = {record.id: record for record in records}
            self._mark_loaded("users")

    def _ensure_domains(self) -> None:
        if not self._loaded["domains"]:
            self._refresh_domains()

    def _refresh_domains(self) -> None:
        with self._lock:
            records = self._fetcher.get_domains()
            self._domains = {record.id: record for record in records}
            self._mark_loaded("domains")

    def _ensure_roles(self) -> None:
        if not self._loaded["roles"]:
            self._refresh_roles()

    def _refresh_roles(self) -> None:
        with self._lock:
            records = self._fetcher.get_roles()
            self._roles = {record.id: record for record in records}
            self._mark_loaded("roles")

    def _ensure_permission_templates(self) -> None:
        if not self._loaded["permission_templates"]:
            self._refresh_permission_templates()

    def _refresh_permission_templates(self) -> None:
        with self._lock:
            records = self._fetcher.get_permission_templates()
            self._permission_templates = {record.id: record for record in records}
            self._mark_loaded("permission_templates")

    def _ensure_ldap_servers(self) -> None:
        if not self._loaded["ldap_servers"]:
            self._refresh_ldap_servers()

    def _refresh_ldap_servers(self) -> None:
        with self._lock:
            self._ldap_servers = self._fetcher.get_ldap_servers()
            self._mark_loaded("ldap_servers")

    def _ensure_password_policy(self) -> None:
        if not self._loaded["password_policy"]:
            self._refresh_password_policy()

    def _refresh_password_policy(self) -> None:
        from videoipath_automation_tool.apps.preferences.uac.domain import UacPasswordPolicy

        with self._lock:
            self._password_policy = UacPasswordPolicy.model_validate(
                self._fetcher.get_password_policy().model_dump(mode="json", by_alias=True)
            )
            self._mark_loaded("password_policy")

    def _mark_loaded(self, section: UacSection) -> None:
        now = datetime.now(UTC)
        self._loaded[section] = True
        self._fetched_at[section] = now

    def _wrap_user(self, user_id: str) -> UacUser:
        from videoipath_automation_tool.apps.preferences.uac.domain import UacUser

        return self._user_cache.setdefault(user_id, UacUser(snapshot=self, id=user_id))

    def _wrap_domain(self, domain_id: str) -> UacDomain:
        from videoipath_automation_tool.apps.preferences.uac.domain import UacDomain

        return self._domain_cache.setdefault(domain_id, UacDomain(snapshot=self, id=domain_id))

    def _wrap_role(self, role_id: str) -> UacRole:
        from videoipath_automation_tool.apps.preferences.uac.domain import UacRole

        return self._role_cache.setdefault(role_id, UacRole(snapshot=self, id=role_id))

    def _wrap_template(self, template_id: str) -> UacPermissionTemplate:
        from videoipath_automation_tool.apps.preferences.uac.domain import UacPermissionTemplate

        return self._template_cache.setdefault(
            template_id,
            UacPermissionTemplate(snapshot=self, id=template_id),
        )


_REFRESHERS = {
    "users": UacSnapshot._refresh_users,
    "domains": UacSnapshot._refresh_domains,
    "roles": UacSnapshot._refresh_roles,
    "permission_templates": UacSnapshot._refresh_permission_templates,
    "ldap_servers": UacSnapshot._refresh_ldap_servers,
    "password_policy": UacSnapshot._refresh_password_policy,
}

__all__ = ["UacSection", "UacSnapshot"]
