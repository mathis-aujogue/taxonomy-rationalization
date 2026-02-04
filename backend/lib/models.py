"""Pydantic models for structured LLM output."""

from pydantic import BaseModel, Field
from typing import Optional


class MatchResult(BaseModel):
    """Result of a category match."""

    matched_category_l2: str = Field(
        description="Matched category L2 from SHQ taxonomy"
    )
    matched_category_l3: str = Field(
        description="Matched category L3 from SHQ taxonomy"
    )
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0",
        ge=0.0,
        le=1.0,
    )


class MatchResultWithReasoning(BaseModel):
    """Result of a category match with reasoning."""

    matched_category_l2: str = Field(
        description="Matched category L2 from SHQ taxonomy"
    )
    matched_category_l3: str = Field(
        description="Matched category L3 from SHQ taxonomy"
    )
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(description="Explanation of why this match was chosen")


class CandidateMatch(BaseModel):
    """A candidate match with score."""

    category_l2: str
    category_l3: str
    score: float
    definition: Optional[str] = None
