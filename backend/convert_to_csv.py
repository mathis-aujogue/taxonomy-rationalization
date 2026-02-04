#!/usr/bin/env python3
"""Convert Excel files to CSV format."""

import pandas as pd
import sys
import argparse

def convert_xlsx_to_csv(xlsx_file, csv_file):
    """Convert an Excel file to CSV format."""
    try:
        # Read the Excel file
        df = pd.read_excel(xlsx_file)

        # Write to CSV
        df.to_csv(csv_file, index=False)

        print(f"✓ Converted {xlsx_file} to {csv_file}")
        print(f"  Rows: {len(df)}, Columns: {len(df.columns)}")
        return True
    except Exception as e:
        print(f"✗ Error converting {xlsx_file}: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Excel files to CSV format.")
    parser.add_argument("xlsx_file", type=str, help="Path to the Excel file to convert.")
    args = parser.parse_args()
    if convert_xlsx_to_csv(args.xlsx_file, f"{args.xlsx_file}.csv"):
        print(f"\nConversion complete: {args.xlsx_file} converted successfully")
    else:
        print(f"\nConversion failed: {args.xlsx_file}")
