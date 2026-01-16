"""Historical mapping-based taxonomy matcher.

This matcher uses historical mappings where client L2+L3 categories have been
previously mapped to our taxonomy's L2+L3 categories. Instead of matching directly
to our taxonomy, we match the target taxonomy to the historical client categories,
then use the associated matched categories from the historical mapping.
"""

import asyncio
import argparse
import time
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Any, List, Dict
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
import json


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
    Note: Lower number = lower precision. L1 is most general, L3 is most specific/precise.
    """
    for emb in embeddings_list:
        metadata = emb["metadata"]
        # Match by l3 (most specific/precise) first, then l2, then l1 (most general)
        # Check most specific first for better matching precision
        if (
            metadata.get("l3", "").strip().lower() == fields.get("l3", "").strip().lower()
            and metadata.get("l2", "").strip().lower() == fields.get("l2", "").strip().lower()
            and metadata.get("l1", "").strip().lower() == fields.get("l1", "").strip().lower()
        ):
            return emb
        # Fallback: match by l2 and l3 if l1 not available
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
    """Main function for historical mapping-based matching."""
    parser = argparse.ArgumentParser(
        description="Match target taxonomy to historical mappings. "
        "Uses historical client L2+L3 mappings to find matches, "
        "then returns the associated matched_l2+matched_l3 from history."
    )
    parser.add_argument(
        "input_csv",
        type=str,
        help="Path to target taxonomy CSV file",
    )
    parser.add_argument(
        "--source-id",
        type=str,
        default="historical_mapping",
        help="Source embeddings target_id to search against (e.g., 'historical_mapping' or 'shq'). "
        "Defaults to 'historical_mapping'.",
    )
    parser.add_argument(
        "--target-id",
        type=str,
        help="Target identifier for pre-ingested client taxonomy embeddings. "
        "If provided, uses pre-existing embeddings from DB instead of creating them on the fly.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Confidence threshold for matches (default: 0.5)",
    )

    args = parser.parse_args()

    setup_logging()
    start_time = time.time()

    source_id = args.source_id
    target_id = args.target_id

    # Initialize services
    services = TaxonomyServices()
    await services.post_init()

    # Load target taxonomy
    print("Loading target taxonomy...")
    target_taxonomy = load_taxonomy_csv(args.input_csv)

    print(f"Loaded {len(target_taxonomy)} categories from target taxonomy")

    # Verify source embeddings exist
    if not services.vectorstore:
        raise ValueError("Vectorstore not initialized")

    # Test query to check if source embeddings exist
    test_results = await services.vectorstore.asimilarity_search_with_score(
        "test",
        k=1,
        filter={"target_id": source_id},
    )
    
    if not test_results:
        print(f"Warning: No source embeddings found in database for source_id '{source_id}'.")
        if source_id == "historical_mapping":
            print(f"Please run: uv run src/ingest_historical_mapping.py <historical_mapping.csv> --id {source_id}")
        else:
            print(f"Please ensure embeddings with target_id '{source_id}' are ingested.")
        await services.aclose()
        return

    print(f"Found source embeddings in database (source_id: {source_id})")

    # If target_id is provided, retrieve embeddings from DB
    target_id_embeddings = None
    if target_id:
        print(f"Retrieving embeddings for target_id '{target_id}' from database...")
        target_id_embeddings = await _retrieve_embeddings_by_target_id(
            services, target_id
        )
        print(f"Retrieved {len(target_id_embeddings)} embeddings for target_id '{target_id}'")
        
        # Debug: Show sample of retrieved embeddings metadata structure
        if target_id_embeddings and len(target_id_embeddings) > 0:
            sample_emb = target_id_embeddings[0]
            print(f"Sample embedding metadata keys: {list(sample_emb.get('metadata', {}).keys())}")
            print(f"Sample embedding l2: '{sample_emb.get('metadata', {}).get('l2', '')}'")
            print(f"Sample embedding l3: '{sample_emb.get('metadata', {}).get('l3', '')}'")

    # Match target taxonomy categories to historical mappings
    print("Matching categories to historical mappings...")
    matches = []
    top_k_scores_list = []

    # Build content lookup map for faster content-based matching (if using pre-ingested embeddings)
    content_lookup = None
    # Also build a direct index by (l2, l3) tuple for exact matching
    l2_l3_lookup = None
    if target_id_embeddings:
        content_lookup = {
            emb.get("content", "").strip(): emb 
            for emb in target_id_embeddings 
            if emb.get("content")
        }
        # Build lookup by (l1, l2, l3) tuple for exact matching
        # Note: Lower number = lower precision. L1 is most general, L3 is most specific/precise.
        # Order: (most general, middle, most specific)
        l2_l3_lookup = {}
        for emb in target_id_embeddings:
            metadata = emb.get("metadata", {})
            l1 = metadata.get("l1", "").strip().lower()
            l2 = metadata.get("l2", "").strip().lower()
            l3 = metadata.get("l3", "").strip().lower()
            if l2 and l3:
                # Use (l1, l2, l3) as key, with l1 optional
                key = (l1, l2, l3) if l1 else (l2, l3)
                l2_l3_lookup[key] = emb
        print(f"Built content lookup map with {len(content_lookup)} entries")
        print(f"Built l1/l2/l3 lookup map with {len(l2_l3_lookup)} entries")

    progress_bar = create_progress_bar(len(target_taxonomy), "Matching")

    matches_found_count = 0
    matches_not_found_count = 0
    
    for idx, row in target_taxonomy.iterrows():
        fields = extract_taxonomy_fields(row)
        query_text = build_page_content(fields)

        # Search for similar categories in source embeddings
        if target_id_embeddings:
            # Use pre-existing embeddings from DB
            # Try direct l1/l2/l3 lookup first (fastest)
            # Note: Order is (l1, l2, l3) where L1 is most general, L3 is most specific/precise
            matching_embedding = None
            if l2_l3_lookup:
                l1_key = fields.get("l1", "").strip().lower()
                l2_key = fields.get("l2", "").strip().lower()
                l3_key = fields.get("l3", "").strip().lower()
                # Try with l1 first (most complete match)
                if l1_key:
                    matching_embedding = l2_l3_lookup.get((l1_key, l2_key, l3_key))
                # Fallback to l2/l3 if l1 not available
                if not matching_embedding:
                    matching_embedding = l2_l3_lookup.get((l2_key, l3_key))
            
            # Fallback to _find_matching_embedding if direct lookup didn't work
            if not matching_embedding:
                matching_embedding = _find_matching_embedding(
                    fields, target_id_embeddings
                )
            
            if not matching_embedding and idx < 3:  # Debug first 3 rows
                print(f"\nDebug: No match found for row {idx}")
                print(f"  Fields: l2='{fields.get('l2', '')}', l3='{fields.get('l3', '')}'")
                print(f"  Query text: '{query_text}'")
                if target_id_embeddings:
                    print(f"  First few embeddings metadata:")
                    for i, emb in enumerate(target_id_embeddings[:3]):
                        meta = emb.get('metadata', {})
                        print(f"    [{i}] l2='{meta.get('l2', '')}', l3='{meta.get('l3', '')}', content='{emb.get('content', '')[:50]}'")
            if matching_embedding:
                matches_found_count += 1
                # Use asimilarity_search_with_score_by_vector
                # Convert numpy array to list if needed (some vectorstores expect lists)
                embedding_vector = matching_embedding["embedding"]
                if isinstance(embedding_vector, np.ndarray):
                    embedding_vector = embedding_vector.tolist()
                results = await services.vectorstore.asimilarity_search_with_score_by_vector(
                    embedding_vector,
                    k=5,
                    filter={"target_id": source_id},
                )
            else:
                matches_not_found_count += 1
                # Fallback: Try content-based matching first before creating new embeddings
                # This is more efficient when matching against the same data
                content_match = content_lookup.get(query_text.strip()) if content_lookup else None
                
                if content_match:
                    # Found by content, use its embedding
                    embedding_vector = content_match["embedding"]
                    if isinstance(embedding_vector, np.ndarray):
                        embedding_vector = embedding_vector.tolist()
                    results = await services.vectorstore.asimilarity_search_with_score_by_vector(
                        embedding_vector,
                        k=5,
                        filter={"target_id": source_id},
                    )
                else:
                    # Last resort: create embedding on the fly if no match found
                    results = await services.vectorstore.asimilarity_search_with_score(
                        query_text,
                        k=5,
                        filter={"target_id": source_id},
                    )
        else:
            # Create embeddings on the fly (original behavior)
            results = await services.vectorstore.asimilarity_search_with_score(
                query_text,
                k=5,
                filter={"target_id": source_id},
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

            # Extract matched categories from metadata
            matched_l2 = doc.metadata.get("matched_l2", "")
            matched_l3 = doc.metadata.get("matched_l3", "")
            
            # Also get the historical client categories for reference
            historical_l2 = doc.metadata.get("l2", "")
            historical_l3 = doc.metadata.get("l3", "")

            candidates.append(
                {
                    "l2": matched_l2,  # Our taxonomy L2 from historical mapping
                    "l3": matched_l3,  # Our taxonomy L3 from historical mapping
                    "confidence": confidence,
                    "historical_l2": historical_l2,  # Historical client L2
                    "historical_l3": historical_l3,  # Historical client L3
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
                "reasoning": f"Matched to historical: {best_match.get('historical_l2', '')} > {best_match.get('historical_l3', '')}",
                "top_3_candidates": [
                    {
                        "l2": c.get("l2", ""),
                        "l3": c.get("l3", ""),
                        "score": c.get("confidence", 0.0),
                        "definition": f"Historical: {c.get('historical_l2', '')} > {c.get('historical_l3', '')}",
                    }
                    for c in candidates[:3]
                ],
            }
        )

        progress_bar.update(1)

    progress_bar.close()

    threshold = args.threshold

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
        target_taxonomy,
        filtered_matches,
        "historical_mapping",
        output_dir,
    )
    generate_detailed_report(filtered_matches, "historical_mapping", output_dir)

    execution_time = time.time() - start_time
    generate_summary_statistics(
        filtered_matches, "historical_mapping", execution_time, output_dir
    )

    print(f"\nCompleted in {execution_time:.2f} seconds")
    print(f"Matched {len([m for m in filtered_matches if m['matched_l3']])} out of {len(filtered_matches)} categories")
    if target_id_embeddings:
        total_queries = matches_found_count + matches_not_found_count
        reuse_rate = (matches_found_count / total_queries * 100) if total_queries > 0 else 0
        print(f"Embedding reuse stats: {matches_found_count}/{total_queries} reused ({reuse_rate:.1f}%), {matches_not_found_count} created on-the-fly")
        if matches_not_found_count > 0 and source_id == target_id:
            print(f"  Note: When matching against the same target_id and source_id, all embeddings should be reused.")
            print(f"  If many are created on-the-fly, there may be a metadata mismatch issue.")

    # Cleanup
    await services.aclose()


if __name__ == "__main__":
    asyncio.run(main())
