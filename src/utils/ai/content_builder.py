"""Utility functions for building taxonomy content strings."""

from typing import Dict


def build_page_content(fields: Dict[str, str]) -> str:
    """
    Build page content string from taxonomy fields.
    Formats as "L1 > L2 > L3: definition" with empty parts omitted.
    Note: Lower number = lower precision. L1 is most general, L3 is most specific/precise.

    Args:
        l1: Level 1 category (most general/lowest precision)
        l2: Level 2 category (middle precision)
        l3: Level 3 category (most specific/highest precision)
        definition: Category definition

    Returns:
        Formatted page content string

    Examples:
        >>> build_page_content({"l1": "Property", "l2": "Facility", "l3": "Cleaning"}, "")
        "Property > Facility > Cleaning"
        >>> build_page_content({"l1": "Banking", "l2": "Loans", "definition": "Banking loan services"}, "")
        "Banking > Loans: Banking loan services"
        >>> build_page_content({"l3": "Cleaning"}, "")
        "Cleaning"
    """
    parts = []
    if fields.get("l1"):
        parts.append(fields["l1"])
    if fields.get("l2"):
        parts.append(fields["l2"])
    if fields.get("l3"):
        parts.append(fields["l3"])

    content = " > ".join(parts)

    if fields.get("definition"):
        content = f"{content}: {fields['definition']}"

    return content
