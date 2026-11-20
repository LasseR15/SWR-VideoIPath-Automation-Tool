from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from videoipath_automation_tool.apps.preferences.uac.model.common import (
    UacAdhocPermissions,
    UacApiBaseModel,
    UacUserPermissions,
)


class UacAuthMethod(StrEnum):
    LOCAL = "local"
    SSO = "sso"
    LDAP = "ldap"


class UacLdapSelection(UacApiBaseModel):
    all: bool = True
    servers: list[str] = Field(default_factory=list)


class UacAuthState(UacApiBaseModel):
    disabled_by_admin: bool = Field(default=False, alias="disabledByAdmin")
    last_password_update_timestamp: str | int | None = Field(
        default=None,
        alias="lastPasswordUpdateTimestamp",
    )


class UacApiUserWrite(UacApiBaseModel):
    active: bool | None = None
    auth_method: UacAuthMethod | None = Field(default=None, alias="authMethod")
    description: str | None = None
    email: str | None = None
    full_name: str | None = Field(default=None, alias="fullName")
    ldap_servers: UacLdapSelection | None = Field(default=None, alias="ldapServers")
    no_session: bool | None = Field(default=None, alias="noSession")
    organization: str | None = None
    phone: str | None = None
    is_admin: bool | None = Field(default=None, alias="isAdmin")
    home_domain: str | None = Field(default=None, alias="homeDomain")
    password: str | None = Field(default=None, repr=False)
    permissions: UacUserPermissions | None = None


class UacApiUser(UacApiBaseModel):
    id: str = Field(alias="_id")
    revision: str = Field(alias="_rev")
    vid: str | None = Field(default=None, alias="_vid")
    active: bool = True
    auth_method: UacAuthMethod = Field(default=UacAuthMethod.LOCAL, alias="authMethod")
    auth_state: UacAuthState = Field(default_factory=UacAuthState, alias="authState")
    description: str = ""
    email: str = ""
    full_name: str = Field(default="", alias="fullName")
    home_domain: str = Field(default="grp:default", alias="homeDomain")
    is_admin: bool = Field(default=False, alias="isAdmin")
    ldap_servers: UacLdapSelection = Field(default_factory=UacLdapSelection, alias="ldapServers")
    locale: str = ""
    name: str
    no_session: bool = Field(default=False, alias="noSession")
    organization: str = ""
    permissions: UacUserPermissions = Field(default_factory=UacAdhocPermissions)
    permissions_info: dict[str, Any] = Field(default_factory=dict, alias="permissionsInfo")
    phone: str = ""
    app_preferences: dict[str, Any] = Field(default_factory=dict, alias="appPrefs")


class UacApiUserMutation(UacApiBaseModel):
    key: str
    revision: str | None = Field(default=None, alias="rev")
    value: UacApiUserWrite


__all__ = [
    "UacApiUser",
    "UacApiUserMutation",
    "UacApiUserWrite",
    "UacAuthMethod",
    "UacAuthState",
    "UacLdapSelection",
]
