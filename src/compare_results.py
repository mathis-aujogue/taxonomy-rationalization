#!/usr/bin/env python3
"""
Compare two CSV files containing taxonomy matching results.

Both files should have columns: L2, L3, matched_l2, matched_l3
The first file is the reference (ground truth), the second is to evaluate.
"""

import argparse
import sys
from pathlib import Path
from typing import Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

# Set style for better-looking plots
sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (12, 8)


def load_csv(file_path: Path) -> pd.DataFrame:
    """Load CSV file and return DataFrame."""
    try:
        df = pd.read_csv(file_path)
        return df
    except Exception as e:
        print(f"Error loading {file_path}: {e}", file=sys.stderr)
        sys.exit(1)


def validate_columns(df: pd.DataFrame, file_name: str) -> None:
    """Validate that required columns exist."""
    required_cols = ["L2", "L3", "matched_l2", "matched_l3"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(
            f"Error: {file_name} is missing required columns: {missing_cols}",
            file=sys.stderr,
        )
        print(f"Available columns: {list(df.columns)}", file=sys.stderr)
        sys.exit(1)


def validate_identical(
    ref_df: pd.DataFrame, eval_df: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Validate that L2 and L3 columns are identical between files."""
    # Sort both dataframes by L1, L2, L3 for comparison (L1 most general, L3 most specific/precise)
    sort_cols = ["L1"] if "L1" in ref_df.columns else []
    sort_cols.extend(["L2", "L3"])
    ref_cols = (["L1"] if "L1" in ref_df.columns else []) + ["L2", "L3"]
    eval_cols = (["L1"] if "L1" in eval_df.columns else []) + ["L2", "L3"]
    ref_sorted = ref_df[ref_cols].sort_values(sort_cols).reset_index(drop=True)
    eval_sorted = eval_df[eval_cols].sort_values(sort_cols).reset_index(drop=True)

    # Check if they have the same number of rows
    if len(ref_sorted) != len(eval_sorted):
        print(
            f"Error: Files have different number of rows. "
            f"Reference: {len(ref_sorted)}, Evaluation: {len(eval_sorted)}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Check if L2 and L3 values are identical
    if not ref_sorted.equals(eval_sorted):
        # Find differences
        merged = ref_sorted.merge(
            eval_sorted, on=["L2", "L3"], how="outer", indicator=True
        )
        differences = merged[merged["_merge"] != "both"]
        if not differences.empty:
            print(
                "Error: L2 and L3 columns are not identical between files.",
                file=sys.stderr,
            )
            print("\nDifferences found:", file=sys.stderr)
            print(differences[["L2", "L3", "_merge"]].to_string(), file=sys.stderr)
            sys.exit(1)

    # Merge back with matched columns, keeping original order
    ref_merged = ref_df.merge(
        eval_df[["L2", "L3", "matched_l2", "matched_l3"]],
        on=["L2", "L3"],
        suffixes=("_ref", "_eval"),
    )

    return ref_merged, eval_df


def normalize_text(text: str) -> str:
    """Normalize text for comparison (strip whitespace, handle NaN)."""
    if pd.isna(text):
        return ""
    return str(text).strip().upper()


def compare_matched_l2(
    ref_df: pd.DataFrame, eval_df: pd.DataFrame, output_dir: Path
) -> dict:
    """Compare matched_l2 between reference and evaluation."""
    # Merge on L2 and L3 to align rows
    merged = ref_df.merge(
        eval_df[["L2", "L3", "matched_l2"]],
        on=["L2", "L3"],
        suffixes=("_ref", "_eval"),
    )

    # Normalize values for comparison
    ref_values = merged["matched_l2_ref"].apply(normalize_text)
    eval_values = merged["matched_l2_eval"].apply(normalize_text)

    # Calculate metrics
    exact_matches = (ref_values == eval_values).sum()
    total = len(merged)
    accuracy = exact_matches / total if total > 0 else 0.0

    # Get unique labels for confusion matrix
    all_labels = sorted(
        set(ref_values.unique()) | set(eval_values.unique())
    )  # Remove empty string if present
    if "" in all_labels:
        all_labels.remove("")

    # Filter out empty matches for confusion matrix
    mask = (ref_values != "") & (eval_values != "")
    ref_filtered = ref_values[mask]
    eval_filtered = eval_values[mask]

    if len(ref_filtered) > 0 and len(all_labels) > 0:
        # Limit labels if too many (for visualization)
        if len(all_labels) > 50:
            # Only include labels that appear in either ref or eval
            ref_counts = ref_filtered.value_counts()
            eval_counts = eval_filtered.value_counts()
            top_labels = sorted(
                set(
                    list(ref_counts.head(25).index)
                    + list(eval_counts.head(25).index)
                )
            )
            all_labels = [l for l in all_labels if l in top_labels]

        cm = confusion_matrix(
            ref_filtered,
            eval_filtered,
            labels=all_labels if all_labels else None,
        )

        # Plot confusion matrix
        plt.figure(figsize=(max(12, len(all_labels) * 0.5), max(10, len(all_labels) * 0.5)))
        sns.heatmap(
            cm,
            annot=True,
            fmt="d",
            cmap="Blues",
            xticklabels=all_labels,
            yticklabels=all_labels,
            cbar_kws={"label": "Count"},
        )
        plt.title("Confusion Matrix: matched_l2 Comparison", fontsize=16, pad=20)
        plt.xlabel("Evaluation matched_l2", fontsize=12)
        plt.ylabel("Reference matched_l2", fontsize=12)
        plt.xticks(rotation=45, ha="right")
        plt.yticks(rotation=0)
        plt.tight_layout()
        plt.savefig(output_dir / "matched_l2_confusion_matrix.png", dpi=300, bbox_inches="tight")
        plt.close()

    stats = {
        "total_rows": total,
        "exact_matches": exact_matches,
        "mismatches": total - exact_matches,
        "accuracy": accuracy,
    }

    return stats


def compare_matched_l2_l3(
    ref_df: pd.DataFrame, eval_df: pd.DataFrame, output_dir: Path
) -> dict:
    """Compare matched_l1 + matched_l2 + matched_l3 combination between reference and evaluation.
    Note: Lower number = lower precision. L1 is most general, L3 is most specific/precise."""
    # Merge on L2 and L3 to align rows
    merge_cols = ["L2", "L3"]
    eval_cols = merge_cols + ["matched_l2", "matched_l3"]
    if "matched_l1" in eval_df.columns:
        eval_cols.append("matched_l1")
    
    merged = ref_df.merge(
        eval_df[eval_cols],
        on=merge_cols,
        suffixes=("_ref", "_eval"),
    )

    # Create combined keys (L1 first as most general, then L2, then L3 as most specific/precise)
    # Order: most general to most specific
    ref_l1 = merged["matched_l1_ref"].apply(normalize_text) if "matched_l1_ref" in merged.columns else pd.Series([""] * len(merged))
    ref_l2 = merged["matched_l2_ref"].apply(normalize_text)
    ref_l3 = merged["matched_l3_ref"].apply(normalize_text)
    ref_combined = ref_l1 + "|" + ref_l2 + "|" + ref_l3
    
    eval_l1 = merged["matched_l1_eval"].apply(normalize_text) if "matched_l1_eval" in merged.columns else pd.Series([""] * len(merged))
    eval_l2 = merged["matched_l2_eval"].apply(normalize_text)
    eval_l3 = merged["matched_l3_eval"].apply(normalize_text)
    eval_combined = eval_l1 + "|" + eval_l2 + "|" + eval_l3

    # Calculate metrics
    exact_matches = (ref_combined == eval_combined).sum()
    total = len(merged)
    accuracy = exact_matches / total if total > 0 else 0.0

    # Get unique labels for confusion matrix
    all_labels = sorted(set(ref_combined.unique()) | set(eval_combined.unique()))
    if "|" in all_labels:
        all_labels.remove("|")

    # Filter out empty matches
    mask = (ref_combined != "|") & (eval_combined != "|")
    ref_filtered = ref_combined[mask]
    eval_filtered = eval_combined[mask]

    if len(ref_filtered) > 0 and len(all_labels) > 0:
        # Limit labels if too many (for visualization)
        if len(all_labels) > 30:
            # Only include labels that appear frequently
            ref_counts = ref_filtered.value_counts()
            eval_counts = eval_filtered.value_counts()
            top_labels = sorted(
                set(
                    list(ref_counts.head(20).index)
                    + list(eval_counts.head(20).index)
                )
            )
            all_labels = [l for l in all_labels if l in top_labels]

        cm = confusion_matrix(
            ref_filtered,
            eval_filtered,
            labels=all_labels if all_labels else None,
        )

        # Plot confusion matrix
        plt.figure(figsize=(max(14, len(all_labels) * 0.6), max(12, len(all_labels) * 0.6)))
        sns.heatmap(
            cm,
            annot=True,
            fmt="d",
            cmap="Greens",
            xticklabels=all_labels,
            yticklabels=all_labels,
            cbar_kws={"label": "Count"},
        )
        plt.title(
            "Confusion Matrix: matched_l1 + matched_l2 + matched_l3 Comparison", fontsize=16, pad=20
        )
        plt.xlabel("Evaluation (matched_l1|matched_l2|matched_l3)", fontsize=12)
        plt.ylabel("Reference (matched_l1|matched_l2|matched_l3)", fontsize=12)
        plt.xticks(rotation=45, ha="right")
        plt.yticks(rotation=0)
        plt.tight_layout()
        plt.savefig(
            output_dir / "matched_l1_l2_l3_confusion_matrix.png", dpi=300, bbox_inches="tight"
        )
        plt.close()

    stats = {
        "total_rows": total,
        "exact_matches": exact_matches,
        "mismatches": total - exact_matches,
        "accuracy": accuracy,
    }

    return stats


def print_statistics(l2_stats: dict, l2_l3_stats: dict) -> None:
    """Print comparison statistics."""
    print("\n" + "=" * 80)
    print("COMPARISON STATISTICS")
    print("=" * 80)

    print("\n--- matched_l2 Comparison ---")
    print(f"Total rows: {l2_stats['total_rows']}")
    print(f"Exact matches: {l2_stats['exact_matches']}")
    print(f"Mismatches: {l2_stats['mismatches']}")
    print(f"Accuracy: {l2_stats['accuracy']:.2%}")

    print("\n--- matched_l1 + matched_l2 + matched_l3 Comparison ---")
    print(f"Total rows: {l2_l3_stats['total_rows']}")
    print(f"Exact matches: {l2_l3_stats['exact_matches']}")
    print(f"Mismatches: {l2_l3_stats['mismatches']}")
    print(f"Accuracy: {l2_l3_stats['accuracy']:.2%}")

    print("\n" + "=" * 80)


def create_summary_plot(l2_stats: dict, l2_l3_stats: dict, output_dir: Path) -> None:
    """Create a summary comparison plot."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Plot 1: Accuracy comparison
    categories = ["matched_l2", "matched_l1 + matched_l2 + matched_l3"]
    accuracies = [l2_stats["accuracy"], l2_l3_stats["accuracy"]]
    colors = ["#3498db", "#2ecc71"]

    bars = ax1.bar(categories, accuracies, color=colors, alpha=0.7, edgecolor="black")
    ax1.set_ylabel("Accuracy", fontsize=12)
    ax1.set_title("Accuracy Comparison", fontsize=14, fontweight="bold")
    ax1.set_ylim([0, 1])
    ax1.grid(axis="y", alpha=0.3)

    # Add value labels on bars
    for bar, acc in zip(bars, accuracies):
        height = bar.get_height()
        ax1.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{acc:.2%}",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )

    # Plot 2: Match/Mismatch comparison
    l2_matches = [l2_stats["exact_matches"], l2_stats["mismatches"]]
    l2_l3_matches = [l2_l3_stats["exact_matches"], l2_l3_stats["mismatches"]]

    x = np.arange(2)
    width = 0.35

    ax2.bar(
        x - width / 2,
        l2_matches,
        width,
        label="matched_l2",
        color="#3498db",
        alpha=0.7,
        edgecolor="black",
    )
    ax2.bar(
        x + width / 2,
        l2_l3_matches,
        width,
        label="matched_l1 + matched_l2 + matched_l3",
        color="#2ecc71",
        alpha=0.7,
        edgecolor="black",
    )

    ax2.set_ylabel("Count", fontsize=12)
    ax2.set_title("Match vs Mismatch Comparison", fontsize=14, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(["Matches", "Mismatches"])
    ax2.legend()
    ax2.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / "summary_comparison.png", dpi=300, bbox_inches="tight")
    plt.close()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Compare two CSV files containing taxonomy matching results"
    )
    parser.add_argument(
        "reference_csv",
        type=Path,
        help="Path to reference CSV file (ground truth)",
    )
    parser.add_argument(
        "evaluation_csv",
        type=Path,
        help="Path to evaluation CSV file (to compare against reference)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to save output plots (default: directory of evaluation CSV file)",
    )

    args = parser.parse_args()

    # Determine output directory: use evaluation CSV's directory if not specified
    if args.output_dir is None:
        args.output_dir = args.evaluation_csv.parent / "comparison"
    
    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load CSV files
    print(f"Loading reference file: {args.reference_csv}")
    ref_df = load_csv(args.reference_csv)
    validate_columns(ref_df, "reference")

    print(f"Loading evaluation file: {args.evaluation_csv}")
    eval_df = load_csv(args.evaluation_csv)
    validate_columns(eval_df, "evaluation")

    # Validate that L2 and L3 are identical
    print("\nValidating that L2 and L3 columns are identical...")
    ref_merged, eval_df = validate_identical(ref_df, eval_df)
    print("✓ L2 and L3 columns are identical")

    # Compare matched_l2
    print("\nComparing matched_l2...")
    l2_stats = compare_matched_l2(ref_df, eval_df, args.output_dir)
    print(f"✓ Generated matched_l2 confusion matrix")

    # Compare matched_l1 + matched_l2 + matched_l3
    print("\nComparing matched_l1 + matched_l2 + matched_l3...")
    l2_l3_stats = compare_matched_l2_l3(ref_df, eval_df, args.output_dir)
    print(f"✓ Generated matched_l1 + matched_l2 + matched_l3 confusion matrix")

    # Print statistics
    print_statistics(l2_stats, l2_l3_stats)

    # Create summary plot
    print("\nCreating summary plots...")
    create_summary_plot(l2_stats, l2_l3_stats, args.output_dir)
    print(f"✓ Generated summary comparison plot")

    print(f"\n✓ All outputs saved to: {args.output_dir}")
    print("\nGenerated files:")
    print(f"  - matched_l2_confusion_matrix.png")
    print(f"  - matched_l1_l2_l3_confusion_matrix.png")
    print(f"  - summary_comparison.png")


if __name__ == "__main__":
    main()
