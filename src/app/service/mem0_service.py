import logging

from mem0 import MemoryClient

from app.common.settings import settings

logger = logging.getLogger(__name__)


class Mem0Service:
    def __init__(self) -> None:
        api_key = settings.mem0_api_key
        try:
            self.client = MemoryClient(api_key)
        except Exception as e:
            logger.warning(f"Failed to initialize Mem0 client: {e}")
            self.client = None

    def add_memory(self, messages: list, session_id: int) -> None:
        if not self.client:
            return
        try:
            for msg in messages:
                self.client.add(
                    {"role": "user", "content": msg}, user_id=str(session_id)
                )
        except Exception:
            logger.exception("Failed to add messages to mem0")

    def search_memories(self, session_id: int, query: str) -> str:
        if not self.client:
            return ""
        try:
            response = self.client.search(
                query=query, filters={"user_id": str(session_id)}
            )

            if not response or "results" not in response:
                return ""

            return "\n".join(f"- {entry['memory']}" for entry in response["results"])

        except Exception:
            logger.exception("Failed to retrieve mem0 memory")
            return ""

    def delete_memories(self, session_id: int) -> None:
        if not self.client:
            return
        try:
            self.client.delete_all(user_id=str(session_id))
        except Exception:
            logger.exception(f"Failed to delete mem0 memories for session {session_id}")
