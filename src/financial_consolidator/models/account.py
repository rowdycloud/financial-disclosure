"""Account data model for financial accounts."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional


class AccountType(Enum):
    """Type of financial account."""

    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    LOAN = "loan"
    INVESTMENT = "investment"
    CRYPTO = "crypto"
    CASH = "cash"
    OTHER = "other"


@dataclass
class Account:
    """Represents a financial account.

    Attributes:
        id: Unique identifier for this account.
        name: Human-readable account name (e.g., "Chase Checking ****1234").
        account_type: Type of account (checking, credit_card, etc.).
        institution: Name of the financial institution (e.g., "Chase", "Bank of America").
        account_number_masked: Last 4 digits of account number for identification.
        opening_balance: Starting balance for running balance calculation.
        opening_balance_date: Date of the opening balance.
        current_balance: Calculated current balance (updated during processing).
        source_file_patterns: Glob patterns to match source files to this account.
        display_order: Order for displaying accounts in output.
        is_active: Whether this account should be processed.
    """

    id: str
    name: str
    account_type: AccountType

    # Optional identifiers
    institution: Optional[str] = None
    account_number_masked: Optional[str] = None

    # Balance tracking
    opening_balance: Decimal = field(default_factory=lambda: Decimal("0"))
    opening_balance_date: Optional[date] = None
    current_balance: Optional[Decimal] = None

    # File mappings
    source_file_patterns: list[str] = field(default_factory=list)

    # Display settings
    display_order: int = 0
    is_active: bool = True

    def matches_file(self, filename: str) -> bool:
        """Check if a filename matches any of this account's patterns.

        Uses simple glob-style matching with * wildcards.

        Args:
            filename: The filename to check.

        Returns:
            True if the filename matches any pattern.
        """
        import fnmatch

        filename_lower = filename.lower()
        for pattern in self.source_file_patterns:
            if fnmatch.fnmatch(filename_lower, pattern.lower()):
                return True
        return False

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Account":
        """Create an Account from a dictionary (e.g., from YAML config).

        Args:
            data: Dictionary containing account data.

        Returns:
            A new Account instance.
        """
        account_type_str = str(data.get("type", "other"))
        try:
            account_type = AccountType(account_type_str)
        except ValueError:
            account_type = AccountType.OTHER

        opening_balance = Decimal("0")
        if "opening_balance" in data:
            opening_balance = Decimal(str(data["opening_balance"]))

        opening_balance_date = None
        if "opening_balance_date" in data:
            date_str = str(data["opening_balance_date"])
            opening_balance_date = date.fromisoformat(date_str)

        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            account_type=account_type,
            institution=str(data["institution"]) if "institution" in data else None,
            account_number_masked=(
                str(data["account_number_masked"]) if "account_number_masked" in data else None
            ),
            opening_balance=opening_balance,
            opening_balance_date=opening_balance_date,
            source_file_patterns=list(data.get("source_file_patterns", [])),  # type: ignore[arg-type]
            display_order=int(data.get("display_order", 0)),  # type: ignore[arg-type]
            is_active=bool(data.get("is_active", True)),
        )

    def __repr__(self) -> str:
        return f"Account(id={self.id!r}, name={self.name!r}, type={self.account_type.value})"
