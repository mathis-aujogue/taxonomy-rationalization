"""
Hybrid matcher that uses cached embeddings (Hierarchy, Full Path, Description) to match categories.
Runs fully offline by retrieving pre-computed embeddings from the vector database.
"""

import asyncio
import argparse
import pandas as pd
import numpy as np
import json
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
from tqdm import tqdm
from datetime import datetime

from lib.services import TaxonomyServices
from utils.ui.progress import setup_logging
from utils.data.data_loader import load_taxonomy_csv
from ingest_taxonomy import extract_taxonomy_fields
from utils.output.output_handler import generate_matched_csv, generate_detailed_report, generate_summary_statistics
from utils.config.constants import constants

# Default weights configuration
DEFAULT_WEIGHTS = {
    "hierarchy": {
        "l1": 0.15,
        "l2": 0.30,
        "l3": 0.55
    },
    "signals": {
        "hierarchy": 0.30,
        "full_path": 0.20,
        "description": 0.50
    }
}

def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors."""
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    return dot_product / (norm_v1 * norm_v2) if norm_v1 > 0 and norm_v2 > 0 else 0.0

class HybridMatcher:
    def __init__(self, services: TaxonomyServices, weights: Optional[Dict[str, Any]] = None):
        self.services = services
        self.target_embeddings = [] # List of dicts with 'l1', 'l2', 'l3', 'full', 'desc' vectors
        self.target_metadata = []   # List of original rows/metadata
        self.weights = weights if weights else DEFAULT_WEIGHTS

    async def _fetch_embeddings_from_db(self, target_id: str) -> Dict[int, Dict[str, np.ndarray]]:
        """
        Fetch all embeddings for a target_id from the database.
        Returns a dict mapped by original_index: { 'l1': vector, 'l2': vector... }
        """
        table_name = constants.TAXONOMY_EMBEDDINGS_TABLE_NAME
        
        # We need to fetch embedding vector and metadata to reconstruct the structure
        # Assuming we can get raw vectors. If LangChain PGVectorStore stores them in a column named 'embedding'
        
        # First, detect column names to be safe (reusing logic from list_vector_db)
        cols_query = f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
        """
        
        with self.services.connection_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(cols_query)
                columns = [r[0] for r in cur.fetchall()]
        
        # Identify columns
        embedding_col = next((c for c in columns if c.lower() in ['embedding', 'vector']), None)
        metadata_col = next((c for c in columns if 'metadata' in c.lower()), None)
        
        if not embedding_col or not metadata_col:
            raise ValueError(f"Could not identify embedding/metadata columns in {table_name}")
            
        query = f"""
            SELECT {metadata_col}, {embedding_col}
            FROM {table_name}
            WHERE {metadata_col}->>'target_id' = %s
        """
        
        # Also try direct column if it exists
        if 'target_id' in columns:
             query = f"""
            SELECT {metadata_col}, {embedding_col}
            FROM {table_name}
            WHERE target_id = %s
        """
        
        print(f"Fetching cached embeddings for '{target_id}'...")
        with self.services.connection_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (target_id,))
                rows = cur.fetchall()
                
        if not rows:
            raise ValueError(f"No embeddings found for target_id='{target_id}'. Run ingest_hybrid_embeddings.py first.")
            
        # Reconstruct structure
        # Map: original_index -> { component_type -> vector }
        reconstructed = {}
        
        for meta_json, vec_str in rows:
            # Parse metadata
            if isinstance(meta_json, str):
                meta = json.loads(meta_json)
            else:
                meta = meta_json
                
            idx = int(meta.get("original_index", -1))
            comp = meta.get("component", "")
            
            if idx == -1 or not comp:
                continue
                
            # Parse vector
            # pgvector returns a string like "[0.1, 0.2, ...]" or list depending on driver
            if isinstance(vec_str, str):
                vec = np.array(json.loads(vec_str), dtype=np.float32)
            else:
                vec = np.array(vec_str, dtype=np.float32)
                
            if idx not in reconstructed:
                reconstructed[idx] = {"meta": meta}
            
            reconstructed[idx][comp] = vec
            # Keep one copy of metadata (they should be identical across components except 'component' field)
            reconstructed[idx]["meta"] = meta 
            
        return reconstructed

    async def load_target_taxonomy(self, target_id: str):
        """Load target (our) taxonomy embeddings from DB."""
        data = await self._fetch_embeddings_from_db(target_id)
        
        # Convert to list sorted by index to match CSV order (optional but good for consistency)
        sorted_indices = sorted(data.keys())
        
        self.target_embeddings = []
        self.target_metadata = []
        
        for idx in sorted_indices:
            item = data[idx]
            self.target_embeddings.append({
                "l1": item.get("l1"),
                "l2": item.get("l2"),
                "l3": item.get("l3"),
                "full": item.get("full"),
                "desc": item.get("desc")
            })
            self.target_metadata.append(item["meta"])
            
        print(f"Loaded {len(self.target_embeddings)} target categories.")

    async def match_client_taxonomy(self, client_target_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Match client taxonomy using cached embeddings.
        """
        client_data = await self._fetch_embeddings_from_db(client_target_id)
        
        sorted_indices = sorted(client_data.keys())
        if limit:
            sorted_indices = sorted_indices[:limit]
            
        results = []
        pbar = tqdm(total=len(sorted_indices), desc="Matching")
        
        for idx in sorted_indices:
            client_item = client_data[idx]
            client_meta = client_item["meta"]
            
            # Vectors
            c_l1 = client_item.get("l1")
            c_l2 = client_item.get("l2")
            c_l3 = client_item.get("l3")
            c_full = client_item.get("full")
            c_desc = client_item.get("desc")
            
            # Ensure vectors are not None before using
            if c_l1 is None or c_l2 is None or c_l3 is None or c_full is None or c_desc is None:
                continue

            matches = []
            
            for t_idx, target in enumerate(self.target_embeddings):
                # Hierarchy Score
                sim_l1 = cosine_similarity(c_l1, target["l1"]) if target["l1"] is not None else 0.0
                sim_l2 = cosine_similarity(c_l2, target["l2"]) if target["l2"] is not None else 0.0
                sim_l3 = cosine_similarity(c_l3, target["l3"]) if target["l3"] is not None else 0.0
                
                hierarchy_score = (
                    self.weights["hierarchy"]["l1"] * sim_l1 +
                    self.weights["hierarchy"]["l2"] * sim_l2 +
                    self.weights["hierarchy"]["l3"] * sim_l3
                )
                
                # Full Path Score
                full_path_score = cosine_similarity(c_full, target["full"]) if target["full"] is not None else 0.0
                
                # Description Score
                desc_score = cosine_similarity(c_desc, target["desc"]) if target["desc"] is not None else 0.0
                
                # Final Weighted Score
                final_score = (
                    self.weights["signals"]["hierarchy"] * hierarchy_score +
                    self.weights["signals"]["full_path"] * full_path_score +
                    self.weights["signals"]["description"] * desc_score
                )
                
                matches.append({
                    "target_idx": t_idx,
                    "score": final_score,
                    "scores": {
                        "hierarchy": hierarchy_score,
                        "full_path": full_path_score,
                        "description": desc_score,
                        "l1": sim_l1,
                        "l2": sim_l2,
                        "l3": sim_l3
                    }
                })
            
            # Sort and pick best
            matches.sort(key=lambda x: x["score"], reverse=True)
            best = matches[0]
            target_meta = self.target_metadata[best["target_idx"]]
            
            # Top candidates
            candidates = []
            for m in matches[:5]:
                tm = self.target_metadata[m["target_idx"]]
                candidates.append({
                    "l1": tm.get("l1", ""),
                    "l2": tm.get("l2", ""),
                    "l3": tm.get("l3", ""),
                    "score": float(m["score"]),
                    "definition": tm.get("definition", "")
                })

            results.append({
                "target_l1": client_meta.get("l1", ""),
                "target_l2": client_meta.get("l2", ""),
                "target_l3": client_meta.get("l3", ""),
                "matched_l1": target_meta.get("l1", ""),
                "matched_l2": target_meta.get("l2", ""),
                "matched_l3": target_meta.get("l3", ""),
                "confidence": float(best["score"]),
                "reasoning": f"Hierarchy: {best['scores']['hierarchy']:.2f}, Desc: {best['scores']['description']:.2f}",
                "top_3_candidates": candidates[:3]
            })
            
            pbar.update(1)
            
        pbar.close()
        return results

async def main():
    parser = argparse.ArgumentParser(description="Hybrid taxonomy matching (Offline/Cached).")
    parser.add_argument("our_target_id", help="Target ID for 'Our Taxonomy' (e.g., shq_hybrid)")
    parser.add_argument("client_target_id", help="Target ID for 'Client Taxonomy' (e.g., zalando_hybrid)")
    parser.add_argument("--limit", type=int, help="Limit number of rows for testing")
    parser.add_argument("--output_name", default="hybrid_results", help="Name for output folder")
    
    args = parser.parse_args()
    setup_logging()
    
    # Initialize services
    services = TaxonomyServices()
    await services.post_init()
    
    try:
        matcher = HybridMatcher(services)
        
        # Load cached embeddings
        await matcher.load_target_taxonomy(args.our_target_id)
        
        # Run matching
        results = await matcher.match_client_taxonomy(args.client_target_id, limit=args.limit)
        
        # Output
        # Need to reconstruct a basic DataFrame for the input to generate_matched_csv
        # We can just use the results themselves to infer input columns
        client_df = pd.DataFrame(results)[["target_l1", "target_l2", "target_l3"]]
        client_df.rename(columns={
            "target_l1": "l1", "target_l2": "l2", "target_l3": "l3"
        }, inplace=True) # Map back to standard keys if needed, but generate_matched_csv expects specific headers?
        
        # Actually generate_matched_csv takes the original client dataframe to preserve other columns (like Amount)
        # Since we are running from cache, we don't have the original CSV here easily unless passed as arg.
        # But we stored metadata in the DB!
        # For now, let's just output the results we have.
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("results", args.output_name, timestamp)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print("Generating reports...")
        # We can't use generate_matched_csv exactly as is without the original DF context (amounts etc.)
        # But we can generate the detailed report which is the most important.
        generate_detailed_report(results, "hybrid_matcher_cached", output_dir)
        generate_summary_statistics(results, "hybrid_matcher_cached", 0, output_dir)
        
        print(f"Results saved to {output_dir}")
        
    finally:
        await services.aclose()

if __name__ == "__main__":
    asyncio.run(main())
