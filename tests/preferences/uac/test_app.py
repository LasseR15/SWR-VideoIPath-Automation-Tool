from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from videoipath_automation_tool.apps.preferences.uac.app import UacApp
from videoipath_automation_tool.utils.cross_app_errors import ApiCommitConflictError


class StatefulRest:
    def __init__(self, payloads: dict[str, dict[str, Any]]) -> None:
        self.payloads = payloads
        self.post_calls: list[tuple[str, Any]] = []

    def get(self, path: str, **_: Any) -> SimpleNamespace:
        section = _section_for_path(path)
        return SimpleNamespace(data=self.payloads[section], header=_header())

    def post(self, path: str, body: Any, **_: Any) -> SimpleNamespace:
        self.post_calls.append((path, body))
        if path.endswith("/updateUser"):
            record = self._user(body.data["key"])
            record.update(body.data["value"])
            record["_rev"] = "2-00000000-0000-4000-8000-000000000010"
        return SimpleNamespace(data=None, header=_header())

    def patch(self, path: str, body: Any, **_: Any) -> SimpleNamespace:
        action = body.model_dump(mode="json", by_alias=True)["actions"][0]
        if path.endswith("/domains") and action["_action"] == "add":
            item = {
                "_id": "grp:domain-b",
                "_rev": "0-00000000-0000-4000-8000-000000000011",
                "_vid": "grp:domain-b",
                "desc": action["desc"],
            }
            self.payloads["domains"]["config"]["domainman"]["domains"]["_items"].append(item)
            return SimpleNamespace(
                header=_header(),
                result=SimpleNamespace(
                    items=[
                        SimpleNamespace(
                            id=item["_id"],
                            rev=item["_rev"],
                            actionRef={"idx": 0},
                            msg="",
                            res="added",
                        )
                    ]
                ),
            )
        raise AssertionError(f"Unexpected PATCH: {path}")

    def _user(self, name: str) -> dict[str, Any]:
        items = self.payloads["users"]["status"]["userman"]["users"]["_items"]
        return next(item for item in items if item["name"] == name)


def test_user_update_uses_snapshot_revision_and_refreshes(
    uac_payloads: dict[str, dict[str, Any]],
) -> None:
    rest = StatefulRest(uac_payloads)
    app = UacApp(SimpleNamespace(rest=rest))  # type: ignore[arg-type]
    user = app.get_user("user-a")
    assert user is not None

    updated = app.update_user(user, full_name="Updated User A")

    assert updated is user
    assert updated.full_name == "Updated User A"
    assert updated.revision.endswith("0010")


def test_domain_create_returns_refreshed_domain(
    uac_payloads: dict[str, dict[str, Any]],
) -> None:
    app = UacApp(SimpleNamespace(rest=StatefulRest(uac_payloads)))  # type: ignore[arg-type]

    domain = app.create_domain("Site B", "Synthetic domain B")

    assert domain.id == "grp:domain-b"
    assert domain.name == "Site B"
    assert domain.description == "Synthetic domain B"


def test_user_update_rejects_empty_change_set(uac_payloads: dict[str, dict[str, Any]]) -> None:
    app = UacApp(SimpleNamespace(rest=StatefulRest(uac_payloads)))  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="At least one user field"):
        app.update_user("user-a")


def test_user_update_detects_server_changes_before_write(
    uac_payloads: dict[str, dict[str, Any]],
) -> None:
    rest = StatefulRest(uac_payloads)
    app = UacApp(SimpleNamespace(rest=rest))  # type: ignore[arg-type]
    user = app.get_user("user-a")
    assert user is not None
    transaction = app.transaction()
    transaction.update_user(user, full_name="Updated User A")
    uac_payloads["users"]["status"]["userman"]["users"]["_items"][0]["email"] = "changed@example.invalid"

    result = transaction.commit()

    assert result.failed
    error = result.failed[0].error
    assert isinstance(error, ApiCommitConflictError)
    assert error.conflicts[0].field_diffs["email"] == (
        "user-a@example.invalid",
        "changed@example.invalid",
    )
    assert rest.post_calls == []


def test_user_update_uses_fresh_revision_when_content_is_unchanged(
    uac_payloads: dict[str, dict[str, Any]],
) -> None:
    rest = StatefulRest(uac_payloads)
    app = UacApp(SimpleNamespace(rest=rest))  # type: ignore[arg-type]
    user = app.get_user("user-a")
    assert user is not None
    fresh_revision = "7-00000000-0000-4000-8000-000000000007"
    uac_payloads["users"]["status"]["userman"]["users"]["_items"][0]["_rev"] = fresh_revision

    app.update_user(user, full_name="Updated User A")

    assert rest.post_calls[0][1].data["rev"] == fresh_revision


def test_user_update_can_explicitly_skip_conflict_comparison(
    uac_payloads: dict[str, dict[str, Any]],
) -> None:
    rest = StatefulRest(uac_payloads)
    app = UacApp(SimpleNamespace(rest=rest))  # type: ignore[arg-type]
    user = app.get_user("user-a")
    assert user is not None
    current = uac_payloads["users"]["status"]["userman"]["users"]["_items"][0]
    current["email"] = "changed@example.invalid"
    fresh_revision = "8-00000000-0000-4000-8000-000000000008"
    current["_rev"] = fresh_revision

    app.update_user(user, full_name="Updated User A", check_conflicts=False)

    assert rest.post_calls[0][1].data["rev"] == fresh_revision


def _section_for_path(path: str) -> str:
    if "/users/" in path:
        return "users"
    if "/domains/" in path:
        return "domains"
    raise AssertionError(f"Unexpected GET: {path}")


def _header() -> SimpleNamespace:
    return SimpleNamespace(
        ok=True,
        code="OK",
        caption="Operation Successful",
        msg=[],
        errorDetails=[],
    )
