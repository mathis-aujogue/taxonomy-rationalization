"""Ingest historical taxonomy mapping into the vector database.

This script ingests historical mappings where client L2+L3 categories are mapped
to our taxonomy's L2+L3 categories. The client categories are stored as embeddings,
and the matched categories are stored in metadata for lookup.
"""

import asyncio
import argparse
import pandas as pd
from pathlib import Path
from typing import Dict
from langchain_core.documents import Document
from lib.services import TaxonomyServices
from utils.config.constants import constants
from utils.ui.progress import setup_logging
from utils.ai.content_builder import build_page_content


def extract_historical_mapping_fields(row: pd.Series) -> Dict[str, str]:
    """
    Extract fields from historical mapping row.
    
    Expected columns:
    - L2: Client L2 category
    - L3: Client L3 category
    - matched_l2: Our taxonomy L2 category
    - matched_l3: Our taxonomy L3 category
    
    Args:
        row: DataFrame row
        
    Returns:
        Dict with keys: l2, l3, matched_l2, matched_l3
    """
    return {
        "l2": str(row.get("L2", "")).strip(),
        "l3": str(row.get("L3", "")).strip(),
        "matched_l2": str(row.get("matched_l2", "")).strip(),
        "matched_l3": str(row.get("matched_l3", "")).strip(),
    }


async def ingest_historical_mapping(
    csv_path: str,
    target_id: str | None = None,
    clear_existing: bool = False,
):
    """
    Ingest historical mapping into the vector database.
    
    The client L2+L3 categories are stored as embeddings (for matching),
    and the matched_l2+matched_l3 are stored in metadata (for lookup).
    
    Args:
        csv_path: Path to historical mapping CSV file
        target_id: Optional target identifier. If None, uses "historical_mapping" as default.
        clear_existing: If True, clear existing historical mappings before ingesting
    """
    setup_logging()
    
    input_path = Path(csv_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Historical mapping CSV not found: {csv_path}")
    
    # Determine target_id: use "historical_mapping" if not provided
    target_id = target_id if target_id else "historical_mapping"
    
    # Initialize services
    services = TaxonomyServices()
    await services.post_init()
    
    # Load historical mapping
    print(f"Loading historical mapping from {csv_path}...")
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    
    # Validate required columns
    required_cols = ["L2", "L3", "matched_l2", "matched_l3"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Missing required columns in historical mapping CSV: {missing_cols}"
        )
    
    print(f"Loaded {len(df)} historical mappings")
    
    # Create documents
    print("Creating documents...")
    documents = []
    for index, row in df.iterrows():
        fields = extract_historical_mapping_fields(row)
        
        # Build page content from client L2+L3 (for matching)
        # We only use l2 and l3 for the embedding content
        page_content = build_page_content({
            "l2": fields["l2"],
            "l3": fields["l3"],
            "definition": "",  # No definition in historical mapping
        })
        
        # Store matched categories in metadata
        metadata = {
            "target_id": target_id,
            "l2": fields["l2"],  # Client L2
            "l3": fields["l3"],  # Client L3
            "matched_l2": fields["matched_l2"],  # Our taxonomy L2
            "matched_l3": fields["matched_l3"],  # Our taxonomy L3
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
            
            print(f"Cleared {deleted_count} existing historical mappings")
        
        print(f"Ingesting {len(documents)} historical mappings into vectorstore...")
        await services.vectorstore.aadd_documents(documents)
        
        print(
            f"Successfully ingested {len(documents)} historical mapping embeddings"
        )
        print(f"Target ID: {target_id}")
    else:
        print("Error: Vectorstore not initialized")
    
    # Cleanup
    await services.aclose()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest historical taxonomy mapping into the vector database. "
        "Client L2+L3 categories are stored as embeddings, "
        "and matched_l2+matched_l3 are stored in metadata."
    )
    
    parser.add_argument(
        "csv_path",
        type=str,
        help="Path to historical mapping CSV file (required). "
        "Expected columns: L2, L3, matched_l2, matched_l3",
    )
    
    parser.add_argument(
        "--id",
        type=str,
        help="Target identifier. If not provided, defaults to 'historical_mapping'.",
    )
    
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing historical mappings before ingesting",
    )
    
    args = parser.parse_args()
    
    await ingest_historical_mapping(
        csv_path=args.csv_path,
        target_id=args.id,
        clear_existing=args.clear,
    )


if __name__ == "__main__":
    asyncio.run(main())
