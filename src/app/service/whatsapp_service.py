import json
import logging

import httpx

logger = logging.getLogger(__name__)


class WhatsAppService:
    GRAPH_API_VERSION = "v24.0"
    GRAPH_BASE_URL = "https://graph.facebook.com"

    @staticmethod
    async def download_media(
        media_id: str, access_token: str
    ) -> tuple[bytes, str] | None:
        """Download media from WhatsApp and return (content, mime_type) or None."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Get media URL + mime_type
                url_response = await client.get(
                    f"{WhatsAppService.GRAPH_BASE_URL}/{WhatsAppService.GRAPH_API_VERSION}/{media_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                if url_response.status_code != 200:
                    return None

                meta = url_response.json()
                media_url = meta.get("url")
                if not media_url:
                    return None

                mime_type = meta.get("mime_type", "application/octet-stream")

                # Download media bytes
                media_response = await client.get(
                    media_url, headers={"Authorization": f"Bearer {access_token}"}
                )

                if media_response.status_code != 200:
                    return None

                return media_response.content, mime_type

        except Exception as media_error:
            logger.warning(
                "Media download failed | error=%s", media_error, exc_info=True
            )
            return None

    @staticmethod
    async def send_template_message(
        phone_number_id: str,
        to_number: str,
        template_name: str,
        language: str,
        access_token: str,
        components: list[dict] | None = None,
        variables: dict | None = None,
    ) -> dict | None:
        """
        Send WhatsApp template message.

        Args:
            phone_number_id: WhatsApp Business phone number ID
            to_number: Recipient phone number (E.164 format)
            template_name: Approved template name
            language: BCP-47 language code (e.g., en_US, hi)
            access_token: WhatsApp access token
            components: Structured template components passed directly to the Meta API.
                Each component follows the Meta API shape, e.g.:
                [
                  {"type": "header", "parameters": [{"type": "image", "image": {"link": "..."}}]},
                  {"type": "body",   "parameters": [{"type": "text", "text": "Raj"}, ...]},
                  {"type": "button", "sub_type": "quick_reply", "index": 0,
                   "parameters": [{"type": "payload", "payload": "YES"}]}
                ]
            variables: Legacy flat dict {"var_1": "val1", ...} — only used when
                       `components` is not provided (broadcast backward compat).

        Returns:
            {"message_id": "wamid.xxx", "status": "sent"} on success
            {"status": "failed", "error": "<Meta error message>"} on failure
        """
        try:
            to_number = (
                str(to_number)
                .strip()
                .replace("+", "")
                .replace(" ", "")
                .replace("-", "")
            )

            # Build components list for the Meta API payload
            built_components: list[dict] = []

            if components:
                # New path: caller supplies fully-structured components.
                # For header/body: strip text parameters with empty/blank values so
                # Meta never receives (#131008) Required parameter is missing.
                # Button components pass through unchanged — their parameters are
                # always intentional and must not be silently dropped.
                cleaned: list[dict] = []
                for comp in components:
                    comp_type = comp.get("type", "")
                    if comp_type == "button":
                        cleaned.append(comp)
                    else:
                        params = comp.get("parameters", [])
                        filtered = [
                            p for p in params
                            if not (p.get("type") == "text" and not (p.get("text") or "").strip())
                        ]
                        if filtered:
                            cleaned.append({**comp, "parameters": filtered})
                        elif "parameters" not in comp:
                            # component has no parameters key at all — keep as-is
                            cleaned.append(comp)
                built_components = cleaned
            elif variables:
                # Legacy path: flat dict → body text parameters (broadcast compat)
                sorted_vars = sorted(
                    [(k, v) for k, v in variables.items() if v], key=lambda x: x[0]
                )
                if sorted_vars:
                    built_components = [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": str(v)} for _, v in sorted_vars
                            ],
                        }
                    ]

            payload = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": language},
                },
            }

            if built_components:
                payload["template"]["components"] = built_components

            logger.info(
                "Sending template to Meta | to=%s | template=%s | components=%s",
                to_number,
                template_name,
                json.dumps(built_components),
            )

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{WhatsAppService.GRAPH_BASE_URL}/{WhatsAppService.GRAPH_API_VERSION}/{phone_number_id}/messages",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code not in (200, 201):
                    error_data = response.json()
                    error_obj = error_data.get("error", {})
                    error_msg = error_obj.get("message", response.text)
                    error_details = error_obj.get("error_data", {})
                    logger.error(
                        "WhatsApp template error | status=%s | error=%s | details=%s | sent_components=%s",
                        response.status_code,
                        error_msg,
                        error_details,
                        json.dumps(built_components),
                    )
                    raise Exception(f"WhatsApp API error: {error_msg}")

                result = response.json()
                message_id = result.get("messages", [{}])[0].get("id")

                logger.info(
                    "WhatsApp template sent | to=%s | template=%s | message_id=%s",
                    to_number,
                    template_name,
                    message_id,
                )

                return {"message_id": message_id, "status": "sent"}

        except Exception as e:
            logger.error(
                "Failed to send template | to=%s | template=%s | error=%s",
                to_number,
                template_name,
                str(e),
                exc_info=True,
            )
            return {"status": "failed", "error": str(e)}

    @staticmethod
    async def send_message(
        phone_number_id: str, to_number: str, message: str, access_token: str
    ) -> str | None:
        try:
            to_number = (
                str(to_number)
                .strip()
                .replace("+", "")
                .replace(" ", "")
                .replace("-", "")
            )

            # Try to parse message as JSON (for media/document support)
            try:
                data = json.loads(message)
                text_message = data.get("message", "")
                media_urls = data.get("media", [])
                documents = data.get("documents", [])
                audio_urls = data.get("audio", [])
            except (json.JSONDecodeError, AttributeError):
                text_message = message
                media_urls = []
                documents = []
                audio_urls = []

            meta_message_id: str | None = None

            async with httpx.AsyncClient(timeout=30) as client:
                # Send text message
                if text_message:
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": to_number,
                        "text": {"body": text_message},
                    }
                    response = await client.post(
                        f"{WhatsAppService.GRAPH_BASE_URL}/{WhatsAppService.GRAPH_API_VERSION}/{phone_number_id}/messages",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    if response.status_code not in (200, 201):
                        logger.error(
                            "WhatsApp text error | status=%s | response=%s",
                            response.status_code,
                            response.text,
                        )
                        return None
                    meta_message_id = response.json().get("messages", [{}])[0].get("id")

                # Send media messages
                video_exts = {".mp4", ".webm", ".avi", ".mov", ".ogg"}
                for media_url in media_urls:
                    ext = (
                        "." + media_url.rsplit(".", 1)[-1].lower()
                        if "." in media_url
                        else ""
                    )
                    is_video = ext in video_exts
                    media_type = "video" if is_video else "image"
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": to_number,
                        "type": media_type,
                        media_type: {"link": media_url},
                    }
                    response = await client.post(
                        f"{WhatsAppService.GRAPH_BASE_URL}/{WhatsAppService.GRAPH_API_VERSION}/{phone_number_id}/messages",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    if response.status_code not in (200, 201):
                        logger.error(
                            "WhatsApp media error | type=%s | status=%s | response=%s",
                            media_type,
                            response.status_code,
                            response.text,
                        )

                # Send audio messages
                for audio_url in audio_urls:
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": to_number,
                        "type": "audio",
                        "audio": {"link": audio_url},
                    }
                    response = await client.post(
                        f"{WhatsAppService.GRAPH_BASE_URL}/{WhatsAppService.GRAPH_API_VERSION}/{phone_number_id}/messages",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    if response.status_code not in (200, 201):
                        logger.error(
                            "WhatsApp audio error | status=%s | response=%s",
                            response.status_code,
                            response.text,
                        )

                # Send document messages
                for doc in documents:
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": to_number,
                        "type": "document",
                        "document": {
                            "link": doc["link"],
                            "filename": doc.get("filename", "document.pdf"),
                        },
                    }
                    response = await client.post(
                        f"{WhatsAppService.GRAPH_BASE_URL}/{WhatsAppService.GRAPH_API_VERSION}/{phone_number_id}/messages",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    if response.status_code not in (200, 201):
                        logger.error(
                            "WhatsApp document error | status=%s | response=%s",
                            response.status_code,
                            response.text,
                        )

                logger.info(
                    "WhatsApp message sent | to=%s | text=%s | media=%d | docs=%d | audio=%d",
                    to_number,
                    bool(text_message),
                    len(media_urls),
                    len(documents),
                    len(audio_urls),
                )
                return meta_message_id

        except Exception as e:
            logger.error(
                "Failed to send WhatsApp message | error=%s", str(e), exc_info=True
            )
            return None

    @staticmethod
    async def send_typing_indicator(
        phone_number_id: str, message_id: str, access_token: str
    ) -> None:
        try:
            payload = {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
                "typing_indicator": {"type": "text"},
            }
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{WhatsAppService.GRAPH_BASE_URL}/{WhatsAppService.GRAPH_API_VERSION}/{phone_number_id}/messages",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code not in (200, 201):
                    logger.warning(
                        "Typing indicator failed | status=%s | response=%s",
                        response.status_code,
                        response.text,
                    )
        except Exception as e:
            logger.warning(
                "Typing indicator error (non-fatal) | message_id=%s | error=%s",
                message_id,
                str(e),
            )

    @staticmethod
    async def send_reaction(
        phone_number_id: str,
        to_number: str,
        message_id: str,
        emoji: str,
        access_token: str,
    ) -> bool:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "reaction",
            "reaction": {"message_id": message_id, "emoji": emoji},
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{WhatsAppService.GRAPH_BASE_URL}/{WhatsAppService.GRAPH_API_VERSION}/{phone_number_id}/messages",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code not in (200, 201):
                    logger.error(
                        "send_reaction failed | status=%s | body=%s",
                        response.status_code,
                        response.text,
                    )
                    return False
                return True
        except Exception as e:
            logger.error("send_reaction error | %s", e)
            return False
