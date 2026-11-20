from types import SimpleNamespace

from videoipath_automation_tool.apps.preferences import UacApp, UacCommitResult, UacTransaction
from videoipath_automation_tool.apps.preferences.preferences_app import PreferencesApp


def test_preferences_uac_is_lazy() -> None:
    preferences = PreferencesApp(SimpleNamespace())  # type: ignore[arg-type]

    assert preferences._uac is None
    assert isinstance(preferences.uac, UacApp)
    assert preferences.uac is preferences.uac
    assert isinstance(preferences.uac.transaction(), UacTransaction)
    assert UacCommitResult.__name__ == "UacCommitResult"
