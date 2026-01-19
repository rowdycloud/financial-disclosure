"""Running balance calculator for transactions."""

from collections import defaultdict
from decimal import Decimal

from financial_consolidator.config import Config
from financial_consolidator.models.transaction import Transaction
from financial_consolidator.utils.logging_config import get_logger

logger = get_logger(__name__)


class BalanceCalculator:
    """Calculates running balances for transactions.

    Running balances are calculated per account, using the account's
    opening balance if available.
    """

    def __init__(self, config: Config):
        """Initialize balance calculator.

        Args:
            config: Application configuration with account info.
        """
        self.config = config

    def calculate_balances(
        self, transactions: list[Transaction]
    ) -> list[Transaction]:
        """Calculate running balances for all transactions.

        Args:
            transactions: List of transactions.

        Returns:
            Same list with running balances set (modified in place).
        """
        # Group transactions by account
        by_account: dict[str, list[Transaction]] = defaultdict(list)
        for txn in transactions:
            by_account[txn.account_id].append(txn)

        # Calculate balances for each account
        for account_id, account_txns in by_account.items():
            self._calculate_account_balances(account_id, account_txns)

        return transactions

    def _calculate_account_balances(
        self,
        account_id: str,
        transactions: list[Transaction],
    ) -> None:
        """Calculate running balances for a single account.

        Args:
            account_id: Account ID.
            transactions: Transactions for this account (modified in place).
        """
        # Get opening balance from account config
        account = self.config.accounts.get(account_id)
        opening_balance = Decimal("0")

        if account and account.opening_balance is not None:
            opening_balance = account.opening_balance

        # Sort by stable fields for cross-run consistency
        # Use sorted() to avoid modifying the caller's list order
        # source_file and source_line provide stable ordering instead of UUID which changes between runs
        sorted_transactions = sorted(
            transactions, key=lambda t: (t.date, t.description, t.amount, t.source_file, t.source_line or 0)
        )

        # Calculate running balance, excluding transactions before opening_balance_date
        running_balance = opening_balance
        opening_date = account.opening_balance_date if account else None

        for txn in sorted_transactions:
            if opening_date is not None and txn.date < opening_date:
                # Explicitly mark as excluded from balance calculation
                txn.running_balance = None
            else:
                running_balance += txn.amount
                txn.running_balance = running_balance

        logger.debug(
            f"Calculated balances for {account_id}: "
            f"{len(transactions)} transactions, "
            f"opening={opening_balance}, closing={running_balance}"
        )

    def get_account_summary(
        self, transactions: list[Transaction]
    ) -> dict[str, dict[str, Decimal]]:
        """Get summary of balances by account.

        Args:
            transactions: List of transactions.

        Returns:
            Dict mapping account_id to summary dict with:
            - opening_balance
            - total_credits
            - total_debits
            - closing_balance
        """
        by_account: dict[str, list[Transaction]] = defaultdict(list)
        for txn in transactions:
            by_account[txn.account_id].append(txn)

        summaries: dict[str, dict[str, Decimal]] = {}

        for account_id, account_txns in by_account.items():
            account = self.config.accounts.get(account_id)
            opening = (
                account.opening_balance
                if account and account.opening_balance is not None
                else Decimal("0")
            )

            credits = sum(
                txn.amount for txn in account_txns if txn.amount > 0
            )
            debits = sum(
                txn.amount for txn in account_txns if txn.amount < 0
            )

            # Get closing balance from last transaction
            sorted_txns = sorted(
                account_txns, key=lambda t: (t.date, t.description, t.amount, t.id)
            )
            closing = (
                sorted_txns[-1].running_balance
                if sorted_txns and sorted_txns[-1].running_balance is not None
                else opening + credits + debits
            )

            summaries[account_id] = {
                "opening_balance": opening,
                "total_credits": credits,
                "total_debits": debits,
                "closing_balance": closing,
            }

        return summaries


def calculate_balances(
    transactions: list[Transaction],
    config: Config,
) -> list[Transaction]:
    """Convenience function to calculate running balances.

    Args:
        transactions: List of transactions.
        config: Application configuration.

    Returns:
        Same list with running balances set.
    """
    calculator = BalanceCalculator(config)
    return calculator.calculate_balances(transactions)
