from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class WhatsAppAccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    phone_number: str
    phone_id: str
    waba_id: str
    token: str
    prompt: str
    stage_flow: Optional[list[dict]] = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> int:
        if not v.isdigit():
            raise ValueError("Phone number must contain only digits")
        if len(v) < 10 or len(v) > 13:
            raise ValueError(
                "Phone number must contain at least 10 digits and at most 13 digits"
            )
        return int(v)

    @field_validator("waba_id")
    @classmethod
    def validate_waba_id(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("WABA ID must contain only digits")
        return v

    @field_validator("phone_id")
    @classmethod
    def validate_phone_id(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Phone ID must contain only digits")
        return v

    @field_validator("stage_flow")
    @classmethod
    def validate_stage_flow(cls, v):
        if v is None:
            return None

        validated = []
        for item in v:
            if "stage" not in item or "goal" not in item:
                raise ValueError("Each stage_flow item must have 'stage' and 'goal'")
            validated.append({"stage": item["stage"], "goal": item["goal"]})

        return validated


class WhatsAppAccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: Optional[str] = None
    stage_flow: Optional[list[dict]] = None

    @field_validator("stage_flow")
    @classmethod
    def validate_stage_flow(cls, v):
        if v is None:
            return None

        validated = []
        for item in v:
            if "stage" not in item or "goal" not in item:
                raise ValueError("Each stage_flow item must have 'stage' and 'goal'")
            validated.append({"stage": item["stage"], "goal": item["goal"]})

        return validated
