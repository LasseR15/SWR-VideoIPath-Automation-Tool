from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from videoipath_automation_tool.utils.cross_app_models import ApiBaseModel


class UacApiBaseModel(ApiBaseModel):
    """Base for UAC wire models."""


class UacDescription(UacApiBaseModel):
    label: str = ""
    description: str = Field(default="", alias="desc")


class UacPermissionAssignment(UacApiBaseModel):
    role_ids: list[str] = Field(default_factory=list, alias="roleIds")
    direct: Any | None = None


class UacDomainPermissions(UacApiBaseModel):
    global_: UacPermissionAssignment = Field(default_factory=UacPermissionAssignment, alias="global")
    home: UacPermissionAssignment = Field(default_factory=UacPermissionAssignment)
    specific: dict[str, UacPermissionAssignment] = Field(default_factory=dict)


class UacPermissionRule(UacApiBaseModel):
    verbs: list[str] = Field(default_factory=list)
    inherited: list[str] = Field(default_factory=list)


class UacRolePermissions(UacApiBaseModel):
    by_resource_type: dict[str, UacPermissionRule] = Field(default_factory=dict, alias="byResourceType")


class UacAdhocPermissions(UacApiBaseModel):
    type: Literal["adhoc"] = "adhoc"
    permissions: UacDomainPermissions = Field(default_factory=UacDomainPermissions)


class UacTemplatePermissions(UacApiBaseModel):
    type: Literal["template"] = "template"
    template_id: str = Field(alias="templateId")


UacUserPermissions = UacAdhocPermissions | UacTemplatePermissions


__all__ = [
    "UacAdhocPermissions",
    "UacApiBaseModel",
    "UacDescription",
    "UacDomainPermissions",
    "UacPermissionAssignment",
    "UacPermissionRule",
    "UacRolePermissions",
    "UacTemplatePermissions",
    "UacUserPermissions",
]
