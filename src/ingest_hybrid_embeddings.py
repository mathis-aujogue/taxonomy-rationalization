"""
Script to ingest taxonomy component embeddings (L1, L2, L3, Description, Full Path) 
into the vector database for the hybrid matcher.

This allows the hybrid matcher to run without API calls by retrieving pre-computed embeddings.
"""

import asyncio
import argparse
import pandas as pd
import numpy as np
import json
from pathlib import Path
from tqdm import tqdm
from typing import List, Dict, Any, Optional

from lib.services import TaxonomyServices
from utils.ui.progress import setup_logging
from utils.data.data_loader import load_taxonomy_csv
from ingest_taxonomy import extract_taxonomy_fields
from utils.config.constants import constants

async def get_embeddings_batch(services: TaxonomyServices, texts: List[str]) -> List[np.ndarray]:
    """Get embeddings for a batch of texts."""
    valid_indices = [i for i, t in enumerate(texts) if t.strip()]
    valid_texts = [texts[i] for i in valid_indices]
    
    embeddings = []
    if valid_texts:
        batch_size = 100
        for i in range(0, len(valid_texts), batch_size):
            batch = valid_texts[i:i+batch_size]
            batch_embeddings = await services.embeddings.aembed_documents(batch)
            embeddings.extend(batch_embeddings)
            
    result = [np.zeros(1536) for _ in texts]
    for idx, emb in zip(valid_indices, embeddings):
        result[idx] = np.array(emb)
        
    return result

async def ingest_hybrid_embeddings(
    csv_path: str,
    target_id: str,
    clear_existing: bool = False
):
    """
    Ingest all embedding components for hybrid matching.
    
    Stores embeddings in the database with metadata indicating the component type:
    - component: 'l1' | 'l2' | 'l3' | 'full' | 'desc'
    """
    setup_logging()
    
    input_path = Path(csv_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Taxonomy CSV not found: {csv_path}")

    print(f"Loading taxonomy from {csv_path}...")
    # Load raw CSV to preserve generated_description if present
    df = pd.read_csv(csv_path)
    
    # Initialize services
    services = TaxonomyServices()
    await services.post_init()
    
    try:
        table_name = constants.TAXONOMY_EMBEDDINGS_TABLE_NAME
        
        # Clear existing embeddings for this target_id if requested
        if clear_existing:
            delete_query = f'DELETE FROM "{table_name}" WHERE target_id = %s'
            with services.connection_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(delete_query, (target_id,))
                    deleted_count = cur.rowcount
            print(f"Cleared {deleted_count} existing embeddings for target ID: {target_id}")

        # Prepare texts
        l1_texts = []
        l2_texts = []
        l3_texts = []
        full_texts = []
        desc_texts = []
        metadata_list = []
        
        print("Preparing text components...")
        for idx, row in df.iterrows():
            fields = extract_taxonomy_fields(row)
            desc = str(row.get("generated_description", "")).strip()
            
            l1 = fields.get("l1", "")
            l2 = fields.get("l2", "")
            l3 = fields.get("l3", "")
            
            full = " > ".join(filter(None, [l1, l2, l3]))
            
            l1_texts.append(l1)
            l2_texts.append(l2)
            l3_texts.append(l3)
            full_texts.append(full)
            desc_texts.append(desc)
            
            metadata_list.append({
                **fields,
                "generated_description": desc,
                "original_index": idx
            })

        # Generate embeddings
        components = {
            "l1": l1_texts,
            "l2": l2_texts, 
            "l3": l3_texts,
            "full": full_texts,
            "desc": desc_texts
        }
        
        total_embeddings = 0
        
        for comp_type, texts in components.items():
            print(f"Generating '{comp_type}' embeddings...")
            embeddings = await get_embeddings_batch(services, texts)
            
            # Prepare documents/rows for insertion
            # We insert directly to ensure control over the structure/metadata
            
            rows_to_insert = []
            for i, emb in enumerate(embeddings):
                # Skip zero vectors (empty text)
                if np.all(emb == 0):
                    continue
                    
                meta = metadata_list[i].copy()
                meta["component"] = comp_type
                
                # Format for pgvector
                # Depending on the library version, might need list or string
                emb_list = emb.tolist()
                
                rows_to_insert.append((
                    target_id,
                    json.dumps(meta),
                    texts[i],
                    emb_list
                ))
            
            # Batch insert
            if rows_to_insert:
                print(f"Inserting {len(rows_to_insert)} '{comp_type}' vectors...")
                
                # Dynamic SQL construction based on table schema
                # Assuming standard langchain pgvector schema: uuid, collection_id, embedding, document, cmetadata
                # But here we seem to have a custom or managed table. 
                # Let's use the services.vectorstore to add documents if possible, 
                # BUT standard add_documents might not let us easily separate components for the same row.
                # Actually, adding them as separate documents with metadata `component=l1` is fine.
                
                from langchain_core.documents import Document
                docs = []
                for target_id, meta_json, content, emb_list in rows_to_insert:
                    meta = json.loads(meta_json)
                    meta["target_id"] = target_id
                    
                    # We can't easily force the embedding vector via add_documents in langchain
                    # So we use the vectorstore's add_embeddings if available, or fallback to raw SQL
                    # LangChain PGVectorStore usually manages embeddings generation internally unless we use a specific method.
                    
                    # Workaround: Use raw SQL for precision and performance
                    pass

                # Using raw SQL insertion to match the schema used by ingest_taxonomy.py
                # First, check schema columns again
                
                cols_query = f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name}'
                """
                
                with services.connection_pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(cols_query)
                        db_cols = [r[0] for r in cur.fetchall()]
                
                # Determine columns to map
                # Usually: id (uuid), embedding (vector), document (text), cmetadata (jsonb), collection_id (uuid)
                # Or custom schema: target_id, embedding, content, metadata
                
                # Let's assume the schema created by ingest_taxonomy.py via LangChain
                # LangChain 0.2+ PGVectorStore uses: id, embedding, document, cmetadata
                
                # We need to map our data to these columns.
                # Since we already computed embeddings, we should use a method that accepts pre-computed embeddings.
                # services.vectorstore.add_embeddings is the standard way.
                
                texts_batch = [r[2] for r in rows_to_insert]
                embeddings_batch = [r[3] for r in rows_to_insert]
                metadatas_batch = [json.loads(r[1]) for r in rows_to_insert]
                
                # Add target_id to metadata for filtering
                for m in metadatas_batch:
                    m["target_id"] = target_id
                
                await services.vectorstore.aadd_embeddings(
                    texts=texts_batch,
                    embeddings=embeddings_batch,
                    metadatas=metadatas_batch
                )
                
                total_embeddings += len(rows_to_insert)

        print(f"Successfully ingested {total_embeddings} hybrid embedding components for target ID: {target_id}")

    finally:
        await services.aclose()

def main():
    parser = argparse.ArgumentParser(description="Ingest hybrid matching embeddings.")
    parser.add_argument("csv_path", help="Path to enriched taxonomy CSV")
    parser.add_argument("target_id", help="Target ID (e.g., 'shq', 'zalando')")
    parser.add_argument("--clear", action="store_true", help="Clear existing embeddings for this target_id")
    
    args = parser.parse_args()
    
    asyncio.run(ingest_hybrid_embeddings(args.csv_path, args.target_id, args.clear))

if __name__ == "__main__":
    main()
