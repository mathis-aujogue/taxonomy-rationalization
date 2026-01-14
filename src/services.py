"""Services initialization for taxonomy matching."""

import logging
from dotenv import load_dotenv
from langchain_openai import AzureOpenAIEmbeddings

# from langchain_openai import AzureChatOpenAI
from langchain_groq import ChatGroq
from langchain_postgres import PGEngine, PGVectorStore
from pydantic import SecretStr
from psycopg_pool import ConnectionPool, AsyncConnectionPool
from src.utils.constants import constants

load_dotenv()

logger = logging.getLogger(__name__)


def check_connection(conn):
    """Validate connection is alive before use."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1")


async def check_async_connection(conn):
    """Validate async connection is alive before use."""
    async with conn.cursor() as cur:
        await cur.execute("SELECT 1")


class TaxonomyServices:
    """Services for taxonomy matching operations."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.pg_engine = PGEngine.from_connection_string(
            url=constants.POSTGRES_CONNECTION_STRING_ASYNC
        )
        # Shared sync connection pool for PostgreSQL operations
        self.connection_pool = ConnectionPool(
            conninfo=constants.POSTGRES_CONNECTION_STRING_SYNC,
            min_size=1,
            max_size=10,
            check=check_connection,
            open=True,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
            },
        )
        self.async_connection_pool = AsyncConnectionPool(
            conninfo=constants.POSTGRES_CONNECTION_STRING_SYNC,
            min_size=1,
            max_size=10,
            check=check_async_connection,
            open=False,  # Will be opened in post_init
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
            },
        )
        self.embeddings = AzureOpenAIEmbeddings(
            api_version=constants.AZURE_API_VERSION,
            azure_endpoint=constants.AZURE_EMBEDDING_ENDPOINT,
            deployment=constants.AZURE_EMBEDDING_MODEL,
            api_key=SecretStr(constants.AZURE_EMBEDDING_API_KEY),
        )
        # self.llm = AzureChatOpenAI(
        #     api_version=constants.AZURE_API_VERSION,
        #     azure_endpoint=constants.AZURE_CHAT_ENDPOINT,
        #     deployment_name=constants.AZURE_CHAT_MODEL,
        #     api_key=SecretStr(constants.AZURE_CHAT_API_KEY),
        #     streaming=False,  # Disable streaming for batch processing
        # )
        self.llm = ChatGroq(
            model=constants.GROQ_MODEL,
            api_key=constants.GROQ_API_KEY,
        )
        self.vectorstore: PGVectorStore | None = None

    async def post_init(self):
        """Initialize vectorstore and connection pools."""
        # Open the async connection pool
        await self.async_connection_pool.open()

        try:
            self.pg_engine.init_vectorstore_table(
                table_name=constants.TAXONOMY_EMBEDDINGS_TABLE_NAME,
                vector_size=1536,  # Azure OpenAI embedding dimension
            )
            self.logger.info(
                f"Initialized vectorstore table: {constants.TAXONOMY_EMBEDDINGS_TABLE_NAME}"
            )
        except Exception as e:
            if "already exists" in str(e) or "DuplicateTableError" in str(e):
                self.logger.info(
                    f"Vectorstore table already exists: {constants.TAXONOMY_EMBEDDINGS_TABLE_NAME}"
                )
            else:
                raise

        self.vectorstore = await self.init_store(
            constants.TAXONOMY_EMBEDDINGS_TABLE_NAME
        )

    async def aclose(self):
        """Close all connection pools and engines."""
        self.logger.info("Closing service connections...")

        # Close async pool
        await self.async_connection_pool.close()

        # Close sync pool
        self.connection_pool.close()

        # Dispose of PG engine
        if hasattr(self.pg_engine, "engine"):
            await self.pg_engine.engine.dispose()

        self.logger.info("All connections closed.")

    async def init_store(self, table_name: str) -> PGVectorStore:
        """Initialize PGVectorStore for taxonomy embeddings."""
        try:
            store = await PGVectorStore.create(
                engine=self.pg_engine,
                table_name=table_name,
                embedding_service=self.embeddings,
            )
            self.logger.info(f"Created new vectorstore: {table_name}")
        except Exception as e:
            if "already exists" in str(e) or "DuplicateTableError" in str(e):
                store = PGVectorStore(
                    engine=self.pg_engine,
                    table_name=table_name,
                    embedding_service=self.embeddings,
                )
                self.logger.info(f"Using existing vectorstore: {table_name}")
            else:
                raise
        return store
