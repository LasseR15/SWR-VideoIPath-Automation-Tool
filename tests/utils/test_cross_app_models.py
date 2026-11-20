import pytest
from pydantic import ValidationError

from videoipath_automation_tool.utils.cross_app_models import FrozenModel, InternalModel


class _MutableRecord(InternalModel):
    value: int


class _FrozenRecord(FrozenModel):
    value: int


def test_internal_model_validates_assignment() -> None:
    record = _MutableRecord(value=1)

    record.value = 2
    assert record.value == 2

    with pytest.raises(ValidationError):
        record.value = "not-an-int"  # type: ignore[assignment]


def test_frozen_model_rejects_mutation() -> None:
    record = _FrozenRecord(value=1)

    with pytest.raises(ValidationError):
        record.value = 2
