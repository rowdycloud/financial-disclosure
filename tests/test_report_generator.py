"""Tests for report_generator P&L calculation logic."""

from datetime import date
from decimal import Decimal

import pytest

from financial_consolidator.config import Config
from financial_consolidator.models.category import Category, CategoryType
from financial_consolidator.models.transaction import Transaction, TransactionType
from financial_consolidator.processing.report_generator import generate_pl_summary


def create_transaction(
    amount: Decimal,
    category: str | None,
    trans_date: date = date(2025, 1, 15),
    description: str = "Test Transaction",
    account_id: str = "test_account",
    account_name: str = "Test Account",
) -> Transaction:
    """Helper to create a Transaction for testing."""
    return Transaction(
        date=trans_date,
        description=description,
        amount=amount,
        transaction_type=TransactionType.DEBIT if amount < 0 else TransactionType.CREDIT,
        account_id=account_id,
        account_name=account_name,
        source_file="test.csv",
        category=category,
    )


def create_config_with_categories() -> Config:
    """Create a Config with test categories."""
    return Config(
        categories={
            "dining": Category(
                id="dining",
                name="Dining",
                category_type=CategoryType.EXPENSE,
            ),
            "groceries": Category(
                id="groceries",
                name="Groceries",
                category_type=CategoryType.EXPENSE,
            ),
            "salary": Category(
                id="salary",
                name="Salary",
                category_type=CategoryType.INCOME,
            ),
            "refunds": Category(
                id="refunds",
                name="Refunds & Rebates",
                category_type=CategoryType.INCOME,
            ),
            "transfers": Category(
                id="transfers",
                name="Transfers",
                category_type=CategoryType.TRANSFER,
            ),
        }
    )


