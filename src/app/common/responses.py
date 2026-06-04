from datetime import datetime
from typing import Any, Dict, List, Union

from fastapi.responses import JSONResponse
from pydantic import BaseModel


class StandardResponse(BaseModel):
    status_code: int
    message: str = ""
    data: Union[List[Any], Dict[str, Any], None] = None


def success_response(
    data: Union[List[Any], Dict[str, Any], Any] = None,
    message: str = "",
    status_code: int = 200,
) -> JSONResponse:
    body = StandardResponse(
        status_code=status_code,
        message=message,
        data=_serialize_data(data),
    )

    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(exclude_none=True),
    )


def _serialize_data(data: Any) -> Any:
    if isinstance(data, datetime):
        return data.isoformat()
    elif isinstance(data, dict):
        return {k: _serialize_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_serialize_data(item) for item in data]
    return data


class ErrorResponse(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
