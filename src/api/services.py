"""Service layer for API operations."""

import pandas as pd
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from lib.services import TaxonomyServices
from .database import TaxonomyJob
from .models import ColumnMapping, MatchResult, CandidateMatch, JobStatus
from utils.data.data_loader import load_taxonomy_csv
from ingest_taxonomy import extract_taxonomy_fields
from ingest_hybrid_embeddings import ingest_hybrid_embeddings
from .generate_descriptions_api import generate_descriptions_api
from hybrid_matcher import HybridMatcher
from utils.ai.content_builder import build_page_content
from utils.config.constants import constants
from langchain_core.documents import Document


class TaxonomyService:
    """Service for taxonomy operations."""

    def __init__(self, db: Session):
        self.db = db
        self.upload_dir = Path("uploads")
        self.upload_dir.mkdir(exist_ok=True)

    async def upload_taxonomy(
        self, target_id: str, filename: str, file_content: bytes, column_mapping: ColumnMapping
    ) -> TaxonomyJob:
        """Upload and save a taxonomy CSV file."""
        # Save file
        file_path = self.upload_dir / f"{target_id}_{filename}"
        file_path.write_bytes(file_content)

        # Create or update job
        job = self.db.query(TaxonomyJob).filter(TaxonomyJob.target_id == target_id).first()
        if job:
            job.filename = filename
            job.status = JobStatus.UPLOADED.value
            job.column_mapping = column_mapping.model_dump()
        else:
            job = TaxonomyJob(
                target_id=target_id,
                filename=filename,
                status=JobStatus.UPLOADED.value,
                column_mapping=column_mapping.model_dump(),
            )
            self.db.add(job)

        self.db.commit()
        self.db.refresh(job)
        return job

    async def ingest_taxonomy(self, target_id: str, clear_existing: bool = False) -> TaxonomyJob:
        """Ingest taxonomy embeddings into vector database."""
        job = self.db.query(TaxonomyJob).filter(TaxonomyJob.target_id == target_id).first()
        if not job:
            raise ValueError(f"Job not found for target_id: {target_id}")

        try:
            job.status = JobStatus.INGESTING.value
            self.db.commit()

            # Get file path
            file_path = self.upload_dir / f"{target_id}_{job.filename}"

            # Load and remap columns
            df = pd.read_csv(file_path)
            mapping = ColumnMapping(**job.column_mapping)

            # Remap columns to standard names
            remapped_data = {}
            if mapping.l1:
                remapped_data["CATEGORY L1"] = df[mapping.l1]
            if mapping.l2:
                remapped_data["CATEGORY L2"] = df[mapping.l2]
            remapped_data["CATEGORY L3"] = df[mapping.l3]
            if mapping.definition:
                remapped_data["DEFINITION"] = df[mapping.definition]
            remapped_df = pd.DataFrame(remapped_data)
            # Preserve generated_description if present (e.g. re-upload of enriched file or different target_id)
            if "generated_description" in df.columns:
                remapped_df["generated_description"] = df["generated_description"]

            # Save remapped CSV temporarily
            temp_path = self.upload_dir / f"{target_id}_remapped.csv"
            cols_to_save = [col for col in ["CATEGORY L1", "CATEGORY L2", "CATEGORY L3", "DEFINITION", "generated_description"] if col in remapped_df.columns]
            remapped_df[cols_to_save].to_csv(temp_path, index=False)

            # Ingest using existing logic
            result = await ingest_hybrid_embeddings(str(temp_path), target_id, clear_existing)

            job.status = JobStatus.INGESTED.value
            self.db.commit()
            job._ingestion_result = result  # for API response
            return job

        except Exception as e:
            job.status = JobStatus.ERROR.value
            job.error_message = str(e)
            self.db.commit()
            raise

    async def augment_taxonomy(
        self, target_id: str, prompt_template: Optional[str] = None, llm_model: Optional[str] = None
    ) -> TaxonomyJob:
        """Generate LLM descriptions for taxonomy."""
        job = self.db.query(TaxonomyJob).filter(TaxonomyJob.target_id == target_id).first()
        if not job:
            raise ValueError(f"Job not found for target_id: {target_id}")

        try:
            job.status = JobStatus.AUGMENTING.value
            self.db.commit()

            # Get file path
            file_path = self.upload_dir / f"{target_id}_{job.filename}"

            # Load and remap
            df = pd.read_csv(file_path)
            mapping = ColumnMapping(**job.column_mapping)

            remapped_data = {}
            if mapping.l1:
                remapped_data["CATEGORY L1"] = df[mapping.l1]
            if mapping.l2:
                remapped_data["CATEGORY L2"] = df[mapping.l2]
            remapped_data["CATEGORY L3"] = df[mapping.l3]
            if mapping.definition:
                remapped_data["DEFINITION"] = df[mapping.definition]
            remapped_df = pd.DataFrame(remapped_data)

            # Save remapped CSV
            temp_input = self.upload_dir / f"{target_id}_remapped.csv"
            remapped_df.to_csv(temp_input, index=False)

            # Generate descriptions
            temp_output = self.upload_dir / f"{target_id}_enriched.csv"
            await generate_descriptions_api(str(temp_input), str(temp_output), prompt_template, llm_model)

            # Update original file with enriched data
            enriched_df = pd.read_csv(temp_output)
            for col in ["CATEGORY L1", "CATEGORY L2", "CATEGORY L3", "DEFINITION"]:
                if col in enriched_df.columns:
                    remapped_df[col] = enriched_df[col]
            remapped_df["generated_description"] = enriched_df.get("generated_description", "")

            # Save back
            remapped_df.to_csv(file_path, index=False)

            # Re-ingest so the vector DB gets the new description embeddings (desc component).
            # At first ingest we had no descriptions; now we do.
            await ingest_hybrid_embeddings(str(temp_output), target_id, clear_existing=True)

            job.status = JobStatus.AUGMENTED.value
            self.db.commit()
            return job

        except Exception as e:
            job.status = JobStatus.ERROR.value
            job.error_message = str(e)
            self.db.commit()
            raise

    async def match_taxonomy(
        self,
        our_target_id: str,
        client_target_id: str,
        threshold: Optional[float] = None,
        weights: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> List[MatchResult]:
        """Run hybrid matching."""
        services = TaxonomyServices()
        await services.post_init()

        try:
            matcher = HybridMatcher(services, weights=weights)
            await matcher.load_target_taxonomy(our_target_id)
            results = await matcher.match_client_taxonomy(client_target_id, limit=limit)

            # Convert to MatchResult format
            match_results = []
            for r in results:
                candidates = [
                    CandidateMatch(
                        l1=c.get("l1", ""),
                        l2=c.get("l2", ""),
                        l3=c.get("l3", ""),
                        score=c.get("score", 0.0),
                        definition=c.get("definition"),
                    )
                    for c in r.get("top_3_candidates", [])
                ]

                status = "auto"
                if threshold and r.get("confidence", 0.0) < threshold:
                    status = "review"

                match_results.append(
                    MatchResult(
                        target_l1=r.get("target_l1", ""),
                        target_l2=r.get("target_l2", ""),
                        target_l3=r.get("target_l3", ""),
                        matched_l1=r.get("matched_l1", ""),
                        matched_l2=r.get("matched_l2", ""),
                        matched_l3=r.get("matched_l3", ""),
                        confidence=r.get("confidence", 0.0),
                        reasoning=r.get("reasoning"),
                        top_3_candidates=candidates,
                        status=status,
                    )
                )

            return match_results

        finally:
            await services.aclose()

    def get_jobs(self) -> List[TaxonomyJob]:
        """Get all jobs."""
        return self.db.query(TaxonomyJob).all()

    def get_job(self, target_id: str) -> Optional[TaxonomyJob]:
        """Get a job by target_id."""
        return self.db.query(TaxonomyJob).filter(TaxonomyJob.target_id == target_id).first()

    async def get_our_taxonomy(self, target_id: str) -> List[Dict[str, Any]]:
        """Get our taxonomy for visualization."""
        services = TaxonomyServices()
        await services.post_init()

        try:
            # Fetch from vector database
            table_name = constants.TAXONOMY_EMBEDDINGS_TABLE_NAME
            # Detect column names dynamically
            cols_query = f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table_name}'
            """
            
            with services.connection_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(cols_query)
                    columns = [r[0] for r in cur.fetchall()]
            
            metadata_col = next((c for c in columns if 'metadata' in c.lower()), None)
            if not metadata_col:
                raise ValueError(f"Could not find metadata column in {table_name}")
            
            # Check if target_id is a direct column or in metadata
            if 'target_id' in columns:
                query = f"""
                    SELECT {metadata_col}
                    FROM "{table_name}"
                    WHERE target_id = %s AND ({metadata_col}->>'component') = 'l3'
                    ORDER BY ({metadata_col}->>'original_index')::int
                """
            else:
                query = f"""
                    SELECT {metadata_col}
                    FROM "{table_name}"
                    WHERE {metadata_col}->>'target_id' = %s AND ({metadata_col}->>'component') = 'l3'
                    ORDER BY ({metadata_col}->>'original_index')::int
                """

            with services.connection_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (target_id,))
                    rows = cur.fetchall()

            nodes = []
            for row in rows:
                meta = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                nodes.append(
                    {
                        "l1": meta.get("l1", ""),
                        "l2": meta.get("l2", ""),
                        "l3": meta.get("l3", ""),
                        "definition": meta.get("definition", ""),
                    }
                )

            return nodes

        finally:
            await services.aclose()
