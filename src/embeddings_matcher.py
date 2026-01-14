"""Embeddings-based taxonomy matcher using semantic similarity."""

import asyncio
import argparse
import time
import json
import numpy as np
from lib.services import TaxonomyServices
from utils.data.data_loader import load_taxonomy_csv
from utils.ai.threshold_detection import calculate_confidence_score
from utils.ui.progress import setup_logging, create_progress_bar
from utils.output.output_handler import (
    generate_matched_csv,
    generate_detailed_report,
    generate_summary_statistics,
)
from utils.ai.content_builder import build_page_content
from utils.config.constants import constants
from ingest_taxonomy import extract_taxonomy_fields
from pathlib import Path
from datetime import datetime
from typing import Any, List, Dict


async def _retrieve_embeddings_by_target_id(
    services: TaxonomyServices, target_id: str
) -> List[Dict[str, Any]]:
    """
    Retrieve embeddings from the vector database for a specific target_id.
    
    Returns a list of dictionaries containing:
    - embedding: numpy array of the embedding vector
    - metadata: dictionary with l1, l2, l3, definition, etc.
    - content: page content string
    """
    table_name = constants.TAXONOMY_EMBEDDINGS_TABLE_NAME
    embeddings_list = []
    
    # First, detect column names dynamically
    structure_query = f"""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = '{table_name}'
    ORDER BY ordinal_position;
    """
    
    with services.connection_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(structure_query)
            columns = cur.fetchall()
    
    column_names = [col[0] for col in columns]
    
    # Find embedding/vector column (could be 'embedding', 'vector', etc.)
    embedding_col = None
    for col_name in column_names:
        if col_name.lower() in ['embedding', 'vector']:
            embedding_col = col_name
            break
    
    if not embedding_col:
        raise ValueError(
            f"Could not find embedding/vector column in table '{table_name}'. "
            f"Available columns: {column_names}"
        )
    
    # Find metadata column
    metadata_col = None
    for col_name in column_names:
        if "metadata" in col_name.lower():
            metadata_col = col_name
            break
    
    # Find content column
    content_col = None
    for col_name in column_names:
        if col_name.lower() in ['page_content', 'content']:
            content_col = col_name
            break
    
    # Build query
    select_cols = [embedding_col]
    if metadata_col:
        select_cols.append(metadata_col)
    if content_col:
        select_cols.append(content_col)
    
    query = f"""
    SELECT {', '.join(select_cols)}
    FROM {table_name}
    WHERE target_id = %s;
    """
    
    with services.connection_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (target_id,))
            results = cur.fetchall()
    
    for row in results:
        embedding_vector = row[0]
        metadata_json = row[1] if metadata_col and len(row) > 1 else None
        content = row[-1] if content_col and len(row) > (2 if metadata_col else 1) else None
        
        # Parse metadata
        if metadata_json is None:
            metadata = {}
        elif isinstance(metadata_json, dict):
            metadata = metadata_json
        elif isinstance(metadata_json, str):
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError:
                metadata = {}
        else:
            metadata = {}
        
        # Convert embedding vector to numpy array
        # Handle different vector types (pgvector returns different formats)
        if isinstance(embedding_vector, str):
            # Parse string representation (pgvector may return as string)
            try:
                # Try parsing as JSON array string like "[1.0, 2.0, 3.0]"
                embedding_array = np.array(json.loads(embedding_vector), dtype=np.float32)
            except (json.JSONDecodeError, ValueError):
                # Try parsing pgvector format (space-separated or comma-separated)
                # Remove brackets if present and split
                cleaned = embedding_vector.strip('[]')
                # Try comma-separated first
                if ',' in cleaned:
                    parts = cleaned.split(',')
                else:
                    # Space-separated (pgvector default text format)
                    parts = cleaned.split()
                try:
                    embedding_array = np.array([float(x.strip()) for x in parts], dtype=np.float32)
                except (ValueError, TypeError) as e:
                    raise ValueError(
                        f"Could not parse embedding vector string. "
                        f"Format: {embedding_vector[:200] if len(embedding_vector) > 200 else embedding_vector}, "
                        f"Error: {e}"
                    )
        elif hasattr(embedding_vector, '__array__'):
            embedding_array = np.array(embedding_vector.__array__(), dtype=np.float32)
        elif isinstance(embedding_vector, (list, tuple)):
            embedding_array = np.array(embedding_vector, dtype=np.float32)
        elif hasattr(embedding_vector, 'tolist'):
            embedding_array = np.array(embedding_vector.tolist(), dtype=np.float32)
        else:
            # Try to convert directly
            try:
                embedding_array = np.array(embedding_vector, dtype=np.float32)
            except Exception:
                raise ValueError(
                    f"Could not convert embedding vector to numpy array. "
                    f"Type: {type(embedding_vector)}, Value: {str(embedding_vector)[:100]}"
                )
        
        embeddings_list.append({
            "embedding": embedding_array,
            "metadata": metadata,
            "content": content or "",
        })
    
    return embeddings_list


def _find_matching_embedding(
    fields: Dict[str, str], embeddings_list: List[Dict[str, Any]]
) -> Dict[str, Any] | None:
    """
    Find the matching embedding for a given taxonomy row by comparing metadata.
    
    Matches by comparing l1, l2, l3 fields.
    """
    for emb in embeddings_list:
        metadata = emb["metadata"]
        # Try to match by l3 first (most specific), then l2, then l1
        if (
            metadata.get("l3", "").strip().lower() == fields.get("l3", "").strip().lower()
            and metadata.get("l2", "").strip().lower() == fields.get("l2", "").strip().lower()
        ):
            return emb
        # Fallback: match by content if available
        if emb.get("content"):
            expected_content = build_page_content(fields)
            if emb["content"].strip() == expected_content.strip():
                return emb
    
    return None