class TestGeneratePLSummary:
    """Tests for generate_pl_summary function."""

    def test_empty_transactions(self) -> None:
        """Test with empty transaction list."""
        config = create_config_with_categories()
        result = generate_pl_summary([], config)

        assert result.period_start is None
        assert result.period_end is None
        assert result.accounts == []

    def test_normal_expense(self) -> None:
        """Test normal expense (negative amount) is recorded as positive expense total."""
        config = create_config_with_categories()
        transactions = [
            create_transaction(Decimal("-50.00"), "dining"),
        ]

        result = generate_pl_summary(transactions, config)

        assert 2025 in result.expense_by_year
        assert "Dining" in result.expense_by_year[2025]
        assert result.expense_by_year[2025]["Dining"] == Decimal("50.00")

    def test_expense_refund(self) -> None:
        """Test expense refund (positive amount in expense category) reduces total."""
        config = create_config_with_categories()
        transactions = [
            create_transaction(Decimal("-100.00"), "dining"),  # Normal expense
            create_transaction(Decimal("30.00"), "dining"),  # Refund
        ]

        result = generate_pl_summary(transactions, config)

        # Net expense should be 100 - 30 = 70
        assert result.expense_by_year[2025]["Dining"] == Decimal("70.00")

    def test_multiple_expenses_same_category(self) -> None:
        """Test multiple expenses in same category are summed correctly."""
        config = create_config_with_categories()
        transactions = [
            create_transaction(Decimal("-25.00"), "dining"),
            create_transaction(Decimal("-75.00"), "dining"),
            create_transaction(Decimal("-50.00"), "dining"),
        ]

        result = generate_pl_summary(transactions, config)

        # Total should be 25 + 75 + 50 = 150
        assert result.expense_by_year[2025]["Dining"] == Decimal("150.00")

    def test_net_negative_expense(self) -> None:
        """Test case where refunds exceed expenses (net negative)."""
        config = create_config_with_categories()
        transactions = [
            create_transaction(Decimal("-30.00"), "dining"),  # Expense
            create_transaction(Decimal("100.00"), "dining"),  # Large refund
        ]

        result = generate_pl_summary(transactions, config)

        # Net should be 30 - 100 = -70 (more refunds than expenses)
        assert result.expense_by_year[2025]["Dining"] == Decimal("-70.00")

    def test_income_positive_amount(self) -> None:
        """Test income (positive amount) is recorded correctly."""
        config = create_config_with_categories()
        transactions = [
            create_transaction(Decimal("5000.00"), "salary"),
        ]

        result = generate_pl_summary(transactions, config)

        assert 2025 in result.income_by_year
        assert "Salary" in result.income_by_year[2025]
        assert result.income_by_year[2025]["Salary"] == Decimal("5000.00")

    def test_mixed_income_and_expenses(self) -> None:
        """Test P&L with both income and expense transactions."""
        config = create_config_with_categories()
        transactions = [
            create_transaction(Decimal("5000.00"), "salary"),
            create_transaction(Decimal("-100.00"), "dining"),
            create_transaction(Decimal("-200.00"), "groceries"),
            create_transaction(Decimal("50.00"), "refunds"),
        ]

        result = generate_pl_summary(transactions, config)

        # Income
        assert result.income_by_year[2025]["Salary"] == Decimal("5000.00")
        assert result.income_by_year[2025]["Refunds & Rebates"] == Decimal("50.00")

        # Expenses
        assert result.expense_by_year[2025]["Dining"] == Decimal("100.00")
        assert result.expense_by_year[2025]["Groceries"] == Decimal("200.00")

    def test_transfer_transactions(self) -> None:
        """Test transfer transactions are tracked separately."""
        config = create_config_with_categories()
        transactions = [
            create_transaction(Decimal("-500.00"), "transfers"),
            create_transaction(Decimal("500.00"), "transfers"),
        ]

        result = generate_pl_summary(transactions, config)

        assert 2025 in result.transfer_by_year
        # Net transfer: -500 + 500 = 0
        assert result.transfer_by_year[2025]["Transfers"] == Decimal("0.00")

    def test_multi_year_transactions(self) -> None:
        """Test transactions spanning multiple years are grouped correctly."""
        config = create_config_with_categories()
        transactions = [
            create_transaction(Decimal("-100.00"), "dining", date(2024, 6, 15)),
            create_transaction(Decimal("-200.00"), "dining", date(2025, 1, 15)),
            create_transaction(Decimal("-300.00"), "dining", date(2025, 6, 15)),
        ]

        result = generate_pl_summary(transactions, config)

        assert result.expense_by_year[2024]["Dining"] == Decimal("100.00")
        assert result.expense_by_year[2025]["Dining"] == Decimal("500.00")  # 200 + 300
        assert result.years == [2024, 2025]

    def test_uncategorized_transactions_ignored(self) -> None:
        """Test that transactions without categories are not counted."""
        config = create_config_with_categories()
        transactions = [
            create_transaction(Decimal("-100.00"), "dining"),
            create_transaction(Decimal("-500.00"), None),  # Uncategorized
        ]

        result = generate_pl_summary(transactions, config)

        # Only the categorized transaction should be counted
        assert result.expense_by_year[2025]["Dining"] == Decimal("100.00")
        # Uncategorized should not create a category entry
        assert len(result.expense_by_year[2025]) == 1

    def test_unknown_category_ignored(self) -> None:
        """Test that transactions with unknown categories are not counted."""
        config = create_config_with_categories()
        transactions = [
            create_transaction(Decimal("-100.00"), "dining"),
            create_transaction(Decimal("-500.00"), "unknown_category"),
        ]

        result = generate_pl_summary(transactions, config)

        # Only the known category should be counted
        assert result.expense_by_year[2025]["Dining"] == Decimal("100.00")
        assert len(result.expense_by_year[2025]) == 1

    def test_period_dates(self) -> None:
        """Test period start and end dates are calculated correctly."""
        config = create_config_with_categories()
        transactions = [
            create_transaction(Decimal("-50.00"), "dining", date(2025, 3, 15)),
            create_transaction(Decimal("-50.00"), "dining", date(2025, 1, 1)),
            create_transaction(Decimal("-50.00"), "dining", date(2025, 12, 31)),
        ]

        result = generate_pl_summary(transactions, config)

        assert result.period_start == date(2025, 1, 1)
        assert result.period_end == date(2025, 12, 31)

    def test_accounts_list(self) -> None:
        """Test accounts list is correctly populated with unique, sorted names."""
        config = create_config_with_categories()
        # Create transactions with distinct account names (unsorted order)
        transactions = [
            create_transaction(
                Decimal("-50.00"),
                "dining",
                account_id="account_c",
                account_name="Zeta Bank Checking",
            ),
            create_transaction(
                Decimal("-50.00"),
                "dining",
                account_id="account_a",
                account_name="Alpha Credit Card",
            ),
            create_transaction(
                Decimal("-50.00"),
                "dining",
                account_id="account_b",
                account_name="Beta Savings",
            ),
            create_transaction(
                Decimal("-50.00"),
                "dining",
                account_id="account_c",
                account_name="Zeta Bank Checking",  # Duplicate - should be deduplicated
            ),
        ]

        result = generate_pl_summary(transactions, config)

        # Verify uniqueness: 4 transactions but only 3 unique account names
        assert len(result.accounts) == 3
        # Verify sorting: accounts should be alphabetically sorted
        assert result.accounts == [
            "Alpha Credit Card",
            "Beta Savings",
            "Zeta Bank Checking",
        ]
