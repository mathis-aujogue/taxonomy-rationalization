"""Embeddings-based taxonomy matcher using semantic similarity."""

import asyncio
import argparse
import time
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
from ingest_taxonomy import extract_taxonomy_fields
from pathlib import Path
from datetime import datetime
from typing import Any

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