async def main():
    """Main function for embeddings-based matching."""
    parser = argparse.ArgumentParser(
        description="Match client taxonomy to SHQ taxonomy using embeddings"
    )
    parser.add_argument(
        "input_csv",
        type=str,
        help="Path to client taxonomy CSV file",
    )
    parser.add_argument(
        "--id",
        type=str,
        help="Target identifier. Uses embeddings in db instead of recreating them.",
    )


    args = parser.parse_args()

    setup_logging()
    start_time = time.time()

    # Initialize services
    services = TaxonomyServices()
    await services.post_init()

    # Load taxonomies
    print("Loading taxonomies...")
    client_taxonomy = load_taxonomy_csv(args.input_csv)

    print(f"Loaded {len(client_taxonomy)} categories from client taxonomy")

    # Note: Embeddings should be ingested separately using ingest_taxonomy.py
    # This script assumes embeddings are already in the vectorstore

    # If target_id is provided, retrieve embeddings from DB
    target_id_embeddings = None
    if args.id:
        print(f"Retrieving embeddings for target_id '{args.id}' from database...")
        target_id_embeddings = await _retrieve_embeddings_by_target_id(
            services, args.id
        )
        print(f"Retrieved {len(target_id_embeddings)} embeddings for target_id '{args.id}'")

    # Match client taxonomy categories
    print("Matching categories...")
    matches = []
    top_k_scores_list = []

    progress_bar = create_progress_bar(len(client_taxonomy), "Matching categories")

    for idx, row in client_taxonomy.iterrows():
        fields = extract_taxonomy_fields(row)
        query_text = build_page_content(fields)

        # Search for similar categories
        if services.vectorstore:
            if target_id_embeddings:
                # Use pre-existing embeddings from DB
                # Find matching embedding for this row
                matching_embedding = _find_matching_embedding(
                    fields, target_id_embeddings
                )
                if matching_embedding:
                    # Use asimilarity_search_with_score_by_vector
                    # Convert numpy array to list if needed (some vectorstores expect lists)
                    embedding_vector = matching_embedding["embedding"]
                    if isinstance(embedding_vector, np.ndarray):
                        embedding_vector = embedding_vector.tolist()
                    results = await services.vectorstore.asimilarity_search_with_score_by_vector(
                        embedding_vector,
                        k=5,
                        filter={"target_id": "shq"},
                    )
                else:
                    # Fallback: create embedding on the fly if no match found
                    results = await services.vectorstore.asimilarity_search_with_score(
                        query_text,
                        k=5,
                        filter={"target_id": "shq"},
                    )
            else:
                # Create embeddings on the fly (original behavior)
                results = await services.vectorstore.asimilarity_search_with_score(
                    query_text,
                    k=5,
                    filter={"target_id": "shq"},
                )
            # Get top-k candidates
            top_k = min(5, len(results))
            candidates = []
            scores = []

            for doc, score in results[:top_k]:
                # score is distance (lower is better), convert to similarity
                similarity = 1 - score
                confidence = calculate_confidence_score(similarity)
                scores.append(confidence)

                candidates.append(
                    {
                        "l2": doc.metadata.get("l2", ""),
                        "l3": doc.metadata.get("l3", ""),
                        "confidence": confidence,
                        "definition": doc.metadata.get("definition", ""),
                    }
                )

            top_k_scores_list.append(scores)

            best_match = candidates[0] if candidates else {}

            matches.append(
                {
                    "target_l1": fields.get("l1", ""),
                    "target_l2": fields.get("l2", ""),
                    "target_l3": fields.get("l3", ""),
                    "matched_l2": best_match.get("l2", ""),
                    "matched_l3": best_match.get("l3", ""),
                    "confidence": best_match.get("confidence", 0.0),
                    "reasoning": best_match.get("definition", ""),
                    "top_3_candidates": [
                        {
                            "l2": c.get("l2", ""),
                            "l3": c.get("l3", ""),
                            "score": c.get("score", 0.0),
                            "definition": c.get("definition", ""),
                        }
                        for c in candidates[:3]
                    ],
                }
            )

        progress_bar.update(1)

    progress_bar.close()

    # Auto-detect threshold
    # all_scores: list[Unknown] = [m["confidence"] for m in matches if m["matched_l3"]]
    # threshold = detect_optimal_threshold(all_scores, top_k_scores_list) or threshold
    # print(f"Detected optimal threshold: {threshold}")
    threshold = 0.5

    # Filter matches by threshold
    filtered_matches: list[dict[str, Any]] = [
        m for m in matches if m["confidence"] >= threshold or not m["matched_l3"]
    ]

    # Generate outputs
    print("Generating outputs...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("results", Path(args.input_csv).stem, timestamp)
    output_dir.mkdir(parents=True, exist_ok=True)
    generate_matched_csv(
        client_taxonomy,
        filtered_matches,
        "similarity_search",
        output_dir,
    )
    generate_detailed_report(filtered_matches, "similarity_search", output_dir)

    execution_time = time.time() - start_time
    generate_summary_statistics(
        filtered_matches, "similarity_search", execution_time, output_dir
    )

    print(f"\nCompleted in {execution_time:.2f} seconds")

    # Cleanup
    await services.aclose()


if __name__ == "__main__":
    asyncio.run(main())
