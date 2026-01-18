"""OFX/QFX parser using ofxparse library."""

import io
import re
from decimal import Decimal
from pathlib import Path
from typing import Optional

from financial_consolidator.models.transaction import RawTransaction, TransactionType
from financial_consolidator.parsers.base import BaseParser, ParseError
from financial_consolidator.utils.logging_config import get_logger

logger = get_logger(__name__)

# Import ofxparse - handle import error gracefully
try:
    from ofxparse import OfxParser as OFXParseLib
    from ofxparse.ofxparse import OfxParserException

    OFXPARSE_AVAILABLE = True
except ImportError:
    OFXPARSE_AVAILABLE = False
    OFXParseLib = None  # type: ignore
    OfxParserException = Exception  # type: ignore

# Maximum OFX file size to prevent memory exhaustion (50 MB)
MAX_OFX_FILE_SIZE = 50 * 1024 * 1024

# Pattern to match DOCTYPE declarations (for XXE protection)
# This removes DOCTYPE including any SYSTEM or PUBLIC external entity references
_DOCTYPE_PATTERN = re.compile(
    rb'<!DOCTYPE\s+[^>]*>',
    re.IGNORECASE | re.DOTALL
)


class OFXParser(BaseParser):
    """Parser for OFX and QFX financial statement files.

    OFX (Open Financial Exchange) is a standardized format used by
    many financial institutions for exporting transaction data.
    QFX is Intuit's (Quicken) variant of OFX.
    """

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported file extensions."""
        return [".ofx", ".qfx"]

    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the file.

        Args:
            file_path: Path to the file.

        Returns:
            True if file is a parseable OFX/QFX.
        """
        if not OFXPARSE_AVAILABLE:
            logger.warning("ofxparse library not installed, OFX parsing unavailable")
            return False

        if not self._check_extension(file_path):
            return False

        # Quick content check for OFX signature
        lines = self._read_first_lines(file_path, 20)
        content = "\n".join(lines).upper()

        # OFX files typically start with OFXHEADER or contain <OFX> tag
        return "OFXHEADER" in content or "<OFX>" in content

    def parse(self, file_path: Path) -> list[RawTransaction]:
        """Parse an OFX/QFX file and return raw transactions.

        Args:
            file_path: Path to the OFX/QFX file.

        Returns:
            List of RawTransaction objects.

        Raises:
            ParseError: If parsing fails.
        """
        if not OFXPARSE_AVAILABLE:
            raise ParseError("ofxparse library not installed", file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check file size to prevent memory exhaustion
        file_size = file_path.stat().st_size
        if file_size > MAX_OFX_FILE_SIZE:
            raise ParseError(
                f"File too large ({file_size / 1024 / 1024:.1f} MB). "
                f"Maximum allowed is {MAX_OFX_FILE_SIZE / 1024 / 1024:.0f} MB",
                file_path,
            )

        logger.info(f"Parsing OFX file: {file_path.name}")

        transactions = []
        try:
            # Read file content and sanitize to prevent XXE attacks
            with open(file_path, "rb") as f:
                content = f.read()

            # Remove DOCTYPE declarations to prevent XXE attacks
            # DOCTYPE can contain SYSTEM/PUBLIC references to external entities
            sanitized_content = _DOCTYPE_PATTERN.sub(b'', content)

            # Parse the sanitized content
            ofx = OFXParseLib.parse(io.BytesIO(sanitized_content))

            # Get institution info
            institution = self._get_institution_name(ofx)
            if institution:
                logger.info(f"Institution: {institution}")

            # Process all accounts in the OFX file
            if ofx.accounts:
                for account in ofx.accounts:
                    account_id = getattr(account, "account_id", None)
                    account_type = getattr(account, "account_type", None)

                    if hasattr(account, "statement") and account.statement:
                        statement = account.statement
                        if hasattr(statement, "transactions"):
                            for txn in statement.transactions:
                                raw_txn = self._parse_transaction(
                                    txn,
                                    file_path.name,
                                    account_id,
                                    account_type,
                                    institution,
                                )
                                if raw_txn:
                                    transactions.append(raw_txn)

            # Handle single account format (older ofxparse versions)
            elif hasattr(ofx, "account") and ofx.account:
                account = ofx.account
                account_id = getattr(account, "account_id", None)
                account_type = getattr(account, "account_type", None)

                if hasattr(account, "statement") and account.statement:
                    statement = account.statement
                    if hasattr(statement, "transactions"):
                        for txn in statement.transactions:
                            raw_txn = self._parse_transaction(
                                txn,
                                file_path.name,
                                account_id,
                                account_type,
                                institution,
                            )
                            if raw_txn:
                                transactions.append(raw_txn)

        except OfxParserException as e:
            raise ParseError(f"Invalid OFX file format: {e}", file_path)
        except Exception as e:
            raise ParseError(f"Failed to parse OFX file: {e}", file_path)

        logger.info(f"Parsed {len(transactions)} transactions from {file_path.name}")
        return transactions

    def detect_institution(self, file_path: Path) -> Optional[str]:
        """Detect financial institution from OFX content.

        Args:
            file_path: Path to the file.

        Returns:
            Institution name if detected.
        """
        if not OFXPARSE_AVAILABLE:
            return None

        try:
            # Read and sanitize content to prevent XXE attacks
            with open(file_path, "rb") as f:
                content = f.read()
            sanitized_content = _DOCTYPE_PATTERN.sub(b'', content)
            ofx = OFXParseLib.parse(io.BytesIO(sanitized_content))
            return self._get_institution_name(ofx)
        except Exception:
            return None

    def _get_institution_name(self, ofx: object) -> Optional[str]:
        """Extract institution name from OFX object.

        Args:
            ofx: Parsed OFX object.

        Returns:
            Institution name if found.
        """
        # Try to get from signon info
        if hasattr(ofx, "signon") and ofx.signon:
            signon = ofx.signon
            if hasattr(signon, "org") and signon.org:
                return str(signon.org)
            if hasattr(signon, "fid") and signon.fid:
                return self._fid_to_name(str(signon.fid))

        # Try to get from account info
        if hasattr(ofx, "accounts") and ofx.accounts:
            for account in ofx.accounts:
                if hasattr(account, "institution") and account.institution:
                    inst = account.institution
                    if hasattr(inst, "organization") and inst.organization:
                        return str(inst.organization)

        return None

    def _fid_to_name(self, fid: str) -> Optional[str]:
        """Convert financial institution ID to name.

        Args:
            fid: Financial institution ID.

        Returns:
            Institution name if known.
        """
        # Common FID mappings
        known_fids = {
            "5959": "Chase",
            "6805": "Bank of America",
            "10898": "Wells Fargo",
            "3101": "American Express",
            "4705": "Capital One",
            "7801": "Discover",
            "24909": "Citi",
            "1": "USAA",
        }
        return known_fids.get(fid)

    def _parse_transaction(
        self,
        txn: object,
        source_file: str,
        account_id: Optional[str],
        account_type: Optional[str],
        institution: Optional[str],
    ) -> Optional[RawTransaction]:
        """Parse a single OFX transaction.

        Args:
            txn: OFX transaction object.
            source_file: Source file name.
            account_id: Account ID from OFX.
            account_type: Account type from OFX.
            institution: Institution name.

        Returns:
            RawTransaction or None.
        """
        # Get date
        txn_date = getattr(txn, "date", None)
        if txn_date is None:
            return None

        # Convert datetime to date
        if hasattr(txn_date, "date"):
            txn_date = txn_date.date()

        # Get amount
        amount = getattr(txn, "amount", None)
        if amount is None:
            return None

        # Convert to Decimal - handle special values (NaN, Infinity)
        if not isinstance(amount, Decimal):
            try:
                amount = Decimal(str(amount))
            except Exception as e:
                logger.warning(f"Invalid amount value '{amount}' in OFX transaction: {e}")
                return None

        # Determine transaction type
        transaction_type = (
            TransactionType.CREDIT if amount >= 0 else TransactionType.DEBIT
        )

        # Get description - try multiple fields
        description = None
        for field in ["name", "memo", "payee"]:
            value = getattr(txn, field, None)
            if value:
                description = str(value)
                break

        if not description:
            description = "Unknown Transaction"

        # Get optional fields
        memo = getattr(txn, "memo", None)
        if memo:
            memo = str(memo)

        check_number = getattr(txn, "checknum", None)
        if check_number:
            check_number = str(check_number)

        # Get transaction ID (FITID)
        fitid = getattr(txn, "id", None)
        if fitid:
            fitid = str(fitid)

        # Get transaction type code (e.g., DEBIT, CREDIT, CHECK)
        type_code = getattr(txn, "type", None)
        if type_code:
            type_code = str(type_code)

        return RawTransaction(
            date=txn_date,
            description=description.strip(),
            amount=amount,
            transaction_type=transaction_type,
            balance=None,  # OFX doesn't typically include running balance per txn
            source_file=source_file,
            original_category=None,
            check_number=check_number,
            memo=memo.strip() or None if memo else None,
            raw_data={
                "fitid": fitid,
                "type_code": type_code,
                "account_id": account_id,
                "account_type": account_type,
                "institution": institution,
                "source": "ofx",
            },
        )
