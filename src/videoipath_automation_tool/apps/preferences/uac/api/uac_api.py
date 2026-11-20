from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel

from videoipath_automation_tool.apps.preferences.uac.errors import (
    UacEntityNotFoundError,
    UacError,
    UacRequestError,
    UacRevisionConflictError,
)
from videoipath_automation_tool.apps.preferences.uac.model import (
    UacApiDomain,
    UacApiDomainWrite,
    UacApiLdapServer,
    UacApiPasswordPolicy,
    UacApiPermissionTemplate,
    UacApiPermissionTemplateWrite,
    UacApiRole,
    UacApiRoleWrite,
    UacApiUser,
    UacApiUserMutation,
    UacApiUserWrite,
)
from videoipath_automation_tool.connector.models.request_rest_v2 import Action, RequestV2Patch, RequestV2Post
from videoipath_automation_tool.connector.models.response_rest_v2 import (
    ResponseV2Patch,
    ResponseV2PatchDataItem,
    ResponseV2Post,
)
from videoipath_automation_tool.connector.vip_connector import VideoIPathConnector
from videoipath_automation_tool.utils.cross_app_errors import ApiHttpError, ApiResponseError
from videoipath_automation_tool.utils.cross_app_utils import create_fallback_logger, extract_required_items_from_rsp

_USERS_PATH = "/rest/v2/data/status/userman/users/**"
_USERS_SKELETON_PATH = "/rest/v2/data/status/userman/users/*/*/.../authState/**/.../.../permissions/**"
_DOMAINS_PATH = "/rest/v2/data/config/domainman/domains/*/desc/**"
_ROLES_PATH = "/rest/v2/data/config/security/users/roles/**"
_TEMPLATES_PATH = "/rest/v2/data/config/security/users/permissionTemplates/**"
_LDAP_PATH = "/rest/v2/data/config/userman/ldapservers/**"
_POLICY_PATH = "/rest/v2/data/status/userman/passwordPolicy/*"


