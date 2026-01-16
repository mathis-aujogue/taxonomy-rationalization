"""Service to check vector database status and embedding completeness."""

import json
from typing import Dict, List, Any, Optional
from collections import defaultdict

from lib.services import TaxonomyServices
from utils.config.constants import constants


async def check_vector_embeddings_status(target_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Check the status of vector embeddings in the database.
    Returns information about what embeddings are available for hybrid matching.
    """
    services = TaxonomyServices()
    await services.post_init()

    try:
        table_name = constants.TAXONOMY_EMBEDDINGS_TABLE_NAME

        # Get table structure
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
        has_target_id_column = "target_id" in column_names

        # Find metadata and content columns
        metadata_col = None
        content_col = None
        for col_name, col_type in columns:
            if "metadata" in col_name.lower():
                metadata_col = col_name
            if "content" in col_name.lower() or "page" in col_name.lower():
                content_col = col_name

        if not metadata_col:
            return {
                "error": f"Could not find metadata column in table '{table_name}'",
                "available_columns": column_names,
            }

        # Build query based on whether target_id is a column or in metadata
        if has_target_id_column:
            if target_id:
                query = f"""
                SELECT 
                    target_id,
                    {metadata_col},
                    {content_col if content_col else 'NULL'} as content
                FROM {table_name}
                WHERE target_id = %s
                ORDER BY target_id;
                """
                params = (target_id,)
            else:
                query = f"""
                SELECT 
                    target_id,
                    {metadata_col},
                    {content_col if content_col else 'NULL'} as content
                FROM {table_name}
                ORDER BY target_id;
                """
                params = ()
        else:
            if target_id:
                query = f"""
                SELECT 
                    {metadata_col},
                    {content_col if content_col else 'NULL'} as content
                FROM {table_name}
                WHERE {metadata_col}->>'target_id' = %s
                ORDER BY ({metadata_col}->>'target_id');
                """
                params = (target_id,)
            else:
                query = f"""
                SELECT 
                    {metadata_col},
                    {content_col if content_col else 'NULL'} as content
                FROM {table_name}
                ORDER BY ({metadata_col}->>'target_id');
                """
                params = ()

        with services.connection_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                results = cur.fetchall()

        # Process results
        target_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_records": 0,
                "components": defaultdict(int),
                "original_indices": set(),
                "has_l1": False,
                "has_l2": False,
                "has_l3": False,
                "has_full": False,
                "has_desc": False,
                "complete": False,
            }
        )

        for row in results:
            if has_target_id_column:
                t_id = row[0]
                metadata_json = row[1]
                content = row[2] if len(row) > 2 else None
            else:
                t_id = None
                metadata_json = row[0]
                content = row[1] if len(row) > 1 else None

            # Parse metadata
            if isinstance(metadata_json, dict):
                metadata = metadata_json
            elif isinstance(metadata_json, str):
                try:
                    metadata = json.loads(metadata_json)
                except json.JSONDecodeError:
                    continue
            else:
                continue

            # Get target_id from metadata if not a column
            if not t_id:
                t_id = metadata.get("target_id")
            if not t_id:
                t_id = "unknown"

            stats = target_stats[t_id]
            stats["total_records"] += 1

            # Check component type
            component = metadata.get("component", "")
            if component:
                stats["components"][component] += 1
                if component == "l1":
                    stats["has_l1"] = True
                elif component == "l2":
                    stats["has_l2"] = True
                elif component == "l3":
                    stats["has_l3"] = True
                elif component == "full":
                    stats["has_full"] = True
                elif component == "desc":
                    stats["has_desc"] = True

            # Track original indices
            original_index = metadata.get("original_index")
            if original_index is not None:
                stats["original_indices"].add(original_index)

        # Check completeness for hybrid matching
        # Hybrid matching needs: l1, l2, l3, full, desc for each original_index
        for t_id, stats in target_stats.items():
            # Check if all required components exist
            required_components = {"l1", "l2", "l3", "full", "desc"}
            has_all_components = all(
                stats["components"][comp] > 0 for comp in required_components
            )

            # Check if we have embeddings for all original indices
            num_indices = len(stats["original_indices"])
            if num_indices > 0:
                # Each index should have 5 components (l1, l2, l3, full, desc)
                expected_records = num_indices * 5
                actual_records = stats["total_records"]
                stats["completeness_ratio"] = (
                    actual_records / expected_records if expected_records > 0 else 0.0
                )
            else:
                stats["completeness_ratio"] = 0.0

            stats["complete"] = (
                has_all_components
                and stats["completeness_ratio"] >= 0.95
            )  # Allow 5% tolerance

            # Convert set to list for JSON serialization
            stats["original_indices"] = sorted(list(stats["original_indices"]))
            stats["num_categories"] = len(stats["original_indices"])

        # Format response
        response = {
            "table_name": table_name,
            "has_target_id_column": has_target_id_column,
            "targets": {},
        }

        for t_id, stats in target_stats.items():
            response["targets"][t_id] = {
                "total_records": stats["total_records"],
                "num_categories": stats["num_categories"],
                "components": dict(stats["components"]),
                "has_required_components": {
                    "l1": stats["has_l1"],
                    "l2": stats["has_l2"],
                    "l3": stats["has_l3"],
                    "full": stats["has_full"],
                    "desc": stats["has_desc"],
                },
                "completeness_ratio": round(stats["completeness_ratio"], 3),
                "ready_for_hybrid_matching": stats["complete"],
                "original_indices": stats["original_indices"][:10],  # First 10 as sample
                "total_indices": len(stats["original_indices"]),
            }

        return response

    finally:
        await services.aclose()
