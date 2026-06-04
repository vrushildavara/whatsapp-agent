import logging
import tempfile
from io import BytesIO
from pathlib import Path

import aiofiles
from fastapi import UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import ErrorResponse, success_response
from app.service.rag_service import RAGService
from app.validation.rag_validation import (
    MAX_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_MB,
    validate_file_size,
    validate_file_upload,
)

logger = logging.getLogger(__name__)

# Temporary directory for chunk storage
TEMP_CHUNK_DIR = Path(tempfile.gettempdir()) / "whatsapp_rag_chunks"


def _get_chunk_dir(user_id: int, file_id: str) -> Path:
    """Get directory path for storing chunks"""
    chunk_dir = TEMP_CHUNK_DIR / f"{user_id}_{file_id}"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    return chunk_dir


def _get_chunk_path(user_id: int, file_id: str, chunk_index: int) -> Path:
    """Get file path for a specific chunk"""
    chunk_dir = _get_chunk_dir(user_id, file_id)
    return chunk_dir / f"chunk_{chunk_index}.bin"


def _get_metadata_path(user_id: int, file_id: str) -> Path:
    """Get metadata file path for tracking received chunks"""
    chunk_dir = _get_chunk_dir(user_id, file_id)
    return chunk_dir / "metadata.txt"


async def upload_file_controller(
    user_id: int, file: UploadFile, db: AsyncSession
) -> JSONResponse:
    """Upload PDF/DOCX/TXT file and create RAG collection"""
    # Validate file type and extension
    validate_file_upload(file)

    # Validate file size and read content
    file_size_mb = await validate_file_size(file)

    logger.info(
        "File validation passed | filename=%s | size=%.2fMB | type=%s",
        file.filename,
        file_size_mb,
        file.content_type,
    )

    # Reset file pointer after validation read
    await file.seek(0)

    service = RAGService(db)

    try:
        # Upload to external RAG service
        result = await service.api_service.upload_file(file)
    except RuntimeError as e:
        raise ErrorResponse(500, str(e))

    # Store in database
    rag_doc = await service.create_rag_document(
        user_id=user_id,
        filename=file.filename or "unknown",
        collection_name=result["collection_name"],
        chunks_count=result["chunks_count"],
    )

    logger.info(
        "RAG document created | user_id=%s | collection=%s | chunks=%s",
        user_id,
        rag_doc["collection_name"],
        rag_doc["chunks_count"],
    )

    return success_response(
        data={
            "collection_name": rag_doc["collection_name"],
            "chunks_count": rag_doc["chunks_count"],
            "filename": rag_doc["filename"],
            "created_at": rag_doc["created_at"],
        },
        message="File uploaded and processed successfully",
        status_code=200,
    )