class UacAPI:
    """Raw UAC transport layer: verified endpoints and typed responses."""

    def __init__(
        self,
        vip_connector: VideoIPathConnector,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or create_fallback_logger("videoipath_automation_tool_uac_api")
        self.vip_connector = vip_connector
        self._logger.debug("UAC API initialized.")

    # --- Reads ---

    def get_users(self, *, detail: bool = False) -> list[UacApiUser]:
        path = _USERS_PATH if detail else _USERS_SKELETON_PATH
        response = self.vip_connector.rest.get(path, allow_projection=not detail)
        items = extract_required_items_from_rsp(response.data, "status", "userman", "users")
        return [UacApiUser.model_validate(item) for item in items]

    def get_domains(self) -> list[UacApiDomain]:
        response = self.vip_connector.rest.get(_DOMAINS_PATH)
        items = extract_required_items_from_rsp(response.data, "config", "domainman", "domains")
        return [UacApiDomain.model_validate(item) for item in items]

    def get_roles(self) -> list[UacApiRole]:
        response = self.vip_connector.rest.get(_ROLES_PATH)
        items = extract_required_items_from_rsp(response.data, "config", "security", "users", "roles")
        return [UacApiRole.model_validate(item) for item in items]

    def get_permission_templates(self) -> list[UacApiPermissionTemplate]:
        response = self.vip_connector.rest.get(_TEMPLATES_PATH)
        items = extract_required_items_from_rsp(
            response.data,
            "config",
            "security",
            "users",
            "permissionTemplates",
        )
        return [UacApiPermissionTemplate.model_validate(item) for item in items]

    def get_ldap_servers(self) -> list[UacApiLdapServer]:
        response = self.vip_connector.rest.get(_LDAP_PATH)
        items = extract_required_items_from_rsp(response.data, "config", "userman", "ldapservers")
        return [UacApiLdapServer.model_validate(item) for item in items]

    def get_password_policy(self) -> UacApiPasswordPolicy:
        response = self.vip_connector.rest.get(_POLICY_PATH)
        status = response.data.get("status")
        if not isinstance(status, dict):
            raise UacRequestError("Password policy response is missing 'status'.")
        userman = status.get("userman")
        if not isinstance(userman, dict):
            raise UacRequestError("Password policy response is missing 'status/userman'.")
        node = userman.get("passwordPolicy")
        if not isinstance(node, dict) or not node:
            raise UacRequestError("Password policy response is missing 'status/userman/passwordPolicy'.")
        return UacApiPasswordPolicy.model_validate(node)

    # --- User writes ---

    def add_user(self, name: str, value: UacApiUserWrite) -> ResponseV2Post:
        request = UacApiUserMutation(key=name, value=value)
        return self._post_user_action("addUser", request, entity_id=name, kind="user")

    def update_user(self, name: str, revision: str, value: UacApiUserWrite) -> ResponseV2Post:
        request = UacApiUserMutation(key=name, rev=revision, value=value)
        return self._post_user_action("updateUser", request, entity_id=name, kind="user")

    def delete_user(self, name: str, revision: str) -> ResponseV2Post:
        request = UacApiUserMutation(key=name, rev=revision, value=UacApiUserWrite())
        return self._post_user_action(
            "deleteUser",
            request,
            entity_id=name,
            kind="user",
            include_value=False,
        )

    # --- Revisioned configuration writes ---

    def add_domain(self, description: UacApiDomainWrite) -> ResponseV2PatchDataItem:
        return self._patch_one("/rest/v2/data/config/domainman/domains", _add_request(description), "domain")

    def update_domain(self, domain: UacApiDomainWrite) -> ResponseV2PatchDataItem:
        return self._patch_one(
            "/rest/v2/data/config/domainman/domains",
            RequestV2Patch().update(domain),
            "domain",
            entity_id=domain.id,
        )

    def delete_domain(self, domain: UacApiDomainWrite) -> ResponseV2PatchDataItem:
        return self._patch_one(
            "/rest/v2/data/config/domainman/domains",
            _remove_request(domain.id, domain.revision),
            "domain",
            entity_id=domain.id,
        )

    def add_role(self, role: UacApiRoleWrite) -> ResponseV2PatchDataItem:
        return self._patch_one("/rest/v2/data/config/security/users/roles", _add_request(role), "role")

    def update_role(self, role: UacApiRoleWrite) -> ResponseV2PatchDataItem:
        return self._patch_one(
            "/rest/v2/data/config/security/users/roles",
            RequestV2Patch().update(role),
            "role",
            entity_id=role.id,
        )

    def delete_role(self, role: UacApiRoleWrite) -> ResponseV2PatchDataItem:
        return self._patch_one(
            "/rest/v2/data/config/security/users/roles",
            _remove_request(role.id, role.revision),
            "role",
            entity_id=role.id,
        )

    def add_permission_template(self, template: UacApiPermissionTemplateWrite) -> ResponseV2PatchDataItem:
        return self._patch_one(
            "/rest/v2/data/config/security/users/permissionTemplates",
            _add_request(template),
            "permission template",
        )

    def update_permission_template(
        self,
        template: UacApiPermissionTemplateWrite,
    ) -> ResponseV2PatchDataItem:
        return self._patch_one(
            "/rest/v2/data/config/security/users/permissionTemplates",
            RequestV2Patch().update(template),
            "permission template",
            entity_id=template.id,
        )

    # --- Batched collection writes ---

    def apply_domain_actions(self, request: RequestV2Patch) -> ResponseV2Patch:
        return self._patch("/rest/v2/data/config/domainman/domains", request, "domain")

    def apply_role_actions(self, request: RequestV2Patch) -> ResponseV2Patch:
        return self._patch("/rest/v2/data/config/security/users/roles", request, "role")

    def apply_permission_template_actions(self, request: RequestV2Patch) -> ResponseV2Patch:
        return self._patch(
            "/rest/v2/data/config/security/users/permissionTemplates",
            request,
            "permission template",
        )

    def delete_permission_template(
        self,
        template: UacApiPermissionTemplateWrite,
    ) -> ResponseV2PatchDataItem:
        return self._patch_one(
            "/rest/v2/data/config/security/users/permissionTemplates",
            _remove_request(template.id, template.revision),
            "permission template",
            entity_id=template.id,
        )

    # --- Internal ---

    def _post_user_action(
        self,
        action: str,
        request: UacApiUserMutation,
        *,
        entity_id: str,
        kind: str,
        include_value: bool = True,
    ) -> ResponseV2Post:
        data = request.model_dump(mode="json", by_alias=True, exclude_none=True)
        if not include_value:
            data.pop("value", None)
        body = RequestV2Post(data=data)
        try:
            response = self.vip_connector.rest.post(f"/rest/v2/actions/userman/{action}", body)
        except ApiHttpError as error:
            raise _translate_http_error(error, entity_id=entity_id, kind=kind) from error
        except ApiResponseError as error:
            raise _translate_response_error(error, entity_id=entity_id, kind=kind) from error
        if not response.header.ok:
            raise UacRequestError(
                _response_message(response.header),
                code=response.header.code,
                details=response.header.errorDetails,
            )
        return response

    def _patch_one(
        self,
        path: str,
        body: RequestV2Patch,
        kind: str,
        *,
        entity_id: str | None = None,
    ) -> ResponseV2PatchDataItem:
        response = self._patch(path, body, kind, entity_id=entity_id)
        if len(response.result.items) != 1:
            raise UacRequestError(f"Expected one UAC {kind} result, got {len(response.result.items)}.")
        return response.result.items[0]

    def _patch(
        self,
        path: str,
        body: RequestV2Patch,
        kind: str,
        *,
        entity_id: str | None = None,
    ) -> ResponseV2Patch:
        try:
            response = self.vip_connector.rest.patch(path, body)
        except ApiHttpError as error:
            raise _translate_http_error(error, entity_id=entity_id, kind=kind) from error
        except ApiResponseError as error:
            raise _translate_response_error(error, entity_id=entity_id, kind=kind) from error
        return response


def _translate_http_error(error: ApiHttpError, *, entity_id: str | None, kind: str) -> UacError:
    body = error.response_body if isinstance(error.response_body, dict) else {}
    header = body.get("header", {})
    details = header.get("errorDetails") if isinstance(header, dict) else None
    messages = header.get("msg") if isinstance(header, dict) else None
    message = _first_message(messages, details) or str(error)
    return _translate_message(
        message,
        entity_id=entity_id,
        kind=kind,
        code=header.get("code") if isinstance(header, dict) else None,
        details=details,
        status_code=error.status_code,
    )


def _translate_response_error(error: ApiResponseError, *, entity_id: str | None, kind: str) -> UacError:
    return _translate_message(
        "; ".join(error.messages) or str(error),
        entity_id=entity_id,
        kind=kind,
        code=error.code,
        details=error.details,
    )


def _translate_message(
    message: str,
    *,
    entity_id: str | None,
    kind: str,
    code: str | None = None,
    details: Any = None,
    status_code: int | None = None,
) -> UacError:
    revision_match = re.search(r"Expected revision '([^']+)', got '([^']+)'", message)
    if revision_match is not None and entity_id is not None:
        return UacRevisionConflictError(entity_id, kind, revision_match.group(1), revision_match.group(2))
    if "doesn't exist" in message and entity_id is not None:
        return UacEntityNotFoundError(entity_id, kind)
    return UacRequestError(message, code=code, details=details, status_code=status_code)


def _first_message(messages: Any, details: Any) -> str | None:
    if isinstance(messages, list):
        values = [str(message) for message in messages if message]
        if values:
            return "; ".join(values)
    if isinstance(details, list):
        values = [str(detail.get("msg")) for detail in details if isinstance(detail, dict) and detail.get("msg")]
        if values:
            return "; ".join(values)
    return None


def _response_message(header: Any) -> str:
    return _first_message(header.msg, header.errorDetails) or header.caption or "UAC request failed."


def _add_request(model: BaseModel) -> RequestV2Patch:
    return RequestV2Patch(
        actions=[
            Action(
                _action="add",
                **model.model_dump(mode="json", by_alias=True, exclude_none=True),
            )
        ]
    )


def _remove_request(entity_id: str | None, revision: str | None) -> RequestV2Patch:
    if entity_id is None or revision is None:
        raise UacRequestError("UAC remove actions require both an entity ID and revision.")
    return RequestV2Patch(
        actions=[
            Action(
                _action="remove",
                _id=entity_id,
                _rev=revision,
            )
        ]
    )


__all__ = ["UacAPI"]
