"""Decimal utilities for financial calculations.

All monetary calculations must use Decimal to avoid floating-point precision issues.
"""

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional


# Currency symbols to strip
CURRENCY_SYMBOLS = {"$", "€", "£", "¥", "₹", "₽", "₩", "₿"}

# Regex for parentheses-enclosed negatives: ($1,234.56) or (1234.56)
PARENS_NEGATIVE_PATTERN = re.compile(r"^\s*\(\s*([^)]+)\s*\)\s*$")

# Regex for trailing DR/CR indicators
DR_CR_PATTERN = re.compile(r"\s*(DR|CR|D|C)\s*$", re.IGNORECASE)


def parse_amount(raw_amount: str, locale: str = "US") -> tuple[Decimal, bool]:
    """Parse a raw amount string into a Decimal.

    Handles various formats:
    - Standard: 1234.56, -1234.56
    - With currency: $1,234.56, -$1,234.56
    - Parentheses for negative: ($1,234.56), (1234.56)
    - European format: 1.234,56 (thousand separator is period)
    - DR/CR suffix: 1234.56 DR, 1234.56 CR

    IMPORTANT - Locale-dependent parsing:
    Ambiguous formats like "1,234" are interpreted based on locale:
    - US (default): "1,234" = 1234 (comma is thousands separator)
    - EU: "1,234" = 1.234 (comma is decimal separator)

    Args:
        raw_amount: The raw amount string to parse.
        locale: Locale hint for ambiguous formats ("US" or "EU"). Default: "US".

    Returns:
        Tuple of (absolute amount as Decimal, is_negative flag).

    Raises:
        ValueError: If the amount cannot be parsed.
    """
    if not raw_amount:
        raise ValueError("Empty amount string")

    original = raw_amount
    amount_str = raw_amount.strip()
    is_negative = False

    # Check for parentheses notation: ($1,234.56) or (1234.56)
    parens_match = PARENS_NEGATIVE_PATTERN.match(amount_str)
    if parens_match:
        amount_str = parens_match.group(1).strip()
        is_negative = True

    # Check for leading minus sign
    if amount_str.startswith("-"):
        is_negative = True
        amount_str = amount_str[1:].strip()

    # Check for DR/CR suffix
    dr_cr_match = DR_CR_PATTERN.search(amount_str)
    if dr_cr_match:
        indicator = dr_cr_match.group(1).upper()
        if indicator in ("DR", "D"):
            is_negative = True
        amount_str = DR_CR_PATTERN.sub("", amount_str).strip()

    # Remove currency symbols
    for symbol in CURRENCY_SYMBOLS:
        amount_str = amount_str.replace(symbol, "")
    amount_str = amount_str.strip()

    # Handle European format (1.234,56 -> 1234.56)
    # Heuristic: if there's a comma followed by 1-4 digits at end,
    # and periods elsewhere, it's European format
    if "," in amount_str and "." in amount_str:
        # Check if comma is the decimal separator (European format)
        # Match 1-4 digits after comma to handle various decimal precisions
        if re.search(r",\d{1,4}$", amount_str) and "." in amount_str[:-3]:
            # European: 1.234,56 -> 1234.56
            amount_str = amount_str.replace(".", "").replace(",", ".")
        else:
            # US format: 1,234.56 -> 1234.56
            amount_str = amount_str.replace(",", "")
    elif "," in amount_str:
        # Only comma present - could be US thousands or European decimal
        # Use locale hint to resolve ambiguity
        if re.search(r",\d{1,2}$", amount_str):
            # Likely European decimal: 1234,56 -> 1234.56
            amount_str = amount_str.replace(",", ".")
        elif re.search(r",\d{3,4}$", amount_str) and locale == "EU":
            # EU locale: treat "1,234" as 1.234 (European decimal with 3-4 places)
            amount_str = amount_str.replace(",", ".")
        else:
            # Default (US): treat comma as thousands separator: 1,234 -> 1234
            amount_str = amount_str.replace(",", "")

    # Remove any remaining whitespace
    amount_str = amount_str.replace(" ", "")

    try:
        amount = Decimal(amount_str)
    except InvalidOperation as e:
        raise ValueError(f"Cannot parse amount '{original}': {e}") from e

    return abs(amount), is_negative


def format_currency(
    amount: Decimal,
    decimal_places: int = 2,
    include_sign: bool = True,
) -> str:
    """Format a Decimal amount for display.

    Args:
        amount: The amount to format.
        decimal_places: Number of decimal places (default 2).
        include_sign: Whether to include sign for negative amounts.

    Returns:
        Formatted string like "-1234.56" or "1234.56".
    """
    # Round to specified decimal places
    quantize_str = "0." + "0" * decimal_places
    rounded = amount.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)

    # Format with sign
    if include_sign and rounded < 0:
        return str(rounded)
    return str(abs(rounded))


def safe_decimal(value: Optional[object], default: Decimal = Decimal("0")) -> Decimal:
    """Safely convert a value to Decimal.

    Args:
        value: Value to convert (string, int, float, or None).
        default: Default value if conversion fails.

    Returns:
        Decimal value or default.
    """
    if value is None:
        return default

    try:
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, str)):
            return Decimal(str(value))
        if isinstance(value, float):
            # Convert float to string first for precision
            return Decimal(str(value))
        return default
    except (InvalidOperation, ValueError):
        return default


def sum_amounts(amounts: list[Decimal]) -> Decimal:
    """Sum a list of Decimal amounts.

    Args:
        amounts: List of Decimal amounts.

    Returns:
        Sum as Decimal.
    """
    total = Decimal("0")
    for amount in amounts:
        total += amount
    return total