async def handle_chunked_upload(
    user_id: int,
    chunk: UploadFile,
    chunk_index: int,
    total_chunks: int,
    file_id: str,
    filename: str,
    db: AsyncSession,
) -> JSONResponse:
    """Handle chunked upload using temporary files"""
    chunk_path = _get_chunk_path(user_id, file_id, chunk_index)
    metadata_path = _get_metadata_path(user_id, file_id)

    # Save chunk to temporary file
    chunk_content = await chunk.read()
    async with aiofiles.open(chunk_path, "wb") as f:
        await f.write(chunk_content)

    # Track received chunks in metadata file
    received_chunks = set()
    if metadata_path.exists():
        async with aiofiles.open(metadata_path, "r") as f:
            content = await f.read()
            received_chunks = set(int(x) for x in content.strip().split(",") if x)

    received_chunks.add(chunk_index)

    async with aiofiles.open(metadata_path, "w") as f:
        await f.write(",".join(map(str, sorted(received_chunks))))

    logger.info(
        "Chunk stored in temp file | user_id=%s | file_id=%s | chunk=%d/%d",
        user_id,
        file_id,
        chunk_index + 1,
        total_chunks,
    )

    if len(received_chunks) < total_chunks:
        return success_response(
            data={
                "chunk_index": chunk_index,
                "received": len(received_chunks),
                "total": total_chunks,
            },
            message=f"Chunk {chunk_index + 1}/{total_chunks} received",
            status_code=200,
        )

    # All chunks received - reassemble
    logger.info(
        "All chunks received, reassembling from temp files | user_id=%s | file_id=%s",
        user_id,
        file_id,
    )

    assembled_content = BytesIO()
    for i in range(total_chunks):
        chunk_file = _get_chunk_path(user_id, file_id, i)
        if not chunk_file.exists():
            await _cleanup_temp_chunks(user_id, file_id)
            raise ErrorResponse(500, f"Chunk {i} missing from temp storage")
        async with aiofiles.open(chunk_file, "rb") as f:
            chunk_data = await f.read()
            assembled_content.write(chunk_data)

    assembled_content.seek(0)
    file_size_mb = len(assembled_content.getvalue()) / (1024 * 1024)

    logger.info(
        "File reassembled from Redis | file_id=%s | filename=%s | size=%.2fMB",
        file_id,
        filename,
        file_size_mb,
    )

    # Validate assembled file size
    if len(assembled_content.getvalue()) > MAX_FILE_SIZE_BYTES:
        await _cleanup_temp_chunks(user_id, file_id)
        raise ErrorResponse(
            400,
            f"Assembled file size ({file_size_mb:.2f}MB) exceeds maximum allowed size of {MAX_FILE_SIZE_MB}MB",
        )

    # Determine content type
    content_type = (
        "application/pdf"
        if filename.endswith(".pdf")
        else (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if filename.endswith(".docx")
            else "text/plain"
        )
    )

    # Create UploadFile from assembled content
    assembled_content.content_type = content_type  # type: ignore
    upload_file = UploadFile(filename=filename, file=assembled_content)  # type: ignore

    try:
        # Validate and upload
        validate_file_upload(upload_file)

        service = RAGService(db)
        result = await service.api_service.upload_file(upload_file)

        rag_doc = await service.create_rag_document(
            user_id=user_id,
            filename=filename,
            collection_name=result["collection_name"],
            chunks_count=result["chunks_count"],
        )

        logger.info(
            "Chunked upload complete | user_id=%s | collection=%s | chunks=%s",
            user_id,
            rag_doc["collection_name"],
            rag_doc["chunks_count"],
        )

        return success_response(
            data={
                "collection_name": rag_doc["collection_name"],
                "chunks_count": rag_doc["chunks_count"],
                "filename": rag_doc["filename"],
                "created_at": rag_doc["created_at"],
            },
            message="File uploaded and processed successfully",
            status_code=200,
        )
    except RuntimeError as e:
        error_msg = str(e)
        if "400" in error_msg:
            raise ErrorResponse(
                400,
                "RAG service rejected the file. It may exceed the size limit or have invalid format.",
            )
        raise ErrorResponse(500, f"RAG service error: {error_msg}")
    finally:
        # Cleanup temporary chunks
        await _cleanup_temp_chunks(user_id, file_id)


async def _cleanup_temp_chunks(user_id: int, file_id: str) -> None:
    """Delete all temporary chunk files and directory"""
    try:
        chunk_dir = _get_chunk_dir(user_id, file_id)
        if chunk_dir.exists():
            # Delete all files in the directory
            for file_path in chunk_dir.iterdir():
                file_path.unlink()
            # Delete the directory itself
            chunk_dir.rmdir()
            logger.info(
                "Temp chunks cleaned up | user_id=%s | file_id=%s", user_id, file_id
            )
    except Exception as e:
        logger.warning(
            "Failed to cleanup temp chunks | user_id=%s | file_id=%s | error=%s",
            user_id,
            file_id,
            e,
        )


async def delete_collection_controller(
    user_id: int, collection_name: str, db: AsyncSession
) -> JSONResponse:
    """Delete RAG collection"""
    service = RAGService(db)

    # Check if document exists and belongs to user
    document = await service.get_document_by_collection(user_id, collection_name)

    if not document:
        raise ErrorResponse(404, "Collection not found or access denied")

    # Hard delete in database
    await service.delete_document(document["id"])

    # Delete from external RAG service (best effort)
    await service.api_service.delete_collection(collection_name)

    logger.info(
        "RAG collection deleted | user_id=%s | collection=%s",
        user_id,
        collection_name,
    )

    return success_response(
        data={"collection_name": collection_name},
        message="Collection deleted successfully",
        status_code=200,
    )


async def list_documents_controller(user_id: int, db: AsyncSession) -> JSONResponse:
    """List all RAG documents for user"""
    service = RAGService(db)

    documents = await service.list_user_documents(user_id)

    return success_response(
        data=documents,
        message="Documents retrieved successfully",
        status_code=200,
    )
