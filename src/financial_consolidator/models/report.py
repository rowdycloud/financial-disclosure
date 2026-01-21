"""Report data models for financial consolidation output."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class PLSummary:
    """Pre-computed P&L summary data with year-by-year breakdown.

    Single source of truth for P&L calculations - used by both CSV and Excel exporters.

    Attributes:
        period_start: First transaction date in the report (None if no data).
        period_end: Last transaction date in the report (None if no data).
        accounts: List of account names included.
        years: Sorted list of years with data.
        income_by_year: Income amounts keyed by year, then category name.
        expense_by_year: Expense amounts (positive) keyed by year, then category name.
        transfer_by_year: Transfer amounts keyed by year, then category name.
    """

    period_start: date | None
    period_end: date | None
    accounts: list[str]
    years: list[int] = field(default_factory=list)
    income_by_year: dict[int, dict[str, Decimal]] = field(default_factory=dict)
    expense_by_year: dict[int, dict[str, Decimal]] = field(default_factory=dict)
    transfer_by_year: dict[int, dict[str, Decimal]] = field(default_factory=dict)

    @property
    def total_income(self) -> Decimal:
        """Sum of all income categories across all years."""
        return sum(
            (sum(cats.values(), Decimal("0")) for cats in self.income_by_year.values()),
            Decimal("0"),
        )

    @property
    def total_expenses(self) -> Decimal:
        """Sum of all expense categories across all years."""
        return sum(
            (sum(cats.values(), Decimal("0")) for cats in self.expense_by_year.values()),
            Decimal("0"),
        )

    @property
    def total_transfers(self) -> Decimal:
        """Sum of all transfer categories across all years."""
        return sum(
            (sum(cats.values(), Decimal("0")) for cats in self.transfer_by_year.values()),
            Decimal("0"),
        )

    @property
    def net_income(self) -> Decimal:
        """Total income minus total expenses."""
        return self.total_income - self.total_expenses

    def income_for_year(self, year: int) -> Decimal:
        """Sum of all income categories for a specific year."""
        return sum(self.income_by_year.get(year, {}).values(), Decimal("0"))

    def expenses_for_year(self, year: int) -> Decimal:
        """Sum of all expense categories for a specific year."""
        return sum(self.expense_by_year.get(year, {}).values(), Decimal("0"))

    def transfers_for_year(self, year: int) -> Decimal:
        """Sum of all transfer categories for a specific year."""
        return sum(self.transfer_by_year.get(year, {}).values(), Decimal("0"))

    def net_income_for_year(self, year: int) -> Decimal:
        """Net income for a specific year."""
        return self.income_for_year(year) - self.expenses_for_year(year)

    @property
    def all_income_categories(self) -> list[str]:
        """Sorted list of all income category names across all years."""
        return sorted({
            cat for year_cats in self.income_by_year.values() for cat in year_cats
        })

    @property
    def all_expense_categories(self) -> list[str]:
        """Sorted list of all expense category names across all years."""
        return sorted({
            cat for year_cats in self.expense_by_year.values() for cat in year_cats
        })

    @property
    def all_transfer_categories(self) -> list[str]:
        """Sorted list of all transfer category names across all years."""
        return sorted({
            cat for year_cats in self.transfer_by_year.values() for cat in year_cats
        })

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
