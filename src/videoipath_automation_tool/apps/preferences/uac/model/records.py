from __future__ import annotations

from pydantic import Field

from videoipath_automation_tool.apps.preferences.uac.model.common import (
    UacApiBaseModel,
    UacDescription,
    UacDomainPermissions,
    UacRolePermissions,
)


class UacApiDomain(UacApiBaseModel):
    id: str = Field(alias="_id")
    revision: str = Field(alias="_rev")
    vid: str | None = Field(default=None, alias="_vid")
    description: UacDescription = Field(default_factory=UacDescription, alias="desc")


class UacApiRole(UacApiBaseModel):
    id: str = Field(alias="_id")
    revision: str = Field(alias="_rev")
    vid: str | None = Field(default=None, alias="_vid")
    description: UacDescription = Field(default_factory=UacDescription, alias="desc")
    permissions: UacRolePermissions = Field(default_factory=UacRolePermissions)
    type: str = "domainRole"


class UacApiPermissionTemplate(UacApiBaseModel):
    id: str = Field(alias="_id")
    revision: str = Field(alias="_rev")
    vid: str | None = Field(default=None, alias="_vid")
    description: UacDescription = Field(default_factory=UacDescription, alias="desc")
    domain_permissions: UacDomainPermissions = Field(
        default_factory=UacDomainPermissions,
        alias="domainPermissions",
    )


class UacApiLdapServer(UacApiBaseModel):
    id: str = Field(alias="_id")
    vid: str | None = Field(default=None, alias="_vid")
    account: str = ""
    authentication: str = ""
    base_dn: str = Field(default="", alias="baseDn")
    encryption: bool = False
    host: str = ""
    key_attribute: str = Field(default="", alias="keyAttribute")
    name: str = ""
    password: str = Field(default="", repr=False)
    port: int = 0


class UacApiPasswordPolicy(UacApiBaseModel):
    expiration: int = 0
    expiration_test: bool = Field(default=False, alias="expirationTest")
    expiration_warning: int = Field(default=5, alias="expirationWarning")
    lower_and_upper_case: bool = Field(default=False, alias="lowerAndUpperCase")
    min_length: int = Field(default=5, alias="minLength")
    numeric: bool = False
    special_char: bool = Field(default=False, alias="specialChar")


class UacApiDomainWrite(UacApiBaseModel):
    id: str | None = Field(default=None, alias="_id")
    revision: str | None = Field(default=None, alias="_rev")
    description: UacDescription = Field(alias="desc")


class UacApiRoleWrite(UacApiBaseModel):
    id: str | None = Field(default=None, alias="_id")
    revision: str | None = Field(default=None, alias="_rev")
    description: UacDescription = Field(alias="desc")
    permissions: UacRolePermissions = Field(default_factory=UacRolePermissions)
    type: str = "domainRole"


class UacApiPermissionTemplateWrite(UacApiBaseModel):
    id: str | None = Field(default=None, alias="_id")
    revision: str | None = Field(default=None, alias="_rev")
    description: UacDescription = Field(alias="desc")
    domain_permissions: UacDomainPermissions = Field(
        default_factory=UacDomainPermissions,
        alias="domainPermissions",
    )


__all__ = [
    "UacApiDomain",
    "UacApiDomainWrite",
    "UacApiLdapServer",
    "UacApiPasswordPolicy",
    "UacApiPermissionTemplate",
    "UacApiPermissionTemplateWrite",
    "UacApiRole",
    "UacApiRoleWrite",
]
