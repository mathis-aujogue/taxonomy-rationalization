"""Output handling for taxonomy matching results."""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


def generate_matched_csv(
    df: pd.DataFrame,
    matches: List[Dict[str, Any]],
    strategy: str,
    output_dir: Path,
) -> Path:
    """
    Generate a copy of the input CSV with GDW_SUBCATEGORY filled (never modifies original).

    Args:
        df: Original DataFrame
        matches: List of match results with either:
            - 'their_category_l3'/'matched_category_l3' (legacy format)
            - 'target_l3'/'matched_l3' (new format)
        strategy: Matching strategy used (for filename)
        output_dir: Directory to save the matched CSV

    Returns:
        Path to the generated matched CSV file
    """

    # Create mapping from target L3 to matched L3
    match_dict = {}
    for match in matches:
        target_l3 = match.get("target_l3")
        matched_l3 = match.get("matched_l3")
        if matched_l3 and target_l3:
            match_dict[target_l3] = matched_l3

    # Create a copy of the dataframe
    df_copy = df.copy()

    # Update GDW_SUBCATEGORY column (create if doesn't exist)
    if "GDW_SUBCATEGORY" not in df_copy.columns:
        df_copy["GDW_SUBCATEGORY"] = 0

        # Determine which column to use for matching
    source_column = "CATEGORY_L3"
    if source_column not in df_copy.columns:
        # Try alternative column names
        for col in df_copy.columns:
            if "L3" in col.upper() or "COMMODITY" in col.upper():
                source_column = col
                break

    # Fill GDW_SUBCATEGORY with matches
    if source_column in df_copy.columns:
        df_copy["GDW_SUBCATEGORY"] = (
            df_copy[source_column].map(match_dict).fillna(df_copy["GDW_SUBCATEGORY"])
        )
    else:
        raise ValueError(f"Column {source_column} not found in dataframe")

    # Generate output path
    output_path = output_dir / "output_taxonomy.csv"

    # Save matched CSV
    df_copy.to_csv(output_path, index=False)
    print(f"Generated matched CSV: {output_path}")

    return output_path


def generate_detailed_report(
    matches: List[Dict[str, Any]],
    method: str,
    output_dir: Path,
) -> Path:
    """
    Generate detailed report CSV with all matching information.

    Args:
        matches: List of match results
        method: Method used (embeddings, llm, hybrid)
        output_dir: Directory to save the report

    Returns:
        Path to the generated report file
    """
    report_path = output_dir / "detailed_report.csv"

    # Prepare report data
    report_data = []
    for match in matches:
        report_data.append(
            {
                "target_l1": match.get("target_l1", ""),
                "target_l2": match.get("target_l2", ""),
                "target_l3": match.get("target_l3", ""),
                "matched_l2": match.get("matched_l2", ""),
                "matched_l3": match.get("matched_l3", ""),
                "confidence": match.get("confidence", 0.0),
                "method_used": method,
                "top_3_candidates": json.dumps(match.get("top_3_candidates", [])),
                "reasoning": match.get("reasoning", ""),
            }
        )

    df_report = pd.DataFrame(report_data)
    df_report.to_csv(report_path, index=False)
    print(f"Generated detailed report: {report_path}")

    return report_path


def generate_summary_statistics(
    matches: List[Dict[str, Any]],
    method: str,
    execution_time: float,
    output_dir: Path,
) -> Path:
    """
    Generate summary statistics JSON file.

    Args:
        matches: List of match results
        method: Method used
        execution_time: Execution time in seconds
        output_dir: Directory to save the statistics

    Returns:
        Path to the generated statistics file
    """
    stats_path = output_dir / "summary.json"

    # Calculate statistics
    total_categories = len(matches)
    matched_categories = sum(1 for m in matches if m.get("matched_category_l3"))
    unmatched_categories = total_categories - matched_categories

    confidence_scores = [
        m.get("confidence_score", 0.0) for m in matches if m.get("matched_category_l3")
    ]

    avg_confidence = (
        sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
    )
    median_confidence = (
        sorted(confidence_scores)[len(confidence_scores) // 2]
        if confidence_scores
        else 0.0
    )

    # Confidence distribution
    high_confidence = sum(1 for c in confidence_scores if c > 0.8)
    medium_confidence = sum(1 for c in confidence_scores if 0.6 <= c <= 0.8)
    low_confidence = sum(1 for c in confidence_scores if c < 0.6)

    statistics = {
        "total_categories": total_categories,
        "matched_categories": matched_categories,
        "unmatched_categories": unmatched_categories,
        "average_confidence": round(avg_confidence, 3),
        "median_confidence": round(median_confidence, 3),
        "confidence_distribution": {
            "high (>0.8)": high_confidence,
            "medium (0.6-0.8)": medium_confidence,
            "low (<0.6)": low_confidence,
        },
        "method": method,
        "execution_time_seconds": round(execution_time, 2),
    }

    with open(stats_path, "w") as f:
        json.dump(statistics, f, indent=2)

    print(f"Generated summary statistics: {stats_path}")

    return stats_path
