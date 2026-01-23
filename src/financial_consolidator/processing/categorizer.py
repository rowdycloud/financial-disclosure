"""Transaction categorizer using rules and manual overrides."""


from financial_consolidator.config import Config
from financial_consolidator.models.category import (
    CategoryCorrection,
    CategoryRule,
    ManualOverride,
    MatchResult,
)
from financial_consolidator.models.transaction import Transaction
from financial_consolidator.utils.date_utils import date_to_iso
from financial_consolidator.utils.logging_config import get_logger

logger = get_logger(__name__)


class Categorizer:
    """Categorizes transactions using corrections, rules, and manual overrides.

    The categorizer applies (in order of priority):
    1. Imported corrections (highest priority - user-reviewed)
    2. Manual overrides
    3. Rule-based categorization (by priority order)
    4. Marks uncategorized if no match
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
        # Try imported correction first (highest priority - user-reviewed)
        correction = self._find_matching_correction(txn)
        if correction:
            # Validate category_id exists (may be stale if categories changed)
            if correction.category_id not in self.config.categories:
                logger.warning(
                    f"Correction for {txn.fingerprint}: category '{correction.category_id}' "
                    "not found, skipping correction"
                )
            else:
                category = self.config.categories.get(correction.category_id)
                category_id = correction.category_id
                subcategory_id = correction.subcategory_id

                # Check if the specified category is actually a subcategory
                if category and category.parent_id:
                    # User specified a subcategory as the main category - adjust
                    subcategory_id = correction.category_id
                    category_id = category.parent_id
                    # Validate parent category exists (may have been deleted)
                    if category_id not in self.config.categories:
                        logger.warning(
                            f"Correction for {txn.fingerprint}: parent category "
                            f"'{category_id}' not found, skipping correction"
                        )
                        return
                    logger.debug(
                        f"Correction for {txn.fingerprint}: '{correction.category_id}' is a "
                        f"subcategory, using parent '{category_id}' as main category"
                    )

                # Validate subcategory_id exists and belongs to the right parent
                if subcategory_id:
                    if subcategory_id not in self.config.categories:
                        logger.warning(
                            f"Correction for {txn.fingerprint}: subcategory '{subcategory_id}' "
                            "not found in categories, ignoring subcategory"
                        )
                        subcategory_id = None
                    else:
                        # Verify subcategory is actually a subcategory (has parent_id)
                        # and belongs to this parent category
                        subcat = self.config.categories.get(subcategory_id)
                        if subcat and not subcat.parent_id:
                            # Top-level category cannot be used as subcategory
                            logger.warning(
                                f"Correction for {txn.fingerprint}: '{subcategory_id}' "
                                "is a top-level category, cannot use as subcategory"
                            )
                            subcategory_id = None
                        elif subcat and subcat.parent_id != category_id:
                            logger.warning(
                                f"Correction for {txn.fingerprint}: subcategory "
                                f"'{subcategory_id}' belongs to '{subcat.parent_id}', "
                                f"not '{category_id}', ignoring subcategory"
                            )
                            subcategory_id = None
                txn.assign_category(
                    category_id=category_id,
                    source="correction",
                    subcategory_id=subcategory_id,
                    confidence=1.0,
                    confidence_factors=["Imported from reviewed output"],
                )
                return

        # Try manual override second
        override = self._find_matching_override(txn)
        if override:
            # Validate category_id exists (may be stale if categories changed)
            if override.category_id not in self.config.categories:
                logger.warning(
                    f"Override (date={override.date_str}, amount={override.amount}): "
                    f"category '{override.category_id}' not found, skipping override"
                )
            else:
                # Validate subcategory_id exists
                subcategory_id = override.subcategory_id
                if subcategory_id and subcategory_id not in self.config.categories:
                    logger.warning(
                        f"Override (date={override.date_str}, amount={override.amount}): "
                        f"subcategory '{subcategory_id}' not found, ignoring subcategory"
                    )
                    subcategory_id = None
                txn.assign_category(
                    category_id=override.category_id,
                    source="manual",
                    subcategory_id=subcategory_id,
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

    def _find_matching_correction(self, txn: Transaction) -> CategoryCorrection | None:
        """Find a matching correction for a transaction by fingerprint.

        Args:
            txn: Transaction to match.

        Returns:
            Matching CategoryCorrection or None.
        """
        correction = self.config.get_matching_correction(txn.fingerprint)
        if correction:
            logger.debug(
                f"Correction matched for {txn.description[:30]}: "
                f"{correction.category_id} (fingerprint: {txn.fingerprint[:8]}...)"
            )
        return correction

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
