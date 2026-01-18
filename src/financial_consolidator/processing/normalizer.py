"""Transaction normalizer for converting raw transactions to normalized format."""

import uuid
from decimal import Decimal
from pathlib import Path
from typing import Optional

from financial_consolidator.config import Config
from financial_consolidator.models.account import Account
from financial_consolidator.models.transaction import RawTransaction, Transaction
from financial_consolidator.utils.date_utils import is_date_in_range
from financial_consolidator.utils.logging_config import get_logger

logger = get_logger(__name__)


class Normalizer:
    """Normalizes raw transactions into the standard Transaction format.

    The normalizer:
    - Generates unique IDs for transactions
    - Associates transactions with accounts
    - Filters by date range
    - Ensures amounts are properly signed
    """

    def __init__(self, config: Config):
        """Initialize normalizer with configuration.

        Args:
            config: Application configuration.
        """
        self.config = config

    def normalize(
        self,
        raw_transactions: list[RawTransaction],
        account: Account,
    ) -> list[Transaction]:
        """Normalize a list of raw transactions.

        Args:
            raw_transactions: Raw transactions from a parser.
            account: Account these transactions belong to.

        Returns:
            List of normalized Transaction objects.
        """
        transactions = []

        for raw_txn in raw_transactions:
            txn = self._normalize_transaction(raw_txn, account)
            if txn is not None:
                transactions.append(txn)

        logger.info(
            f"Normalized {len(transactions)}/{len(raw_transactions)} "
            f"transactions for account {account.name}"
        )

        return transactions

    def normalize_all(
        self,
        raw_transactions_by_file: dict[str, list[RawTransaction]],
    ) -> list[Transaction]:
        """Normalize transactions from multiple files.

        Args:
            raw_transactions_by_file: Dict mapping filename to raw transactions.

        Returns:
            List of all normalized transactions.
        """
        all_transactions: list[Transaction] = []

        for filename, raw_txns in raw_transactions_by_file.items():
            # Get account for this file
            account = self.config.get_account_for_file(filename)

            if account is None:
                logger.warning(f"No account mapping for file: {filename}")
                continue

            transactions = self.normalize(raw_txns, account)
            all_transactions.extend(transactions)

        logger.info(f"Total normalized transactions: {len(all_transactions)}")
        return all_transactions

    def _normalize_transaction(
        self,
        raw: RawTransaction,
        account: Account,
    ) -> Optional[Transaction]:
        """Normalize a single raw transaction.

        Args:
            raw: Raw transaction.
            account: Account for this transaction.

        Returns:
            Normalized Transaction or None if filtered out.
        """
        # Filter by date range
        if self.config.start_date or self.config.end_date:
            if not is_date_in_range(
                raw.date, self.config.start_date, self.config.end_date
            ):
                return None

        # Generate unique ID
        transaction_id = str(uuid.uuid4())

        # Ensure amount is properly signed
        amount = raw.amount
        if amount is None:
            logger.warning(f"Transaction has no amount: {raw.description}")
            return None

        # Determine transaction type from amount sign or raw data
        from financial_consolidator.models.transaction import TransactionType
        transaction_type = raw.transaction_type
        if transaction_type is None:
            transaction_type = TransactionType.CREDIT if amount >= 0 else TransactionType.DEBIT

        # Create normalized transaction
        return Transaction(
            id=transaction_id,
            date=raw.date,
            description=raw.description,
            amount=amount,
            transaction_type=transaction_type,
            account_id=account.id,
            account_name=account.name,
            source_file=raw.source_file,
            raw_data=raw,
            # These will be set by later processing stages
            category=None,
            subcategory=None,
            is_uncategorized=True,
            category_source="default",
            running_balance=raw.balance,  # May be updated by balance calculator
            is_duplicate=False,
            is_anomaly=False,
            anomaly_reasons=[],
        )


def normalize_transactions(
    raw_transactions: list[RawTransaction],
    account: Account,
    config: Config,
) -> list[Transaction]:
    """Convenience function to normalize transactions.

    Args:
        raw_transactions: Raw transactions from a parser.
        account: Account these transactions belong to.
        config: Application configuration.

    Returns:
        List of normalized Transaction objects.
    """
    normalizer = Normalizer(config)
    return normalizer.normalize(raw_transactions, account)
