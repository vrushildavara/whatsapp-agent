from typing import Any, List, Optional, Union

from pydantic import BaseModel, ConfigDict, field_validator


class BroadcastCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    template_name: str
    template_language: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or len(v) > 255:
            raise ValueError("Campaign name must be between 1 and 255 characters")
        return v

    @field_validator("template_language")
    @classmethod
    def validate_template_language(cls, v: str) -> str:
        # BCP-47 format validation (basic)
        if not v or len(v) > 20:
            raise ValueError("Template language must be a valid BCP-47 code")
        return v


class BroadcastUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    status: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v or len(v) > 255):
            raise ValueError("Campaign name must be between 1 and 255 characters")
        return v


class BroadcastContactResponse(BaseModel):
    id: int
    phone_number: str
    template_variables: Optional[Union[list, dict]] = None
    status: str
    meta_message_id: Optional[str] = None
    error_code: Optional[int] = None
    error_message: Optional[str] = None
    sent_at: Optional[str] = None
    delivered_at: Optional[str] = None
    created_at: str


class BroadcastResponse(BaseModel):
    id: int
    account_id: int
    name: str
    template_name: str
    template_language: str
    status: str
    total_contacts: int
    sent_count: int
    delivered_count: int
    failed_count: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class BroadcastDetailResponse(BaseModel):
    id: int
    account_id: int
    name: str
    template_name: str
    template_language: str
    template_snapshot: Optional[dict] = None
    status: str
    total_contacts: int
    sent_count: int
    delivered_count: int
    failed_count: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    contacts: Optional[List[BroadcastContactResponse]] = None


class PaginatedBroadcastsResponse(BaseModel):
    data: List[BroadcastResponse]
    total: int
    page: int
    page_size: int


class InvalidContactRow(BaseModel):
    row_number: int
    phone_number: str
    error: str


class ContactUploadResponse(BaseModel):
    broadcast_id: int
    filename: str
    contacts_uploaded: int
    invalid_contacts: int
    invalid_rows: list[InvalidContactRow]
