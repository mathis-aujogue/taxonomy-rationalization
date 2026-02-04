"""Script to drop and recreate the vectorstore table with target_id as a filterable column."""

import asyncio
from lib.services import TaxonomyServices
from utils.config.constants import constants
from utils.ui.progress import setup_logging


async def recreate_table():
    """Drop existing table and recreate with metadata_columns support."""
    setup_logging()

    services = TaxonomyServices()

    # Open async connection pool
    await services.async_connection_pool.open()

    table_name = constants.TAXONOMY_EMBEDDINGS_TABLE_NAME

    print(f"Dropping existing table: {table_name}")
    print("=" * 80)

    try:
        # Drop the existing table
        drop_query = f'DROP TABLE IF EXISTS "{table_name}" CASCADE;'
        with services.connection_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(drop_query)
        print(f"✓ Dropped table: {table_name}")
    except Exception as e:
        print(f"Error dropping table: {e}")
        print("You may need to drop it manually:")
        print(f'  DROP TABLE IF EXISTS "{table_name}" CASCADE;')
        await services.aclose()
        return

    print("\nRecreating table with metadata_columns support...")
    print("=" * 80)

    # Now initialize with metadata_columns
    await services.post_init()

    print("\n✓ Table recreated successfully!")
    print(f"  Table: {table_name}")
    print(f"  Metadata columns: ['target_id']")
    print("\nYou can now re-ingest your taxonomies:")
    print(
        "  1. Ingest SHQ taxonomy: uv run src/ingest_taxonomy.py assets/our_taxonomy.csv"
    )
    print(
        "  2. Ingest client taxonomy: uv run src/ingest_taxonomy.py assets/zalando_taxonomy.csv --target-id zalando"
    )

    await services.aclose()


if __name__ == "__main__":
    asyncio.run(recreate_table())
