from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.controller.rag_controller import (
    delete_collection_controller,
    handle_chunked_upload,
    list_documents_controller,
    upload_file_controller,
)
from app.database.db_handler import get_db
from app.utils.middleware import CurrentUser, get_current_user

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post("/upload")
async def upload_file(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(None),
    # Chunked upload fields
    chunk: UploadFile = File(None),
    chunk_index: int = Form(None),
    total_chunks: int = Form(None),
    file_id: str = Form(None),
    filename: str = Form(None),
) -> JSONResponse:
    """Upload PDF/DOCX/TXT file (supports both direct and chunked upload)"""
    # Chunked upload
    if chunk and chunk_index is not None:
        return await handle_chunked_upload(
            current_user.id, chunk, chunk_index, total_chunks, file_id, filename, db
        )

    # Direct upload (existing)
    return await upload_file_controller(current_user.id, file, db)


@router.delete("/collection/{collection_name}")
async def delete_collection(
    collection_name: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Delete a RAG collection"""
    return await delete_collection_controller(current_user.id, collection_name, db)


@router.get("/documents")
async def list_documents(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """List all RAG documents for the current user"""
    return await list_documents_controller(current_user.id, db)
