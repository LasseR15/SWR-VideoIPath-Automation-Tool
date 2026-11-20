from __future__ import annotations

from typing import Any

from pydantic import Field

from videoipath_automation_tool.apps.preferences.uac.model import (
    UacApiDomain,
    UacApiLdapServer,
    UacApiPasswordPolicy,
    UacApiPermissionTemplate,
    UacApiRole,
    UacApiUser,
    UacAuthMethod,
    UacAuthState,
    UacDescription,
    UacDomainPermissions,
    UacLdapSelection,
    UacRolePermissions,
    UacUserPermissions,
)
from videoipath_automation_tool.apps.preferences.uac.snapshot import UacSnapshot
from videoipath_automation_tool.utils.cross_app_models import FrozenModel
from videoipath_automation_tool.utils.cross_app_utils import format_repr


class UacUser(FrozenModel):
    snapshot: UacSnapshot = Field(exclude=True, repr=False)
    id: str

    @property
    def record(self) -> UacApiUser:
        return self.snapshot.get_user_record(self.id)

    @property
    def name(self) -> str:
        return self.record.name

    @property
    def revision(self) -> str:
        return self.record.revision

    @property
    def vid(self) -> str | None:
        return self.record.vid

    @property
    def active(self) -> bool:
        return self.record.active

    @property
    def auth_method(self) -> UacAuthMethod:
        return self.record.auth_method

    @property
    def auth_state(self) -> UacAuthState:
        return self.record.auth_state

    @property
    def description(self) -> str:
        return self.record.description

    @property
    def email(self) -> str:
        return self.record.email

    @property
    def full_name(self) -> str:
        return self.record.full_name

    @property
    def home_domain(self) -> str:
        return self.record.home_domain

    @property
    def is_admin(self) -> bool:
        return self.record.is_admin

    @property
    def ldap_servers(self) -> UacLdapSelection:
        return self.record.ldap_servers

    @property
    def no_session(self) -> bool:
        return self.record.no_session

    @property
    def organization(self) -> str:
        return self.record.organization

    @property
    def phone(self) -> str:
        return self.record.phone

    @property
    def permissions(self) -> UacUserPermissions:
        return self.record.permissions

    @property
    def locale(self) -> str:
        return self.record.locale

    @property
    def permissions_info(self) -> dict[str, Any]:
        return self.record.permissions_info

    @property
    def app_preferences(self) -> dict[str, Any]:
        return self.record.app_preferences

    def __repr__(self) -> str:
        return format_repr(self, id=self.id, name=self.name, active=self.active)

    __str__ = __repr__


class UacDomain(FrozenModel):
    snapshot: UacSnapshot = Field(exclude=True, repr=False)
    id: str

    @property
    def record(self) -> UacApiDomain:
        return self.snapshot.get_domain_record(self.id)

    @property
    def revision(self) -> str:
        return self.record.revision

    @property
    def descriptor(self) -> UacDescription:
        return self.record.description

    @property
    def name(self) -> str:
        return self.descriptor.label

    @property
    def description(self) -> str:
        return self.descriptor.description

    def __repr__(self) -> str:
        return format_repr(self, id=self.id, name=self.name)

    __str__ = __repr__


class UacRole(FrozenModel):
    snapshot: UacSnapshot = Field(exclude=True, repr=False)
    id: str

    @property
    def record(self) -> UacApiRole:
        return self.snapshot.get_role_record(self.id)

    @property
    def revision(self) -> str:
        return self.record.revision

    @property
    def descriptor(self) -> UacDescription:
        return self.record.description

    @property
    def name(self) -> str:
        return self.descriptor.label

    @property
    def description(self) -> str:
        return self.descriptor.description

    @property
    def permissions(self) -> UacRolePermissions:
        return self.record.permissions

    @property
    def type(self) -> str:
        return self.record.type

    def __repr__(self) -> str:
        return format_repr(self, id=self.id, name=self.name, type=self.type)

    __str__ = __repr__


class UacPermissionTemplate(FrozenModel):
    snapshot: UacSnapshot = Field(exclude=True, repr=False)
    id: str

    @property
    def record(self) -> UacApiPermissionTemplate:
        return self.snapshot.get_permission_template_record(self.id)

    @property
    def revision(self) -> str:
        return self.record.revision

    @property
    def descriptor(self) -> UacDescription:
        return self.record.description

    @property
    def name(self) -> str:
        return self.descriptor.label

    @property
    def description(self) -> str:
        return self.descriptor.description

    @property
    def domain_permissions(self) -> UacDomainPermissions:
        return self.record.domain_permissions

    def __repr__(self) -> str:
        return format_repr(self, id=self.id, name=self.name)

    __str__ = __repr__


class UacLdapServer(FrozenModel):
    id: str
    name: str
    host: str
    port: int
    base_dn: str
    account: str
    authentication: str
    encryption: bool
    key_attribute: str

    @classmethod
    def from_api(cls, record: UacApiLdapServer) -> UacLdapServer:
        return cls.model_validate(
            {
                "id": record.id,
                "name": record.name,
                "host": record.host,
                "port": record.port,
                "base_dn": record.base_dn,
                "account": record.account,
                "authentication": record.authentication,
                "encryption": record.encryption,
                "key_attribute": record.key_attribute,
            }
        )

    def __repr__(self) -> str:
        return format_repr(self, id=self.id, name=self.name, host=self.host, port=self.port)

    __str__ = __repr__


class UacPasswordPolicy(UacApiPasswordPolicy):
    """Stable public view of the server password policy."""


__all__ = [
    "UacDomain",
    "UacLdapServer",
    "UacPasswordPolicy",
    "UacPermissionTemplate",
    "UacRole",
    "UacUser",
]
