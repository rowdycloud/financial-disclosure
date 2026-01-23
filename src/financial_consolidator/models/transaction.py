"""Transaction data models for financial records."""

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


class TransactionType(Enum):
    """Type of transaction (credit or debit)."""

    CREDIT = "credit"  # Money in (positive)
    DEBIT = "debit"  # Money out (negative)


@dataclass
class RawTransaction:
    """Parsed transaction data before normalization.

    This intermediate representation captures what the parser extracts
    from the source file, ready for normalization into a Transaction.
    """

    date: date
    description: str
    amount: Decimal
    transaction_type: TransactionType | None = None
    balance: Decimal | None = None
    source_file: str = ""
    original_category: str | None = None
    check_number: str | None = None
    memo: str | None = None
    raw_data: dict | None = None


@dataclass
class Transaction:
    """Normalized transaction with all computed fields.

    Attributes:
        id: Unique identifier (UUID) for this transaction.
        date: Transaction date in ISO format.
        description: Merchant/payee description (normalized).
        amount: Transaction amount as Decimal (signed: positive=credit, negative=debit).
        transaction_type: Whether this is a credit or debit.
        account_id: Reference to the account this transaction belongs to.
        account_name: Human-readable account name.
        category: Assigned category ID (None if uncategorized).
        subcategory: Assigned subcategory ID.
        is_uncategorized: Explicit flag for filtering uncategorized transactions.
        category_source: How the category was assigned ("rule", "manual", or "default").
        running_balance: Calculated running balance after this transaction.
        source_file: Name of the file this transaction was parsed from.
        source_line: Line number in source file (if applicable).
        raw_data: Original parsed data preserved for audit trail.
        is_duplicate: Whether this transaction is flagged as a duplicate.
        duplicate_of: ID of the original transaction if this is a duplicate.
        is_anomaly: Whether this transaction has anomaly flags.
        anomaly_reasons: List of reasons why this is flagged as anomalous.
    """

    # Core fields (required)
    date: date
    description: str
    amount: Decimal
    transaction_type: TransactionType
    account_id: str
    account_name: str
    source_file: str

    # Generated ID
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Categorization
    category: str | None = None
    subcategory: str | None = None
    is_uncategorized: bool = True
    category_source: str = "default"
    category_rule_id: str | None = None

    # Confidence scoring
    confidence_score: float = 0.0
    confidence_factors: list[str] = field(default_factory=list)
    matched_pattern: str | None = None

    # Computed fields
    running_balance: Decimal | None = None

    # Audit trail
    source_line: int | None = None
    raw_data: RawTransaction | None = None

    # Flags
    is_duplicate: bool = False
    duplicate_of: str | None = None
    is_anomaly: bool = False
    anomaly_reasons: list[str] = field(default_factory=list)

    @property
    def signed_amount(self) -> Decimal:
        """Return the signed amount (already stored with correct sign).

        Returns:
            The amount as stored (negative for debits, positive for credits).
        """
        return self.amount

    @property
    def fingerprint(self) -> str:
        """Generate a stable fingerprint for matching across analysis runs.

        The fingerprint is deterministic based on transaction data,
        allowing the same transaction to be identified across runs.
        Uses date, description (normalized), amount, and account_id.

        Note:
            Transactions with identical date, description, amount, and account
            will have the same fingerprint. This is intentional - such transactions
            are indistinguishable and any correction will apply to all matches.
            Example: Two $5.00 Starbucks purchases on the same day from the same
            account will share a fingerprint, so correcting one corrects both.

        Returns:
            A 16-character hex string uniquely identifying this transaction.
        """
        # Normalize components for consistent hashing
        date_str = self.date.isoformat()
        # Normalize description: lowercase, strip, collapse whitespace
        desc_normalized = re.sub(r"\s+", " ", self.description.lower().strip())
        # Normalize amount: use Decimal directly for full precision
        # Quantize to 2 decimal places for consistency, normalize to handle -0
        amount_normalized = self.amount.quantize(Decimal("0.01"))
        if amount_normalized == 0:
            amount_normalized = Decimal("0.00")  # Normalize -0 to 0
        amount_str = str(amount_normalized)
        account_str = self.account_id

        # Create stable hash
        data = f"{date_str}|{desc_normalized}|{amount_str}|{account_str}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def assign_category(
        self,
        category_id: str,
        source: str,
        subcategory_id: str | None = None,
        rule_id: str | None = None,
        confidence: float = 1.0,
        confidence_factors: list[str] | None = None,
        matched_pattern: str | None = None,
    ) -> None:
        """Assign a category to this transaction.

        Args:
            category_id: The category ID to assign.
            source: How the category was assigned ("rule", "manual", "ai", "default").
            subcategory_id: Optional subcategory ID.
            rule_id: Optional ID of the rule that matched (for rule-based assignment).
            confidence: Confidence score from 0.0 to 1.0 (default 1.0 for manual).
            confidence_factors: List of reasons explaining the confidence score.
            matched_pattern: The keyword or regex pattern that matched.
        """
        self.category = category_id
        self.subcategory = subcategory_id
        self.category_source = source
        self.category_rule_id = rule_id
        self.is_uncategorized = False
        self.confidence_score = confidence
        self.confidence_factors = confidence_factors if confidence_factors else []
        self.matched_pattern = matched_pattern

    def flag_as_duplicate(self, original_id: str) -> None:
        """Mark this transaction as a duplicate of another.

        Args:
            original_id: The ID of the original transaction.
        """
        self.is_duplicate = True
        self.duplicate_of = original_id

    def add_anomaly(self, reason: str) -> None:
        """Add an anomaly flag to this transaction.

        Args:
            reason: Description of why this is anomalous.
        """
        self.is_anomaly = True
        if reason not in self.anomaly_reasons:
            self.anomaly_reasons.append(reason)

    def __repr__(self) -> str:
        return (
            f"Transaction(date={self.date}, "
            f"description={self.description[:30]!r}..., "
            f"amount={self.signed_amount}, "
            f"account={self.account_name})"
        )
