"""Output handling for taxonomy matching results."""

import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any


def generate_matched_csv(
    df: pd.DataFrame,
    matches: List[Dict[str, Any]],
    strategy: str,
    output_dir: Path,
) -> Path:
    """
    Generate a new CSV file from scratch using only the generated columns.

    Args:
        df: Filtered DataFrame with category columns (CATEGORY L1, L2, L3)
            Note: Lower number = lower precision. L1 is most general, L3 is most specific/precise.
        matches: List of match results with:
            - 'target_l1'/'target_l2'/'target_l3' (input categories)
            - 'matched_l1'/'matched_l2'/'matched_l3' (matched categories)
        strategy: Matching strategy used (for filename)
        output_dir: Directory to save the matched CSV

    Returns:
        Path to the generated matched CSV file
    """

    # Create a mapping from target L3 to matched data for quick lookup
    match_lookup = {}
    for match in matches:
        target_l3 = match.get("target_l3", "")
        if target_l3:
            match_lookup[target_l3] = {
                "matched_l2": match.get("matched_l2", ""),
                "matched_l3": match.get("matched_l3", ""),
            }

    # Build new DataFrame from scratch
    output_data = []
    
    # Find the L3 column in the filtered df
    l3_column = None
    l2_column = None
    l1_column = None
    
    for col in df.columns:
        col_upper = col.upper()
        if col == "CATEGORY L3" or (l3_column is None and "L3" in col_upper):
            l3_column = col
        if col == "CATEGORY L2" or (l2_column is None and "L2" in col_upper):
            l2_column = col
        if col == "CATEGORY L1" or (l1_column is None and "L1" in col_upper):
            l1_column = col
    
    if not l3_column:
        raise ValueError(f"Could not find L3 column in dataframe. Available columns: {list(df.columns)}")
    
    # Build rows from the filtered df and matches
    for idx, row in df.iterrows():
        target_l3 = str(row.get(l3_column, "")).strip()
        target_l2 = str(row.get(l2_column, "")).strip() if l2_column else ""
        target_l1 = str(row.get(l1_column, "")).strip() if l1_column else ""
        
        # Get matched data
        match_data = match_lookup.get(target_l3, {})
        matched_l2 = match_data.get("matched_l2", "")
        matched_l3 = match_data.get("matched_l3", "")
        
        # GDW_SUBCATEGORY is the matched L3 (or 0 if no match)
        gdw_subcategory = matched_l3 if matched_l3 else 0
        
        # Create row with only the columns we generate
        output_row = {
            "L1": target_l1,
            "L2": target_l2,
            "L3": target_l3,
            "matched_l2": matched_l2,
            "matched_l3": matched_l3,
            "GDW_SUBCATEGORY": gdw_subcategory,
        }
        
        output_data.append(output_row)
    
    # Create new DataFrame from scratch
    df_output = pd.DataFrame(output_data)

    # Generate output path
    output_path = output_dir / "output_taxonomy.csv"

    # Save matched CSV
    df_output.to_csv(output_path, index=False)
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
    
    # Handle different key names for compatibility
    def get_matched_l3(m):
        return m.get("matched_l3") or m.get("matched_category_l3")
        
    def get_confidence(m):
        if "confidence" in m:
            return m["confidence"]
        return m.get("confidence_score", 0.0)

    matched_categories = sum(1 for m in matches if get_matched_l3(m))
    unmatched_categories = total_categories - matched_categories

    confidence_scores = [
        get_confidence(m) for m in matches if get_matched_l3(m)
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
