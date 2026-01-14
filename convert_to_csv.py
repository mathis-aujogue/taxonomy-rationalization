#!/usr/bin/env python3
"""Convert Excel files to CSV format."""

import pandas as pd
import sys


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
    files_to_convert = [
        ("our_taxonomy.xlsx", "our_taxonomy.csv"),
        ("their_taxonomy.xlsx", "their_taxonomy.csv"),
    ]

    success_count = 0
    for xlsx_file, csv_file in files_to_convert:
        if convert_xlsx_to_csv(xlsx_file, csv_file):
            success_count += 1

    print(
        f"\nConversion complete: {success_count}/{len(files_to_convert)} files converted successfully"
    )
