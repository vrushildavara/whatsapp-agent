import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select

from app.models.model import RAGDocument

# -------------------------UPLOAD FILE (DIRECT)----------------------------


@pytest.mark.asyncio
@patch(
    "app.service.rag_service.RAGAPIService.upload_file",
    new_callable=AsyncMock,
    return_value={"collection_name": "col_pdf_001", "chunks_count": 4},
)
async def test_upload_file_pdf_success(
    mock_upload, client, mock_auth, db_session
) -> None:
    response = await client.post(
        "/rag/upload",
        files={"file": ("report.pdf", b"%PDF-1.4 test content", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "File uploaded and processed successfully"
    mock_upload.assert_called_once()

    result = await db_session.execute(
        select(RAGDocument).where(RAGDocument.collection_name == "col_pdf_001")
    )
    doc = result.scalar_one_or_none()
    assert doc is not None


@pytest.mark.asyncio
@patch(
    "app.service.rag_service.RAGAPIService.upload_file",
    new_callable=AsyncMock,
    return_value={"collection_name": "col_docx_001", "chunks_count": 3},
)
async def test_upload_file_docx_success(
    mock_upload, client, mock_auth, db_session
) -> None:
    response = await client.post(
        "/rag/upload",
        files={
            "file": (
                "document.docx",
                b"DOCX content bytes",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "File uploaded and processed successfully"
    mock_upload.assert_called_once()

    result = await db_session.execute(
        select(RAGDocument).where(RAGDocument.collection_name == "col_docx_001")
    )
    doc = result.scalar_one_or_none()
    assert doc is not None
    assert doc.user_id == mock_auth.id
    assert doc.filename == "document.docx"


@pytest.mark.asyncio
@patch(
    "app.service.rag_service.RAGAPIService.upload_file",
    new_callable=AsyncMock,
    return_value={"collection_name": "col_txt_001", "chunks_count": 2},
)
async def test_upload_file_txt_success(
    mock_upload, client, mock_auth, db_session
) -> None:
    response = await client.post(
        "/rag/upload",
        files={"file": ("notes.txt", b"Plain text content here", "text/plain")},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "File uploaded and processed successfully"
    mock_upload.assert_called_once()

    result = await db_session.execute(
        select(RAGDocument).where(RAGDocument.collection_name == "col_txt_001")
    )
    doc = result.scalar_one_or_none()
    assert doc is not None
    assert doc.user_id == mock_auth.id


@pytest.mark.asyncio
async def test_upload_file_invalid_extension_jpg(client, mock_auth) -> None:
    response = await client.post(
        "/rag/upload",
        files={"file": ("image.jpg", b"JPEG content", "image/jpeg")},
    )

    assert response.status_code == 400
    assert "Unsupported file type. Allowed extensions:" in response.json()["message"]


@pytest.mark.asyncio
async def test_upload_file_empty(client, mock_auth) -> None:
    response = await client.post(
        "/rag/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Empty file uploaded"


@pytest.mark.asyncio
async def test_upload_file_too_large(client, mock_auth) -> None:
    oversized_content = b"x" * (11 * 1024 * 1024)  # 11MB

    response = await client.post(
        "/rag/upload",
        files={"file": ("large.pdf", oversized_content, "application/pdf")},
    )

    assert response.status_code == 400
    assert "exceeds maximum allowed size" in response.json()["message"]


@pytest.mark.asyncio
async def test_upload_file_unauthorized(client) -> None:
    response = await client.post(
        "/rag/upload",
        files={"file": ("report.pdf", b"%PDF-1.4 content", "application/pdf")},
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------UPLOAD FILE (CHUNKED)----------------------------


@pytest.mark.asyncio
async def test_chunked_upload_partial_chunk(client, mock_auth) -> None:
    file_id = str(uuid.uuid4())

    response = await client.post(
        "/rag/upload",
        data={
            "chunk_index": "0",
            "total_chunks": "3",
            "file_id": file_id,
            "filename": "bigfile.pdf",
        },
        files={
            "chunk": ("chunk_0.bin", b"first chunk data", "application/octet-stream")
        },
    )

    assert response.status_code == 200
    assert "Chunk 1/3 received" in response.json()["message"]


@pytest.mark.asyncio
@patch(
    "app.service.rag_service.RAGAPIService.upload_file",
    new_callable=AsyncMock,
    return_value={"collection_name": "col_chunked_001", "chunks_count": 6},
)
async def test_chunked_upload_all_chunks_complete(
    mock_upload, client, mock_auth, db_session
) -> None:
    file_id = str(uuid.uuid4())
    chunk_data = b"chunk content " * 100

    # Send first chunk
    r1 = await client.post(
        "/rag/upload",
        data={
            "chunk_index": "0",
            "total_chunks": "2",
            "file_id": file_id,
            "filename": "assembled.pdf",
        },
        files={"chunk": ("chunk_0.bin", chunk_data, "application/octet-stream")},
    )
    assert r1.status_code == 200
    assert "Chunk 1/2 received" in r1.json()["message"]

    # Send last chunk - triggers assembly
    r2 = await client.post(
        "/rag/upload",
        data={
            "chunk_index": "1",
            "total_chunks": "2",
            "file_id": file_id,
            "filename": "assembled.pdf",
        },
        files={"chunk": ("chunk_1.bin", chunk_data, "application/octet-stream")},
    )

    assert r2.status_code == 200
    assert r2.json()["message"] == "File uploaded and processed successfully"
    mock_upload.assert_called_once()

    result = await db_session.execute(
        select(RAGDocument).where(RAGDocument.collection_name == "col_chunked_001")
    )
    doc = result.scalar_one_or_none()
    assert doc is not None
    assert doc.user_id == mock_auth.id


@pytest.mark.asyncio
async def test_chunked_upload_unauthorized(client) -> None:
    file_id = str(uuid.uuid4())

    response = await client.post(
        "/rag/upload",
        data={
            "chunk_index": "0",
            "total_chunks": "2",
            "file_id": file_id,
            "filename": "file.pdf",
        },
        files={"chunk": ("chunk_0.bin", b"data", "application/octet-stream")},
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------DELETE COLLECTION----------------------------


@pytest.mark.asyncio
@patch(
    "app.service.rag_service.RAGAPIService.delete_collection",
    new_callable=AsyncMock,
    return_value={"success": True},
)
async def test_delete_collection_success(
    mock_delete, client, seed_rag_document, mock_auth, db_session
) -> None:
    collection_name = seed_rag_document.collection_name

    response = await client.delete(f"/rag/collection/{collection_name}")

    assert response.status_code == 200
    assert response.json()["message"] == "Collection deleted successfully"

    mock_delete.assert_called_once_with(collection_name)
    assert seed_rag_document.user_id == mock_auth.id

    result = await db_session.execute(
        select(RAGDocument).where(
            RAGDocument.collection_name == collection_name,
            RAGDocument.deleted_at.is_(None),
        )
    )
    doc = result.scalar_one_or_none()
    assert doc is None


@pytest.mark.asyncio
async def test_delete_collection_not_found(client, mock_auth, db_session) -> None:
    response = await client.delete("/rag/collection/nonexistent_collection")

    assert response.status_code == 404
    assert response.json()["message"] == "Collection not found or access denied"

    result = await db_session.execute(
        select(RAGDocument).where(
            RAGDocument.collection_name == "nonexistent_collection"
        )
    )
    doc = result.scalar_one_or_none()
    assert doc is None


@pytest.mark.asyncio
async def test_delete_collection_unauthorized(client, seed_rag_document) -> None:
    collection_name = seed_rag_document.collection_name

    response = await client.delete(f"/rag/collection/{collection_name}")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------LIST DOCUMENTS----------------------------


@pytest.mark.asyncio
async def test_list_documents_success(
    client, seed_rag_document, mock_auth, db_session
) -> None:
    response = await client.get("/rag/documents")

    assert response.status_code == 200
    assert response.json()["message"] == "Documents retrieved successfully"

    result = await db_session.execute(
        select(RAGDocument).where(
            RAGDocument.user_id == mock_auth.id,
            RAGDocument.deleted_at.is_(None),
        )
    )
    db_docs = result.scalars().all()
    assert len(db_docs) == 1


@pytest.mark.asyncio
async def test_list_documents_unauthorized(client) -> None:
    response = await client.get("/rag/documents")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Authentication required: provide JWT token or X-API-Key header"
    )


# -------------------------RAG API SERVICE — upload_file----------------------------


@pytest.mark.asyncio
@patch("app.service.rag_service.httpx.AsyncClient")
async def test_upload_external_service_http_status_error(
    mock_client_cls, client, mock_auth
) -> None:
    mock_http = mock_client_cls.return_value.__aenter__.return_value
    mock_http.post.side_effect = httpx.HTTPStatusError(
        "server error",
        request=MagicMock(),
        response=httpx.Response(500, text="Internal Server Error"),
    )

    response = await client.post(
        "/rag/upload",
        files={"file": ("test.pdf", b"%PDF-1.4 content", "application/pdf")},
    )

    assert response.status_code == 500


@pytest.mark.asyncio
@patch("app.service.rag_service.httpx.AsyncClient")
async def test_upload_external_service_request_error(
    mock_client_cls, client, mock_auth
) -> None:
    mock_http = mock_client_cls.return_value.__aenter__.return_value
    mock_http.post.side_effect = httpx.RequestError(
        "Connection refused", request=MagicMock()
    )

    response = await client.post(
        "/rag/upload",
        files={"file": ("test.pdf", b"%PDF-1.4 content", "application/pdf")},
    )

    assert response.status_code == 500


@pytest.mark.asyncio
@patch("app.service.rag_service.httpx.AsyncClient")
async def test_upload_external_service_unexpected_exception(
    mock_client_cls, client, mock_auth
) -> None:
    mock_http = mock_client_cls.return_value.__aenter__.return_value
    mock_http.post.side_effect = Exception("unexpected boom")

    response = await client.post(
        "/rag/upload",
        files={"file": ("test.pdf", b"%PDF-1.4 content", "application/pdf")},
    )

    assert response.status_code == 500


# -------------------------RAG API SERVICE — delete_collection----------------------------


@pytest.mark.asyncio
@patch("app.service.rag_service.httpx.AsyncClient")
async def test_delete_external_service_http_status_error(
    mock_client_cls, client, mock_auth, seed_rag_document, db_session
) -> None:
    mock_http = mock_client_cls.return_value.__aenter__.return_value
    mock_http.delete.side_effect = httpx.HTTPStatusError(
        "not found",
        request=MagicMock(),
        response=httpx.Response(404, text="Not Found"),
    )

    response = await client.delete(
        f"/rag/collection/{seed_rag_document.collection_name}"
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Collection deleted successfully"
    assert seed_rag_document.user_id == mock_auth.id

    result = await db_session.execute(
        select(RAGDocument).where(
            RAGDocument.collection_name == seed_rag_document.collection_name
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
@patch("app.service.rag_service.httpx.AsyncClient")
async def test_delete_external_service_request_error(
    mock_client_cls, client, mock_auth, seed_rag_document, db_session
) -> None:
    mock_http = mock_client_cls.return_value.__aenter__.return_value
    mock_http.delete.side_effect = httpx.RequestError("timeout", request=MagicMock())

    response = await client.delete(
        f"/rag/collection/{seed_rag_document.collection_name}"
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Collection deleted successfully"

    result = await db_session.execute(
        select(RAGDocument).where(
            RAGDocument.collection_name == seed_rag_document.collection_name
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
@patch("app.service.rag_service.httpx.AsyncClient")
async def test_delete_external_service_generic_exception(
    mock_client_cls, client, mock_auth, seed_rag_document, db_session
) -> None:
    mock_http = mock_client_cls.return_value.__aenter__.return_value
    mock_http.delete.side_effect = Exception("unknown failure")

    response = await client.delete(
        f"/rag/collection/{seed_rag_document.collection_name}"
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Collection deleted successfully"

    result = await db_session.execute(
        select(RAGDocument).where(
            RAGDocument.collection_name == seed_rag_document.collection_name
        )
    )
    assert result.scalar_one_or_none() is None
