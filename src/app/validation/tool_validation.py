from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

ALLOWED_TOOL_TYPES = {"knowledge", "api_request"}
ALLOWED_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
ALLOWED_API_REQUEST_CONFIG_FIELDS = {"url", "method", "description", "headers", "body", "query_params"}
ALLOWED_KNOWLEDGE_CONFIG_FIELDS = {"file_ids"}
ALL_ALLOWED_CONFIG_FIELDS = ALLOWED_API_REQUEST_CONFIG_FIELDS | ALLOWED_KNOWLEDGE_CONFIG_FIELDS


def _validate_api_request_config_fields(config: dict) -> None:
    """Validate individual field values in an api_request config dict."""
    extra = set(config.keys()) - ALLOWED_API_REQUEST_CONFIG_FIELDS
    if extra:
        raise ValueError(
            f"api_request config contains unknown fields: {sorted(extra)}. "
            f"Allowed fields: {sorted(ALLOWED_API_REQUEST_CONFIG_FIELDS)}"
        )

    url = config.get("url")
    if url is not None:
        if not isinstance(url, str) or not url.strip():
            raise ValueError("api_request config 'url' must be a non-empty string")

    method = config.get("method")
    if method is not None:
        if not isinstance(method, str) or method.upper() not in ALLOWED_HTTP_METHODS:
            raise ValueError(
                f"api_request config 'method' must be one of: {sorted(ALLOWED_HTTP_METHODS)}"
            )

    description = config.get("description")
    if description is not None:
        if not isinstance(description, str) or not description.strip():
            raise ValueError("api_request config 'description' must be a non-empty string")

    headers = config.get("headers")
    if headers is not None:
        if not isinstance(headers, dict) or not isinstance(headers.get("properties"), list):
            raise ValueError(
                "api_request config 'headers' must be an object with a 'properties' list"
            )

    body = config.get("body")
    if body is not None:
        if not isinstance(body, dict) or not isinstance(body.get("properties"), list):
            raise ValueError(
                "api_request config 'body' must be an object with a 'properties' list"
            )

    query_params = config.get("query_params")
    if query_params is not None:
        if not isinstance(query_params, dict) or not isinstance(query_params.get("properties"), list):
            raise ValueError(
                "api_request config 'query_params' must be an object with a 'properties' list"
            )


class AssistantToolCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    tool_type: str = "api_request"
    config: dict
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 255:
            raise ValueError("Tool name must be between 1 and 255 characters")
        return v

    @field_validator("tool_type")
    @classmethod
    def validate_tool_type(cls, v: str) -> str:
        if v not in ALLOWED_TOOL_TYPES:
            raise ValueError(f"tool_type must be one of: {ALLOWED_TOOL_TYPES}")
        return v

    @model_validator(mode="after")
    def validate_config_for_type(self) -> "AssistantToolCreate":
        config = self.config
        if not config:
            raise ValueError("config must not be empty")
        if self.tool_type == "api_request":
            url = config.get("url")
            if not url or not isinstance(url, str) or not url.strip():
                raise ValueError("api_request config must include a non-empty 'url' string")
            _validate_api_request_config_fields(config)
        elif self.tool_type == "knowledge":
            extra = set(config.keys()) - ALLOWED_KNOWLEDGE_CONFIG_FIELDS
            if extra:
                raise ValueError(
                    f"knowledge config contains unknown fields: {sorted(extra)}. "
                    f"Allowed fields: {sorted(ALLOWED_KNOWLEDGE_CONFIG_FIELDS)}"
                )
            file_ids = config.get("file_ids")
            if not isinstance(file_ids, list) or not file_ids:
                raise ValueError("knowledge config must include a non-empty 'file_ids' list")
        return self


class AssistantToolUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    config: Optional[dict] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v or len(v) > 255:
                raise ValueError("Tool name must be between 1 and 255 characters")
        return v

    @field_validator("config")
    @classmethod
    def validate_config(cls, v: Optional[dict]) -> Optional[dict]:
        if v is None:
            return v
        if not v:
            raise ValueError("config must not be empty")
        extra = set(v.keys()) - ALL_ALLOWED_CONFIG_FIELDS
        if extra:
            raise ValueError(
                f"config contains unknown fields: {sorted(extra)}. "
                f"Allowed fields: {sorted(ALL_ALLOWED_CONFIG_FIELDS)}"
            )
        # Validate any api_request-specific fields that are present
        api_request_keys = set(v.keys()) & ALLOWED_API_REQUEST_CONFIG_FIELDS
        if api_request_keys:
            _validate_api_request_config_fields({k: v[k] for k in api_request_keys})
        return v
