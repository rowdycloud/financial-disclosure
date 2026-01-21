"""Report data generation for financial consolidation output."""

from decimal import Decimal

from financial_consolidator.config import Config
from financial_consolidator.models.report import PLSummary
from financial_consolidator.models.transaction import Transaction


def generate_pl_summary(transactions: list[Transaction], config: Config) -> PLSummary:
    """Generate P&L summary from transactions with year-by-year breakdown.

    Single source of truth for P&L calculations - used by both CSV and Excel exporters.

    Args:
        transactions: List of processed transactions.
        config: Application configuration (for category lookups).

    Returns:
        PLSummary with pre-computed totals by year and category.
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

    # Collect all years
    years = sorted({t.date.year for t in transactions})

    # Year-keyed category totals
    income_by_year: dict[int, dict[str, Decimal]] = {}
    expense_by_year: dict[int, dict[str, Decimal]] = {}
    transfer_by_year: dict[int, dict[str, Decimal]] = {}

    for t in transactions:
        if not t.category:
            continue

        cat = config.categories.get(t.category)
        if not cat:
            continue

        year = t.date.year
        cat_name = cat.name
        cat_type = cat.category_type.value if cat.category_type else None

        if cat_type == "income":
            year_cats = income_by_year.setdefault(year, {})
            year_cats[cat_name] = year_cats.get(cat_name, Decimal("0")) + t.amount
        elif cat_type == "expense":
            year_cats = expense_by_year.setdefault(year, {})
            year_cats[cat_name] = year_cats.get(cat_name, Decimal("0")) + abs(t.amount)
        elif cat_type == "transfer":
            year_cats = transfer_by_year.setdefault(year, {})
            year_cats[cat_name] = year_cats.get(cat_name, Decimal("0")) + t.amount

    return PLSummary(
        period_start=period_start,
        period_end=period_end,
        accounts=accounts,
        years=years,
        income_by_year=income_by_year,
        expense_by_year=expense_by_year,
        transfer_by_year=transfer_by_year,
    )
