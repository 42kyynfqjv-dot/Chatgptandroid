from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

AppName = Literal["chatgpt", "settings", "clock", "browser"]
IdempotencyKey = Annotated[str, Field(min_length=16, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]
Label = Annotated[str, Field(max_length=80, pattern=r"^[^\x00-\x1f\x7f]*$")]
Detail = Annotated[str, Field(max_length=240, pattern=r"^[^\x00-\x1f\x7f]*$")]
Hour = Annotated[int, Field(strict=True, ge=0, le=23)]
Minute = Annotated[int, Field(strict=True, ge=0, le=59)]
Status = Literal["queued", "awaiting_confirmation", "handed_off", "rejected", "expired", "failed", "unknown"]
ResultStatus = Literal["handed_off", "rejected", "failed", "unknown"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class OpenAppParams(StrictModel):
    app: AppName


class AlarmParams(StrictModel):
    hour: Hour
    minute: Minute
    label: Label = ""


class OpenAppRequest(StrictModel):
    action: Literal["open_app"]
    params: OpenAppParams
    idempotency_key: IdempotencyKey


class AlarmRequest(StrictModel):
    action: Literal["set_alarm"]
    params: AlarmParams
    idempotency_key: IdempotencyKey


CreateAction = Annotated[Union[OpenAppRequest, AlarmRequest], Field(discriminator="action")]


class Action(StrictModel):
    id: str
    action: Literal["open_app", "set_alarm"]
    params: Union[OpenAppParams, AlarmParams]
    status: Status
    created_at: float
    expires_at: float
    detail: Detail | None = None


class NextAction(StrictModel):
    action: Action | None


class DeviceResult(StrictModel):
    status: ResultStatus
    detail: Detail = ""
