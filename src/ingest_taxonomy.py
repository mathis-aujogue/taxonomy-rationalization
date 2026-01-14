"""Unified ingestion script to populate vector database with taxonomy embeddings."""

import asyncio
import argparse
import pandas as pd
from pathlib import Path
from typing import Dict
from langchain_core.documents import Document
from lib.services import TaxonomyServices
from utils.config.constants import constants
from utils.data.data_loader import load_taxonomy_csv
from utils.ui.progress import setup_logging
from utils.ai.content_builder import build_page_content


def extract_taxonomy_fields(row: pd.Series) -> Dict[str, str]:
    """
    Extract L1, L2, L3, and definition from a taxonomy row.
    Automatically detects taxonomy format based on available columns.
    Handles missing fields gracefully by returning empty strings.

    Args:
        row: DataFrame row

    Returns:
        Dict with keys: l1, l2, l3, definition
    """
    # SHQ taxonomy: CATEGORY L2, CATEGORY L3, DEFINITION
    obj = {}
    if "CATEGORY L1" in row.index:
        obj["l1"] = str(row.get("CATEGORY L1", "")).strip()
    if "CATEGORY L2" in row.index:
        obj["l2"] = str(row.get("CATEGORY L2", "")).strip()
    if "CATEGORY L3" in row.index:
        obj["l3"] = str(row.get("CATEGORY L3", "")).strip()
    if "DEFINITION" in row.index:
        obj["definition"] = str(row.get("DEFINITION", "")).strip()
    return obj


async def ingest_taxonomy(
    csv_path: str,
    target_id: str | None = None,
    clear_existing: bool = False,
):
    """
    Ingest taxonomy into the vector database.

    Args:
        csv_path: Path to taxonomy CSV file (required)
        target_id: Optional target identifier. If None, uses "shq" for SHQ taxonomy.
        clear_existing: If True, clear existing embeddings before ingesting (only for shq taxonomy)
    """
    setup_logging()

    input_path = Path(csv_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Taxonomy CSV not found: {csv_path}")

    # Determine target_id: use "shq" if not provided (SHQ taxonomy)
    target_id = target_id if target_id else "shq"

    # Initialize services
    services = TaxonomyServices()
    await services.post_init()

    # Load taxonomy
    print(f"Loading taxonomy from {csv_path}...")
    taxonomy = load_taxonomy_csv(csv_path)

    # Create documents using unified logic
    print("Creating documents...")
    documents = []
    for index, row in taxonomy.iterrows():
        fields = extract_taxonomy_fields(row)
        page_content = build_page_content(fields)

        metadata = {
            "target_id": target_id,
            **fields,
        }
        documents.append(Document(page_content=page_content, metadata=metadata))

    # Store embeddings in vectorstore
    if services.vectorstore:
        if clear_existing:
            table_name = constants.TAXONOMY_EMBEDDINGS_TABLE_NAME
            delete_query = f'DELETE FROM "{table_name}" WHERE target_id = %s'
            
            # Use sync connection pool for deletion
            with services.connection_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(delete_query, (target_id,))
                    deleted_count = cur.rowcount
            
            print(f"Cleared {deleted_count} existing embeddings for target ID: {target_id}")
        print(f"Ingesting {len(documents)} documents into vectorstore...")
        await services.vectorstore.aadd_documents(documents)

        print(
            f"Successfully ingested {len(documents)} taxonomy embeddings into vectorstore"
        )
        print(f"Target ID: {target_id}")
    else:
        print("Error: Vectorstore not initialized")

    # Cleanup
    await services.aclose()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest taxonomy into the vector database. "
        "If --id is provided, uses that identifier. "
        "Otherwise, uses 'shq' for SHQ taxonomy."
    )

    # CSV path (required)
    parser.add_argument(
        "csv_path",
        type=str,
        help="Path to taxonomy CSV file (required)",
    )

    # Target ID
    parser.add_argument(
        "--id",
        type=str,
        help="Target identifier. If not provided, defaults to 'shq' for SHQ taxonomy.",
    )

    # Clear option (only for shq taxonomy)
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing embeddings before ingesting (requires manual table drop). "
        "Only used when --id is not provided (shq taxonomy)",
    )

    args = parser.parse_args()

    await ingest_taxonomy(
        csv_path=args.csv_path,
        target_id=args.id,
        clear_existing=args.clear,
    )


if __name__ == "__main__":
    asyncio.run(main())
