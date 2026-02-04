"""Data loading utilities for taxonomy CSV files."""

import pandas as pd
from pathlib import Path


def load_taxonomy_csv(csv_path: str | Path) -> pd.DataFrame:
    """
    Load and parse taxonomy CSV file.

    Args:
        csv_path: Path to taxonomy CSV file

    Returns:
        DataFrame with columns: CATEGORY L2, CATEGORY L3 at least.
    """
    try:
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip()
        for col in df.columns:
            if "L3" in col.upper():
                df.rename(columns={col: "CATEGORY L3"}, inplace=True)
            if "L2" in col.upper():
                df.rename(columns={col: "CATEGORY L2"}, inplace=True)
            if "L1" in col.upper():
                df.rename(columns={col: "CATEGORY L1"}, inplace=True)

        if "CATEGORY L3" not in df.columns or "CATEGORY L2" not in df.columns:
            raise ValueError(
                "CATEGORY L3 and CATEGORY L2 columns not found in taxonomy CSV file"
            )

        # Keep only CATEGORY L2, CATEGORY L3, CATEGORY L1, and DEFINITION columns if present
        keep_cols = [
            col
            for col in ["CATEGORY L1", "CATEGORY L2", "CATEGORY L3", "DEFINITION"]
            if col in df.columns
        ]
        df = df[keep_cols]

        return df
    except Exception as e:
        print(f"Error loading taxonomy CSV: {e}")
        # TaxonomyServices.aclose()
        raise
