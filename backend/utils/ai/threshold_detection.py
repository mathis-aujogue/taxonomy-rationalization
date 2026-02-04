"""Threshold detection algorithms for similarity scores."""

import numpy as np
from typing import List, Tuple


def detect_optimal_threshold(
    similarity_scores: List[float],
    top_k_scores: List[List[float]] | None = None,
) -> float:
    """
    Auto-detect optimal similarity threshold using statistical analysis.

    Args:
        similarity_scores: List of similarity scores (0-1) for best matches
        top_k_scores: Optional list of top-k scores per query for gap analysis

    Returns:
        Optimal threshold value (0-1)
    """
    if not similarity_scores:
        return 0.7  # Default threshold

    scores = np.array(similarity_scores)

    # Method 1: Gap analysis (if top_k_scores provided)
    if top_k_scores:
        gaps = []
        for top_scores in top_k_scores:
            if len(top_scores) >= 2:
                gap = top_scores[0] - top_scores[1]
                gaps.append(gap)

        if gaps:
            avg_gap = np.mean(gaps)
            # If average gap is large, we can use a lower threshold
            # If average gap is small, we need a higher threshold
            if avg_gap > 0.15:
                threshold = 0.65
            elif avg_gap > 0.1:
                threshold = 0.70
            else:
                threshold = 0.75
        else:
            threshold = _distribution_analysis(scores)
    else:
        threshold = _distribution_analysis(scores)

    return round(threshold, 2)


def _distribution_analysis(scores: np.ndarray) -> float:
    """
    Analyze score distribution to determine threshold.

    Uses percentile-based approach:
    - If scores are generally high (>0.8), use 0.75
    - If scores are mixed, use median - 1 std dev
    - If scores are generally low, use 0.65
    """
    median = np.median(scores)
    mean = np.mean(scores)
    std = np.std(scores)

    # High confidence scores
    if median > 0.8:
        return 0.75
    # Medium confidence scores
    elif median > 0.6:
        # Use mean - 0.5*std, but not below 0.6
        threshold = max(0.6, mean - 0.5 * std)
        return min(0.8, threshold)
    # Low confidence scores
    else:
        return 0.65


def calculate_confidence_score(
    similarity: float, distance: float | None = None
) -> float:
    """
    Calculate normalized confidence score from similarity or distance.

    Args:
        similarity: Similarity score (0-1, higher is better)
        distance: Optional distance score (0-1, lower is better)

    Returns:
        Confidence score (0-1)
    """
    if distance is not None:
        # Convert distance to similarity (assuming cosine distance)
        # Cosine distance = 1 - cosine similarity
        similarity = 1 - distance

    # Ensure score is in valid range
    return max(0.0, min(1.0, similarity))
