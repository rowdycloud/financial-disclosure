"""Duplicate transaction detection."""

from collections import defaultdict
from decimal import Decimal
from difflib import SequenceMatcher

from financial_consolidator.config import Config
from financial_consolidator.models.transaction import Transaction
from financial_consolidator.utils.logging_config import get_logger

logger = get_logger(__name__)


class Deduplicator:
    """Detects and flags duplicate transactions.

    Duplicates are identified using:
    - Same amount
    - Same or similar description
    - Date within tolerance (for clearing delays)
    - Same account

    Duplicates are flagged but not removed (for audit purposes).

    Note: This class is NOT thread-safe. Methods mutate transactions in place
    and should only be called from a single thread.
    """

    def __init__(
        self,
        config: Config,
        similarity_threshold: float = 0.9,
        date_tolerance_days: int = 1,
    ):
        """Initialize deduplicator.

        Args:
            config: Application configuration.
            similarity_threshold: Description similarity threshold (0-1).
            date_tolerance_days: Max date difference to consider duplicates.
        """
        self.config = config
        self.similarity_threshold = similarity_threshold
        self.date_tolerance_days = date_tolerance_days

    def find_duplicates(
        self, transactions: list[Transaction]
    ) -> list[Transaction]:
        """Find and flag duplicate transactions.

        Args:
            transactions: List of transactions to check.

        Returns:
            Same list with duplicates flagged (modified in place).
        """
        if not transactions:
            return transactions

        # Group transactions by account and approximate key
        # Key: (account_id, amount) -> list of transactions
        by_key: dict[tuple[str, Decimal], list[Transaction]] = defaultdict(list)

        for txn in transactions:
            key = (txn.account_id, txn.amount)
            by_key[key].append(txn)

        duplicate_count = 0

        # Check each group for duplicates
        for _key, group in by_key.items():
            if len(group) < 2:
                continue

            # Sort by stable fields for cross-run consistency
            # Use source_file and source_line as tie-breakers instead of UUID (which changes between runs)
            # This ensures the same transaction is flagged as duplicate vs original consistently
            sorted_group = sorted(
                group, key=lambda t: (t.date, t.description, t.amount, t.source_file, t.source_line or 0)
            )

            # Compare each pair
            for i, txn1 in enumerate(sorted_group):
                if txn1.is_duplicate:
                    continue

                for txn2 in sorted_group[i + 1 :]:
                    # Don't skip txn2 if already flagged - we still compare to find all duplicates
                    # But only flag it if not already flagged
                    if self._are_duplicates(txn1, txn2) and not txn2.is_duplicate:
                        # Flag txn2 as duplicate of txn1 (txn2 is always later due to sorting)
                        txn2.flag_as_duplicate(txn1.id)
                        duplicate_count += 1

        logger.info(f"Found {duplicate_count} duplicate transactions")
        return transactions

    def _are_duplicates(self, txn1: Transaction, txn2: Transaction) -> bool:
        """Check if two transactions are duplicates.

        Args:
            txn1: First transaction.
            txn2: Second transaction.

        Returns:
            True if transactions are duplicates.
        """
        # Must be same account
        if txn1.account_id != txn2.account_id:
            return False

        # If both have check numbers and they differ, not duplicates
        # (legitimate recurring payments often have different check numbers)
        check1 = txn1.raw_data.check_number if txn1.raw_data else None
        check2 = txn2.raw_data.check_number if txn2.raw_data else None
        if check1 and check2 and check1 != check2:
            return False

        # Must have same amount
        # TODO: Consider adding configurable tolerance for near-duplicates with penny differences
        # (e.g., config option for amount_tolerance_cents). Currently requires exact match.
        if txn1.amount != txn2.amount:
            return False

        # Check date tolerance
        date_diff = abs((txn1.date - txn2.date).days)
        if date_diff > self.date_tolerance_days:
            return False

        # Check description similarity
        similarity = self._description_similarity(
            txn1.description, txn2.description
        )

        # For same-day transactions, require higher similarity to reduce
        # false positives for legitimate recurring payments (e.g., multiple
        # subscription charges, utility payments on the same day)
        same_day_threshold = 0.95
        if txn1.date == txn2.date:
            if similarity < same_day_threshold:
                return False
        elif similarity < self.similarity_threshold:
            return False

        # Check if from different source files (common duplicate scenario)
        if txn1.source_file != txn2.source_file:
            logger.debug(
                f"Potential cross-file duplicate: "
                f"{txn1.description} ({txn1.source_file}) vs "
                f"{txn2.description} ({txn2.source_file})"
            )

        return True

    def _description_similarity(self, desc1: str, desc2: str) -> float:
        """Calculate similarity between two descriptions.

        Args:
            desc1: First description.
            desc2: Second description.

        Returns:
            Similarity score between 0 and 1.
        """
        # Normalize descriptions
        desc1 = desc1.lower().strip()
        desc2 = desc2.lower().strip()

        # Exact match
        if desc1 == desc2:
            return 1.0

        # Use SequenceMatcher for fuzzy matching
        return SequenceMatcher(None, desc1, desc2).ratio()

    def get_duplicate_groups(
        self, transactions: list[Transaction]
    ) -> list[list[Transaction]]:
        """Group transactions that are duplicates of each other.

        Groups are formed by (account_id, amount) key. Within each key group,
        all transactions that have at least one duplicate relationship with
        another transaction are collected together. This achieves transitive
        grouping: if A↔B and B↔C are duplicates, all three will be in the
        same group even if A↔C don't meet duplicate criteria directly.
        This is intentional for manual review purposes.

        Note: Transactions must share the same account_id AND amount to be
        grouped together. Transactions with different amounts are never grouped.

        Args:
            transactions: List of transactions.

        Returns:
            List of groups, where each group contains duplicate transactions.
        """
        # Build duplicate groups using union-find-like approach
        groups: dict[str, list[Transaction]] = {}

        # Group by key
        by_key: dict[tuple[str, Decimal], list[Transaction]] = defaultdict(list)
        for txn in transactions:
            key = (txn.account_id, txn.amount)
            by_key[key].append(txn)

        for key, group in by_key.items():
            if len(group) < 2:
                continue

            # Find all pairs that are duplicates
            duplicate_ids: set[str] = set()
            for i, txn1 in enumerate(group):
                for txn2 in group[i + 1 :]:
                    if self._are_duplicates(txn1, txn2):
                        duplicate_ids.add(txn1.id)
                        duplicate_ids.add(txn2.id)

            if duplicate_ids:
                # Create group for these duplicates
                group_id = f"dup_{key[0]}_{key[1]}"
                groups[group_id] = [
                    txn for txn in group if txn.id in duplicate_ids
                ]

        return list(groups.values())


def find_duplicates(
    transactions: list[Transaction],
    config: Config,
) -> list[Transaction]:
    """Convenience function to find and flag duplicates.

    Args:
        transactions: List of transactions to check.
        config: Application configuration.

    Returns:
        Same list with duplicates flagged.
    """
    deduplicator = Deduplicator(config)
    return deduplicator.find_duplicates(transactions)
