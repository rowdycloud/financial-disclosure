"""Report data models for financial consolidation output."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class PLSummary:
    """Pre-computed P&L summary data.

    Single source of truth for P&L calculations - used by both CSV and Excel exporters.

    Attributes:
        period_start: First transaction date in the report (None if no data).
        period_end: Last transaction date in the report (None if no data).
        accounts: List of account names included.
        income_by_category: Income amounts keyed by category name.
        expense_by_category: Expense amounts (positive) keyed by category name.
        transfer_by_category: Transfer amounts keyed by category name.
    """

    period_start: date | None
    period_end: date | None
    accounts: list[str]
    income_by_category: dict[str, Decimal] = field(default_factory=dict)
    expense_by_category: dict[str, Decimal] = field(default_factory=dict)
    transfer_by_category: dict[str, Decimal] = field(default_factory=dict)

    @property
    def total_income(self) -> Decimal:
        """Sum of all income categories."""
        return sum(self.income_by_category.values(), Decimal("0"))

    @property
    def total_expenses(self) -> Decimal:
        """Sum of all expense categories."""
        return sum(self.expense_by_category.values(), Decimal("0"))

    @property
    def total_transfers(self) -> Decimal:
        """Sum of all transfer categories."""
        return sum(self.transfer_by_category.values(), Decimal("0"))

    @property
    def net_income(self) -> Decimal:
        """Total income minus total expenses."""
        return self.total_income - self.total_expenses

    @property
    def period_display(self) -> str:
        """Formatted date range string."""
        if self.period_start is None or self.period_end is None:
            return "No data"
        return f"{self.period_start.strftime('%Y-%m-%d')} to {self.period_end.strftime('%Y-%m-%d')}"

    @property
    def accounts_display(self) -> str:
        """Comma-separated list of account names."""
        return ", ".join(self.accounts)
