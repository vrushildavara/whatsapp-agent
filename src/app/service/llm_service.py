import asyncio
import logging

import httpx

from app.common.settings import settings
from app.utils.media_utils import mime_from_url

logger = logging.Logger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds


class LLMService:
    @staticmethod
    def _clean_text(raw_text: str) -> str:
        """
        Return raw text as-is to preserve stage tags.
        Stage extraction happens in assistant_service.
        """
        return raw_text.strip()

    @staticmethod
    async def generate_response(
        system_prompt: str,
        user_message: str,
        media_urls: list[str] | None = None,
        tools: list[dict] | None = None,
    ) -> tuple[str, int | None, int | None]:
        llm_api_url = f"{settings.llm_api_url}/chat"
        if not llm_api_url:
            return "LLM API URL not configured", None, None

        user_parts: list[dict] = [{"text": user_message}]

        if media_urls:
            for media_url in media_urls:
                user_parts.insert(
                    0,
                    {
                        "file_data": {
                            "mime_type": mime_from_url(media_url),
                            "file_uri": media_url,
                        }
                    },
                )

        payload: dict = {
            "messages": [
                {"role": "system", "parts": [{"text": system_prompt}]},
                {"role": "user", "parts": user_parts},
            ]
        }

        if tools:
            payload["tools"] = tools

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=160.0) as client:
                    response = await client.post(
                        llm_api_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )

                # Check for 5xx errors - retry only for server errors
                if response.status_code >= 500:
                    logger.warning(
                        f"Server error {response.status_code} on attempt {attempt}"
                    )
                    last_error = f"Server error: {response.status_code}"
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(RETRY_DELAY * attempt)
                        continue
                    return (
                        "Sorry, I’m having a little trouble connecting right now. Could you try again in a minute?",
                        None,
                        None,
                    )

                # For 4xx errors, don’t retry - return immediately
                response.raise_for_status()
                data = response.json()

                input_tokens: int | None = data.get("input_tokens")
                output_tokens: int | None = data.get("output_tokens")

                # Handle multi-turn conversation response
                if "messages" in data:
                    for msg in reversed(data["messages"]):
                        if msg.get("role") in ["model", "assistant"]:
                            parts = msg.get("parts", [])
                            if parts and parts[0].get("text"):
                                return (
                                    LLMService._clean_text(parts[0]["text"]),
                                    input_tokens,
                                    output_tokens,
                                )

                # Custom wrapped response
                if "data" in data and "assistant_message" in data["data"]:
                    return (
                        LLMService._clean_text(data["data"]["assistant_message"]),
                        input_tokens,
                        output_tokens,
                    )

                # Fallbacks
                result = (
                    LLMService._clean_text(data.get("response", ""))
                    or LLMService._clean_text(data.get("text", ""))
                    or None
                )

                if result:
                    return result, input_tokens, output_tokens

                return "Something went wrong", None, None

            except httpx.HTTPStatusError as e:
                # 4xx errors - don’t retry
                logger.error(f"HTTP error {e.response.status_code}: {e}")
                return f"LLM request failed: {e.response.status_code}", None, None
            except Exception as e:
                # Network errors - retry
                last_error = str(e)
                logger.error(f"LLM error on attempt {attempt}/{MAX_RETRIES}: {e}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY * attempt)

        return (
            f"Failed to connect to LLM after {MAX_RETRIES} attempts: {last_error}",
            None,
            None,
        )
