import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    @staticmethod
    def _require(name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"{name} environment variable is not set")
        return value

    @property
    def database_url(self) -> str:
        return self._require("DATABASE_URL")

    @property
    def redis_host(self) -> str:
        return self._require("REDIS_HOST")

    @property
    def redis_port(self) -> str:
        return self._require("REDIS_PORT")

    @property
    def redis_password(self) -> str:
        return os.getenv("REDIS_PASSWORD", "")

    @property
    def secret_key(self) -> str:
        return self._require("SECRET_KEY")

    @property
    def gemini_api_key(self) -> str:
        return self._require("GEMINI_API_KEY")

    @property
    def mem0_api_key(self) -> str:
        return self._require("MEM0_API_KEY")

    @property
    def llm_api_url(self) -> str:
        return self._require("LLM_API_URL")

    @property
    def mail_username(self) -> str:
        return self._require("MAIL_USERNAME")

    @property
    def mail_password(self) -> str:
        return self._require("MAIL_PASSWORD")

    @property
    def mail_from(self) -> str:
        return self._require("MAIL_FROM")

    @property
    def mail_host(self) -> str:
        return self._require("MAIL_HOST")

    @property
    def mail_port(self) -> str:
        return self._require("MAIL_PORT")

    @property
    def API_KEY_ENCRYPTION_KEY(self) -> str:
        return self._require("API_KEY_ENCRYPTION_KEY")

    @property
    def rag_service_url(self) -> str:
        return self._require("RAG_SERVICE_URL")



settings = Settings()
