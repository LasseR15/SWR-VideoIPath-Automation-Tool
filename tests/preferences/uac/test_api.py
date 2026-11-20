from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from videoipath_automation_tool.apps.preferences.uac.api import UacAPI
from videoipath_automation_tool.apps.preferences.uac.errors import UacRequestError, UacRevisionConflictError
from videoipath_automation_tool.apps.preferences.uac.model import (
    UacApiDomainWrite,
    UacApiUserWrite,
    UacAuthMethod,
    UacDescription,
    UacTemplatePermissions,
)
from videoipath_automation_tool.connector.models.request_rest_v2 import Action, RequestV2Patch
from videoipath_automation_tool.utils.cross_app_errors import ApiHttpError


class FakeRest:
    def __init__(self, payloads: dict[str, dict[str, Any]]) -> None:
        self.payloads = payloads
        self.get_calls: list[tuple[str, bool]] = []
        self.post_calls: list[tuple[str, Any]] = []
        self.patch_calls: list[tuple[str, Any]] = []
        self.post_error: ApiHttpError | None = None

    def get(self, path: str, allow_projection: bool = False, **_: Any) -> SimpleNamespace:
        self.get_calls.append((path, allow_projection))
        section = _section_for_path(path)
        return SimpleNamespace(data=self.payloads[section], header=_header())

    def post(self, path: str, body: Any, **_: Any) -> SimpleNamespace:
        self.post_calls.append((path, body))
        if self.post_error is not None:
            raise self.post_error
        return SimpleNamespace(data=None, header=_header())

    def patch(self, path: str, body: Any, **_: Any) -> SimpleNamespace:
        self.patch_calls.append((path, body))
        item = SimpleNamespace(
            id="grp:domain-b",
            rev="0-00000000-0000-4000-8000-000000000009",
            msg="",
            res="added",
        )
        return SimpleNamespace(
            header=_header(),
            result=SimpleNamespace(items=[item]),
        )


def test_reads_typed_users_and_preserves_template_permissions(
    uac_payloads: dict[str, dict[str, Any]],
) -> None:
    rest = FakeRest(uac_payloads)
    api = UacAPI(SimpleNamespace(rest=rest))  # type: ignore[arg-type]

    users = api.get_users()

    assert [user.name for user in users] == ["user-a", "user-b"]
    assert users[0].auth_method is UacAuthMethod.LOCAL
    assert users[1].auth_method is UacAuthMethod.SSO
    assert isinstance(users[1].permissions, UacTemplatePermissions)
    assert rest.get_calls[0][1] is True
    assert "/.../" in rest.get_calls[0][0]


def test_auth_method_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        UacApiUserWrite(authMethod="kerberos")


def test_reads_other_uac_sections(uac_payloads: dict[str, dict[str, Any]]) -> None:
    rest = FakeRest(uac_payloads)
    api = UacAPI(SimpleNamespace(rest=rest))  # type: ignore[arg-type]

    assert api.get_domains()[0].id == "grp:domain-a"
    assert api.get_roles()[0].permissions.by_resource_type["device"].verbs == ["read"]
    assert api.get_permission_templates()[0].id == "template-read"
    assert api.get_ldap_servers()[0].host == "ldap.example"
    assert api.get_password_policy().min_length == 12


def test_update_user_uses_action_and_omits_unset_fields(
    uac_payloads: dict[str, dict[str, Any]],
) -> None:
    rest = FakeRest(uac_payloads)
    api = UacAPI(SimpleNamespace(rest=rest))  # type: ignore[arg-type]

    api.update_user("user-a", "1-rev-a", UacApiUserWrite(fullName="Updated User", password="test-password"))

    path, request = rest.post_calls[0]
    assert path.endswith("/actions/userman/updateUser")
    assert request.data == {
        "key": "user-a",
        "rev": "1-rev-a",
        "value": {
            "fullName": "Updated User",
            "password": "test-password",
        },
    }
    assert "test-password" not in repr(UacApiUserWrite(password="test-password"))


