"""Report data generation for financial consolidation output."""

from decimal import Decimal

from financial_consolidator.config import Config
from financial_consolidator.models.report import PLSummary
from financial_consolidator.models.transaction import Transaction


def generate_pl_summary(transactions: list[Transaction], config: Config) -> PLSummary:
    """Generate P&L summary from transactions.

    Single source of truth for P&L calculations - used by both CSV and Excel exporters.

    Args:
        transactions: List of processed transactions.
        config: Application configuration (for category lookups).

    Returns:
        PLSummary with pre-computed totals by category.
    """
    if not transactions:
        return PLSummary(
            period_start=None,
            period_end=None,
            accounts=[],
        )

    # Date range
    period_start = min(t.date for t in transactions)
    period_end = max(t.date for t in transactions)

    # Accounts (sorted, unique)
    accounts = sorted({t.account_name for t in transactions})

    # Category totals
    income_by_cat: dict[str, Decimal] = {}
    expense_by_cat: dict[str, Decimal] = {}
    transfer_by_cat: dict[str, Decimal] = {}

    for t in transactions:
        if not t.category:
            continue

        cat = config.categories.get(t.category)
        if not cat:
            continue

        cat_name = cat.name
        cat_type = cat.category_type.value if cat.category_type else None

        if cat_type == "income":
            income_by_cat[cat_name] = income_by_cat.get(cat_name, Decimal("0")) + t.amount
        elif cat_type == "expense":
            expense_by_cat[cat_name] = expense_by_cat.get(cat_name, Decimal("0")) + abs(t.amount)
        elif cat_type == "transfer":
            transfer_by_cat[cat_name] = transfer_by_cat.get(cat_name, Decimal("0")) + t.amount

    return PLSummary(
        period_start=period_start,
        period_end=period_end,
        accounts=accounts,
        income_by_category=income_by_cat,
        expense_by_category=expense_by_cat,
        transfer_by_category=transfer_by_cat,
    )
