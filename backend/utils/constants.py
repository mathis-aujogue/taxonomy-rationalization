"""Constants and environment variable management."""

from dotenv import load_dotenv
from os import getenv
from dataclasses import dataclass, field
from typing import ClassVar

load_dotenv()


@dataclass
class Constants:
    # Required environment variable names and their default values (if any)
    REQUIRED_VARS: ClassVar[list[tuple[str, str | None]]] = [
        ("AZURE_EMBEDDING_API_KEY", None),
        ("AZURE_CHAT_API_KEY", None),
        ("AZURE_API_VERSION", None),
        ("AZURE_EMBEDDING_ENDPOINT", None),
        ("AZURE_CHAT_ENDPOINT", None),
        ("AZURE_CHAT_MODEL", None),
        ("AZURE_EMBEDDING_MODEL", None),
    ]

    OPTIONAL_VARS: ClassVar[list[tuple[str, str | None]]] = [
        ("GROQ_API_KEY", None),
        ("GROQ_MODEL", None),
    ]

    AZURE_API_VERSION: str = field(init=False)
    AZURE_EMBEDDING_API_KEY: str = field(init=False)
    AZURE_EMBEDDING_ENDPOINT: str = field(init=False)
    AZURE_EMBEDDING_MODEL: str = field(init=False)
    AZURE_CHAT_API_KEY: str = field(init=False)
    AZURE_CHAT_MODEL: str = field(init=False)
    AZURE_CHAT_ENDPOINT: str = field(init=False)
    POSTGRES_CONNECTION_STRING_SYNC: str = field(init=False)
    POSTGRES_CONNECTION_STRING_ASYNC: str = field(init=False)
    TAXONOMY_EMBEDDINGS_TABLE_NAME: str = field(
        init=True, default="taxonomy_embeddings"
    )
    TOP_K_CANDIDATES: int = field(init=True, default=5)
    SIMILARITY_THRESHOLD: float | None = field(init=True, default=None)
    GROQ_API_KEY: str = field(init=False)
    GROQ_MODEL: str = field(init=False)

    def __post_init__(self):
        missing_vars = []

        # Dynamically fetch and set required environment vars as attributes
        for var_name, default in self.REQUIRED_VARS:
            value = getenv(var_name) if default is None else getenv(var_name, default)
            if not value:
                missing_vars.append(var_name)
            setattr(self, var_name, value)

        # Dynamically fetch and set optional environment vars as attributes
        for var_name, default in self.OPTIONAL_VARS:
            value = getenv(var_name) if default is None else getenv(var_name, default)
            if not value:
                missing_vars.append(var_name)
            setattr(self, var_name, value)

        if missing_vars:
            raise EnvironmentError(
                f"Required environment variables are missing: {', '.join(missing_vars)}"
            )

        # Get database URL
        url = getenv("LOCAL_POSTGRESQL_URL")
        if not url:
            raise EnvironmentError(
                "LOCAL_POSTGRESQL_URL environment variable is not set. "
                "Check .env.example for instructions."
            )

        if url and "?" in url:
            url = url.split("?")[0]
        if url and url.startswith("postgres://"):
            sync_url = url.replace("postgres://", "postgresql://", 1)
        else:
            sync_url = url
        self.POSTGRES_CONNECTION_STRING_SYNC = sync_url
        if sync_url and sync_url.startswith("postgresql://"):
            async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        else:
            async_url = sync_url
        self.POSTGRES_CONNECTION_STRING_ASYNC = async_url


constants = Constants()
