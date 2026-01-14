"""Progress tracking utilities."""

import logging
from typing import Optional
from tqdm import tqdm

logger = logging.getLogger(__name__)


def setup_logging(level: int = logging.INFO) -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def create_progress_bar(total: int, desc: str = "Processing") -> tqdm:
    """
    Create a progress bar for tracking operations.

    Args:
        total: Total number of items to process
        desc: Description for the progress bar

    Returns:
        tqdm progress bar instance
    """
    return tqdm(total=total, desc=desc, unit="item")


def log_progress(current: int, total: int, item_name: str = "") -> None:
    """
    Log progress information.

    Args:
        current: Current item number
        total: Total number of items
        item_name: Optional name of current item
    """
    percentage = (current / total) * 100
    if item_name:
        logger.info(f"Progress: {current}/{total} ({percentage:.1f}%) - {item_name}")
    else:
        logger.info(f"Progress: {current}/{total} ({percentage:.1f}%)")
