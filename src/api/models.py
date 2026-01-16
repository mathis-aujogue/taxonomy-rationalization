"""Pydantic models for API requests and responses."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    """Status of a taxonomy job."""
    UPLOADED = "uploaded"
    INGESTING = "ingesting"
    INGESTED = "ingested"
    AUGMENTING = "augmenting"
    AUGMENTED = "augmented"
    MATCHING = "matching"
    MATCHED = "matched"
    ERROR = "error"


class ColumnMapping(BaseModel):
    """Column mapping from CSV headers to internal schema."""
    l1: Optional[str] = Field(None, description="CSV column name for L1")
    l2: Optional[str] = Field(None, description="CSV column name for L2")
    l3: str = Field(..., description="CSV column name for L3 (required)")
    definition: Optional[str] = Field(None, description="CSV column name for definition")


class UploadRequest(BaseModel):
    """Request to upload a taxonomy CSV."""
    target_id: str = Field(..., description="Target identifier for this taxonomy")
    column_mapping: ColumnMapping = Field(..., description="Mapping of CSV columns to internal schema")


class IngestRequest(BaseModel):
    """Request to ingest embeddings."""
    target_id: str = Field(..., description="Target identifier")
    clear_existing: bool = Field(False, description="Clear existing embeddings for this target_id")


class AugmentRequest(BaseModel):
    """Request to generate LLM descriptions."""
    target_id: str = Field(..., description="Target identifier")
    prompt_template: Optional[str] = Field(None, description="Custom prompt template (optional)")
    llm_model: Optional[str] = Field(None, description="LLM model to use (optional)")


class MatchRequest(BaseModel):
    """Request to run hybrid matching."""
    our_target_id: str = Field(..., description="Target ID for our taxonomy (e.g., 'shq_hybrid')")
    client_target_id: str = Field(..., description="Target ID for client taxonomy")
    threshold: Optional[float] = Field(None, description="Confidence threshold for auto-accept")
    weights: Optional[Dict[str, Any]] = Field(None, description="Custom weights for matching")
    limit: Optional[int] = Field(None, description="Limit number of rows for testing")


class CandidateMatch(BaseModel):
    """A candidate match with score."""
    l1: str = ""
    l2: str
    l3: str
    score: float
    definition: Optional[str] = None


class MatchResult(BaseModel):
    """Result of a category match."""
    target_l1: str
    target_l2: str
    target_l3: str
    matched_l1: str = ""
    matched_l2: str
    matched_l3: str
    confidence: float
    reasoning: Optional[str] = None
    top_3_candidates: List[CandidateMatch] = []
    status: str = Field("auto", description="Status: auto, manual, review")


class MatchResponse(BaseModel):
    """Response from matching endpoint."""
    results: List[MatchResult]
    total: int
    matched: int
    unmatched: int
    average_confidence: float


class JobInfo(BaseModel):
    """Information about a taxonomy job."""
    id: int
    target_id: str
    filename: str
    status: JobStatus
    column_mapping: ColumnMapping
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None


class JobListResponse(BaseModel):
    """List of jobs."""
    jobs: List[JobInfo]


class TaxonomyNode(BaseModel):
    """A node in the taxonomy tree."""
    l1: Optional[str] = None
    l2: Optional[str] = None
    l3: str
    definition: Optional[str] = None
    children: List["TaxonomyNode"] = []


TaxonomyNode.model_rebuild()


class TaxonomyResponse(BaseModel):
    """Response containing our taxonomy."""
    target_id: str
    nodes: List[TaxonomyNode]


class ExportRequest(BaseModel):
    """Request to export matched taxonomy."""
    target_id: str = Field(..., description="Target identifier")
    format: str = Field("csv", description="Export format: csv or excel")


class MatchSessionCreate(BaseModel):
    """Request to create a match session."""
    our_target_id: str
    client_target_id: str
    threshold: Optional[float] = None
    results: List[MatchResult]


class MatchSessionUpdate(BaseModel):
    """Request to update validation state."""
    validation_states: Dict[str, str] = Field(..., description="Map of target_l3 to validation status")


class MatchSessionResponse(BaseModel):
    """Response containing match session."""
    id: int
    our_target_id: str
    client_target_id: str
    threshold: Optional[float]
    results: List[MatchResult]
    validation_states: Dict[str, str]
    created_at: datetime
    updated_at: datetime


class ExportMatchResultsRequest(BaseModel):
    """Request to export match results."""
    results: List[MatchResult]
    validation_states: Optional[Dict[str, str]] = None
    format: str = Field("csv", description="Export format: csv or excel")


class ExportTaxonomyRequest(BaseModel):
    """Request to export taxonomy tree."""
    target_id: str
    format: str = Field("csv", description="Export format: csv or excel")


class ExportVectorStatusRequest(BaseModel):
    """Request to export vector status."""
    target_id: Optional[str] = None
    format: str = Field("csv", description="Export format: csv or excel")
