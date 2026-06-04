import logging

import httpx
from fastapi import UploadFile
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.settings import settings
from app.models.model import RAGDocument

logger = logging.getLogger(__name__)


class RAGAPIService:
    """Service to interact with external RAG API (voice-agents-tools)"""

    def __init__(self):
        self.base_url = settings.rag_service_url

    async def upload_file(self, file: UploadFile) -> dict:
        """Upload file to voice-agents-tools RAG service"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                files = {"file": (file.filename, await file.read(), file.content_type)}
                response = await client.post(f"{self.base_url}/rag/upload", files=files)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "RAG API upload failed | status=%s | response=%s",
                e.response.status_code,
                e.response.text,
            )
            raise RuntimeError(f"External RAG service error: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error("RAG API request failed | error=%s", str(e))
            raise RuntimeError(f"Failed to connect to RAG service: {str(e)}")
        except Exception as e:
            logger.exception("Unexpected error during file upload")
            raise RuntimeError(f"File upload failed: {str(e)}")

    async def delete_collection(self, collection_name: str) -> dict:
        """Delete collection from voice-agents-tools service"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.base_url}/rag/collection/{collection_name}"
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(
                "RAG API delete failed | collection=%s | status=%s",
                collection_name,
                e.response.status_code,
            )
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.warning(
                "Failed to delete from external RAG service | collection=%s | error=%s",
                collection_name,
                str(e),
            )
            return {"success": False, "error": str(e)}


class RAGService:
    """Service to manage RAG documents in database"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.model = RAGDocument
        self.api_service = RAGAPIService()

    async def create_rag_document(
        self, user_id: int, filename: str, collection_name: str, chunks_count: int
    ) -> dict:
        """Create RAG document record in database"""
        stmt = (
            insert(self.model)
            .values(
                user_id=user_id,
                filename=filename,
                collection_name=collection_name,
                chunks_count=chunks_count,
            )
            .returning(
                self.model.id,
                self.model.user_id,
                self.model.filename,
                self.model.collection_name,
                self.model.chunks_count,
                self.model.created_at,
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return dict(result.mappings().one())

    async def get_document_by_collection(
        self, user_id: int, collection_name: str
    ) -> dict | None:
        """Get RAG document by collection name"""
        stmt = select(
            self.model.id,
            self.model.user_id,
            self.model.filename,
            self.model.collection_name,
            self.model.chunks_count,
            self.model.created_at,
        ).where(
            self.model.user_id == user_id,
            self.model.collection_name == collection_name,
            self.model.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        doc = result.mappings().one_or_none()
        return dict(doc) if doc else None

    async def list_user_documents(self, user_id: int) -> list[dict]:
        """List all RAG documents for a user"""
        stmt = (
            select(
                self.model.id,
                self.model.filename,
                self.model.collection_name,
                self.model.chunks_count,
                self.model.created_at,
            )
            .where(
                self.model.user_id == user_id,
                self.model.deleted_at.is_(None),
            )
            .order_by(self.model.created_at.desc())
        )

        result = await self.db.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    async def delete_document(self, document_id: int) -> None:
        """Hard delete RAG document"""
        await self.db.execute(
            delete(self.model).where(self.model.id == document_id)
        )
        await self.db.commit()
