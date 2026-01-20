"""Transaction categorizer using rules and manual overrides."""


from financial_consolidator.config import Config
from financial_consolidator.models.category import CategoryRule, ManualOverride, MatchResult
from financial_consolidator.models.transaction import Transaction
from financial_consolidator.utils.date_utils import date_to_iso
from financial_consolidator.utils.logging_config import get_logger

logger = get_logger(__name__)


class Categorizer:
    """Categorizes transactions using rules and manual overrides.

    The categorizer applies:
    1. Manual overrides (highest priority)
    2. Rule-based categorization (by priority order)
    3. Marks uncategorized if no match
    """

    def __init__(self, config: Config):
        """Initialize categorizer with configuration.

        Args:
            config: Application configuration with rules and overrides.
        """
        self.config = config

    def categorize(self, transactions: list[Transaction]) -> list[Transaction]:
        """Categorize a list of transactions.

        Args:
            transactions: List of transactions to categorize.

        Returns:
            Same list with categories assigned (modified in place).
        """
        categorized_count = 0
        uncategorized_count = 0

        for txn in transactions:
            self._categorize_transaction(txn)
            if txn.is_uncategorized:
                uncategorized_count += 1
            else:
                categorized_count += 1

        logger.info(
            f"Categorized {categorized_count} transactions, "
            f"{uncategorized_count} uncategorized"
        )

        return transactions

    def _categorize_transaction(self, txn: Transaction) -> None:
        """Categorize a single transaction.

        Args:
            txn: Transaction to categorize (modified in place).
        """
        # Try manual override first (highest priority)
        override = self._find_matching_override(txn)
        if override:
            txn.assign_category(
                category_id=override.category_id,
                source="manual",
                subcategory_id=override.subcategory_id,
                confidence=1.0,
                confidence_factors=["Manual override"],
            )
            return

        # Try rule-based categorization
        rule, match_result = self._find_matching_rule(txn)
        if rule and match_result:
            # Get category info
            category = self.config.categories.get(rule.category_id)
            subcategory_id = None
            if category and category.parent_id:
                # This is a subcategory, the parent is the main category
                subcategory_id = rule.category_id
                # Find parent category name
                parent_cat = self.config.categories.get(category.parent_id)
                if parent_cat:
                    txn.assign_category(
                        category_id=category.parent_id,
                        source="rule",
                        subcategory_id=subcategory_id,
                        rule_id=rule.id,
                        confidence=match_result.confidence,
                        confidence_factors=match_result.factors,
                        matched_pattern=match_result.matched_value,
                    )
                else:
                    txn.assign_category(
                        category_id=rule.category_id,
                        source="rule",
                        rule_id=rule.id,
                        confidence=match_result.confidence,
                        confidence_factors=match_result.factors,
                        matched_pattern=match_result.matched_value,
                    )
            else:
                txn.assign_category(
                    category_id=rule.category_id,
                    source="rule",
                    rule_id=rule.id,
                    confidence=match_result.confidence,
                    confidence_factors=match_result.factors,
                    matched_pattern=match_result.matched_value,
                )
            return

        # No match - remains uncategorized
        # is_uncategorized is already True by default

    def _find_matching_override(self, txn: Transaction) -> ManualOverride | None:
        """Find a matching manual override for a transaction.

        Args:
            txn: Transaction to match.

        Returns:
            Matching ManualOverride or None.
        """
        txn_date_str = date_to_iso(txn.date)

        for override in self.config.manual_overrides:
            if override.matches(txn_date_str, txn.amount, txn.description):
                logger.debug(
                    f"Manual override matched for {txn.description}: "
                    f"{override.category_id}"
                )
                return override

        return None

    def _find_matching_rule(
        self, txn: Transaction
    ) -> tuple[CategoryRule | None, MatchResult | None]:
        """Find a matching categorization rule for a transaction.

        Args:
            txn: Transaction to match.

        Returns:
            Tuple of (matching CategoryRule, MatchResult) or (None, None).
        """
        for rule in self.config.category_rules:
            match_result = rule.matches(txn.description, txn.amount, txn.account_id)
            if match_result:
                logger.debug(
                    f"Rule {rule.id} matched for {txn.description}: "
                    f"{rule.category_id} (confidence: {match_result.confidence:.2f})"
                )
                return rule, match_result

        return None, None

    def get_category_summary(
        self, transactions: list[Transaction]
    ) -> dict[str, int]:
        """Get count of transactions by category.

        Args:
            transactions: List of transactions.

        Returns:
            Dict mapping category to transaction count.
        """
        summary: dict[str, int] = {}

        for txn in transactions:
            category = txn.category or "Uncategorized"
            summary[category] = summary.get(category, 0) + 1

        return summary


def categorize_transactions(
    transactions: list[Transaction],
    config: Config,
) -> list[Transaction]:
    """Convenience function to categorize transactions.

    Args:
        transactions: List of transactions to categorize.
        config: Application configuration.

    Returns:
        Same list with categories assigned.
    """
    categorizer = Categorizer(config)
    return categorizer.categorize(transactions)