def test_revision_error_is_translated(
    uac_payloads: dict[str, dict[str, Any]],
) -> None:
    rest = FakeRest(uac_payloads)
    rest.post_error = ApiHttpError(
        method="POST",
        url="https://vip-server.example/rest/v2/actions/userman/updateUser",
        status_code=422,
        reason="Unprocessable Entity",
        response_body={
            "header": {
                "code": "VALIDATION_ERROR",
                "msg": ["Update error: Expected revision '1-current', got '0-stale'"],
                "errorDetails": [],
            }
        },
    )
    api = UacAPI(SimpleNamespace(rest=rest))  # type: ignore[arg-type]

    with pytest.raises(UacRevisionConflictError) as error:
        api.update_user("user-a", "0-stale", UacApiUserWrite(fullName="Updated User"))

    assert error.value.entity_id == "user-a"
    assert error.value.expected == "1-current"
    assert error.value.actual == "0-stale"


def test_patch_create_uses_strict_action_without_null_identity(
    uac_payloads: dict[str, dict[str, Any]],
) -> None:
    rest = FakeRest(uac_payloads)
    api = UacAPI(SimpleNamespace(rest=rest))  # type: ignore[arg-type]

    api.add_domain(UacApiDomainWrite(desc=UacDescription(label="Site B", desc="Synthetic domain")))

    _, request = rest.patch_calls[0]
    assert request.model_dump(mode="json", by_alias=True) == {
        "actions": [
            {
                "_action": "add",
                "desc": {
                    "label": "Site B",
                    "desc": "Synthetic domain",
                },
            }
        ],
        "mode": "strict",
    }


def test_apply_domain_actions_preserves_multiple_actions(
    uac_payloads: dict[str, dict[str, Any]],
) -> None:
    rest = FakeRest(uac_payloads)
    api = UacAPI(SimpleNamespace(rest=rest))  # type: ignore[arg-type]
    first = UacApiDomainWrite(desc=UacDescription(label="Site B"))
    second = UacApiDomainWrite(desc=UacDescription(label="Site C"))
    request = RequestV2Patch(
        actions=[
            Action(_action="add", desc=first.description.model_dump(mode="json", by_alias=True)),
            Action(_action="add", desc=second.description.model_dump(mode="json", by_alias=True)),
        ]
    )

    api.apply_domain_actions(request)

    path, submitted = rest.patch_calls[0]
    assert path.endswith("/domainman/domains")
    assert len(submitted.actions) == 2


def test_delete_patch_includes_revision(uac_payloads: dict[str, dict[str, Any]]) -> None:
    rest = FakeRest(uac_payloads)
    api = UacAPI(SimpleNamespace(rest=rest))  # type: ignore[arg-type]

    api.delete_domain(
        UacApiDomainWrite(
            _id="grp:domain-a",
            _rev="2-revision",
            desc=UacDescription(label="Site A"),
        )
    )

    _, request = rest.patch_calls[0]
    assert request.model_dump(mode="json", by_alias=True)["actions"] == [
        {
            "_action": "remove",
            "_id": "grp:domain-a",
            "_rev": "2-revision",
        }
    ]


def test_missing_password_policy_is_rejected(uac_payloads: dict[str, dict[str, Any]]) -> None:
    rest = FakeRest(uac_payloads)
    rest.payloads["passwordPolicy"] = {}
    api = UacAPI(SimpleNamespace(rest=rest))  # type: ignore[arg-type]

    with pytest.raises(UacRequestError, match="missing 'status'"):
        api.get_password_policy()


def _section_for_path(path: str) -> str:
    if "/userman/users/" in path:
        return "users"
    if "/domains/" in path:
        return "domains"
    if "/roles/" in path:
        return "roles"
    if "/permissionTemplates/" in path:
        return "permissionTemplates"
    if "/ldapservers/" in path:
        return "ldapServers"
    if "/passwordPolicy/" in path:
        return "passwordPolicy"
    raise AssertionError(f"Unexpected path: {path}")


def _header() -> SimpleNamespace:
    return SimpleNamespace(
        ok=True,
        code="OK",
        caption="Operation Successful",
        msg=[],
        errorDetails=[],
    )
