"""List contents of the vector database."""

import asyncio
import json
from collections import defaultdict
from lib.services import TaxonomyServices
from utils.config.constants import constants
from utils.ui.progress import setup_logging


async def list_vector_db_contents():
    """List all contents in the vector database."""
    setup_logging()

    # Initialize services
    services = TaxonomyServices()
    await services.post_init()

    table_name = constants.TAXONOMY_EMBEDDINGS_TABLE_NAME

    print(f"Querying vector database table: {table_name}\n")

    try:
        # First, check if table exists and get its structure
        check_table_query = f"""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = '{table_name}'
        );
        """

        with services.connection_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(check_table_query)
                table_exists = cur.fetchone()[0]

        if not table_exists:
            print(f"Table '{table_name}' does not exist in the database.")
            print("Run ingest_taxonomy.py first to create the table.")
            return

        # Get table structure to understand column names
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

        # Check if target_id exists as a separate column (metadata_columns)
        column_names = [col[0] for col in columns]
        has_target_id_column = "target_id" in column_names

        # Find metadata column (could be 'metadata' or 'cmetadata' or similar)
        metadata_col = None
        for col_name, col_type in columns:
            if "metadata" in col_name.lower():
                metadata_col = col_name
                break

        # Query the database - use target_id column if it exists, otherwise extract from JSON metadata
        if has_target_id_column:
            # target_id is stored as a separate column (metadata_columns)
            query = f"""
            SELECT 
                target_id,
                COUNT(*) as count
            FROM {table_name}
            GROUP BY target_id
            ORDER BY count DESC;
            """
        elif metadata_col:
            # Fallback: extract from JSON metadata column
            query = f"""
            SELECT 
                {metadata_col}->>'target_id' as target_id,
                COUNT(*) as count
            FROM {table_name}
            GROUP BY {metadata_col}->>'target_id'
            ORDER BY count DESC;
            """
        else:
            print(f"Could not find target_id column or metadata column in table '{table_name}'.")
            print(f"Available columns: {column_names}")
            return

        # Use sync connection pool for querying
        with services.connection_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                results = cur.fetchall()

        if not results:
            print("No records found in the vector database.")
            return

        # Group by target_id
        taxonomy_stats = defaultdict(int)
        total_records = 0

        for target_id, count in results:
            total_records += count
            target_id = target_id if target_id else "unknown"
            taxonomy_stats[target_id] += count

        # Print summary
        print("=" * 80)
        print("VECTOR DATABASE CONTENTS SUMMARY")
        print("=" * 80)
        print(f"\nTotal records: {total_records}\n")

        # Print SHQ taxonomy stats
        if "shq" in taxonomy_stats:
            shq_total = taxonomy_stats["shq"]
            print("SHQ Taxonomy (target_id='shq'):")
            print(f"  Total embeddings: {shq_total}")
            print()

        # Print client taxonomy stats
        client_stats = {
            k: v for k, v in taxonomy_stats.items() if k != "shq" and k != "unknown"
        }
        if client_stats:
            client_total = sum(client_stats.values())
            print("Client Taxonomies:")
            print(f"  Total embeddings: {client_total}")
            print(f"  Number of clients: {len(client_stats)}")
            print()

            print("  Breakdown by target_id:")
            for target_id, count in sorted(
                client_stats.items(), key=lambda x: x[1], reverse=True
            ):
                print(f"    - {target_id}: {count} embeddings")
            print()

        # Print unknown taxonomy stats
        if "unknown" in taxonomy_stats:
            unknown_total = taxonomy_stats["unknown"]
            if unknown_total > 0:
                print("Unknown/Other (target_id not set):")
                print(f"  Total embeddings: {unknown_total}")
                print()

        # Print detailed breakdown
        print("=" * 80)
        print("DETAILED BREAKDOWN")
        print("=" * 80)

        # Query for more details
        if has_target_id_column:
            detail_query = f"""
            SELECT 
                target_id,
                COUNT(*) as count
            FROM {table_name}
            GROUP BY target_id
            ORDER BY target_id;
            """
        else:
            detail_query = f"""
            SELECT 
                {metadata_col}->>'target_id' as target_id,
                COUNT(*) as count
            FROM {table_name}
            GROUP BY {metadata_col}->>'target_id'
            ORDER BY target_id;
            """

        with services.connection_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(detail_query)
                detail_results = cur.fetchall()

        print("\nTarget ID | Count")
        print("-" * 80)
        for target_id, count in detail_results:
            target_display = target_id if target_id else "(null)"
            print(f"{target_display:20} | {count}")

        # Sample records
        print("\n" + "=" * 80)
        print("SAMPLE RECORDS (first 5)")
        print("=" * 80)

        # Find content column
        content_col = None
        for col_name, col_type in columns:
            if "content" in col_name.lower() or "page" in col_name.lower():
                content_col = col_name
                break

        # Build sample query - include target_id if it's a separate column
        if has_target_id_column:
            if content_col:
                sample_query = f"""
                SELECT 
                    target_id,
                    {metadata_col if metadata_col else 'NULL'} as metadata,
                    LEFT({content_col}, 100) as content_preview
                FROM {table_name}
                LIMIT 5;
                """
            else:
                sample_query = f"""
                SELECT 
                    target_id,
                    {metadata_col if metadata_col else 'NULL'} as metadata
                FROM {table_name}
                LIMIT 5;
                """
        else:
            if content_col:
                sample_query = f"""
                SELECT 
                    {metadata_col},
                    LEFT({content_col}, 100) as content_preview
                FROM {table_name}
                LIMIT 5;
                """
            else:
                sample_query = f"""
                SELECT 
                    {metadata_col}
                FROM {table_name}
                LIMIT 5;
                """

        with services.connection_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sample_query)
                sample_results = cur.fetchall()

        for idx, row in enumerate(sample_results, 1):
            # Parse row structure based on query structure
            if has_target_id_column:
                target_id_val = row[0]
                metadata_json = row[1] if len(row) > 1 else None
                content_preview = row[2] if len(row) > 2 else None
            else:
                target_id_val = None
                if content_col:
                    metadata_json, content_preview = row
                else:
                    metadata_json = row[0]
                    content_preview = None

            # Handle different metadata formats
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

            print(f"\nRecord {idx}:")
            if has_target_id_column and target_id_val:
                print(f"  Target ID: {target_id_val}")
            if content_preview:
                print(f"  Content: {content_preview}...")
            if metadata:
                print(f"  Metadata: {json.dumps(metadata, indent=4)}")

    except Exception as e:
        print(f"Error querying database: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Cleanup
        await services.aclose()


async def main():
    """Main entry point."""
    await list_vector_db_contents()


if __name__ == "__main__":
    asyncio.run(main())
