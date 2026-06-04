import logging
import os
from functools import lru_cache
from typing import Any

import boto3
import httpx
from google import genai
from google.genai import types
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.media_utils import GEMINI_SUPPORTED_MIME_TYPES

logger = logging.getLogger(__name__)


class S3ConfigError(RuntimeError):
    """Raised when mandatory S3 configuration is missing."""


def _build_s3_kwargs() -> dict[str, Any]:
    access_key = os.getenv("HETZNER_ACCESS_KEY")
    secret_key = os.getenv("HETZNER_SECRET_KEY")
    endpoint_url = os.getenv("HETZNER_S3_ENDPOINT")
    region = os.getenv("HETZNER_S3_REGION", "us-east-1")

    if not access_key or not secret_key:
        logger.error("HETZNER S3 credentials are not configured")
        raise S3ConfigError("HETZNER S3 credentials are not configured.")

    if not endpoint_url:
        logger.error("HETZNER S3 endpoint URL is not configured")
        raise S3ConfigError("HETZNER S3 endpoint URL is not configured.")

    return {
        "aws_access_key_id": access_key,
        "aws_secret_access_key": secret_key,
        "endpoint_url": endpoint_url,
        "region_name": region,
    }


@lru_cache
def get_s3_client():
    """Return a cached S3 client instance."""
    kwargs = _build_s3_kwargs()
    bucket_name = os.getenv("HETZNER_S3_BUCKET")

    if not bucket_name:
        logger.error("HETZNER S3 bucket name is not configured")
        raise S3ConfigError("HETZNER S3 bucket name is not configured.")

    s3_client = boto3.client("s3", **kwargs)

    logger.info(
        "Hetzner S3 client initialized | endpoint=%s | region=%s | bucket=%s",
        kwargs.get("endpoint_url"),
        kwargs.get("region_name"),
        bucket_name,
    )

    # Optional CORS
    cors_config = {
        "CORSRules": [
            {
                "AllowedHeaders": ["*"],
                "AllowedMethods": ["GET", "HEAD", "PUT", "POST", "DELETE"],
                "AllowedOrigins": ["*"],
                "ExposeHeaders": ["ETag"],
                "MaxAgeSeconds": 3600,
            }
        ]
    }

    try:
        s3_client.put_bucket_cors(
            Bucket=bucket_name,
            CORSConfiguration=cors_config,
        )
        logger.debug("CORS configuration applied to bucket=%s", bucket_name)
    except Exception as e:
        logger.warning(
            "Unable to set CORS on bucket=%s | error=%s",
            bucket_name,
            e,
            exc_info=True,
        )

    return s3_client


class S3Service:
    def __init__(self, db_session: AsyncSession | None = None) -> None:
        self.bucket_name = os.getenv("HETZNER_S3_BUCKET")
        self.endpoint_url = os.getenv("HETZNER_S3_ENDPOINT")
        self.s3_client = get_s3_client()
        self.db_session = db_session

        logger.info(
            "S3Service initialized | endpoint=%s | bucket=%s",
            self.endpoint_url,
            self.bucket_name,
        )

    async def upload_media(
        self, file_content: bytes, file_name: str, content_type: str
    ) -> str | None:
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_name,
                Body=file_content,
                ContentType=content_type,
                ACL="public-read",
            )

            url = f"{self.endpoint_url}/{self.bucket_name}/{file_name}"

            logger.info(
                "Hetzner S3 upload successful | bucket=%s | key=%s",
                self.bucket_name,
                file_name,
            )

            return url

        except Exception as e:
            logger.error(
                "Hetzner S3 upload failed | bucket=%s | key=%s | error=%s",
                self.bucket_name,
                file_name,
                e,
                exc_info=True,
            )
            return None

    async def extract_media_metadata(
        self, media_url: str, message_id: int, mime_type: str = "image/jpeg"
    ) -> None:
        """Background task to extract media description using Gemini and store it."""
        if mime_type not in GEMINI_SUPPORTED_MIME_TYPES:
            logger.info(
                "Skipping media metadata extraction — unsupported MIME type | mime=%s | message_id=%s",
                mime_type,
                message_id,
            )
            return

        if mime_type.startswith("image/"):
            prompt = "Describe what you see in this image clearly in 2–3 sentences."
        elif mime_type.startswith("video/"):
            prompt = "Describe what happens in this video clearly in 2–3 sentences."
        elif mime_type.startswith("audio/"):
            prompt = (
                "Transcribe or summarize the content of this audio in 2–3 sentences."
            )
        else:
            prompt = "Summarize the key content of this document in 2–3 sentences."

        try:
            if not self.db_session:
                logger.warning(
                    "DB session not available, skipping media metadata extraction"
                )
                return

            # Download media
            async with httpx.AsyncClient(timeout=20) as http_client:
                response = await http_client.get(media_url)
                response.raise_for_status()
                media_bytes = response.content

            # Gemini client
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

            # Call Gemini (MEDIA FIRST, THEN PROMPT)
            gemini_response = await client.aio.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=[
                    types.Part.from_bytes(
                        data=media_bytes,
                        mime_type=mime_type,
                    ),
                    prompt,
                ],
            )

            media_text = gemini_response.text.strip() if gemini_response.text else None

            # Store in DB
            if media_text:
                from app.models.model import WhatsAppMessage

                stmt = (
                    update(WhatsAppMessage)
                    .where(WhatsAppMessage.id == message_id)
                    .values(media_text=media_text)
                )

                await self.db_session.execute(stmt)
                await self.db_session.commit()

                logger.info(
                    "Media metadata extracted successfully | mime=%s | message_id=%s",
                    mime_type,
                    message_id,
                )

        except Exception as e:
            logger.error(
                "Failed to extract media metadata | mime=%s | message_id=%s | error=%s",
                mime_type,
                message_id,
                e,
                exc_info=True,
            )
