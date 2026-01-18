"""CSV parser with multi-bank format detection."""

import csv
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional

from financial_consolidator.models.transaction import RawTransaction, TransactionType
from financial_consolidator.parsers.base import BaseParser, ParseError
from financial_consolidator.utils.date_utils import parse_date
from financial_consolidator.utils.decimal_utils import parse_amount
from financial_consolidator.utils.logging_config import get_logger

logger = get_logger(__name__)

# Maximum CSV file size to prevent memory exhaustion (50 MB)
MAX_CSV_FILE_SIZE = 50 * 1024 * 1024

# Maximum number of rows to prevent memory exhaustion from many small rows
MAX_CSV_ROWS = 500_000


@dataclass
class ColumnMapping:
    """Mapping of CSV columns to transaction fields."""

    date_col: int
    description_col: int
    amount_col: Optional[int] = None  # Single amount column (signed)
    debit_col: Optional[int] = None  # Separate debit column
    credit_col: Optional[int] = None  # Separate credit column
    balance_col: Optional[int] = None
    category_col: Optional[int] = None
    type_col: Optional[int] = None  # Transaction type column
    check_number_col: Optional[int] = None
    memo_col: Optional[int] = None


@dataclass
class CSVFormat:
    """Detected CSV format information."""

    delimiter: str
    has_header: bool
    skip_rows: int
    column_mapping: ColumnMapping
    institution: Optional[str] = None
    date_format: Optional[str] = None


# Known bank column patterns for auto-detection
# Each pattern maps header names (lowercase) to column roles
KNOWN_FORMATS = {
    "chase": {
        "headers": ["transaction date", "post date", "description", "category", "type", "amount"],
        "mapping": lambda cols: ColumnMapping(
            date_col=cols.get("transaction date", cols.get("posting date", 0)),
            description_col=cols.get("description", 1),
            amount_col=cols.get("amount"),
            category_col=cols.get("category"),
            type_col=cols.get("type"),
        ),
        "institution": "Chase",
    },
    "bank_of_america": {
        "headers": ["date", "description", "amount", "running bal."],
        "mapping": lambda cols: ColumnMapping(
            date_col=cols.get("date", 0),
            description_col=cols.get("description", 1),
            amount_col=cols.get("amount", 2),
            balance_col=cols.get("running bal."),
        ),
        "institution": "Bank of America",
    },
    "wells_fargo": {
        "headers": ["date", "amount", "description"],
        "mapping": lambda cols: ColumnMapping(
            date_col=cols.get("date", 0),
            description_col=cols.get("description", 2),
            amount_col=cols.get("amount", 1),
        ),
        "institution": "Wells Fargo",
    },
    "amex": {
        "headers": ["date", "description", "amount"],
        "mapping": lambda cols: ColumnMapping(
            date_col=cols.get("date", 0),
            description_col=cols.get("description", 1),
            amount_col=cols.get("amount", 2),
        ),
        "institution": "American Express",
    },
    "capital_one": {
        "headers": ["transaction date", "posted date", "card no.", "description", "category", "debit", "credit"],
        "mapping": lambda cols: ColumnMapping(
            date_col=cols.get("transaction date", cols.get("posted date", 0)),
            description_col=cols.get("description", 3),
            debit_col=cols.get("debit"),
            credit_col=cols.get("credit"),
            category_col=cols.get("category"),
        ),
        "institution": "Capital One",
    },
    "discover": {
        "headers": ["trans. date", "post date", "description", "amount", "category"],
        "mapping": lambda cols: ColumnMapping(
            date_col=cols.get("trans. date", cols.get("post date", 0)),
            description_col=cols.get("description", 2),
            amount_col=cols.get("amount", 3),
            category_col=cols.get("category"),
        ),
        "institution": "Discover",
    },
    "citi": {
        "headers": ["date", "description", "debit", "credit"],
        "mapping": lambda cols: ColumnMapping(
            date_col=cols.get("date", 0),
            description_col=cols.get("description", 1),
            debit_col=cols.get("debit"),
            credit_col=cols.get("credit"),
        ),
        "institution": "Citi",
    },
    "usaa": {
        "headers": ["date", "description", "original description", "category", "amount"],
        "mapping": lambda cols: ColumnMapping(
            date_col=cols.get("date", 0),
            description_col=cols.get("original description", cols.get("description", 1)),
            amount_col=cols.get("amount"),
            category_col=cols.get("category"),
        ),
        "institution": "USAA",
    },
    "ally": {
        "headers": ["date", "time", "amount", "type", "description"],
        "mapping": lambda cols: ColumnMapping(
            date_col=cols.get("date", 0),
            description_col=cols.get("description", 4),
            amount_col=cols.get("amount", 2),
            type_col=cols.get("type"),
        ),
        "institution": "Ally Bank",
    },
    "generic_debit_credit": {
        "headers": ["date", "description", "debit", "credit"],
        "mapping": lambda cols: ColumnMapping(
            date_col=cols.get("date", 0),
            description_col=cols.get("description", 1),
            debit_col=cols.get("debit"),
            credit_col=cols.get("credit"),
        ),
        "institution": None,
    },
    "generic_amount": {
        "headers": ["date", "description", "amount"],
        "mapping": lambda cols: ColumnMapping(
            date_col=cols.get("date", 0),
            description_col=cols.get("description", 1),
            amount_col=cols.get("amount", 2),
        ),
        "institution": None,
    },
}


