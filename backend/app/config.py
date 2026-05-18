import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    openai_api_key: str
    openai_model: str
    azure_tenant_id: str
    azure_client_id: str
    azure_client_secret: str
    cosmos_account_name: str
    mongo_db_name: str
    mongo_collection_name: str
    api_host: str
    api_port: int
    cors_origins: tuple[str, ...]


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} environment variable is required.")
    return value


def load_settings() -> Settings:
    cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    cors_origins = tuple(origin.strip() for origin in cors_raw.split(",") if origin.strip())

    return Settings(
        openai_api_key=_require("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        azure_tenant_id=_require("AZURE_TENANT_ID"),
        azure_client_id=_require("AZURE_CLIENT_ID"),
        azure_client_secret=_require("AZURE_CLIENT_SECRET"),
        cosmos_account_name=os.getenv("COSMOS_ACCOUNT_NAME", "user-onboarding-db"),
        mongo_db_name=os.getenv("MONGO_DB_NAME", "debugging"),
        mongo_collection_name=os.getenv("MONGO_COLLECTION_NAME", "data"),
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("API_PORT", "8000")),
        cors_origins=cors_origins,
    )
