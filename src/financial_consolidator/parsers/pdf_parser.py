"""PDF parser using pdfplumber library for structured tables."""

from decimal import Decimal
from pathlib import Path

from financial_consolidator.models.transaction import RawTransaction, TransactionType
from financial_consolidator.parsers.base import BaseParser, ParseError
from financial_consolidator.utils.date_utils import parse_date
from financial_consolidator.utils.decimal_utils import parse_amount
from financial_consolidator.utils.logging_config import get_logger

logger = get_logger(__name__)

# Import pdfplumber - handle import error gracefully
try:
    import pdfplumber

    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    pdfplumber = None  # type: ignore

# Maximum number of pages to process to prevent resource exhaustion
MAX_PDF_PAGES = 500


class PDFParser(BaseParser):
    """Parser for PDF financial statements with structured tables.

    Uses pdfplumber to extract tables from PDFs. Only supports PDFs
    with well-structured tables - does not use OCR.
    """

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported file extensions."""
        return [".pdf"]

    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the file.

        Args:
            file_path: Path to the file.

        Returns:
            True if file is a parseable PDF with tables.
        """
        if not PDFPLUMBER_AVAILABLE:
            logger.warning("pdfplumber library not installed, PDF parsing unavailable")
            return False

        if not self._check_extension(file_path):
            return False

        # Try to open and check for tables
        try:
            with pdfplumber.open(file_path) as pdf:
                # Check first few pages for tables
                for page in pdf.pages[:3]:
                    tables = page.extract_tables()
                    if tables:
                        return True
            return False
        except Exception:
            return False

    def parse(self, file_path: Path) -> list[RawTransaction]:
        """Parse a PDF file and return raw transactions.

        Args:
            file_path: Path to the PDF file.

        Returns:
            List of RawTransaction objects.

        Raises:
            ParseError: If parsing fails.
        """
        if not PDFPLUMBER_AVAILABLE:
            raise ParseError("pdfplumber library not installed", file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Parsing PDF file: {file_path.name}")

        transactions = []
        total_skipped = 0
        try:
            with pdfplumber.open(file_path) as pdf:
                # Check page count to prevent resource exhaustion
                if len(pdf.pages) > MAX_PDF_PAGES:
                    raise ParseError(
                        f"PDF has too many pages ({len(pdf.pages)}). "
                        f"Maximum allowed is {MAX_PDF_PAGES}",
                        file_path,
                    )

                for page_num, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables()

                    for table_num, table in enumerate(tables, start=1):
                        if not table:
                            continue

                        page_txns, skipped = self._parse_table(
                            table, file_path.name, page_num, table_num
                        )
                        transactions.extend(page_txns)
                        total_skipped += skipped

        except Exception as e:
            raise ParseError(f"Failed to parse PDF file: {e}", file_path) from e

        logger.info(
            f"Parsed {len(transactions)} transactions from {file_path.name} "
            f"({total_skipped} rows skipped)"
        )
        return transactions

    def detect_institution(self, file_path: Path) -> str | None:
        """Detect financial institution from PDF content.

        Args:
            file_path: Path to the file.

        Returns:
            Institution name if detected.
        """
        if not PDFPLUMBER_AVAILABLE:
            return None

        try:
            with pdfplumber.open(file_path) as pdf:
                # Check first page text for institution names
                if pdf.pages:
                    text = pdf.pages[0].extract_text() or ""
                    return self._detect_institution_from_text(text)
        except Exception as e:
            logger.warning(f"Error detecting institution in {file_path.name}: {e}")
            return None

        return None

    def _detect_institution_from_text(self, text: str) -> str | None:
        """Detect institution from page text.

        Args:
            text: Extracted text from PDF page.

        Returns:
            Institution name if detected.
        """
        text_lower = text.lower()

        institution_patterns = [
            ("chase", "Chase"),
            ("bank of america", "Bank of America"),
            ("wells fargo", "Wells Fargo"),
            ("american express", "American Express"),
            ("capital one", "Capital One"),
            ("discover", "Discover"),
            ("citi", "Citi"),
            ("usaa", "USAA"),
            ("ally bank", "Ally Bank"),
            ("fidelity", "Fidelity"),
            ("schwab", "Charles Schwab"),
            ("vanguard", "Vanguard"),
            ("td ameritrade", "TD Ameritrade"),
            ("e*trade", "E*TRADE"),
        ]

        for pattern, name in institution_patterns:
            if pattern in text_lower:
                return name

        return None

    def _parse_table(
        self,
        table: list[list[str | None]],
        source_file: str,
        page_num: int,
        table_num: int,
    ) -> tuple[list[RawTransaction], int]:
        """Parse a single table from the PDF.

        Args:
            table: Table data as list of rows.
            source_file: Source file name.
            page_num: Page number in PDF.
            table_num: Table number on page.

        Returns:
            Tuple of (transactions, skipped_count).
        """
        if not table or len(table) < 2:
            return [], 0

        transactions: list[RawTransaction] = []

        # Find header row
        header_row_idx = self._find_header_row(table)
        if header_row_idx is None:
            logger.debug(
                f"No header found in table {table_num} on page {page_num}"
            )
            return transactions, 0

        headers = [
            (str(h).lower().strip() if h else "") for h in table[header_row_idx]
        ]

        # Detect column mapping
        mapping = self._detect_column_mapping(headers)
        if mapping is None:
            logger.debug(
                f"Could not detect columns in table {table_num} on page {page_num}"
            )
            return transactions, 0

        # Parse data rows
        skipped_count = 0
        for row_num, row in enumerate(table[header_row_idx + 1 :], start=1):
            if not row or all(cell is None or str(cell).strip() == "" for cell in row):
                continue

            try:
                txn = self._parse_row(
                    row, mapping, source_file, page_num, table_num
                )
                if txn:
                    transactions.append(txn)
                else:
                    skipped_count += 1
                    logger.debug(
                        f"Skipping row {row_num} in table {table_num} "
                        f"on page {page_num}: could not parse transaction"
                    )
            except Exception as e:
                logger.warning(
                    f"Error parsing row {row_num} in table {table_num} "
                    f"on page {page_num}: {e}"
                )
                skipped_count += 1

        return transactions, skipped_count

    def _find_header_row(
        self, table: list[list[str | None]]
    ) -> int | None:
        """Find the header row in a table.

        Args:
            table: Table data.

        Returns:
            Index of header row or None.
        """
        header_keywords = [
            "date", "description", "amount", "debit", "credit", "balance",
            "transaction", "posted", "memo", "check", "withdrawal", "deposit",
        ]

        for i, row in enumerate(table[:5]):  # Check first 5 rows
            if not row:
                continue

            # Count keyword matches
            text_cells = [str(cell).lower() for cell in row if cell]
            keyword_matches = sum(
                1 for cell in text_cells
                if any(kw in cell for kw in header_keywords)
            )

            if keyword_matches >= 2:
                return i

        return None

    def _detect_column_mapping(
        self, headers: list[str]
    ) -> dict[str, int] | None:
        """Detect column mapping from headers.

        Args:
            headers: List of header strings (lowercase).

        Returns:
            Mapping of field name to column index.
        """
        mapping: dict[str, int] = {}

        for i, header in enumerate(headers):
            if not header:
                continue

            # Date column
            if "date" not in mapping and any(
                kw in header for kw in ["date", "posted", "trans"]
            ):
                if "description" not in header:
                    mapping["date"] = i

            # Description column
            if "description" not in mapping and any(
                kw in header
                for kw in ["description", "desc", "memo", "payee", "merchant", "detail"]
            ):
                mapping["description"] = i

            # Amount column
            if "amount" not in mapping and "amount" in header:
                mapping["amount"] = i

            # Debit column
            if "debit" not in mapping and any(
                kw in header for kw in ["debit", "withdrawal", "payment", "charge"]
            ):
                mapping["debit"] = i

            # Credit column
            if "credit" not in mapping and any(
                kw in header for kw in ["credit", "deposit"]
            ):
                mapping["credit"] = i

            # Balance column
            if "balance" not in mapping and any(
                kw in header for kw in ["balance", "bal"]
            ):
                mapping["balance"] = i

        # Validate minimum required columns
        if "date" not in mapping or "description" not in mapping:
            return None

        if "amount" not in mapping and (
            "debit" not in mapping or "credit" not in mapping
        ):
            # Try to detect amount from single column containing numbers
            return None

        return mapping

    def _parse_row(
        self,
        row: list[str | None],
        mapping: dict[str, int],
        source_file: str,
        page_num: int,
        table_num: int,
    ) -> RawTransaction | None:
        """Parse a single row into a RawTransaction.

        Args:
            row: Table row as list of cell values.
            mapping: Column mapping.
            source_file: Source file name.
            page_num: Page number.
            table_num: Table number.

        Returns:
            RawTransaction or None.
        """
        # Get date
        date_str = self._safe_get(row, mapping.get("date"))
        if not date_str:
            return None

        parsed_date = parse_date(date_str)
        if parsed_date is None:
            return None

        # Get description
        description = self._safe_get(row, mapping.get("description"))
        if not description:
            return None
        description = description.strip()

        # Get amount
        amount: Decimal | None = None
        transaction_type: TransactionType | None = None

        if "amount" in mapping:
            amount_str = self._safe_get(row, mapping["amount"])
            if amount_str:
                try:
                    abs_amount, is_negative = parse_amount(amount_str)
                    amount = -abs_amount if is_negative else abs_amount
                    transaction_type = (
                        TransactionType.CREDIT if amount >= 0 else TransactionType.DEBIT
                    )
                except ValueError:
                    pass
        else:
            # Separate debit/credit columns
            debit_str = self._safe_get(row, mapping.get("debit"))
            credit_str = self._safe_get(row, mapping.get("credit"))

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

            if debit_amt is not None and debit_amt != 0:
                amount = -abs(debit_amt)
                transaction_type = TransactionType.DEBIT
            elif credit_amt is not None and credit_amt != 0:
                amount = abs(credit_amt)
                transaction_type = TransactionType.CREDIT

        if amount is None:
            return None

        # Get optional balance
        balance: Decimal | None = None
        if "balance" in mapping:
            balance_str = self._safe_get(row, mapping["balance"])
            if balance_str:
                try:
                    abs_balance, is_neg = parse_amount(balance_str)
                    balance = -abs_balance if is_neg else abs_balance
                except ValueError:
                    pass

        return RawTransaction(
            date=parsed_date,
            description=description,
            amount=amount,
            transaction_type=transaction_type,
            balance=balance,
            source_file=source_file,
            original_category=None,
            check_number=None,
            memo=None,
            raw_data={
                "page_num": page_num,
                "table_num": table_num,
                "row": [str(v) if v else None for v in row],
                "source": "pdf",
            },
        )

    def _safe_get(
        self, row: list[str | None], idx: int | None
    ) -> str | None:
        """Safely get value from row.

        Args:
            row: Table row.
            idx: Column index.

        Returns:
            Value at index or None.
        """
        if idx is None or idx < 0 or idx >= len(row):
            return None
        value = row[idx]
        return str(value).strip() if value else None