class CSVParser(BaseParser):
    """Parser for CSV financial statement files."""

    def __init__(self, strict: bool = False):
        """Initialize CSV parser.

        Args:
            strict: If True, raise ParseError on row-level parse failures.
                   If False, log warnings and skip unparseable rows.
        """
        self.strict = strict

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported file extensions."""
        return [".csv", ".tsv", ".txt"]

    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the file.

        Args:
            file_path: Path to the file.

        Returns:
            True if file is a parseable CSV.
        """
        if not self._check_extension(file_path):
            return False

        # Try to detect format
        try:
            fmt = self._detect_format(file_path)
            return fmt is not None
        except Exception as e:
            logger.debug(f"Format detection failed for {file_path.name}: {e}")
            return False

    def parse(self, file_path: Path) -> list[RawTransaction]:
        """Parse a CSV file and return raw transactions.

        Args:
            file_path: Path to the CSV file.

        Returns:
            List of RawTransaction objects.

        Raises:
            ParseError: If parsing fails.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check file size to prevent memory exhaustion
        file_size = file_path.stat().st_size
        if file_size > MAX_CSV_FILE_SIZE:
            raise ParseError(
                f"File too large ({file_size / 1024 / 1024:.1f} MB). "
                f"Maximum allowed is {MAX_CSV_FILE_SIZE / 1024 / 1024:.0f} MB",
                file_path,
            )

        fmt = self._detect_format(file_path)
        if fmt is None:
            raise ParseError(f"Could not detect CSV format for {file_path}", file_path)

        logger.info(
            f"Parsing {file_path.name} as {fmt.institution or 'generic'} format "
            f"(delimiter={repr(fmt.delimiter)})"
        )

        transactions = []
        skipped_count = 0
        try:
            with open(file_path, encoding="utf-8", errors="replace", newline="") as f:
                # Skip initial rows if needed
                for _ in range(fmt.skip_rows):
                    next(f)

                reader = csv.reader(f, delimiter=fmt.delimiter)

                # Skip header row if present
                if fmt.has_header:
                    next(reader)

                for row_num, row in enumerate(reader, start=1):
                    # Limit total rows to prevent memory exhaustion
                    if row_num > MAX_CSV_ROWS:
                        raise ParseError(
                            f"File exceeds maximum row limit ({MAX_CSV_ROWS:,} rows). "
                            f"Split file into smaller chunks.",
                            file_path,
                        )

                    if not row or all(cell.strip() == "" for cell in row):
                        continue

                    try:
                        txn = self._parse_row(row, fmt.column_mapping, file_path.name)
                        if txn:
                            transactions.append(txn)
                        else:
                            skipped_count += 1
                            if self.strict:
                                raise ParseError(
                                    f"Row {row_num}: Could not parse transaction",
                                    file_path,
                                )
                    except ParseError:
                        raise  # Re-raise ParseError from strict mode
                    except Exception as e:
                        if self.strict:
                            raise ParseError(
                                f"Row {row_num}: {e}", file_path
                            )
                        logger.warning(
                            f"Error parsing row {row_num} in {file_path.name}: {e}"
                        )
                        skipped_count += 1

        except ParseError:
            raise  # Preserve original ParseError with context
        except Exception as e:
            raise ParseError(f"Failed to parse CSV file: {e}", file_path)

        logger.info(f"Parsed {len(transactions)} transactions from {file_path.name} ({skipped_count} rows skipped)")
        if skipped_count > 0:
            logger.warning(f"{skipped_count} rows could not be parsed in {file_path.name} - use -vv for details")
        return transactions

    def detect_institution(self, file_path: Path) -> Optional[str]:
        """Detect financial institution from CSV content.

        Args:
            file_path: Path to the file.

        Returns:
            Institution name if detected.
        """
        fmt = self._detect_format(file_path)
        return fmt.institution if fmt else None

    def _detect_format(self, file_path: Path) -> Optional[CSVFormat]:
        """Detect CSV format from file content.

        Args:
            file_path: Path to the CSV file.

        Returns:
            CSVFormat if detection succeeds, None otherwise.
        """
        lines = self._read_first_lines(file_path, 20)
        if not lines:
            return None

        # Detect delimiter
        delimiter = self._detect_delimiter(lines)

        # Find header row and skip rows
        header_row_idx = 0
        skip_rows = 0

        for i, line in enumerate(lines):
            if self._looks_like_header(line, delimiter):
                header_row_idx = i
                skip_rows = i
                break
            # Skip lines that look like metadata (account info, dates, etc.)
            if self._is_metadata_line(line):
                continue

        # Parse header - check bounds to prevent IndexError
        if header_row_idx >= len(lines):
            logger.debug(f"Header row index {header_row_idx} exceeds available lines {len(lines)}")
            return None
        headers = self._parse_header(lines[header_row_idx], delimiter)
        if not headers:
            return None

        # Try to match known formats
        col_indices = {h.lower().strip(): i for i, h in enumerate(headers)}

        for format_name, format_info in KNOWN_FORMATS.items():
            known_headers = format_info["headers"]
            match_count = sum(1 for h in known_headers if h in col_indices)

            # Require at least date, description, and amount/debit+credit
            if match_count >= 3:
                mapping = format_info["mapping"](col_indices)

                # Validate we have required columns
                if mapping.date_col is None or mapping.description_col is None:
                    continue
                if mapping.amount_col is None and (
                    mapping.debit_col is None or mapping.credit_col is None
                ):
                    continue

                return CSVFormat(
                    delimiter=delimiter,
                    has_header=True,
                    skip_rows=skip_rows,
                    column_mapping=mapping,
                    institution=format_info.get("institution"),
                )

        # Fallback: try to auto-detect columns
        mapping = self._auto_detect_columns(headers, col_indices)
        if mapping:
            return CSVFormat(
                delimiter=delimiter,
                has_header=True,
                skip_rows=skip_rows,
                column_mapping=mapping,
                institution=None,
            )

        return None

    def _detect_delimiter(self, lines: list[str]) -> str:
        """Detect CSV delimiter from content.

        Args:
            lines: First few lines of file.

        Returns:
            Detected delimiter character.
        """
        # First try Python's csv.Sniffer which handles quoted fields correctly
        sample = "\n".join(lines[:10])
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',\t;|')
            return dialect.delimiter
        except csv.Error:
            pass

        # Fallback to simple counting (less accurate with quoted fields)
        delimiters = [",", "\t", ";", "|"]
        delimiter_counts: dict[str, list[int]] = {d: [] for d in delimiters}

        for line in lines[:10]:
            for d in delimiters:
                count = line.count(d)
                delimiter_counts[d].append(count)

        # Choose delimiter with most consistent non-zero count
        best_delimiter = ","
        best_score = 0

        for d, counts in delimiter_counts.items():
            non_zero = [c for c in counts if c > 0]
            if not non_zero:
                continue

            # Score: consistency (low variance) + frequency
            avg = sum(non_zero) / len(non_zero)
            if avg > best_score and len(non_zero) > len(counts) / 2:
                best_score = avg
                best_delimiter = d

        return best_delimiter

    def _looks_like_header(self, line: str, delimiter: str) -> bool:
        """Check if line looks like a CSV header.

        Args:
            line: Line to check.
            delimiter: CSV delimiter.

        Returns:
            True if line looks like a header.
        """
        parts = line.split(delimiter)
        if len(parts) < 2:
            return False

        # Headers typically:
        # - Contain common keywords (date, description, amount, etc.)
        # - Are mostly text (not numbers)
        header_keywords = [
            "date", "description", "amount", "debit", "credit", "balance",
            "type", "category", "memo", "check", "transaction", "posted",
        ]

        text_count = sum(
            1 for p in parts
            if p.strip() and not re.match(r"^[\d\$\-\.,\(\)]+$", p.strip())
        )
        keyword_count = sum(
            1 for p in parts
            if any(kw in p.lower() for kw in header_keywords)
        )

        return text_count >= len(parts) / 2 and keyword_count >= 2

    def _is_metadata_line(self, line: str) -> bool:
        """Check if line is metadata (not data or header).

        Args:
            line: Line to check.

        Returns:
            True if line is metadata.
        """
        line = line.strip().lower()
        metadata_patterns = [
            r"^account\s*(number|#|:)",
            r"^statement\s*(period|date)",
            r"^as\s*of",
            r"^downloaded",
            r"^generated",
            r"^\s*$",  # Empty line
        ]
        return any(re.match(p, line) for p in metadata_patterns)

    def _parse_header(self, line: str, delimiter: str) -> list[str]:
        """Parse header line into column names.

        Args:
            line: Header line.
            delimiter: CSV delimiter.

        Returns:
            List of column names.
        """
        try:
            reader = csv.reader([line], delimiter=delimiter)
            return next(reader)
        except Exception:
            return line.split(delimiter)

    def _auto_detect_columns(
        self, headers: list[str], col_indices: dict[str, int]
    ) -> Optional[ColumnMapping]:
        """Auto-detect column mapping from header names.

        Args:
            headers: List of header names.
            col_indices: Mapping of header name to column index.

        Returns:
            ColumnMapping if detection succeeds.
        """
        date_col = None
        desc_col = None
        amount_col = None
        debit_col = None
        credit_col = None
        balance_col = None

        for header, idx in col_indices.items():
            header_lower = header.lower()

            # Date column
            if date_col is None and any(
                kw in header_lower for kw in ["date", "posted", "trans"]
            ):
                if "description" not in header_lower:
                    date_col = idx

            # Description column
            if desc_col is None and any(
                kw in header_lower
                for kw in ["description", "desc", "memo", "payee", "merchant"]
            ):
                desc_col = idx

            # Amount column (single)
            if amount_col is None and "amount" in header_lower:
                amount_col = idx

            # Debit column
            if debit_col is None and any(
                kw in header_lower for kw in ["debit", "withdrawal", "payment"]
            ):
                debit_col = idx

            # Credit column
            if credit_col is None and any(
                kw in header_lower for kw in ["credit", "deposit"]
            ):
                credit_col = idx

            # Balance column
            if balance_col is None and any(
                kw in header_lower for kw in ["balance", "bal", "running"]
            ):
                balance_col = idx

        # Validate minimum required columns
        if date_col is None or desc_col is None:
            return None

        if amount_col is None and (debit_col is None or credit_col is None):
            return None

        return ColumnMapping(
            date_col=date_col,
            description_col=desc_col,
            amount_col=amount_col,
            debit_col=debit_col,
            credit_col=credit_col,
            balance_col=balance_col,
        )

    def _parse_row(
        self, row: list[str], mapping: ColumnMapping, source_file: str
    ) -> Optional[RawTransaction]:
        """Parse a single CSV row into a RawTransaction.

        Args:
            row: CSV row as list of values.
            mapping: Column mapping.
            source_file: Source file name.

        Returns:
            RawTransaction or None if row should be skipped.
        """
        # Get date
        date_str = self._safe_get(row, mapping.date_col, "")
        if not date_str:
            logger.debug(f"Skipping row in {source_file}: empty date field")
            return None

        try:
            parsed_date = parse_date(date_str)
        except ValueError:
            logger.debug(f"Skipping row in {source_file}: unparseable date '{date_str}'")
            return None
        if parsed_date is None:
            logger.debug(f"Skipping row in {source_file}: unparseable date '{date_str}'")
            return None

        # Get description
        description = self._safe_get(row, mapping.description_col, "")
        if not description:
            logger.debug(f"Skipping row in {source_file}: empty description")
            return None

        # Get amount
        amount: Optional[Decimal] = None
        transaction_type: Optional[TransactionType] = None

        if mapping.amount_col is not None:
            # Single amount column (signed)
            amount_str = self._safe_get(row, mapping.amount_col, "")
            if amount_str:
                try:
                    abs_amount, is_negative = parse_amount(amount_str)
                    amount = -abs_amount if is_negative else abs_amount
                    # Determine type from sign
                    transaction_type = (
                        TransactionType.CREDIT if amount >= 0 else TransactionType.DEBIT
                    )
                except ValueError:
                    amount = None
        elif mapping.debit_col is not None or mapping.credit_col is not None:
            # Separate debit/credit columns
            debit_str = self._safe_get(row, mapping.debit_col, "") if mapping.debit_col is not None else ""
            credit_str = self._safe_get(row, mapping.credit_col, "") if mapping.credit_col is not None else ""

            debit_amt = None
            credit_amt = None
            try:
                if debit_str:
                    abs_debit, _ = parse_amount(debit_str)
                    debit_amt = abs_debit
            except ValueError:
                pass
            try:
                if credit_str:
                    abs_credit, _ = parse_amount(credit_str)
                    credit_amt = abs_credit
            except ValueError:
                pass

            # Warn if both debit and credit columns have non-zero values
            if debit_amt is not None and credit_amt is not None and debit_amt != 0 and credit_amt != 0:
                logger.warning(
                    f"Row in {source_file} has both debit ({debit_amt}) and credit ({credit_amt}); using debit"
                )

            # Allow zero-amount transactions (fee reversals, balance adjustments)
            if debit_amt is not None:
                amount = -abs(debit_amt) if debit_amt != 0 else Decimal("0")
                transaction_type = TransactionType.DEBIT
            elif credit_amt is not None:
                amount = abs(credit_amt) if credit_amt != 0 else Decimal("0")
                transaction_type = TransactionType.CREDIT

        if amount is None:
            logger.debug(f"Skipping row in {source_file}: could not parse amount")
            return None

        # Get optional fields
        balance: Optional[Decimal] = None
        if mapping.balance_col is not None:
            balance_str = self._safe_get(row, mapping.balance_col, "")
            if balance_str:
                try:
                    abs_balance, is_neg = parse_amount(balance_str)
                    balance = -abs_balance if is_neg else abs_balance
                except ValueError:
                    pass

        category = None
        if mapping.category_col is not None:
            category = self._safe_get(row, mapping.category_col, "")

        memo = None
        if mapping.memo_col is not None:
            memo = self._safe_get(row, mapping.memo_col, "")

        check_number = None
        if mapping.check_number_col is not None:
            check_number = self._safe_get(row, mapping.check_number_col, "")

        return RawTransaction(
            date=parsed_date,
            description=description.strip(),
            amount=amount,
            transaction_type=transaction_type,
            balance=balance,
            source_file=source_file,
            original_category=category.strip() if category else None,
            check_number=check_number.strip() if check_number else None,
            memo=memo.strip() if memo else None,
            raw_data={
                "row": row,
                "source": "csv",
            },
        )

    def _safe_get(self, row: list[str], idx: Optional[int], default: str) -> str:
        """Safely get value from row.

        Args:
            row: CSV row.
            idx: Column index.
            default: Default value.

        Returns:
            Value at index or default.
        """
        if idx is None or idx < 0 or idx >= len(row):
            return default
        return row[idx].strip()
