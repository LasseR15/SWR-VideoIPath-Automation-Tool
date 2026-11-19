from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class InternalModel(BaseModel):
    """Base model for validated, mutable objects used inside an app."""

    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)


class FrozenModel(InternalModel):
    """Immutable, slot-backed variant of :class:`InternalModel`."""

    model_config = ConfigDict(frozen=True, slots=True, validate_assignment=True, arbitrary_types_allowed=True)


class HydrationLevel(str, Enum):
    SKELETON = "skeleton"
    FULL = "full"


class ApiBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, validate_assignment=True, extra="allow")


class ApiResponseHeaderBaseModel(ApiBaseModel):
    auth: bool
    caption: str
    code: str
    errorCodes: list[Any] = Field(default_factory=list)
    errorDetails: list[Any] = Field(default_factory=list)
    id: str
    msg: list[str] = Field(default_factory=list)
    ok: bool
    user: str


class ApiResponseDataBaseModel(ApiBaseModel):
    @property
    def success(self) -> bool:
        # Should be overwritten if body also provides info about success
        # Gets called by the ApiResponseBaseModel success method
        return True


_DataT = TypeVar("_DataT")


class ApiResponseBaseModel(ApiBaseModel, Generic[_DataT]):
    data: _DataT
    """ Should optimally be extending ApiResponseDataBaseModel """
    header: ApiResponseHeaderBaseModel

    @property
    def success(self) -> bool:
        """ Returns the status reported inside the ``header`` part of the response body
            and calls the success check from data if the data attribute extends the ApiResponseDataBaseModel.
        """
        if isinstance(self.data, ApiResponseDataBaseModel):
            return self.header.ok and self.data.success
        return self.header.ok