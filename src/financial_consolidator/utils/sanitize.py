"""Sanitization utilities for safe output generation."""

from typing import Optional


# Characters that trigger formula execution in spreadsheet applications
# when they appear at the start of a cell value
# Includes | for DDE (Dynamic Data Exchange) attack prevention
_FORMULA_CHARS = ("=", "+", "-", "@", "\t", "\r", "\n", "|")


def sanitize_for_csv(value: Optional[str]) -> Optional[str]:
    """Sanitize a string value for safe CSV/Excel output.

    Prevents formula injection by prefixing values that start with
    formula-triggering characters (=, +, -, @, tab, etc.) with a
    single quote. This is the standard mitigation recommended by
    OWASP for CSV injection.

    Args:
        value: String value to sanitize, or None.

    Returns:
        Sanitized string, or None if input was None.
    """
    if value is None:
        return None

    if not value:
        return value

    # Check if value starts with a formula-triggering character
    if value.startswith(_FORMULA_CHARS):
        # Prefix with single quote to prevent formula execution
        return "'" + value

    return value
