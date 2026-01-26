"""Anomaly detection for financial transactions."""

import re
from collections import defaultdict

from financial_consolidator.config import Config
from financial_consolidator.models.category import _is_safe_pattern
from financial_consolidator.models.transaction import Transaction
from financial_consolidator.utils.logging_config import get_logger

logger = get_logger(__name__)


class AnomalyDetector:
    """Detects anomalies in financial transactions.

    Anomalies include:
    - Large transactions (above threshold)
    - Fees and charges
    - Cash advances
    - Date gaps (missing transaction periods)
    - Custom pattern matches
    """

    def __init__(self, config: Config):
        """Initialize anomaly detector.

        Args:
            config: Application configuration with anomaly thresholds.
        """
        self.config = config
        self.anomaly_config = config.anomaly

    def detect_anomalies(
        self, transactions: list[Transaction]
    ) -> list[Transaction]:
        """Detect and flag anomalies in transactions.

        Args:
            transactions: List of transactions to check.

        Returns:
            Same list with anomalies flagged (modified in place).
        """
        anomaly_count = 0

        for txn in transactions:
            reasons = self._check_transaction(txn)
            for reason in reasons:
                txn.add_anomaly(reason)
                anomaly_count += 1

        # Check for date gaps
        date_gap_anomalies = self._detect_date_gaps(transactions)
        logger.info(f"Detected {len(date_gap_anomalies)} date gap anomalies")

        logger.info(f"Detected {anomaly_count} transaction anomalies")
        return transactions

    def _check_transaction(self, txn: Transaction) -> list[str]:
        """Check a single transaction for anomalies.

        Args:
            txn: Transaction to check.

        Returns:
            List of anomaly reasons.
        """
        reasons: list[str] = []

        # Check for large transaction
        if self._is_large_transaction(txn):
            reasons.append(
                f"Large transaction: ${abs(txn.amount):,.2f}"
            )

        # Check for fees
        if self._is_fee(txn):
            reasons.append("Fee or charge detected")

        # Check for cash advance
        if self._is_cash_advance(txn):
            reasons.append("Cash advance detected")

        # Check custom patterns
        pattern_match = self._check_custom_patterns(txn)
        if pattern_match:
            reasons.append(pattern_match)

        return reasons

    def _is_large_transaction(self, txn: Transaction) -> bool:
        """Check if transaction exceeds large transaction threshold.

        Args:
            txn: Transaction to check.

        Returns:
            True if transaction is large.
        """
        threshold = self.anomaly_config.large_transaction_threshold
        return abs(txn.amount) >= threshold

    def _is_fee(self, txn: Transaction) -> bool:
        """Check if transaction is a fee or charge.

        Args:
            txn: Transaction to check.

        Returns:
            True if transaction appears to be a fee.
        """
        description = txn.description.upper()

        # Exclude known POS/merchant prefixes (these are never fees)
        merchant_prefixes = ["TST*", "SQ *", "SQU*", "TOAST*"]
        for prefix in merchant_prefixes:
            if description.startswith(prefix):
                return False

        # Strong fee keywords that override transfer indicators
        # These are definitive fee indicators even when combined with transfer services
        strong_keywords = ["FEE", "PENALTY", "OVERDRAFT", "NSF", "LATE FEE", "ANNUAL FEE", "MONTHLY FEE"]
        for keyword in strong_keywords:
            if re.search(r"\b" + re.escape(keyword) + r"\b", description):
                return True

        # Exclude transfers (to avoid "CHARGE" false positives like "VENMO CHARGE")
        transfer_indicators = ["TRANSFER", "VENMO", "ZELLE", "PAYPAL", "ACH", "WIRE"]
        for indicator in transfer_indicators:
            if indicator in description:
                return False

        # Check for weaker fee keywords (like "CHARGE") only if no transfer indicator
        weak_keywords = ["CHARGE"]
        for keyword in weak_keywords:
            if re.search(r"\b" + re.escape(keyword) + r"\b", description):
                return True

        return False

    def _is_cash_advance(self, txn: Transaction) -> bool:
        """Check if transaction is a cash advance.

        Args:
            txn: Transaction to check.

        Returns:
            True if transaction appears to be a cash advance.
        """
        description = txn.description.upper()
        for keyword in self.anomaly_config.cash_advance_keywords:
            if keyword.upper() in description:
                return True
        return False

    def _check_custom_patterns(self, txn: Transaction) -> str | None:
        """Check transaction against custom anomaly patterns.

        Args:
            txn: Transaction to check.

        Returns:
            Reason string if pattern matches, None otherwise.
        """
        for pattern_config in self.anomaly_config.custom_patterns:
            pattern = pattern_config.get("pattern", "")
            reason = pattern_config.get("reason", "Custom pattern match")

            # Skip empty patterns (would match everything)
            if not pattern or not pattern.strip():
                logger.warning("Skipping empty pattern in custom_patterns")
                continue

            # Validate pattern for ReDoS
            is_safe, safety_reason = _is_safe_pattern(pattern)
            if not is_safe:
                logger.warning(f"Skipping unsafe pattern '{pattern}': {safety_reason}")
                continue

            try:
                if re.search(pattern, txn.description, re.IGNORECASE):
                    return reason
            except re.error:
                logger.warning(f"Invalid regex pattern: {pattern}")

        # Amount-based detection for payment apps (more accurate than regex)
        if abs(txn.amount) >= 500:
            desc_upper = txn.description.upper()
            if "VENMO" in desc_upper:
                return "Large Venmo transfer ($500+)"
            if "ZELLE" in desc_upper:
                return "Large Zelle transfer ($500+)"

        return None

    def _detect_date_gaps(
        self, transactions: list[Transaction]
    ) -> list[dict[str, object]]:
        """Detect gaps in transaction dates.

        Args:
            transactions: List of transactions.

        Returns:
            List of date gap anomalies.
        """
        # Group by account
        by_account: dict[str, list[Transaction]] = defaultdict(list)
        for txn in transactions:
            by_account[txn.account_id].append(txn)

        gaps: list[dict[str, object]] = []

        for account_id, account_txns in by_account.items():
            if len(account_txns) < 2:
                continue

            # Sort with fingerprint tiebreaker for deterministic ordering
            sorted_txns = sorted(account_txns, key=lambda t: (t.date, t.description, t.fingerprint))

            # Check gaps between consecutive transactions
            for i in range(1, len(sorted_txns)):
                prev_date = sorted_txns[i - 1].date
                curr_date = sorted_txns[i].date
                gap_days = (curr_date - prev_date).days

                # Use > instead of >= because gap_days counts days between dates,
                # not missing days. Jan 1 to Jan 8 = 7 days, but only 6 are "missing"
                if gap_days > self.anomaly_config.date_gap_alert_days:
                    gaps.append({
                        "account_id": account_id,
                        "start_date": prev_date,
                        "end_date": curr_date,
                        "gap_days": gap_days,
                        "severity": "alert",
                    })
                elif gap_days > self.anomaly_config.date_gap_warning_days:
                    gaps.append({
                        "account_id": account_id,
                        "start_date": prev_date,
                        "end_date": curr_date,
                        "gap_days": gap_days,
                        "severity": "warning",
                    })

        return gaps

    def get_anomaly_summary(
        self, transactions: list[Transaction]
    ) -> dict[str, list[Transaction]]:
        """Get transactions grouped by anomaly type.

        Args:
            transactions: List of transactions.

        Returns:
            Dict mapping anomaly reason to list of transactions.
        """
        summary: dict[str, list[Transaction]] = defaultdict(list)

        for txn in transactions:
            if txn.is_anomaly:
                for reason in txn.anomaly_reasons:
                    summary[reason].append(txn)

        return dict(summary)

    def get_date_gaps(
        self, transactions: list[Transaction]
    ) -> list[dict[str, object]]:
        """Get all date gaps detected.

        Args:
            transactions: List of transactions.

        Returns:
            List of date gap information.
        """
        return self._detect_date_gaps(transactions)


def detect_anomalies(
    transactions: list[Transaction],
    config: Config,
) -> list[Transaction]:
    """Convenience function to detect anomalies.

    Args:
        transactions: List of transactions.
        config: Application configuration.

    Returns:
        Same list with anomalies flagged.
    """
    detector = AnomalyDetector(config)
    return detector.detect_anomalies(transactions)
