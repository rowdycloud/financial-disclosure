"""Date parsing and normalization utilities."""

import re
from datetime import date, datetime

# Common date format patterns
#
# IMPORTANT - Date Format Ambiguity:
# Slash-separated dates (e.g., "03/04/2024") are always interpreted as US format (MM/DD/YYYY).
# For European dates (DD/MM/YYYY), use period-separated format (03.04.2024) or ISO format (2024-04-03).
#
# Two-digit years use Python's strptime pivot:
# - Years 00-68 map to 2000-2068
# - Years 69-99 map to 1969-1999
# For historical dates before 1969, use 4-digit years (e.g., "01/15/1968").
#
DATE_PATTERNS = [
    # ISO format (most common, try first) - PREFERRED for unambiguous dates
    (r"^(\d{4})-(\d{1,2})-(\d{1,2})$", "%Y-%m-%d"),
    # US formats (MM/DD/YYYY) - slash-separated always interpreted as US
    (r"^(\d{1,2})/(\d{1,2})/(\d{4})$", "%m/%d/%Y"),
    (r"^(\d{1,2})/(\d{1,2})/(\d{2})$", "%m/%d/%y"),
    (r"^(\d{1,2})-(\d{1,2})-(\d{4})$", "%m-%d-%Y"),
    (r"^(\d{1,2})-(\d{1,2})-(\d{2})$", "%m-%d-%y"),
    # European formats (DD.MM.YYYY) - period-separated for European dates
    (r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", "%d.%m.%Y"),
    (r"^(\d{1,2})\.(\d{1,2})\.(\d{2})$", "%d.%m.%y"),
    # Text month formats
    (r"^(\d{1,2})-(\w{3})-(\d{4})$", "%d-%b-%Y"),
    (r"^(\d{1,2})-(\w{3})-(\d{2})$", "%d-%b-%y"),
    (r"^(\w{3})\s+(\d{1,2}),?\s+(\d{4})$", "%b %d, %Y"),
    (r"^(\w+)\s+(\d{1,2}),?\s+(\d{4})$", "%B %d, %Y"),
    # Compact formats
    (r"^(\d{8})$", "%Y%m%d"),
    (r"^(\d{4})(\d{2})(\d{2})$", "%Y%m%d"),
]

# Compiled regex patterns for efficiency
COMPILED_PATTERNS = [(re.compile(pattern), fmt) for pattern, fmt in DATE_PATTERNS]


def parse_date(raw_date: str) -> date:
    """Parse a raw date string into a date object.

    Handles various formats:
    - ISO: 2024-01-15
    - US: 01/15/2024, 1/15/24, 01-15-2024
    - European: 15.01.2024
    - Text: 15-Jan-2024, Jan 15, 2024, January 15, 2024
    - Compact: 20240115

    Args:
        raw_date: The raw date string to parse.

    Returns:
        Parsed date object.

    Raises:
        ValueError: If the date cannot be parsed.
    """
    if not raw_date:
        raise ValueError("Empty date string")

    date_str = raw_date.strip()
    if not date_str:
        raise ValueError("Empty date string after stripping whitespace")

    # Try each pattern
    for pattern, fmt in COMPILED_PATTERNS:
        if pattern.match(date_str):
            try:
                parsed = datetime.strptime(date_str, fmt)
                return parsed.date()
            except ValueError:
                # Pattern matched but format didn't work, try next
                continue

    # Try generic parsing as fallback
    try:
        # Handle datetime objects (e.g., from ofxparse)
        if isinstance(raw_date, datetime):
            return raw_date.date()

        # Try ISO format parsing
        return date.fromisoformat(date_str)
    except (ValueError, AttributeError):
        pass

    raise ValueError(f"Cannot parse date: '{raw_date}'")


def format_date(d: date, fmt: str = "%Y-%m-%d") -> str:
    """Format a date object as a string.

    Args:
        d: Date to format.
        fmt: Format string (default ISO format).

    Returns:
        Formatted date string.
    """
    return d.strftime(fmt)


def date_to_iso(d: date) -> str:
    """Convert a date to ISO 8601 format (YYYY-MM-DD).

    Args:
        d: Date to convert.

    Returns:
        ISO format date string.
    """
    return d.isoformat()


def safe_parse_date(raw_date: str | None, default: date | None = None) -> date | None:
    """Safely parse a date string, returning default on failure.

    Args:
        raw_date: The raw date string to parse.
        default: Default value if parsing fails.

    Returns:
        Parsed date or default.
    """
    if not raw_date:
        return default

    try:
        return parse_date(raw_date)
    except ValueError:
        return default


def get_month_year(d: date) -> tuple[int, int]:
    """Get month and year from a date.

    Args:
        d: Date to extract from.

    Returns:
        Tuple of (year, month).
    """
    return (d.year, d.month)


def get_quarter(d: date) -> int:
    """Get the quarter (1-4) for a date.

    Args:
        d: Date to get quarter for.

    Returns:
        Quarter number (1-4).
    """
    return (d.month - 1) // 3 + 1


def is_date_in_range(
    d: date,
    start_date: date | None = None,
    end_date: date | None = None,
) -> bool:
    """Check if a date is within a range.

    Args:
        d: Date to check.
        start_date: Start of range (inclusive). None means no lower bound.
        end_date: End of range (inclusive). None means no upper bound.

    Returns:
        True if date is within range.
    """
    if start_date is not None and d < start_date:
        return False
    if end_date is not None and d > end_date:
        return False
    return True


def generate_month_range(start: date, end: date) -> list[tuple[int, int]]:
    """Generate a list of (year, month) tuples for a date range.

    Args:
        start: Start date.
        end: End date.

    Returns:
        List of (year, month) tuples covering the range.
    """
    months = []
    current_year = start.year
    current_month = start.month

    while (current_year, current_month) <= (end.year, end.month):
        months.append((current_year, current_month))
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    return months
