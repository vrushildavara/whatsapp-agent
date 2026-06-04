import json
import logging
from typing import Any

import httpx

from app.common.responses import ErrorResponse
from app.utils.redis_manager import get_redis_client

logger = logging.getLogger(__name__)


class TemplatesService:
    GRAPH_API_VERSION = "v19.0"
    GRAPH_BASE_URL = "https://graph.facebook.com"
    CACHE_TTL = 300  # 5 minutes

    @staticmethod
    async def fetch_templates(
        waba_id: str,
        access_token: str,
        status: str = "APPROVED",
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Fetch message templates from Meta Graph API with Redis caching.

        Args:
            waba_id: WhatsApp Business Account ID
            access_token: Meta access token
            status: Filter by status (APPROVED, PENDING, REJECTED)
            limit: Number of templates to fetch (max 100)

        Returns:
            {
                "data": [...templates],
                "paging": {"cursors": {...}}
            }
        """
        # Check Redis cache first
        cache_key = f"templates:{waba_id}:{status}"
        redis = get_redis_client()

        if redis:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    logger.info(f"Templates cache hit | waba_id={waba_id}")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Redis cache read failed: {e}")

        # Fetch from Meta API
        url = f"{template_service.GRAPH_BASE_URL}/{template_service.GRAPH_API_VERSION}/{waba_id}/message_templates"

        params = {
            "fields": "id,name,status,category,language,components",
            "limit": min(limit, 100),
        }

        if status:
            params["status"] = status

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                if response.status_code != 200:
                    error_data = response.json() if response.text else {}
                    error_msg = error_data.get("error", {}).get(
                        "message", response.text
                    )
                    logger.error(
                        f"Meta template API error | status={response.status_code} | error={error_msg}"
                    )
                    raise ErrorResponse(
                        status_code=500, message=f"Meta API error: {error_msg}"
                    )

                result = response.json()

                # Cache the result
                if redis:
                    try:
                        await redis.setex(
                            cache_key, template_service.CACHE_TTL, json.dumps(result)
                        )
                    except Exception as e:
                        logger.warning(f"Redis cache write failed: {e}")

                logger.info(
                    f"Templates fetched from Meta | waba_id={waba_id} | count={len(result.get('data', []))}"
                )

                return result
        except httpx.TimeoutException:
            logger.error(f"Meta API timeout | waba_id={waba_id}")
            raise Exception("Meta API request timed out")
        except ErrorResponse:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch templates | error={e}", exc_info=True)
            raise

    @staticmethod
    async def get_template_by_name(
        waba_id: str, access_token: str, template_name: str, language: str
    ) -> dict[str, Any] | None:
        """
        Get a specific template by name and language.
        """
        templates = await template_service.fetch_templates(waba_id, access_token)
        for template in templates.get("data", []):
            if (
                template.get("name") == template_name
                and template.get("language") == language
            ):
                return template

        return None

    @staticmethod
    def parse_template_variables(template: dict[str, Any]) -> dict[str, Any]:
        """
        Extract variable placeholders from all template components, keyed by component type.

        Returns a dict with any of these keys present when variables exist:
          {
            "header": ["{{1}}"],
            "body":   ["{{1}}", "{{2}}"],
            "buttons": [{"index": 0, "sub_type": "url", "variables": ["{{1}}"]}]
          }
        """
        import re

        result: dict[str, Any] = {}
        components = template.get("components", [])

        for component in components:
            comp_type = component.get("type", "").upper()

            if comp_type in ("HEADER", "BODY"):
                text = component.get("text", "")
                matches = re.findall(r"\{\{(\d+)\}\}", text)
                if matches:
                    vars_list = [
                        f"{{{{{m}}}}}" for m in sorted(set(matches), key=int)
                    ]
                    result[comp_type.lower()] = vars_list

            elif comp_type == "BUTTONS":
                button_vars = []
                for btn_idx, btn in enumerate(component.get("buttons", [])):
                    url = btn.get("url", "")
                    matches = re.findall(r"\{\{(\d+)\}\}", url)
                    if matches:
                        button_vars.append(
                            {
                                "index": btn_idx,
                                "sub_type": "url",
                                "variables": [
                                    f"{{{{{m}}}}}" for m in sorted(set(matches), key=int)
                                ],
                            }
                        )
                if button_vars:
                    result["buttons"] = button_vars

        return result


    @staticmethod
    def render_template_message(
        template: dict[str, Any],
        components: list[dict] | None,
    ) -> str:
        """
        Render the template text with variable values substituted from components.

        Collects text from HEADER (text format), BODY, and FOOTER components and
        joins them into a single human-readable string.  Variable placeholders
        ({{N}}) in HEADER and BODY are replaced with values from the supplied
        components list.

        Falls back to "[Template: <name>]" only when no text can be extracted
        from any component.
        """
        import re

        template_name = template.get("name", "unknown")
        template_components = template.get("components", [])

        # Build a lookup of component text by type (HEADER, BODY, FOOTER)
        comp_text: dict[str, str] = {}
        for comp in template_components:
            comp_type = comp.get("type", "").upper()
            if comp_type == "HEADER":
                # Only text-format headers have a renderable string
                if comp.get("format", "").upper() == "TEXT":
                    text = comp.get("text", "")
                    if text:
                        comp_text["HEADER"] = text
            elif comp_type in ("BODY", "FOOTER"):
                text = comp.get("text", "")
                if text:
                    comp_text[comp_type] = text

        if not comp_text:
            return f"[Template: {template_name}]"

        # Substitute {{N}} placeholders using the message components (HEADER + BODY)
        if components:
            for comp in components:
                msg_type = comp.get("type", "").lower()
                if msg_type in ("header", "body"):
                    target_key = msg_type.upper()
                    if target_key not in comp_text:
                        continue
                    for idx, param in enumerate(comp.get("parameters", []), start=1):
                        if param.get("type") == "text":
                            comp_text[target_key] = comp_text[target_key].replace(
                                f"{{{{{idx}}}}}",
                                param.get("text", f"{{{{{idx}}}}}"),
                            )

        # Replace any remaining unfilled placeholders (keep them visible)
        for key in comp_text:
            comp_text[key] = re.sub(r"\{\{(\d+)\}\}", r"[var\1]", comp_text[key])

        # Assemble final display text in natural reading order
        parts = [comp_text[k] for k in ("HEADER", "BODY", "FOOTER") if k in comp_text]
        return "\n".join(parts)


template_service = TemplatesService()
