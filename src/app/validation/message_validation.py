from typing import Annotated, List, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_serializer,
    model_validator,
)


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_number: int
    to_number: int
    message: str
    media: Optional[str] = None
    meta_message_id: Optional[str] = None
    media_type: Optional[str] = None  # MIME type hint (e.g. "audio/ogg", "video/mp4")
    media_bytes: Optional[list[str]] = None
    sandbox: bool = False

    @field_validator("from_number", mode="before")
    @classmethod
    def validate_from_number(cls, v) -> int:
        if v is None:
            raise ValueError("Phone number cannot be None")
        return int("".join(filter(str.isdigit, str(v))))

    @field_validator("to_number", mode="before")
    @classmethod
    def validate_to_number(cls, v) -> int:
        if v is None:
            raise ValueError("to_number cannot be None")
        return int("".join(filter(str.isdigit, str(v))))

    @field_validator("message", mode="before")
    @classmethod
    def validate_message(cls, v) -> str:
        if v is None or v == "":
            return "[Media]"
        return str(v)


class ReactionSend(BaseModel):
    account_id: int
    to_number: int
    message_id: str
    emoji: str
    sandbox: bool = False

    @field_validator("to_number", mode="before")
    @classmethod
    def validate_to_number(cls, v) -> int:
        if v is None:
            raise ValueError("to_number cannot be None")
        return int("".join(filter(str.isdigit, str(v))))


class TextParameter(BaseModel):
    type: Literal["text"] = "text"
    text: str

    @field_validator("text")
    @classmethod
    def text_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("text parameter must not be empty")
        return v


class ImageParameter(BaseModel):
    """Pass `link` (public URL) or `id` (WhatsApp media ID) directly — no nested dict."""

    type: Literal["image"] = "image"
    link: Optional[str] = None
    id: Optional[str] = None

    @model_serializer
    def _to_meta(self) -> dict:
        media = {k: v for k, v in {"link": self.link, "id": self.id}.items() if v}
        return {"type": "image", "image": media}


class VideoParameter(BaseModel):
    """Pass `link` (public URL) or `id` (WhatsApp media ID) directly — no nested dict."""

    type: Literal["video"] = "video"
    link: Optional[str] = None
    id: Optional[str] = None

    @model_serializer
    def _to_meta(self) -> dict:
        media = {k: v for k, v in {"link": self.link, "id": self.id}.items() if v}
        return {"type": "video", "video": media}


class DocumentParameter(BaseModel):
    """Pass `link`, `id`, and optional `filename` directly — no nested dict."""

    type: Literal["document"] = "document"
    link: Optional[str] = None
    id: Optional[str] = None
    filename: Optional[str] = None

    @model_serializer
    def _to_meta(self) -> dict:
        doc = {
            k: v
            for k, v in {
                "link": self.link,
                "id": self.id,
                "filename": self.filename,
            }.items()
            if v
        }
        return {"type": "document", "document": doc}


class PayloadParameter(BaseModel):
    """Used for quick-reply button parameters."""

    type: Literal["payload"] = "payload"
    payload: str


TemplateParameter = Annotated[
    Union[
        TextParameter,
        ImageParameter,
        VideoParameter,
        DocumentParameter,
        PayloadParameter,
    ],
    Field(discriminator="type"),
]


class HeaderComponent(BaseModel):
    type: Literal["header"] = "header"
    parameters: List[TemplateParameter]


class BodyComponent(BaseModel):
    type: Literal["body"] = "body"
    parameters: List[TemplateParameter]


class ButtonComponent(BaseModel):
    type: Literal["button"] = "button"
    sub_type: Literal["quick_reply", "url"]
    index: int
    parameters: List[TemplateParameter]

    @model_validator(mode="after")
    def validate_parameter_types(self) -> "ButtonComponent":
        if self.sub_type == "url":
            for p in self.parameters:
                if not isinstance(p, TextParameter):
                    raise ValueError(
                        f"URL buttons require 'text' parameters, got '{p.type}'"
                    )
        elif self.sub_type == "quick_reply":
            for p in self.parameters:
                if not isinstance(p, PayloadParameter):
                    raise ValueError(
                        f"quick_reply buttons require 'payload' parameters, got '{p.type}'"
                    )
        return self


TemplateComponent = Annotated[
    Union[HeaderComponent, BodyComponent, ButtonComponent],
    Field(discriminator="type"),
]


class TemplateMessage(BaseModel):
    name: str
    language: str
    components: Optional[List[TemplateComponent]] = None


class TemplateSend(BaseModel):
    to_number: str
    template_name: str
    language: str = "en"
    components: Optional[List[TemplateComponent]] = None


class AssistantMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: int
    to_number: int
    message: Optional[str] = None
    media_bytes: Optional[list[str]] = None
    media_names: Optional[list[str]] = None
    template: Optional[TemplateMessage] = None
    sandbox: bool = False

    @field_validator("to_number", mode="before")
    @classmethod
    def validate_to_number(cls, v) -> int:
        if v is None:
            raise ValueError("to_number cannot be None")
        return int("".join(filter(str.isdigit, str(v))))

    @field_validator("message", mode="before")
    @classmethod
    def validate_message_optional(cls, v) -> str | None:
        if v is None or v == "":
            return None
        return str(v)

    @model_validator(mode="after")
    def validate_payload(self) -> "AssistantMessage":
        has_message = self.message is not None
        has_template = self.template is not None
        has_media = bool(self.media_bytes or self.media_names)

        if not has_message and not has_template and not has_media:
            raise ValueError("Either message, template, or media must be provided")
        if has_message and has_template:
            raise ValueError("Only one of message or template can be provided")
        if has_template and has_media:
            raise ValueError("Media is not supported with templates")

        return self
