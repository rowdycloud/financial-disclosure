"""Transaction data models for financial records."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional
import uuid


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
    transaction_type: Optional[TransactionType] = None
    balance: Optional[Decimal] = None
    source_file: str = ""
    original_category: Optional[str] = None
    check_number: Optional[str] = None
    memo: Optional[str] = None
    raw_data: Optional[dict] = None


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
    category: Optional[str] = None
    subcategory: Optional[str] = None
    is_uncategorized: bool = True
    category_source: str = "default"
    category_rule_id: Optional[str] = None

    # Computed fields
    running_balance: Optional[Decimal] = None

    # Audit trail
    source_line: Optional[int] = None
    raw_data: Optional[RawTransaction] = None

    # Flags
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    is_anomaly: bool = False
    anomaly_reasons: list[str] = field(default_factory=list)

    @property
    def signed_amount(self) -> Decimal:
        """Return the signed amount (already stored with correct sign).

        Returns:
            The amount as stored (negative for debits, positive for credits).
        """
        return self.amount

    def assign_category(
        self,
        category_id: str,
        source: str,
        subcategory_id: Optional[str] = None,
        rule_id: Optional[str] = None,
    ) -> None:
        """Assign a category to this transaction.

        Args:
            category_id: The category ID to assign.
            source: How the category was assigned ("rule", "manual", "default").
            subcategory_id: Optional subcategory ID.
            rule_id: Optional ID of the rule that matched (for rule-based assignment).
        """
        self.category = category_id
        self.subcategory = subcategory_id
        self.category_source = source
        self.category_rule_id = rule_id
        self.is_uncategorized = False

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
