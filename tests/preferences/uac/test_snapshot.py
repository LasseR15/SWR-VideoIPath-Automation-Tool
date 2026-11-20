from __future__ import annotations

from typing import Any

from videoipath_automation_tool.apps.preferences.uac.model import (
    UacApiDomain,
    UacApiLdapServer,
    UacApiPasswordPolicy,
    UacApiPermissionTemplate,
    UacApiRole,
    UacApiUser,
)
from videoipath_automation_tool.apps.preferences.uac.snapshot import UacSnapshot


class FakeUacAPI:
    def __init__(self, payloads: dict[str, dict[str, Any]]) -> None:
        self.payloads = payloads
        self.calls: list[str] = []

    def get_users(self, *, detail: bool = False) -> list[UacApiUser]:
        self.calls.append("users:detail" if detail else "users")
        items = self.payloads["users"]["status"]["userman"]["users"]["_items"]
        return [UacApiUser.model_validate(item) for item in items]

    def get_domains(self) -> list[UacApiDomain]:
        self.calls.append("domains")
        items = self.payloads["domains"]["config"]["domainman"]["domains"]["_items"]
        return [UacApiDomain.model_validate(item) for item in items]

    def get_roles(self) -> list[UacApiRole]:
        self.calls.append("roles")
        items = self.payloads["roles"]["config"]["security"]["users"]["roles"]["_items"]
        return [UacApiRole.model_validate(item) for item in items]

    def get_permission_templates(self) -> list[UacApiPermissionTemplate]:
        self.calls.append("permission_templates")
        items = self.payloads["permissionTemplates"]["config"]["security"]["users"]["permissionTemplates"]["_items"]
        return [UacApiPermissionTemplate.model_validate(item) for item in items]

    def get_ldap_servers(self) -> list[UacApiLdapServer]:
        self.calls.append("ldap_servers")
        items = self.payloads["ldapServers"]["config"]["userman"]["ldapservers"]["_items"]
        return [UacApiLdapServer.model_validate(item) for item in items]

    def get_password_policy(self) -> UacApiPasswordPolicy:
        self.calls.append("password_policy")
        value = self.payloads["passwordPolicy"]["status"]["userman"]["passwordPolicy"]
        return UacApiPasswordPolicy.model_validate(value)


def test_sections_load_lazily_and_are_cached(uac_payloads: dict[str, dict[str, Any]]) -> None:
    api = FakeUacAPI(uac_payloads)
    snapshot = UacSnapshot(api)  # type: ignore[arg-type]

    assert snapshot.get_user("user-a") is not None
    assert snapshot.get_user("user-a") is snapshot.get_user("user-a")
    assert api.calls == ["users"]

    assert snapshot.roles[0].name == "Read Access"
    assert api.calls == ["users", "roles"]


def test_domain_view_resolves_refreshed_revision(uac_payloads: dict[str, dict[str, Any]]) -> None:
    api = FakeUacAPI(uac_payloads)
    snapshot = UacSnapshot(api)  # type: ignore[arg-type]
    user = snapshot.get_user("user-a")
    assert user is not None
    assert user.revision.endswith("0001")

    uac_payloads["users"]["status"]["userman"]["users"]["_items"][0]["_rev"] = "2-00000000-0000-4000-8000-000000000006"
    snapshot.refresh("users")

    assert user.revision.endswith("0006")
    assert api.calls == ["users", "users"]


def test_user_detail_is_loaded_on_demand(uac_payloads: dict[str, dict[str, Any]]) -> None:
    api = FakeUacAPI(uac_payloads)
    snapshot = UacSnapshot(api)  # type: ignore[arg-type]

    assert snapshot.get_users()
    assert snapshot.get_users(detail=True)

    assert api.calls == ["users", "users:detail"]


def test_read_only_sections_parse_without_exposing_ldap_password(
    uac_payloads: dict[str, dict[str, Any]],
) -> None:
    snapshot = UacSnapshot(FakeUacAPI(uac_payloads))  # type: ignore[arg-type]

    server = snapshot.ldap_servers[0]
    policy = snapshot.password_policy

    assert server.host == "ldap.example"
    assert "password" not in repr(server)
    assert policy.min_length == 12
