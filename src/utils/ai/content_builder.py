"""Utility functions for building taxonomy content strings."""

from typing import Dict


def build_page_content(fields: Dict[str, str]) -> str:
    """
    Build page content string from taxonomy fields.
    Formats as "L1 > L2 > L3: definition" with empty parts omitted.

    Args:
        l1: Level 1 category
        l2: Level 2 category
        l3: Level 3 category
        definition: Category definition

    Returns:
        Formatted page content string

    Examples:
        >>> build_page_content("Property", "Facility", "Cleaning", "")
        "Property > Facility > Cleaning"
        >>> build_page_content("", "Banking", "Loans", "Banking loan services")
        "Banking > Loans: Banking loan services"
        >>> build_page_content("", "", "Cleaning", "")
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
