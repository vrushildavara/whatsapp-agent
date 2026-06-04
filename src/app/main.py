import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from scalar_fastapi import get_scalar_api_reference

from app.common.responses import ErrorResponse
from app.database.db_handler import lifespan as db_lifespan
from app.router import (
    account_router,
    broadcast_router,
    message_router,
    rag_router,
    session_router,
    template_router,
    tool_router,
    user_router,
)
from app.service.background_job import start_background_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with db_lifespan(app):
        await start_background_jobs()
        yield


app = FastAPI(
    title="WhatsApp Agent API Docs",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
)

app.include_router(user_router.router)
app.include_router(account_router.router)
app.include_router(session_router.router)
app.include_router(message_router.router)
app.include_router(broadcast_router.router)
app.include_router(template_router.router)
app.include_router(tool_router.router)
app.include_router(rag_router.router)


@app.get("/docs", include_in_schema=False)
def scalar_docs() -> HTMLResponse:
    return get_scalar_api_reference(
        openapi_url="/openapi.json",
        title="WhatsApp Agent API Docs",
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ErrorResponse)
async def error_response_handler(request: Request, exc: ErrorResponse) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"status_code": exc.status_code, "message": exc.message},
    )


@app.get("/", include_in_schema=False)
def read_root() -> dict:
    return {"message": "Whatsapp agent is running."}


@app.get("/health", include_in_schema=False)
def health_check() -> dict:
    return {"status": "healthy"}


def main() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
