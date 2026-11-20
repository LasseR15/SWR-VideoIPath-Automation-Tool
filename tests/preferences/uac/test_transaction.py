from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from videoipath_automation_tool.apps.preferences.uac.app import UacApp
from videoipath_automation_tool.apps.preferences.uac.errors import UacRequestError


class TransactionRest:
    def __init__(self, payloads: dict[str, dict[str, Any]]) -> None:
        self.payloads = payloads
        self.post_calls: list[tuple[str, Any]] = []
        self.patch_calls: list[tuple[str, Any]] = []
        self.fail_user: str | None = None
        self.fail_patch = False
        self.fail_get_section: str | None = None

    def get(self, path: str, **_: Any) -> SimpleNamespace:
        section = _section_for_path(path)
        if section == self.fail_get_section:
            raise UacRequestError(f"Synthetic GET failure for '{section}'")
        return SimpleNamespace(data=deepcopy(self.payloads[section]), header=_header())

    def post(self, path: str, body: Any, **_: Any) -> SimpleNamespace:
        self.post_calls.append((path, body))
        name = body.data["key"]
        if name == self.fail_user:
            raise UacRequestError(f"Synthetic failure for '{name}'")
        if path.endswith("/addUser"):
            self.payloads["users"]["status"]["userman"]["users"]["_items"].append(
                {
                    "_id": name,
                    "_rev": "1-new-user",
                    "_vid": name,
                    "name": name,
                    **body.data["value"],
                }
            )
        elif path.endswith("/updateUser"):
            record = self._user(name)
            record.update(body.data["value"])
            record["_rev"] = f"next-{record['_rev']}"
        elif path.endswith("/deleteUser"):
            users = self.payloads["users"]["status"]["userman"]["users"]["_items"]
            users[:] = [record for record in users if record.get("name") != name]
        return SimpleNamespace(data=None, header=_header())

    def patch(self, path: str, body: Any, **_: Any) -> SimpleNamespace:
        self.patch_calls.append((path, body))
        if self.fail_patch:
            raise UacRequestError("Synthetic PATCH failure")

        actions = body.model_dump(mode="json", by_alias=True)["actions"]
        items = []
        for index, action in enumerate(actions):
            entity_id = action.get("_id") or f"{_section_for_path(path)}-{index}"
            items.append(
                SimpleNamespace(
                    actionRef={"idx": index},
                    id=entity_id,
                    rev=f"{index}-patched",
                    msg="",
                    res={"add": "added", "update": "updated", "remove": "removed"}[action["_action"]],
                )
            )
        return SimpleNamespace(header=_header(), result=SimpleNamespace(items=items))

    def _user(self, name: str) -> dict[str, Any]:
        records = self.payloads["users"]["status"]["userman"]["users"]["_items"]
        return next(record for record in records if record["name"] == name)


def test_transaction_stages_without_network_write(uac_payloads: dict[str, dict[str, Any]]) -> None:
    rest = TransactionRest(uac_payloads)
    app = UacApp(SimpleNamespace(rest=rest))  # type: ignore[arg-type]
    transaction = app.transaction()

    transaction.create_user("user-c", full_name="Test User C")
    transaction.update_role("role-read", description="Updated role")

    assert len(transaction) == 2
    assert rest.post_calls == []
    assert rest.patch_calls == []
    transaction.discard()


def test_user_transaction_continues_after_failure(
    uac_payloads: dict[str, dict[str, Any]],
) -> None:
    rest = TransactionRest(uac_payloads)
    rest.fail_user = "user-c"
    app = UacApp(SimpleNamespace(rest=rest))  # type: ignore[arg-type]

    with app.transaction() as transaction:
        transaction.create_user("user-c")
        transaction.create_user("user-d")
        result = transaction.commit()

    assert result.ok is False
    assert [failure.entity_id for failure in result.failed] == ["user-c"]
    assert [applied.entity_id for applied in result.applied] == ["user-d"]
    assert [call[1].data["key"] for call in rest.post_calls] == ["user-c", "user-d"]


def test_collection_operations_are_sent_in_one_strict_patch(
    uac_payloads: dict[str, dict[str, Any]],
) -> None:
    rest = TransactionRest(uac_payloads)
    app = UacApp(SimpleNamespace(rest=rest))  # type: ignore[arg-type]

    with app.transaction() as transaction:
        transaction.update_role("role-read", description="Updated role")
        transaction.create_role("Synthetic Role")
        result = transaction.commit()

    assert result.ok is True
    assert len(rest.patch_calls) == 1
    path, request = rest.patch_calls[0]
    assert path.endswith("/config/security/users/roles")
    assert request.mode == "strict"
    assert [action.action for action in request.actions] == ["update", "add"]


def test_collection_patch_failure_reports_every_action(
    uac_payloads: dict[str, dict[str, Any]],
) -> None:
    rest = TransactionRest(uac_payloads)
    rest.fail_patch = True
    app = UacApp(SimpleNamespace(rest=rest))  # type: ignore[arg-type]

    with app.transaction() as transaction:
        transaction.update_role("role-read", description="Updated role")
        transaction.create_role("Synthetic Role")
        result = transaction.commit()

    assert len(result.failed) == 2
    assert all("Synthetic PATCH failure" == failure.message for failure in result.failed)


def test_conflicted_operation_is_skipped_while_other_user_applies(
    uac_payloads: dict[str, dict[str, Any]],
) -> None:
    rest = TransactionRest(uac_payloads)
    app = UacApp(SimpleNamespace(rest=rest))  # type: ignore[arg-type]
    user_a = app.get_user("user-a")
    assert user_a is not None

    transaction = app.transaction()
    transaction.update_user(user_a, full_name="Updated User A")
    transaction.create_user("user-c")
    uac_payloads["users"]["status"]["userman"]["users"]["_items"][0]["email"] = "changed@example.invalid"

    result = transaction.commit()

    assert [failure.action for failure in result.failed] == ["update"]
    assert [applied.action for applied in result.applied] == ["add"]
    assert [call[1].data["key"] for call in rest.post_calls] == ["user-c"]


def test_failed_user_preflight_does_not_prevent_patch_group(
    uac_payloads: dict[str, dict[str, Any]],
) -> None:
    rest = TransactionRest(uac_payloads)
    app = UacApp(SimpleNamespace(rest=rest))  # type: ignore[arg-type]

    transaction = app.transaction()
    transaction.update_user("user-a", full_name="Updated User A")
    transaction.create_role("Synthetic Role")
    rest.fail_get_section = "users"

    result = transaction.commit()

    assert [failure.kind for failure in result.failed] == ["user"]
    assert [applied.kind for applied in result.applied] == ["role"]
    assert len(rest.patch_calls) == 1


def _section_for_path(path: str) -> str:
    if "/userman/users/" in path or "/userman/" in path and path.endswith(("addUser", "updateUser", "deleteUser")):
        return "users"
    if "/domains" in path:
        return "domains"
    if "/roles" in path:
        return "roles"
    if "/permissionTemplates" in path:
        return "permissionTemplates"
    raise AssertionError(f"Unexpected path: {path}")


def _header() -> SimpleNamespace:
    return SimpleNamespace(
        ok=True,
        code="OK",
        caption="Operation Successful",
        msg=[],
        errorDetails=[],
    )
