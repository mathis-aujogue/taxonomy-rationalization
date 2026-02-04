#!/usr/bin/env python3
"""
Script to count unique values in matched_l2 and matched_l1 columns
from the historical_mapping.csv file.
"""

import pandas as pd
import sys
from pathlib import Path


def count_unique_matches(csv_path: str):
    """Count unique values in matched_l2 and matched_l1 columns."""
    
    # Read the CSV file
    print(f"Reading CSV file: {csv_path}")
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)
    
    # Display available columns
    print(f"\nAvailable columns: {', '.join(df.columns.tolist())}")
    
    # Count unique values in matched_l2
    if 'matched_l2' in df.columns:
        unique_matched_l2 = df['matched_l2'].nunique()
        total_matched_l2 = df['matched_l2'].notna().sum()
        print("\nmatched_l2:")
        print(f"  Unique values: {unique_matched_l2}")
        print(f"  Total non-null values: {total_matched_l2}")
        print(f"  Null values: {df['matched_l2'].isna().sum()}")
        
        # Show the unique values
        print("\n  Unique matched_l2 values:")
        unique_values_l2 = df['matched_l2'].dropna().unique()
        for i, value in enumerate(sorted(unique_values_l2), 1):
            print(f"    {i}. {value}")
    else:
        print("\nmatched_l2 column not found in the CSV file.")
    
    # Count unique values in matched_l1
    if 'matched_l1' in df.columns:
        unique_matched_l1 = df['matched_l1'].nunique()
        total_matched_l1 = df['matched_l1'].notna().sum()
        print("\nmatched_l1:")
        print(f"  Unique values: {unique_matched_l1}")
        print(f"  Total non-null values: {total_matched_l1}")
        print(f"  Null values: {df['matched_l1'].isna().sum()}")
        
        # Show the unique values
        print("\n  Unique matched_l1 values:")
        unique_values_l1 = df['matched_l1'].dropna().unique()
        for i, value in enumerate(sorted(unique_values_l1), 1):
            print(f"    {i}. {value}")
    else:
        print("\nmatched_l1 column not found in the CSV file.")
        print("  Available columns with 'matched' in name:")
        matched_cols = [col for col in df.columns if 'matched' in col.lower()]
        for col in matched_cols:
            print(f"    - {col}")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    if 'matched_l2' in df.columns:
        print(f"matched_l2 unique count: {df['matched_l2'].nunique()}")
    if 'matched_l1' in df.columns:
        print(f"matched_l1 unique count: {df['matched_l1'].nunique()}")


if __name__ == "__main__":
    # Default path
    default_path = Path(__file__).parent.parent / "assets" / "historical_mapping.csv"
    
    # Allow custom path via command line argument
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = str(default_path)
    
    count_unique_matches(csv_path)
